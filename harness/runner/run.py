#!/usr/bin/env python3
"""Run WebVoyager tasks with Claude Code or Codex driving browser-cmd.

Each task gets its own daemon, profile and artifacts; the plugin supplies the
operating skill and the answer check, exactly as a user installing it would get
(Codex: the same skill as a workspace skill, the same check run by this runner on
stop). Tasks run in a fixed working directory per worker, under a neutral temporary
root rather than the run directory, so the actor's prompt prefix is the same from
task to task and nothing in its paths names the benchmark.

    python3 run.py --out runs/final                     # all 615 tasks
    python3 run.py --out runs/smoke --ids Allrecipes--0,GitHub--13
    python3 run.py --out runs/final --resume            # rerun tasks that hit an execution error
    python3 run.py --out runs/codex --host codex --web-tools --ids ...
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import itertools
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import codex
import dates

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parents[1]
PLUGIN = ROOT / 'plugin'
SKILL = PLUGIN / 'skills' / 'browser-cmd' / 'SKILL.md'
# Codex default: interface and hard boundaries only. On Hard22 it matched the full contract's score
# with a third less time and 60% fewer input tokens (evaluations/*ablation*-20261020).
LEAN_SKILL = BENCH / 'skills' / 'lean' / 'SKILL.md'
sys.path.insert(0, str(PLUGIN / 'scripts'))
import stop_check  # noqa: E402
import review  # noqa: E402

DEFAULTS = {'claude': ('claude-opus-5', None), 'codex': ('gpt-5.6-sol', 'high')}
TASKS = ROOT / 'bench' / 'webvoyager' / 'tasks_615.jsonl'
# Sites that refuse the machine's own address and that tasks lead to: only these
# go through BROWSER_CMD_PROXY, so a metered proxy is spent where it is needed.
PROXY_HOSTS = 'transfermarkt.com,transfermarkt.us,transfermarkt.co.uk,transfermarkt.de,transfermarkt.world,target.com,walmart.com'
# Tasks that go through BROWSER_CMD_PROXY whole, so a site and the frames and CDNs it pulls in all see one
# address: by site, where the site refuses or geo-redirects this machine's network (Allrecipes answers it 402);
# by task, where a task's route leads to such a site.
PROXY_SITES = {'ESPN', 'GitHub', 'Cambridge Dictionary', 'Allrecipes'}
PROXY_TASKS = {'Google Search--14', 'Google Map--11'}


def proxied(task):
    return task.get('web_name') in PROXY_SITES or task['id'] in PROXY_TASKS


def carried(log):
    """Bytes the task's browser sent through the proxy, as its daemon says on exit; None when it did not say."""
    said = re.search(r'the proxy carried (\d+) bytes', log.read_text(errors='replace')) if log.exists() else None
    return int(said.group(1)) if said else None


def proxy_answers(proxy):
    """Whether the proxy carries a request: one out of traffic or credit answers 402 to every tunnel. Asked three
    times, as a proxy that works now and then drops a request."""
    return any(subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-m', '30',
                               'https://ipv4.icanhazip.com'], capture_output=True, text=True,
                              env={'PATH': os.environ['PATH'], 'https_proxy': proxy}).stdout == '200' for _ in range(3))
# Set once the plan is exhausted: the tasks after it are left for --resume.
LIMITED = threading.Event()
# Each pool thread keeps one working directory for all its tasks.
WORKER = threading.local()
WORKER_IDS = itertools.count()
# Only the browser-cmd plugin and the flags below shape the actor: no user,
# project or local settings (so no personal skills, plugins, hooks or CLAUDE.md;
# Claude Code gates all of them on the "user" setting source), no MCP servers,
# and the per-machine prompt sections (cwd, git status) moved out of the system
# prompt so it is byte-identical across tasks and workers.
ISOLATION = ['--setting-sources', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
             '--exclude-dynamic-system-prompt-sections', '--plugin-dir', str(PLUGIN)]
# Claude Code's documented CLAUDE_CODE_PROMPT_CACHE_TTL ("5m" | "1h"; unset means
# 1 h on a subscription). No gap between an actor's turns is near 5 minutes, and
# 1-hour cache writes cost more.
CACHE_TTL = '5m'

PROMPT = '''You are solving one web task in a real browser. Use the browser-cmd skill, and browser-cmd for every browser action; `browser-cmd CMD --help` gives one command's syntax.

TASK: {ques}
START URL: {web}
TIME: about {minutes} minutes; shortly before the end you will be told to finish with what you have.

When done, save one genuine screenshot as ./final.png: the only evidence image read, shrunk to about 1280 px on its long side. Make it a viewport (not `screenshot full`) of the page the answer comes from (for a task that asks for an action, such as adding to a cart, the page confirming it was done), scrolled so the item's name and the facts that decide the task (the values it constrains) are in view together; filters, sorts and dates applied and visible; no pop-up, banner or open dialog over it. Do not cite other screenshots. Then write your final answer to ./ANSWER.txt; the file is what is read, so end with one short line, not the answer again. The answer states the result and its evidence: verify a doubtful point in the browser rather than writing the doubt into the answer. Read the task as the person who set it means it and as the site supports it (a spelling or plural variant is no miss). When its wording allows two readings that give different results (per night or in total, one course or the whole program), give a result for each, the likelier first. When nothing on the site fits a stricter reading, the best item found is the answer, with its difference in one line. Take the facts from the website the task names whenever it holds them, and figures from the page itself with any arithmetic shown; check that the chosen item is the best by the task's measure (latest, nearest, about the topic) among those the site shows, and check a result that looks implausible another way. Apply only the filters the task names; where the site lacks one it names, apply it yourself by checking the candidates in the site's own order, and widen a window the site offers (today, this week, this month) before substituting another measure. A claim that something does not exist names the page that would hold it. A count is one number, counted on the list or index the site keeps for those items, not a lower bound. Say plainly only what truly could not be done. {rules}{subagents} Do not sign in, purchase, send messages, or change account data the task does not ask to change.'''
NO_WEB_TOOLS = 'Do not fabricate evidence or use another web tool.'
# Kept back from the actor's time, at most a sixth of it, for a turn that makes it finish with what it has.
FINISH = 180
# Review rounds at most: each is a reviewer call and an actor turn.
REVIEWS = 2
FINISH_PROMPT = ('Time is almost up: stop researching now. Within two minutes write ./ANSWER.txt from what you have '
                 'verified (NOTES.md, CHECK.md, the open pages), first line `FINAL: ` and your answer, save the final '
                 'screenshot to ./final.png, and end with one short line.')
# The host's own web search and fetch, held to discovery: the named website is read with browser-cmd.
WEB_TOOLS = ('Do not fabricate evidence. Use web search and the pages it opens to find and read sources the task does '
             'not name: no `site:` operators, and never read the website the task names through them; read that '
             'website with browser-cmd. Open in the browser what the task names, what must be interacted with or left '
             'open, and the page your final screenshot shows.')
# Codex subagents for independent reading, each in a browser session of its own.
SUBAGENTS = (' Sources to read and compare that are independent of each other (candidates across sites, one item '
             'per source) may go to at most three subagents at once. Give each its exact question and URLs and tell '
             'it to: start every browser-cmd command with `BROWSER_CMD_SESSION=<its name>` (the one variable it may '
             'set), leave the site the task names to you, write only notes/<its name>.md, spawn no agents, and '
             'return each fact with its URL and exact words. Keep working while they read; merge what they return '
             'into NOTES.md.')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plugin_sha():
    digest = hashlib.sha256()
    for path in sorted(p for p in PLUGIN.rglob('*') if p.is_file()):
        digest.update(str(path.relative_to(PLUGIN)).encode() + b'\0' + path.read_bytes())
    return digest.hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def build(out, given=None):
    """The binary under test: this checkout's release build, or one given for comparison."""
    if not given:
        subprocess.run(['cargo', 'build', '--release', '-p', 'browser-cmd'], cwd=ROOT, check=True)
    binary = out / 'bin' / 'browser-cmd'
    binary.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(given or ROOT / 'target/release/browser-cmd', binary)
    return binary


def select(rows, args):
    if args.ids:
        wanted = set(args.ids.split(','))
        rows = [row for row in rows if row['id'] in wanted]
        missing = wanted - {row['id'] for row in rows}
        if missing:
            raise SystemExit(f'unknown task ids: {sorted(missing)}')
    if args.sites:
        rows = [row for row in rows if row['web_name'] in set(args.sites.split(','))]
    return rows[:args.limit] if args.limit else rows


def start(out, args):
    """A new run: the binary, the task layer with its dates rolled, and a manifest."""
    if (out / 'manifest.json').exists():
        raise SystemExit('Refusing to overwrite an existing run; use --resume')
    today = datetime.date.fromisoformat(args.as_of) if args.as_of else datetime.date.today()
    tasks = [json.loads(line) for line in args.tasks.read_text().splitlines() if line.strip()]
    rolled, changes = dates.roll_all(select(tasks, args), today)
    if not rolled:
        raise SystemExit('no tasks selected')
    (out / 'tasks.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rolled))
    (out / 'date_updates.json').write_text(json.dumps(
        {'policy': dates.__doc__.strip(), 'as_of': today.isoformat(), 'changes': changes}, ensure_ascii=False, indent=2))
    binary = build(out, args.binary)
    proxy = None if args.cdp else os.environ.get('BROWSER_CMD_PROXY')
    if not proxy and not args.cdp:
        print(f'warning: BROWSER_CMD_PROXY is not set; {PROXY_HOSTS} will be reached directly', flush=True)
    elif proxy and not proxy_answers(proxy.replace('{session}', secrets.token_hex(4))):
        raise SystemExit('BROWSER_CMD_PROXY does not carry requests (out of traffic or credit?)')
    version = subprocess.check_output([args.host, '--version'], text=True).strip()
    manifest = {
        'host': args.host, 'host_version': version, 'model': args.model, 'effort': args.effort,
        'web_tools': args.web_tools, 'subagents': args.subagents, 'skill_sha256': sha(args.skill),
        'stop_check': args.stop_check, 'review': args.review, 'tasks': len(rolled), 'workers': args.workers, 'timeout_seconds': args.timeout,
        'budget_per_task_usd': args.budget_per_task if args.host == 'claude' else None,
        'binary_source': str(args.binary.resolve()) if args.binary else 'build',
        'binary_sha256': sha(binary), 'plugin_sha256': plugin_sha(), 'task_layer': str(args.tasks), 'task_layer_sha256': sha(args.tasks),
        'tasks_sha256': sha(out / 'tasks.jsonl'), 'dates_rolled': len(changes), 'as_of': today.isoformat(),
        'cdp': args.cdp,
        'browser': 'attached, prepared by the operator (signed in where tasks lead)' if args.cdp else 'launched headless per task',
        'network': 'proxy ' + proxy.rsplit('@', 1)[-1] if proxy else 'the attached browser\'s own' if args.cdp else 'direct',
        'proxy_hosts': os.environ.get('BROWSER_CMD_PROXY_HOSTS', PROXY_HOSTS) if proxy else '',
        'proxied_tasks': sorted(task['id'] for task in rolled if proxy and proxied(task)),
        'timezone': args.timezone or os.environ.get('BROWSER_CMD_TIMEZONE') or host_timezone(),
        'prompt_cache_ttl': CACHE_TTL if args.host == 'claude' else None,
        'actor_isolation': ISOLATION[:-2] if args.host == 'claude' else codex.settings(args),
        'git_head': git('rev-parse', 'HEAD'), 'dirty_worktree': bool(git('status', '--porcelain')),
        'started_at': time.time(), 'status': 'running',
    }
    subprocess.run(['tar', '-czf', str(out / 'source.tar.gz'), 'Cargo.toml', 'Cargo.lock', 'crates/browser-cmd', 'plugin'],
                   cwd=ROOT, check=True)
    return manifest


def resume(out, args):
    """The same experiment again: nothing it depends on may have changed."""
    manifest = json.loads((out / 'manifest.json').read_text())
    manifest.setdefault('subagents', False)
    now = {'binary_sha256': sha(out / 'bin' / 'browser-cmd'), 'plugin_sha256': plugin_sha(),
           'tasks_sha256': sha(out / 'tasks.jsonl'), 'model': args.model, 'host': args.host, 'effort': args.effort,
           'web_tools': args.web_tools, 'subagents': args.subagents, 'skill_sha256': sha(args.skill),
           'stop_check': args.stop_check, 'review': args.review, 'cdp': args.cdp}
    changed = [key for key, value in now.items() if manifest.get(key) != value]
    if changed:
        raise SystemExit(f'Cannot resume: {changed} differ from the original run')
    manifest['status'] = 'running'
    manifest.setdefault('resumed_at', []).append(time.time())
    return manifest


def host_timezone():
    zone = os.path.realpath('/etc/localtime')
    return zone.split('zoneinfo/', 1)[1] if 'zoneinfo/' in zone else 'UTC'


def worker_dir(root):
    if not hasattr(WORKER, 'dir'):
        WORKER.dir = root / f'w{next(WORKER_IDS)}'
    return WORKER.dir


def actor_command(args, prompt):
    tools = ['Bash', 'Read', 'Write', 'Skill', *(['WebSearch', 'WebFetch'] if args.web_tools else [])]
    return ['claude', '-p', '--model', args.model, *(['--effort', args.effort] if args.effort else []),
            '--output-format', 'stream-json', '--verbose',
            '--max-budget-usd', str(args.budget_per_task), '--no-session-persistence', '--permission-mode', 'dontAsk',
            *ISOLATION, '--tools', ','.join(tools), '--allowedTools', *tools, '--', prompt]


def environment(root, index, port, timezone, task, cdp=None):
    env = {key: value for key, value in os.environ.items() if not key.startswith(('BROWSER_CMD_', 'OPENAI_'))}
    env.update(PATH=f'{root / "bin"}{os.pathsep}{env.get("PATH", "")}', BROWSER_CMD_ADDR=f'127.0.0.1:{port}',
               BROWSER_CMD_PACE='0.3',
               BROWSER_CMD_RPC_TOKEN=secrets.token_hex(32), BROWSER_CMD_ANSWER_FILE='ANSWER.txt', BROWSER_CMD_NO_SPAWN='1',
               BROWSER_CMD_NETWORK='1',
               BROWSER_CMD_TIMEZONE=timezone, TZ=timezone, CLAUDE_CODE_PROMPT_CACHE_TTL=CACHE_TTL,
               CLAUDE_CODE_DISABLE_AUTO_MEMORY='1', CODEX_HOME=str(root / 'codex'),
               CMUX_CLAUDE_HOOKS_DISABLED='1', CMUX_CODEX_HOOKS_DISABLED='1', CMUX_COMPUTER_USE_MCP_DISABLED='1')
    # Recording canvas text wraps the page's own functions: the operator's call.
    if os.environ.get('BROWSER_CMD_CANVAS_TEXT'):
        env['BROWSER_CMD_CANVAS_TEXT'] = os.environ['BROWSER_CMD_CANVAS_TEXT']
    # A Chrome the operator prepared (signed in where tasks lead) is attached to and keeps its own network;
    # otherwise each task launches a fresh headless one.
    if cdp:
        env['BROWSER_CMD_CDP'] = cdp
        return env
    env.update(BROWSER_CMD_HEADLESS='1', BROWSER_CMD_PROFILE=str(root / 'profiles' / str(index)))
    # {session} pins one exit address for the whole task; a proxy that rotates
    # per request would change address mid-page.
    if os.environ.get('BROWSER_CMD_PROXY'):
        env['BROWSER_CMD_PROXY'] = os.environ['BROWSER_CMD_PROXY'].replace('{session}', secrets.token_hex(4))
        if not proxied(task):
            env['BROWSER_CMD_PROXY_HOSTS'] = os.environ.get('BROWSER_CMD_PROXY_HOSTS', PROXY_HOSTS)
    return env


def actor(command, cwd, env, trace, err, seconds):
    """Run one actor process to completion or its deadline; the execution error, if any."""
    child = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=trace, stderr=err,
                             start_new_session=True)
    try:
        child.wait(timeout=max(seconds, 1))
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        return 'planner_timeout'
    return 'planner_exit_nonzero' if child.returncode else None


def codex_actor(args, task, prompt, job, cwd, env, trace, err):
    """Codex, then the plugin's stop check once, continuing the session when it blocks. The last
    FINISH seconds are kept back: a session still working then is stopped and told to finish, so a
    long task ends with its deliverable rather than mid-research. A model at capacity is asked once
    to go on."""
    started, last, finish = time.time(), job / 'last_message.txt', min(FINISH, args.timeout // 6)
    left = lambda: args.timeout - (time.time() - started)  # noqa: E731
    error = actor(codex.command(args, prompt, last), cwd, env, trace, err, args.timeout - finish)
    trace.flush()
    thread = codex.summary(job / 'transcript.jsonl')['thread']
    failure = codex.summary(job / 'transcript.jsonl')['failure'] or ''
    if thread and 'capacity' in failure.lower() and left() > finish:
        error = actor(codex.resume(args, thread, 'Continue the task where you left off.', last), cwd, env, trace,
                      err, left() - finish)
        trace.flush()
    if thread and error == 'planner_timeout':
        (job / 'finish_turn.txt').write_text(FINISH_PROMPT)
        error = actor(codex.resume(args, thread, FINISH_PROMPT, last), cwd, env, trace, err, left())
        trace.flush()
    keep_rollout(args, thread, job)
    verdict = None if error or not args.stop_check else stop_check.decide({'cwd': str(cwd)}, 'ANSWER.txt')
    if verdict and thread:
        (job / 'stop_check.txt').write_text(verdict['reason'])
        error = actor(codex.resume(args, thread, verdict['reason'], last), cwd, env, trace, err, left())
        keep_rollout(args, thread, job)
    for round in range(REVIEWS if args.review else 0):
        if error or not thread or left() < finish:
            break
        said = review.verdict(args.review, task, cwd)
        (job / f'review_{round}.json').write_text(json.dumps(said, ensure_ascii=False, indent=2))
        if not said['issues']:
            break
        error = actor(codex.resume(args, thread, review.RESUME.format(issues=said['issues']), last), cwd, env, trace,
                      err, left())
        keep_rollout(args, thread, job)
    return error


def keep_rollout(args, thread, job):
    """Codex's per-call log of the task, for what each model call cost: the transcript has totals only.
    A subagent's log names its parent's thread in its first line."""
    for path in (args.root / 'codex' / 'sessions').rglob('*.jsonl') if thread else ():
        if path.name.endswith(f'{thread}.jsonl'):
            shutil.copy2(path, job / 'rollout.jsonl')
        elif thread in path.open().readline():
            shutil.copy2(path, job / f'rollout.sub-{path.stem[-36:]}.jsonl')


def subagent_sessions(job):
    """The browser sessions the actor's subagents were told to use, as the task's transcripts name them."""
    said = ''.join(path.read_text(errors='replace') for path in sorted(job.glob('*.jsonl')))
    return list(dict.fromkeys(re.findall(r'BROWSER_CMD_SESSION=\\?["\']?([\w.-]+)', said)))


def audit_tabs(args, cwd, env, job):
    """What the browser holds as the actor and each subagent session leave it, audited by the harness rather
    than claimed by the actor: one section per session."""
    sections = []
    for name in [None, *subagent_sessions(job)]:
        try:
            audit = subprocess.run([str(args.root / 'bin' / 'browser-cmd'), 'tab', 'check'], cwd=cwd,
                                   env=env if name is None else {**env, 'BROWSER_CMD_SESSION': name},
                                   capture_output=True, text=True, timeout=120)
            said = audit.stdout + audit.stderr
        except (OSError, subprocess.SubprocessError) as exc:
            said = f'tab check failed: {exc}\n'
        sections.append(f'## session {name or "of the actor"}\n{said}')
    (job / 'tabs.txt').write_text('\n'.join(sections))


def close_sessions(args, cwd, env, job):
    """An attached browser is the operator's and outlives the task: each session's tabs, kept ones too, are
    closed and borrowed ones given back, so the next task starts from a clean slate."""
    for name in [None, *subagent_sessions(job)]:
        own = env if name is None else {**env, 'BROWSER_CMD_SESSION': name}

        def call(*words):
            try:
                return subprocess.run([str(args.root / 'bin' / 'browser-cmd'), *words], cwd=cwd, env=own,
                                      capture_output=True, text=True, timeout=120).stdout
            except (OSError, subprocess.SubprocessError):
                return ''
        for handle in re.findall(r'^[ *](t\d+) ', call('tab', 'list').split("Not any session's")[0], re.M):
            call('tab', 'unkeep', handle)
        call('close')


def keep_tab_shots(job, work):
    """The screenshots tab check took, beside its report."""
    for shot in re.findall(r'\[screenshot (media/browser/[\w-]+\.png)\]', (job / 'tabs.txt').read_text()):
        if (work / shot).exists():
            (job / 'tabs').mkdir(exist_ok=True)
            shutil.copy2(work / shot, job / 'tabs' / Path(shot).name)


def attempt(out, args, index, task):
    job = out / f'task_{index}'
    work = job / 'work'
    if args.resume and (job / 'result.json').exists():
        kept = json.loads((job / 'result.json').read_text())
        if not kept['execution_error']:
            return kept
    if LIMITED.is_set():
        return {'task': task, 'out_dir': f'task_{index}', 'execution_error': 'rate_limited'}
    if job.exists():
        shutil.rmtree(job)
    job.mkdir(parents=True)
    cwd = worker_dir(args.root)
    shutil.rmtree(cwd, ignore_errors=True)
    cwd.mkdir(parents=True)
    if args.host == 'codex':
        (cwd / '.agents' / 'skills' / 'browser-cmd').mkdir(parents=True)
        shutil.copy2(args.skill, cwd / '.agents' / 'skills' / 'browser-cmd' / 'SKILL.md')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    env = environment(args.root, index, port, args.timezone, task, args.cdp)
    prompt = PROMPT.format(**task, rules=WEB_TOOLS if args.web_tools else NO_WEB_TOOLS,
                           subagents=SUBAGENTS if args.subagents else '', minutes=round(args.timeout / 60))
    (job / 'prompt.txt').write_text(prompt)
    error, started = None, time.time()
    with (job / 'daemon.log').open('w') as log:
        daemon = subprocess.Popen([str(args.root / 'bin' / 'browser-cmd'), '--serve', env['BROWSER_CMD_ADDR']], cwd=cwd,
                                  env={**env, 'BROWSER_CMD_NO_SPAWN': '0'},
                                  stdout=subprocess.DEVNULL, stderr=log, start_new_session=True)
        try:
            # A task that goes whole through the proxy is not run without it: it is left for --resume.
            if 'BROWSER_CMD_PROXY' in env and proxied(task) and not proxy_answers(env['BROWSER_CMD_PROXY']):
                raise RuntimeError('proxy_unavailable')
            for _ in range(100):
                if daemon.poll() is not None:
                    raise RuntimeError('daemon startup failed')
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=.1):
                        break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('daemon startup timeout')
            with (job / 'transcript.jsonl').open('w') as trace, (job / 'stderr.log').open('w') as err:
                if args.host == 'codex':
                    error = codex_actor(args, task, prompt, job, cwd, env, trace, err)
                else:
                    error = actor(actor_command(args, prompt), cwd, env, trace, err, args.timeout)
            audit_tabs(args, cwd, env, job)
        except (OSError, RuntimeError) as exc:
            error = str(exc)
        finally:
            if args.cdp and daemon.poll() is None:
                close_sessions(args, cwd, env, job)
            daemon.terminate()
            try:
                daemon.wait(timeout=10)
            except subprocess.TimeoutExpired:
                daemon.kill()
                daemon.wait()
            # A launched Chrome shares the daemon's process group: nothing of the task outlives it.
            # An attached one is in no group of ours and stays.
            try:
                os.killpg(daemon.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            # The task's files leave the shared directory for its own record.
            shutil.move(cwd, work)
    if (job / 'tabs.txt').exists():
        keep_tab_shots(job, work)
    usage = codex.summary(job / 'transcript.jsonl') if args.host == 'codex' else {}
    for line in (job / 'transcript.jsonl').read_text().splitlines() if args.host == 'claude' else []:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') == 'result':
            usage = event
    if usage:
        (job / 'usage.json').write_text(json.dumps(usage, indent=2))
    # An exhausted plan says so in place of an answer; that text is not a trial outcome.
    if usage.get('api_error_status') == 429 or usage.get('rate_limited'):
        error, usage['result'] = 'rate_limited', ''
        LIMITED.set()
    # A session that never wrote its answer is judged on its notes, which hold what it found, rather
    # than on its last message, which is usually a line about what it was doing.
    written = [work / name for name in ('ANSWER.txt', 'NOTES.md') if (work / name).exists()]
    answer = written[0].read_text().strip() if written else usage.get('result', '')
    (job / 'ANSWER.txt').write_text(answer or 'NO_ANSWER')
    shot, selection = work / 'final.png', 'agent_selected'
    if not shot.exists():
        shots = list((work / 'media/browser').glob('*.png'))
        shot = max(shots, key=lambda p: p.stat().st_mtime_ns) if shots else None
        selection = 'latest_real_capture_fallback'
    if shot:
        shutil.copy2(shot, job / 'final.png')
    # The judge reads the actor's answer from `claude`, whichever host produced it.
    row = {'task': task, 'host': args.host, 'claude': {'final_answer': answer, 'result_text': answer, 'is_error': bool(error) or not answer,
                                    'timed_out': error == 'planner_timeout'},
           'browser_artifacts': {'screenshot': f'task_{index}/final.png' if shot else None,
                                 'screenshot_error': None if shot else 'missing', 'selection': selection},
           'out_dir': f'task_{index}', 'elapsed_seconds': time.time() - started, 'execution_error': error,
           'proxy_bytes': carried(job / 'daemon.log')}
    (job / 'result.json').write_text(json.dumps(row, ensure_ascii=False, indent=2))
    print(json.dumps({'task': task['id'], 'answer': bool(answer), 'screenshot': bool(shot), 'error': error,
                      'seconds': round(row['elapsed_seconds'])}), flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--host', choices=sorted(DEFAULTS), default='claude')
    parser.add_argument('--model', help='default: claude-opus-5 for Claude Code, gpt-5.6-sol for Codex')
    parser.add_argument('--effort', help='reasoning effort (default: the host default; high for Codex)')
    parser.add_argument('--web-tools', action='store_true',
                        help="allow the host's own web search and fetch, limited by the prompt to discovery")
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--timeout', type=int, default=900, help='seconds per task')
    parser.add_argument('--skill', type=Path, help='Codex: SKILL.md to give (default: the lean skill)')
    parser.add_argument('--stop-check', action='store_true', help='Codex: apply the plugin\'s stop check')
    parser.add_argument('--binary', type=Path, help='a prebuilt browser-cmd to run instead of building this checkout')
    parser.add_argument('--auto-compact', type=int, default=300000,
                        help='Codex: compact the context past this many tokens; 0 keeps the Codex default')
    parser.add_argument('--review', metavar='MODEL', help='Codex: MODEL reviews the answer and screenshot; the actor '
                        f'fixes what it names, at most {REVIEWS} times')
    parser.add_argument('--subagents', action='store_true', help='Codex: subagents for independent reading')
    parser.add_argument('--fast', action='store_true', help='Codex: the priority service tier (faster, uses more of the plan)')
    parser.add_argument('--budget-per-task', type=float, default=3, help='USD (Claude Code only)')
    parser.add_argument('--tasks', type=Path, default=TASKS, help='task rows: id, web_name, ques, web (default: WebVoyager 615)')
    parser.add_argument('--ids', help='comma-separated task ids')
    parser.add_argument('--sites', help='comma-separated site names')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--as-of', help='date the task dates are rolled against (default: today)')
    parser.add_argument('--timezone', help='IANA zone for the browser and the actor (default: BROWSER_CMD_TIMEZONE, '
                        'else the host zone); a resumed run keeps its own')
    parser.add_argument('--resume', action='store_true', help='rerun only the tasks that ended in an execution error')
    parser.add_argument('--cdp', metavar='URL', help='attach to a running Chrome the operator prepared (signed in '
                        'where tasks lead) at its DevTools URL, e.g. ws://127.0.0.1:9222/devtools/browser; one '
                        'worker, no proxy, each task in a clean session of its own')
    args = parser.parse_args()
    if args.cdp and args.workers != 1:
        raise SystemExit('--cdp shares one browser: use --workers 1')
    model, effort = DEFAULTS[args.host]
    args.model, args.effort = args.model or model, args.effort or effort
    if args.host == 'claude' and (args.skill or args.stop_check or args.subagents or args.review):
        raise SystemExit('--skill, --stop-check, --subagents and --review apply to Codex; Claude Code takes the plugin as is')
    args.tasks = args.tasks.resolve()
    args.skill = (args.skill or (LEAN_SKILL if args.host == 'codex' else SKILL)).resolve()
    args.stop_check = args.stop_check or args.host == 'claude'
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest = resume(out, args) if args.resume else start(out, args)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    args.timezone = manifest['timezone']
    # Working directories, profiles, the binary and Codex's home live outside the run directory.
    args.root = Path(tempfile.mkdtemp(prefix='bc-')).resolve()
    (args.root / 'bin').mkdir()
    shutil.copy2(out / 'bin' / 'browser-cmd', args.root / 'bin' / 'browser-cmd')
    if args.host == 'codex':
        codex.home(args.root)
    rows = [json.loads(line) for line in (out / 'tasks.jsonl').read_text().splitlines() if line.strip()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        # Tasks through the metered proxy go last: a run stopped early has not spent it.
        order = sorted(enumerate(rows), key=lambda item: proxied(item[1]))
        done = dict(pool.map(lambda item: (item[0], attempt(out, args, *item)), order))
        results = [done[index] for index in range(len(rows))]
    shutil.rmtree(args.root, ignore_errors=True)
    (out / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    limited = sum(row['execution_error'] == 'rate_limited' for row in results)
    manifest.update(status='rate_limited_resume_needed' if limited else 'trials_collected_not_judged', finished_at=time.time())
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(f'{len(results)} tasks, {sum(bool(r["execution_error"]) for r in results)} execution errors ({limited} rate limited)')


if __name__ == '__main__':
    main()

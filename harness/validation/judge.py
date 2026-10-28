#!/usr/bin/env python3
"""Cross-check a WebVoyager run with the pinned auto_eval prompts on another model: through `codex exec`
(JUDGE_CODEX=MODEL) or `claude -p` (JUDGE_CLAUDE=MODEL) on a subscription, else the OpenAI API.

    JUDGE_CODEX=gpt-5.6-sol python3 judge.py RUN
    JUDGE_CLAUDE=claude-opus-5-5 python3 judge.py RUN

Verdicts from two judges are not comparable, so both arms of an A/B take the same one.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'runner'))
import codex as host  # noqa: E402  the actor's isolation: no personal skills, extra tools or features


MODEL = 'gpt-5.5'


def ask(system, text, images=()):
    if os.environ.get('JUDGE_CODEX'):
        return ask_codex(system, text, images)
    if os.environ.get('JUDGE_CLAUDE'):
        return ask_claude(system, text, images)
    content = [{'type': 'text', 'text': text},
               *({'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{data}'}} for data in images)]
    body = json.dumps({'model': MODEL, 'seed': 42, 'max_completion_tokens': 8192,
                       'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': content}]})
    for attempt in range(8):
        request = urllib.request.Request('https://api.openai.com/v1/chat/completions', body.encode(), {
            'Authorization': f"Bearer {os.environ['OPENAI_API_KEY']}", 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return json.load(response)['choices'][0]['message']['content']
        except OSError as error:
            if attempt == 7:
                raise
            # A rate limit is a minute's budget spent: wait it out, not a few seconds.
            limited = getattr(error, 'code', None) == 429
            time.sleep((60 if limited else 10) * (attempt + 1))


# Wrappers that add their own tools or hooks to codex are switched off, as they are for the actor.
NO_EXTRAS = {'CMUX_CLAUDE_HOOKS_DISABLED': '1', 'CMUX_CODEX_HOOKS_DISABLED': '1', 'CMUX_COMPUTER_USE_MCP_DISABLED': '1'}


def ask_codex(system, text, images):
    """One answer from a subscription model through codex exec, in a home of its own with no tools."""
    with tempfile.TemporaryDirectory(prefix='judge-') as tmp:
        home = Path(tmp) / 'codex'
        home.mkdir()
        (home / 'auth.json').symlink_to(Path.home() / '.codex' / 'auth.json')
        attached = [part for path in small_images(images, tmp) for part in ('--image', str(path))]
        last = Path(tmp) / 'last.txt'
        isolated = host.settings(argparse.Namespace(effort='medium', web_tools=False, auto_compact=None, subagents=False))
        command = ['codex', 'exec', '--skip-git-repo-check', '-m', os.environ['JUDGE_CODEX'], *isolated,
                   '--output-last-message', str(last), *attached, '-']
        failure = ''
        for attempt in range(4):
            try:
                done = subprocess.run(command, input=f'{system}\n\n{text}', text=True, capture_output=True, cwd=tmp,
                                      env={**os.environ, 'CODEX_HOME': str(home), **NO_EXTRAS}, timeout=1200)
            except subprocess.TimeoutExpired:
                failure = 'no answer within 20 minutes'
                continue
            if done.returncode == 0 and last.exists() and last.read_text().strip():
                return last.read_text()
            failure = done.stderr[-500:]
            time.sleep(30 * (attempt + 1))
        raise RuntimeError(f'codex judge failed: {failure}')


def small_images(images, tmp):
    """The screenshots as files, smaller: twenty full-size ones make a request too large to answer in time."""
    paths = []
    for index, data in enumerate(images):
        image = Path(tmp) / f'{index}.png'
        image.write_bytes(base64.b64decode(data))
        small = image.with_suffix('.jpg')
        subprocess.run(['sips', '-Z', '1280', '-s', 'format', 'jpeg', str(image), '--out', str(small)],
                       capture_output=True, check=True)
        paths.append(small)
    return paths


def ask_claude(system, text, images):
    """One answer from a Claude model through `claude -p`: no settings, plugins or MCP, only Read for the screenshots."""
    with tempfile.TemporaryDirectory(prefix='judge-') as tmp:
        paths = small_images(images, tmp)
        shown = ''.join(f'\n{path}' for path in paths)
        prompt = text + (f'\n\nThe screenshots, in order: read every one of these files with the Read tool before '
                         f'answering.{shown}' if paths else '')
        command = ['claude', '-p', '--model', os.environ['JUDGE_CLAUDE'], '--setting-sources', '',
                   '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--no-session-persistence',
                   '--permission-mode', 'dontAsk', '--tools', 'Read', '--allowedTools', 'Read',
                   '--system-prompt', system, '--output-format', 'json']
        failure = ''
        for attempt in range(4):
            try:
                done = subprocess.run(command, input=prompt, text=True, capture_output=True, cwd=tmp,
                                      env={**os.environ, **NO_EXTRAS}, timeout=1200)
            except subprocess.TimeoutExpired:
                failure = 'no answer within 20 minutes'
                continue
            answer = json.loads(done.stdout or '{}') if done.returncode == 0 else {}
            if answer.get('result', '').strip() and not answer.get('is_error'):
                return answer['result']
            failure = (done.stderr or done.stdout)[-500:]
            time.sleep(30 * (attempt + 1))
        raise RuntimeError(f'claude judge failed: {failure}')


def judge_webvoyager(task, task_dir):
    """The pinned WebVoyager auto_eval prompts, read as text, over the answer and the final screenshot."""
    source = (Path(__file__).resolve().parent.parent / 'webvoyager' / '.judge' / 'auto_eval.py').read_text()
    system = re.search(r'SYSTEM_PROMPT = """(.*?)"""', source, re.S).group(1)
    user = re.search(r'USER_PROMPT = """(.*?)"""', source, re.S).group(1)
    answer = (task_dir / 'ANSWER.txt').read_text().strip() if (task_dir / 'ANSWER.txt').exists() else ''
    shots = [base64.b64encode((task_dir / 'final.png').read_bytes()).decode()] if (task_dir / 'final.png').exists() else []
    text = user.replace('<task>', task['ques']).replace('<answer>', answer).replace('<num>', str(len(shots)))
    raw = ask(system, text + '\nYour verdict:\n', shots)
    return {'pass': passed(raw), 'reasoning': raw}


def passed(raw):
    """The last stated verdict, wherever it stands: a judge may open with it and later say a point
    "doesn't change the verdict"."""
    stated = re.findall(r'verdict\W*(NOT SUCCESS|SUCCESS)', raw, re.I)
    verdict = stated[-1].upper() if stated else raw.upper()
    return 'NOT SUCCESS' not in verdict and 'SUCCESS' in verdict


SUBSCRIPTION = os.environ.get('JUDGE_CODEX') or os.environ.get('JUDGE_CLAUDE')


def main(run):
    # Verdicts already given survive a judge stopped part way, so a rerun asks only for the rest.
    # Each judge keeps its own verdicts: one judge's are never mixed with another's.
    name = 'validation_judge' + (f'.{SUBSCRIPTION}' if SUBSCRIPTION else '')
    partial = run / f'{name}.partial.json'
    verdicts = json.loads(partial.read_text()) if partial.exists() else {}
    for result in sorted(run.glob('task_*/result.json'), key=lambda p: int(p.parent.name.split('_')[1])):
        task = json.loads(result.read_text())['task']
        if task['id'] not in verdicts:
            verdicts[task['id']] = judge_webvoyager(task, result.parent)
            partial.write_text(json.dumps(verdicts, ensure_ascii=False))
        print(task['id'], verdicts[task['id']]['pass'], flush=True)
    summary = {'judge': f'webvoyager auto_eval prompts on {SUBSCRIPTION or MODEL}', 'tasks': len(verdicts),
               'pass': sum(v['pass'] for v in verdicts.values())}
    (run / f'{name}.json').write_text(json.dumps({'summary': summary, 'verdicts': verdicts},
                                                 ensure_ascii=False, indent=2))
    print(json.dumps(summary))


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())

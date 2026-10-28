import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402

DAEMON = '''import socket, sys, time
host, port = sys.argv[2].split(':')
server = socket.socket()
server.bind((host, int(port)))
server.listen()
time.sleep(60)
'''
ACTOR = '''import json, os, sys
open('ANSWER.txt', 'w').write(json.dumps({'cwd': os.getcwd(), 'prompt': sys.argv[-1], 'tz': os.environ['TZ'],
                                           'ttl': os.environ['CLAUDE_CODE_PROMPT_CACHE_TTL']}))
open('final.png', 'wb').write(b'png')
print(json.dumps({'type': 'result', 'result': 'done', 'total_cost_usd': 0}))
'''


def args(**overrides):
    return argparse.Namespace(**{'host': 'claude', 'model': 'm', 'effort': None, 'web_tools': False,
                                 'skill': run.SKILL, 'stop_check': True,
                                 'budget_per_task': 3, 'resume': False, 'timeout': 30, 'binary': None, 'auto_compact': None, 'fast': False, 'subagents': False, 'cdp': None,
                                 'timezone': 'America/New_York', **overrides})


class ActorIsolationTests(unittest.TestCase):
    def test_command_loads_only_the_plugin_and_no_task_path(self):
        first, second = run.actor_command(args(), 'task one'), run.actor_command(args(), 'task two')
        self.assertEqual(first[:-1], second[:-1])
        self.assertEqual(first[first.index('--setting-sources') + 1], '')
        self.assertEqual([first[i + 1] for i, flag in enumerate(first) if flag == '--plugin-dir'], [str(run.PLUGIN)])
        self.assertIn('--exclude-dynamic-system-prompt-sections', first)
        self.assertIn('--strict-mcp-config', first)
        self.assertNotIn('--add-dir', first)
        self.assertEqual(first[first.index('--tools') + 1], 'Bash,Read,Write,Skill')
        web = run.actor_command(args(web_tools=True), 'task')
        self.assertEqual(web[web.index('--tools') + 1], 'Bash,Read,Write,Skill,WebSearch,WebFetch')

    def test_codex_runs_in_its_own_home_without_personal_skills_or_extra_tools(self):
        command = run.codex.command(args(host='codex', effort='high', web_tools=True), 'task', Path('/r/last'))
        settings = dict(value.split('=', 1) for flag, value in zip(command, command[1:]) if flag == '-c')
        self.assertEqual((settings['web_search'], settings['skills.bundled.enabled']), ('"live"', 'false'))
        self.assertEqual(settings['features.multi_agent'], 'false')
        self.assertEqual(command[-1], 'task')
        quiet = run.codex.command(args(host='codex', effort='high'), 'task', Path('/r/last'))
        self.assertIn('web_search="disabled"', quiet)

    def test_environment_sets_zone_cache_and_answer_file(self):
        os.environ['BROWSER_CMD_TIMEZONE'] = 'Europe/Paris'
        self.addCleanup(os.environ.pop, 'BROWSER_CMD_TIMEZONE')
        env = run.environment(Path('/r'), 3, 1234, 'America/New_York', {'id': 'Apple--0', 'web_name': 'Apple'})
        self.assertEqual((env['TZ'], env['BROWSER_CMD_TIMEZONE']), ('America/New_York', 'America/New_York'))
        self.assertEqual(env['CLAUDE_CODE_PROMPT_CACHE_TTL'], '5m')
        self.assertEqual(env['BROWSER_CMD_ANSWER_FILE'], 'ANSWER.txt')
        self.assertEqual(env['CLAUDE_CODE_DISABLE_AUTO_MEMORY'], '1')
        self.assertEqual((env['BROWSER_CMD_PROFILE'], env['CODEX_HOME']), ('/r/profiles/3', '/r/codex'))

    def test_a_proxied_site_goes_whole_through_the_proxy_and_others_only_by_host(self):
        os.environ['BROWSER_CMD_PROXY'] = 'http://u:p_session-{session}@proxy.example:1'
        self.addCleanup(os.environ.pop, 'BROWSER_CMD_PROXY')
        whole = run.environment(Path('/r'), 0, 1, 'UTC', {'id': 'GitHub--1', 'web_name': 'GitHub'})
        hosts = run.environment(Path('/r'), 0, 1, 'UTC', {'id': 'Apple--0', 'web_name': 'Apple'})
        self.assertNotIn('{session}', whole['BROWSER_CMD_PROXY'])
        self.assertNotIn('BROWSER_CMD_PROXY_HOSTS', whole)
        self.assertEqual(hosts['BROWSER_CMD_PROXY_HOSTS'], run.PROXY_HOSTS)

    def test_an_attached_browser_keeps_its_own_profile_and_network(self):
        os.environ['BROWSER_CMD_PROXY'] = 'http://u:p@proxy.example:1'
        self.addCleanup(os.environ.pop, 'BROWSER_CMD_PROXY')
        env = run.environment(Path('/r'), 0, 1, 'UTC', {'id': 'GitHub--1', 'web_name': 'GitHub'}, 'ws://127.0.0.1:9222/x')
        self.assertEqual(env['BROWSER_CMD_CDP'], 'ws://127.0.0.1:9222/x')
        self.assertFalse({'BROWSER_CMD_PROXY', 'BROWSER_CMD_PROFILE', 'BROWSER_CMD_HEADLESS'} & env.keys())

    def test_worker_directory_is_fixed_per_thread(self):
        seen = []
        thread = lambda: seen.append((run.worker_dir(Path('/r')), run.worker_dir(Path('/r'))))
        workers = [threading.Thread(target=thread) for _ in range(2)]
        for worker in workers:
            worker.start()
            worker.join()
        self.assertTrue(all(a == b for a, b in seen))
        self.assertNotEqual(seen[0][0], seen[1][0])


class AttemptTests(unittest.TestCase):
    def test_tasks_share_a_worker_directory_and_keep_separate_artifacts(self):
        out = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        (root / 'bin').mkdir()
        for name, body in (('browser-cmd', DAEMON), ('claude', ACTOR)):
            (root / 'bin' / name).write_text(f'#!{sys.executable}\n{body}')
            (root / 'bin' / name).chmod(0o755)
        tasks = [{'id': f'T--{i}', 'ques': f'question {i}', 'web': 'https://example.invalid/'} for i in range(2)]
        rows = []
        worker = threading.Thread(target=lambda: rows.extend(run.attempt(out, args(root=root), i, t) for i, t in enumerate(tasks)))
        worker.start()
        worker.join()
        answers = [json.loads((out / f'task_{i}' / 'ANSWER.txt').read_text()) for i in range(2)]
        self.assertEqual(answers[0]['cwd'], answers[1]['cwd'])
        self.assertTrue(answers[0]['cwd'].startswith(str(root)))
        self.assertIn('question 0', answers[0]['prompt'])
        self.assertIn(run.NO_WEB_TOOLS, answers[0]['prompt'])
        self.assertEqual(answers[0]['prompt'].count('https://example.invalid/'), 1)
        self.assertIn('question 1', answers[1]['prompt'])
        self.assertEqual((answers[0]['tz'], answers[0]['ttl']), ('America/New_York', '5m'))
        self.assertTrue((out / 'task_1' / 'work' / 'final.png').exists())
        self.assertFalse(Path(answers[0]['cwd']).exists())
        self.assertEqual([row['execution_error'] for row in rows], [None, None])

    def test_the_tab_audit_has_a_section_per_session_the_transcripts_name(self):
        job = Path(self.enterContext(tempfile.TemporaryDirectory()))
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (job / 'transcript.jsonl').write_text('{"cmd":"BROWSER_CMD_SESSION=\\"sub-a\\" browser-cmd text"}\n'
                                              'BROWSER_CMD_SESSION=<its name>\n')
        (job / 'rollout.sub-1.jsonl').write_text("BROWSER_CMD_SESSION='sub.b' browser-cmd tab list; "
                                                 'BROWSER_CMD_SESSION=sub-a browser-cmd text')
        self.assertEqual(run.subagent_sessions(job), ['sub.b', 'sub-a'])
        (root / 'bin').mkdir()
        (root / 'bin' / 'browser-cmd').write_text('#!/bin/sh\necho "checked ${BROWSER_CMD_SESSION:-default}"\n')
        (root / 'bin' / 'browser-cmd').chmod(0o755)
        run.audit_tabs(args(root=root), job, {'PATH': os.environ['PATH']}, job)
        self.assertEqual((job / 'tabs.txt').read_text(), '## session of the actor\nchecked default\n\n'
                         '## session sub.b\nchecked sub.b\n\n## session sub-a\nchecked sub-a\n')

    def test_an_attached_browser_is_left_without_the_tasks_tabs(self):
        job = Path(self.enterContext(tempfile.TemporaryDirectory()))
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (job / 'transcript.jsonl').write_text('BROWSER_CMD_SESSION=sub-a browser-cmd text\n')
        (root / 'bin').mkdir()
        listed = ('<browser>\n*t1 ok https://a — A\n t3 kept "x" ok https://b — B\n'
                  "Not any session's; `tab use N` borrows one:\nt9 1 https://u — U\n</browser>\n")
        (root / 'bin' / 'browser-cmd').write_text(
            f'#!{sys.executable}\nimport os, sys\n'
            "open('calls', 'a').write(os.environ.get('BROWSER_CMD_SESSION', 'actor') + ' ' + ' '.join(sys.argv[1:]) + '\\n')\n"
            f"print({listed!r} if sys.argv[1:] == ['tab', 'list'] else '')\n")
        (root / 'bin' / 'browser-cmd').chmod(0o755)
        run.close_sessions(args(root=root), job, {'PATH': os.environ['PATH']}, job)
        calls = (job / 'calls').read_text().splitlines()
        self.assertEqual(calls[:4], ['actor tab list', 'actor tab unkeep t1', 'actor tab unkeep t3', 'actor close'])
        self.assertEqual(calls[-1], 'sub-a close')
        self.assertEqual(len(calls), 8)


class ReviewTests(unittest.TestCase):
    def verdict(self, said):
        bin = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (bin / 'codex').write_text(
            f'#!{sys.executable}\nimport sys\nargs = sys.argv\n'
            f"open(args[args.index('--output-last-message') + 1], 'w').write({said!r})\n"
            "print('{\"type\": \"turn.completed\", \"usage\": {\"input_tokens\": 7}}')\n")
        (bin / 'codex').chmod(0o755)
        os.environ['PATH'] = f'{bin}{os.pathsep}{os.environ["PATH"]}'
        self.addCleanup(os.environ.__setitem__, 'PATH', os.environ['PATH'].split(os.pathsep, 1)[1])
        work = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (work / 'ANSWER.txt').write_text('FINAL: x')
        return run.review.verdict('m', {'ques': 'q', 'web': 'https://example.invalid/'}, work)

    def test_every_verdict_is_recorded_with_its_cost(self):
        self.assertEqual(self.verdict('REVISE\n- check x'),
                         {'verdict': 'REVISE', 'issues': '- check x', 'usage': {'input_tokens': 7}, 'failure': None})
        self.assertEqual(self.verdict('OK')['verdict'], 'OK')
        self.assertEqual(self.verdict('')['verdict'], 'unreadable')
        self.assertIsNone(self.verdict('OK')['issues'])


if __name__ == '__main__':
    unittest.main()

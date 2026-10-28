#!/usr/bin/env python3
"""Audit a run's transcripts for how the actor used the web outside browser-cmd.

Per task: host web searches and fetches, `site:` queries, pages of the task's own
website read outside the browser, shell commands that reach the network, any touch of
benchmark material (contamination), and tools beyond the intended surface. Writes
audit.json into the run; reads transcripts only.

    python3 audit.py runs/codex
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

BENCHMARK = re.compile(r'webvoyager|reference_answer|minorjerry|omxyz|tasks_615|auto_eval|[A-Za-z ]+--\d+', re.I)
SHELL_NET = re.compile(r'\b(curl|wget|urllib|requests\.|http\.client|fetch\(|lynx|nc )', re.I)
# The actor starting its own daemon or Chrome, or rewiring browser-cmd's settings.
BROWSER_ESCAPE = re.compile(r'--serve|BROWSER_CMD_[A-Z_]+=|Google Chrome|chromium|--remote-debugging|playwright|puppeteer', re.I)
CLAUDE_TOOLS = {'Bash', 'Read', 'Write', 'Skill', 'WebSearch', 'WebFetch'}
CODEX_ITEMS = {'agent_message', 'reasoning', 'command_execution', 'web_search', 'file_change', 'error', 'todo_list'}


def calls(host, transcript):
    """(kind, text) for every tool call: kind is search, fetch, shell or the tool's own name."""
    for line in transcript.read_text().splitlines() if transcript.exists() else []:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if host == 'claude':
            for part in (event.get('message') or {}).get('content') or []:
                if isinstance(part, dict) and part.get('type') == 'tool_use':
                    given = part.get('input') or {}
                    kind = {'WebSearch': 'search', 'WebFetch': 'fetch', 'Bash': 'shell'}.get(part['name'], part['name'])
                    yield kind, str(given.get('query') or given.get('url') or given.get('command') or given)
        elif event.get('type') == 'item.completed':
            item = event['item']
            if item['type'] == 'web_search':
                action = item.get('action') or {}
                kind = 'search' if action.get('type', 'search') == 'search' else 'fetch'
                yield kind, str(action.get('url') or action.get('query') or action.get('queries') or item.get('query'))
            elif item['type'] == 'command_execution':
                yield 'shell', item.get('command', '')
            elif item['type'] not in ('agent_message', 'reasoning', 'error'):
                yield item['type'], json.dumps(item)[:300]


def site(url):
    host = urlparse(url).hostname or ''
    return host.removeprefix('www.')


def audit(run):
    manifest = json.loads((run / 'manifest.json').read_text())
    host, rows = manifest.get('host', 'claude'), {}
    expected = CLAUDE_TOOLS if host == 'claude' else CODEX_ITEMS
    for result in sorted(run.glob('task_*/result.json'), key=lambda p: int(p.parent.name.split('_')[1])):
        task = json.loads(result.read_text())['task']
        own, seen = site(task['web']), list(calls(host, result.parent / 'transcript.jsonl'))
        texts = [text for kind, text in seen if kind in ('search', 'fetch')]
        rows[task['id']] = {
            'searches': sum(kind == 'search' for kind, _ in seen),
            'fetches': sum(kind == 'fetch' for kind, _ in seen),
            'browser_cmd_commands': sum(kind == 'shell' and 'browser-cmd' in text for kind, text in seen),
            'site_queries': [text for kind, text in seen if kind == 'search' and 'site:' in text.lower()],
            'own_site_fetches': [text for kind, text in seen if kind == 'fetch' and own and own in site(text)],
            'shell_network': [text[:300] for kind, text in seen
                              if kind == 'shell' and 'browser-cmd' not in text and SHELL_NET.search(text)],
            'benchmark_material': [text[:300] for text in texts + [t for k, t in seen if k == 'shell']
                                   if BENCHMARK.search(text)],
            'browser_escape': [text[:300] for kind, text in seen if kind == 'shell' and BROWSER_ESCAPE.search(text)],
            'unexpected_tools': sorted({kind for kind, _ in seen
                                        if kind not in ('search', 'fetch', 'shell') and kind not in expected}),
            'stop_check_continued': (result.parent / 'stop_check.txt').exists(),
        }
    flagged = {key: [task for task, row in rows.items() if row[key]] for key in
               ('site_queries', 'own_site_fetches', 'shell_network', 'benchmark_material', 'browser_escape',
                'unexpected_tools')}
    report = {'host': host, 'web_tools': manifest.get('web_tools', False), 'tasks': len(rows),
              'searches': sum(row['searches'] for row in rows.values()),
              'fetches': sum(row['fetches'] for row in rows.values()), 'flagged': flagged, 'per_task': rows}
    (run / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    summary = audit(Path(sys.argv[1]).resolve())
    print(json.dumps({key: summary[key] for key in ('host', 'tasks', 'searches', 'fetches', 'flagged')}, indent=2))

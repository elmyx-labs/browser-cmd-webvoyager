#!/usr/bin/env python3
"""What a Codex run cost, per task and in all: input (and cached), output, model calls, calls spent only
collecting a command's output (write_stdin polls), the context of the average and largest call, and the
bytes browser-cmd printed. Reads usage.json, rollout.jsonl and transcript.jsonl; writes cost.json.

    python3 cost.py runs/codex
"""
import json
import sys
from pathlib import Path


def events(path):
    """Each JSON line of a log; the last line of a task killed at its deadline may be cut short."""
    for line in path.read_text().splitlines() if path.exists() else []:
        try:
            yield json.loads(line)
        except ValueError:
            continue


def task(job):
    usage = json.loads((job / 'usage.json').read_text()).get('usage', {}) if (job / 'usage.json').exists() else {}
    calls, polls, contexts, running = 0, 0, [], {}
    for event in events(job / 'rollout.jsonl'):
        payload = event.get('payload') or {}
        if payload.get('type') == 'custom_tool_call':
            calls += 1
            polls += 'write_stdin' in payload.get('input', '')
        elif payload.get('type') == 'token_count' and (payload.get('info') or {}).get('last_token_usage'):
            contexts.append(payload['info']['last_token_usage']['input_tokens'])
            running = payload['info'].get('total_token_usage') or running
    # A task stopped at its deadline never reports usage; its rollout's running total does.
    usage = usage or running
    printed = 0
    for event in events(job / 'transcript.jsonl'):
        item = event.get('item') or {}
        if item.get('type') == 'command_execution' and 'browser-cmd' in item.get('command', ''):
            printed += len(item.get('aggregated_output', ''))
    return {'input': usage.get('input_tokens'), 'cached': usage.get('cached_input_tokens'),
            'output': usage.get('output_tokens'), 'calls': calls, 'polls': polls,
            'mean_context': round(sum(contexts) / len(contexts)) if contexts else None,
            'peak_context': max(contexts, default=None), 'browser_cmd_bytes': printed}


def run(path):
    rows = {}
    for result in sorted(path.glob('task_*/result.json'), key=lambda p: int(p.parent.name.split('_')[1])):
        row = json.loads(result.read_text())
        rows[row['task']['id']] = {**task(result.parent), 'seconds': round(row['elapsed_seconds'])}
    total = {key: sum(row[key] or 0 for row in rows.values())
             for key in ('input', 'cached', 'output', 'calls', 'polls', 'browser_cmd_bytes', 'seconds')}
    total['tasks_without_usage'] = sum(row['input'] is None for row in rows.values())
    report = {'total': total, 'per_task': rows}
    (path / 'cost.json').write_text(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    print(json.dumps(run(Path(sys.argv[1]).resolve())['total'], indent=2))

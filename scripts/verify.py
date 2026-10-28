#!/usr/bin/env python3
"""Recount every judge's score from the judge outputs themselves and check that each counted
attempt carries the evidence the judges saw. Needs no API key and no network.

    python3 scripts/verify.py
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / 'results' / 'runs' / 'codex-gpt-6.1-sol'
TASKS = ROOT / 'benchmark' / 'data' / 'browser-cmd' / 'WebVoyager_data.jsonl'


def read(path):
    return json.loads(path.read_text())


def gpt55():
    evals = (RUN / 'llm-judge-openai-gpt-5.5-alumnium-vanilla').glob('*.eval.json')
    return {e['id']: e['pass'] for e in map(read, evals)}


def cli_judge(name):
    return {k: v['pass'] for k, v in read(RUN / 'cross-judges' / f'{name}.json').items()}


def gemini():
    """Shard verdicts, with the 8000-token retries taking the place of answers cut off at 2000 tokens."""
    base = RUN / 'cross-judges' / 'gemini-3.8-flash'
    paths = sorted(base.glob('shard*/*.eval.json')) + sorted(base.glob('retry8k/*.eval.json'))
    return {e['id']: e['pass'] for e in map(read, paths)}


def main():
    ids = [json.loads(line)['id'] for line in TASKS.open()]
    recorded = read(RUN / 'verdicts.json')
    judges = {'gpt-5.5': gpt55(), 'gpt-5.6-sol': cli_judge('gpt-5.6-sol'), 'opus-5.5': cli_judge('opus-5.5'),
              'gemini-3.8-flash': gemini()}
    problems = []
    for name, verdicts in judges.items():
        if set(verdicts) != set(ids):
            problems.append(f'{name}: verdicts for {len(verdicts)} tasks, expected {len(ids)}')
        if {i: verdicts.get(i) for i in ids} != recorded[name]:
            problems.append(f'{name}: verdicts.json differs from the judge outputs')
        failed = sorted(i for i in ids if not verdicts.get(i))
        passed = len(ids) - len(failed)
        print(f'{name:18} {passed}/{len(ids)} = {100 * passed / len(ids):.2f}%  not passed: {", ".join(failed)}')
    judgments = {j['id']: j['pass'] for j in read(RUN / 'judgments.json')}
    if judgments != judges['gpt-5.5'] or read(RUN / 'summary.json')['success'] != sum(judgments.values()):
        problems.append('judgments.json or summary.json differs from the GPT-5.5 judge outputs')
    if [r['task']['id'] for r in read(RUN / 'results.json')] != ids:
        problems.append('results.json does not list the tasks in order')
    for i in ids:
        for name in ('ANSWER.txt', 'final.png', 'prompt.txt', 'transcript.jsonl'):
            if not (RUN / 'tasks' / i / name).is_file():
                problems.append(f'{i}: {name} missing')
    digest, name = (ROOT / 'snapshot' / 'SHA256SUMS').read_text().split()
    if hashlib.sha256((ROOT / 'snapshot' / name).read_bytes()).hexdigest() != digest:
        problems.append('snapshot: checksum mismatch')
    print('\n'.join(problems) or 'OK: scores match the judge outputs; every counted attempt has its evidence')
    sys.exit(1 if problems else 0)


main()

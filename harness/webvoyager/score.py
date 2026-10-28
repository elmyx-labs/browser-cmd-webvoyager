#!/usr/bin/env python3
"""The per-site split of a judged run, read from the judge's own judgments.json
(never re-judging).

    python3 score.py runs/final
"""
import collections
import json
import sys
from pathlib import Path

run = Path(sys.argv[1]) if len(sys.argv) > 1 else sys.exit(__doc__)
site = {task['id']: task['web_name'] for task in map(json.loads, (run / 'tasks.jsonl').read_text().splitlines())}
verdict = {j['id']: j.get('result') for j in json.loads((run / 'judgments.json').read_text())}

by = collections.defaultdict(collections.Counter)
for task, web in site.items():
    result = verdict.get(task)
    bucket = 'pending' if result is None else 'success' if result == 1 else 'not'
    by[web][bucket] += 1
    by['All'][bucket] += 1


def line(name, count):
    judged = count['success'] + count['not']
    score = 100 * count['success'] / judged if judged else 0
    return f"| {name} | {sum(count.values())} | {count['success']} | {count['not']} | {count['pending']} | {score:.1f}% |"


print('| Site | Total | Success | Not | Pending | Score |\n| --- | ---: | ---: | ---: | ---: | ---: |')
print('\n'.join(line(web, by[web]) for web in sorted(by) if web != 'All'))
print(line('**All**', by['All']))

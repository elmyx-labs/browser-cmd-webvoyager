#!/usr/bin/env python3
"""Keep date-gated tasks runnable: an explicit date that has already passed on a
booking or flight site cannot be searched, so every dated mention in such a task
is moved forward by whole years until its earliest date is not in the past.

The judge is reference-free, so this changes what can be run, not how it is
scored. Other sites are untouched: their dates are historical questions.
"""
import datetime
import re

SITES = {'Booking', 'Google Flights'}
MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september',
          'october', 'november', 'december']
MONTH = r'(%s)\.?' % '|'.join(m for name in MONTHS for m in (name, name[:3]))
DAY = r'(\d{1,2})(?:st|nd|rd|th)?'
YEAR = re.compile(r'(?<![$\d.,])\b(20\d\d)\b')
# What may stand right before a year and name the date it closes:
# "July 10, 2026", "July 1-7, 2026", "Dec 25th - Dec 26th, 2026", "8 July 2026", "21/12/2026".
BEFORE = [
    (re.compile(MONTH + r' ' + DAY + r'(?:\s*[-–]\s*' + DAY + r')?,?\s*$', re.IGNORECASE),
     lambda m: (m.group(1), int(m.group(3) or m.group(2)))),
    (re.compile(DAY + r' ' + MONTH + r',?\s*$', re.IGNORECASE), lambda m: (m.group(2), int(m.group(1)))),
    (re.compile(r'\b(\d{1,2})/(\d{1,2})/$'), lambda m: (int(m.group(2)), int(m.group(1)))),
]


def month(name):
    if isinstance(name, int):
        return name
    return next(i for i, full in enumerate(MONTHS, 1) if full.startswith(name.lower()[:3]))


def dated_years(ques):
    """Every year in the text that closes a date, with that date."""
    found = []
    for match in YEAR.finditer(ques):
        head = ques[max(0, match.start() - 40):match.start()]
        for pattern, parts in BEFORE:
            if near := pattern.search(head):
                name, day = parts(near)
                try:
                    found.append((match, datetime.date(int(match.group(1)), month(name), day)))
                except ValueError:
                    pass
                break
    return found


def roll(task, today):
    """The task with its past explicit dates moved forward, and how many years."""
    if task['web_name'] not in SITES:
        return task, 0
    years = dated_years(task['ques'])
    if not years:
        return task, 0
    earliest = min(date for _, date in years)
    shift = 0
    while earliest.replace(year=earliest.year + shift) < today:
        shift += 1
    if not shift:
        return task, 0
    ques = task['ques']
    for match, _ in reversed(years):
        ques = ques[:match.start()] + str(int(match.group(1)) + shift) + ques[match.end():]
    return {**task, 'ques': ques}, shift


def roll_all(tasks, today):
    rows, changes = [], []
    for task in tasks:
        rolled, years = roll(task, today)
        rows.append(rolled)
        if years:
            changes.append({'id': task['id'], 'years': years, 'from': task['ques'], 'to': rolled['ques']})
    stale = [row['id'] for row in rows if row['web_name'] in SITES
             and any(date < today for _, date in dated_years(row['ques']))]
    unread = [row['id'] for row in rows if row['web_name'] in SITES
              and len(YEAR.findall(row['ques'])) > len(dated_years(row['ques']))]
    if stale or unread:
        raise SystemExit(f'date roll left past dates in {stale} and unread years in {unread}')
    return rows, changes


if __name__ == '__main__':
    import json, pathlib, sys
    today = datetime.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.date.today()
    tasks = [json.loads(line) for line in (pathlib.Path(__file__).parent.parent / 'webvoyager' / 'tasks_615.jsonl').read_text().splitlines() if line.strip()]
    for change in roll_all(tasks, today)[1]:
        print(change['id'], '+%d' % change['years'], '|', change['to'])

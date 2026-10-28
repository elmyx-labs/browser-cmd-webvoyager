"""A second model reads the actor's answer and final screenshot before the task ends, as a goal check
would, and names what to fix; the actor checks each point in the browser. The reviewer cannot browse."""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

import codex

PROMPT = '''You review another agent's answer to a web task before it is handed in. You see the task, the answer \
it wrote, its notes of what it read in the browser and its final screenshot; you cannot browse.

TASK: {ques}
START URL: {web}

ANSWER:
{answer}

NOTES:
{notes}

List every requirement the task states (each constraint, count, date, duration, filter, variant and item asked \
for), read as the person who set the task means it and as the site supports it: "released" is not "announced", \
four nights are not three, but a spelling or plural variant is not a miss, and wording open to two readings \
that give different results is answered for each. For each: is it answered, supported by the notes or the screenshot, consistent with them and computed \
correctly? Is the answer the result itself, without doubts the agent could have settled in the browser? When the \
notes show the site holds nothing closer, the best item found, with its difference stated, is the answer: never ask \
to replace it with "not found". An answer that opens with a negative ("no …", "could not", "not found", "not \
verified", "not a dedicated …") while it names candidate items reads as a failure to whoever grades it: ask for the \
best candidate to lead as the result, its difference stated in one line after. So does a count given as "at least" or \
without its total: ask for one number counted on the list or index the site keeps for those items. The screenshot is one viewport: it should be readable, from the page the answer \
comes from (for a task that asks for an action, the page confirming it was done), show the item's name with the \
facts that decide the task, have filters, sorts and dates applied, and nothing over it; it need not show every \
requirement, the notes support the rest.

Ask for a revision only for a real problem with the result: a requirement unmet or unsupported where the site may \
hold a better item, an item not the best by the task's measure (latest, nearest, about the topic) among those \
shown, a filter the task does not name narrowing the result, facts the named website holds taken from elsewhere, a \
figure not from the page or with its arithmetic missing, a claim that something does not exist without the page that \
would hold it, a contradiction, a miscalculation, a doubt left in the answer, a screenshot that is unreadable, \
from another page, covered or shows a filter or sort not applied. Not for presentation.

First line exactly OK or REVISE. After REVISE, a short list of what to fix, each item concrete and checkable in \
the browser.'''
RESUME = ('A reviewer read your answer and final screenshot. It cannot browse and may be wrong:\n{issues}\n\nCheck '
          'each point in the browser and fix what is wrong, then rewrite ./ANSWER.txt and ./final.png. Keep what you '
          'verify is right; when nothing better exists, the best item you found stays the answer, with its '
          'difference stated. The answer states the result and its evidence; it does not discuss the review.')
# The end of the notes the reviewer reads, in characters.
NOTES = 8000
NO_EXTRAS = {'CMUX_CLAUDE_HOOKS_DISABLED': '1', 'CMUX_CODEX_HOOKS_DISABLED': '1', 'CMUX_COMPUTER_USE_MCP_DISABLED': '1'}


def verdict(model, task, work):
    """The reviewer's verdict (OK, REVISE, or why there is none), what it wants fixed and what it cost."""
    answer = work / 'ANSWER.txt'
    shot = work / 'final.png'
    with tempfile.TemporaryDirectory(prefix='review-') as tmp:
        home = Path(tmp) / 'codex'
        codex.home(Path(tmp))
        last, events = Path(tmp) / 'last.txt', Path(tmp) / 'events.jsonl'
        isolated = codex.settings(argparse.Namespace(effort='high', web_tools=False, auto_compact=None, subagents=False))
        command = ['codex', 'exec', '--json', '--skip-git-repo-check', '-m', model, *isolated,
                   '--output-last-message', str(last), *(['--image', str(shot)] if shot.exists() else []), '-']
        clean = {key: value for key, value in os.environ.items() if not key.startswith(('BROWSER_CMD_', 'OPENAI_'))}
        notes = work / 'NOTES.md'
        text = PROMPT.format(**task, answer=answer.read_text() if answer.exists() else '(no ANSWER.txt)',
                             notes=notes.read_text()[-NOTES:] if notes.exists() else '(none)')
        try:
            with events.open('w') as out:
                subprocess.run(command, input=text, text=True, stdout=out, stderr=subprocess.DEVNULL, cwd=tmp,
                               timeout=300, env={**clean, 'CODEX_HOME': str(home), **NO_EXTRAS})
        except subprocess.TimeoutExpired:
            return {'verdict': 'timeout', 'issues': None, 'usage': {}, 'failure': 'no answer within 300 s'}
        ran = codex.summary(events)
        said = last.read_text().strip() if last.exists() else ''
    head, _, rest = said.partition('\n')
    word = head.strip().upper()
    found = 'OK' if word.startswith('OK') else 'REVISE' if word.startswith('REVISE') else 'unreadable'
    return {'verdict': found, 'issues': rest.strip() or None if found == 'REVISE' else None,
            'usage': ran['usage'], 'failure': ran['failure']}

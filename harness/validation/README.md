# Cross-check judge

`judge.py RUN` scores a WebVoyager run with the same pinned prompts as `evaluation/auto_eval.py`, through a
subscription CLI instead of the OpenAI API, so a second model family can check the leaderboard judge:

```sh
JUDGE_CODEX=gpt-5.6-sol python3 judge.py RUN       # codex exec
JUDGE_CLAUDE=claude-opus-5-5 python3 judge.py RUN  # claude -p
```

It writes `validation_judge.<model>.json` into the run, with each task's verdict and reasoning. The verdict
is the last one the judge states.

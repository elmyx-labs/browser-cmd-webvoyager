# WebVoyager

A Codex agent with the browser-cmd skill on the 615-task WebVoyager layer, scored by the leaderboard's judge.

- **Tasks.** `tasks_615.jsonl` is byte-for-byte `benchmark/data/current/WebVoyager_data.jsonl`
  of [omxyz/webvoyager](https://github.com/omxyz/webvoyager) at `df42681`.
- **Dates.** Booking and Google Flights cannot search a date that has passed, so on
  those two sites every explicit date is moved forward by whole years until the
  earliest one is not in the past (`../runner/dates.py`). Each run records what was rolled
  in `date_updates.json`. The judge is reference-free, so this affects what can be
  run, not how it is scored.
- **Agent.** One `codex exec` session per task (`--host codex`) with the browser-cmd skill,
  its own daemon and headless Chrome profile, pace 0.3, and a reviewer model that checks the
  answer and screenshot before the task ends (`--review`). See [../runner](../runner/README.md).
- **Judge.** `evaluation/auto_eval.py` of omxyz/webvoyager at `df42681`, verified by
  hash, with GPT-5.5 and the leader's dependency lock (`../../evaluation/`).

## Run

From a browser-cmd checkout with this directory as `bench/`:

```sh
cd bench/runner
python3 run.py --out runs/wv615 --host codex --model gpt-6.1-sol --effort high --web-tools \
  --review gpt-6.1-terra --timeout 900 --timezone America/New_York --workers 3
OPENAI_API_KEY=... python3 ../webvoyager/judge.py runs/wv615
python3 ../webvoyager/score.py runs/wv615          # per-site table
```

The judge writes `judge/`, `judgments.json` and `summary.json` into the run; its pinned evaluator and venv
live in `.judge/` here.

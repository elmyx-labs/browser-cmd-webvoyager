<p align="center">
  <img alt="browser-cmd" src="docs/assets/logo.svg" width="360">
</p>

<p align="center">
  <strong>WebVoyager results: every trajectory, screenshot and verdict behind the score.</strong>
</p>

<p align="center">
  <img alt="WebVoyager 611/615" src="https://img.shields.io/badge/WebVoyager-99.35%25%20(611%2F615)-0B0D12">
  <img alt="Four judges" src="https://img.shields.io/badge/4%20judges-99.19%E2%80%9399.67%25-0B0D12">
  <img alt="Site-specific prompts" src="https://img.shields.io/badge/site--specific%20prompts-0-0B0D12">
  <a href="https://github.com/elmyx-labs/browser-cmd"><img alt="browser-cmd" src="https://img.shields.io/badge/agent%20browser-browser--cmd-0B0D12"></a>
</p>

<p align="center">
  <a href="#results">Results</a> ·
  <a href="#what-makes-this-result">Method</a> ·
  <a href="#run-protocol">Protocol</a> ·
  <a href="#tasks">Tasks</a> ·
  <a href="#verify-it">Verify</a> ·
  <a href="results/reports/20261028-codex-gpt-6.1-sol-report.md">Full report</a>
</p>

---

A Codex gpt-6.1-sol agent driving a real Chrome through [browser-cmd](https://github.com/elmyx-labs/browser-cmd)
completes **611 of 615** WebVoyager tasks under the leaderboard's judge, above the current top entry
(610/615) on the same task layer and the same judge.

## Results

| Judge | Passed | Score |
| --- | ---: | ---: |
| **GPT-5.5**, Alumnium vanilla (leaderboard judge) | **611 / 615** | **99.35%** |
| gpt-5.6-sol, same prompt | 612 / 615 | 99.51% |
| Claude Opus 5.5, same prompt | 610 / 615 | 99.19% |
| Gemini 3.8 Flash, same prompt | 613 / 615 | 99.67% |

Four judges from three model families agree on 607 tasks and score the run between 99.19% and 99.67%.

| Site | Score | Site | Score |
| --- | ---: | --- | ---: |
| Allrecipes | 40 / 40 | Coursera | 40 / 40 |
| Amazon | 40 / 40 | ESPN | 44 / 44 |
| Apple | 40 / 40 | GitHub | 40 / 41 |
| ArXiv | 43 / 43 | Google Flights | 40 / 40 |
| BBC News | 39 / 39 | Google Map | 40 / 40 |
| Booking | 39 / 40 | Google Search | 41 / 42 |
| Cambridge Dictionary | 41 / 41 | Huggingface | 39 / 39 |
| | | Wolfram Alpha | 45 / 46 |

Per site, under the leaderboard judge. 11 of 15 sites at 100%.

## What makes this result

- **No site knowledge.** No per-site skill, prompt, selector or reconnaissance. The agent knows the 15 sites
  only from training; its skill is general browser-cmd usage.
- **The leaderboard's own tasks and judge.** The top entry's 615-task layer and its pinned `auto_eval.py`,
  one screenshot per task, reference-free. No task removed or reworded by us; 49 Booking and Google Flights
  dates rolled forward one year so they can still be searched.
- **Four judges, three model families.** The leaderboard judge (GPT-5.5) shares a vendor with the actor, so the
  same trajectories were also scored by Claude Opus 5.5 and Gemini 3.8 Flash. Every judge scores 610/615 or more.
- **No verdict touched.** Every verdict of every judge is published as parsed.
- **Reruns in the open.** 21 tasks count a later attempt, rerun after a general fix to the harness, never to
  browser-cmd; the latest attempt counts whatever its verdict. The
  [rerun ledger](results/reports/20261028-codex-gpt-6.1-sol-report.md#rerun-ledger) lists each one, why and what
  changed.
- **A frozen build.** The browser-cmd source is identical in every counted attempt and is published in
  `snapshot/`.
- **Nothing hidden.** All 615 counted trajectories, every superseded attempt and the raw output of all four
  judges are in this repository.
- **Fast.** A median of 128 seconds per task.

The [full report](results/reports/20261028-codex-gpt-6.1-sol-report.md) covers the setup, the run history,
where the four misses come from and the limitations.

## Run protocol

1. **Tasks.** The 615 tasks of the top entry's layer, with 49 past dates rolled forward
   ([Tasks](#tasks)). Each task has a 900-second budget.
2. **A clean start per task.** A fresh Codex CLI 0.163.0 session (gpt-6.1-sol, reasoning effort high) in its own
   empty working directory and `CODEX_HOME`: no user skills, plugins, MCP servers or sub-agents. A fresh
   browser-cmd daemon and a fresh headless Chrome profile; no cookies or sign-ins carried between tasks.
3. **What the agent gets.** The browser-cmd skill (`harness/runner/skills/lean/SKILL.md`) and one prompt: the task,
   its start URL, the time budget, the answer rules and the evidence rule (`harness/runner/run.py`). Codex's own
   web search is allowed for sources the task does not name; the task's website is read only through browser-cmd.
4. **Evidence.** The agent ends on the page that proves the answer, saves one viewport screenshot as `final.png`
   and writes `ANSWER.txt`. At 180 seconds before the deadline it is told to finish with what it has.
5. **Review.** A second model (gpt-6.1-terra) that cannot browse reads the task, the answer, the agent's notes and
   the screenshot, and names what to fix; the agent checks each point in the browser. At most two rounds.
6. **Network.** Time zone America/New_York. Sites that refuse non-US addresses (Allrecipes, Cambridge Dictionary,
   ESPN, GitHub) and two tasks that lead to them go through a US residential proxy; everything else goes direct.
   Two tasks behind a sign-in wall (Cambridge Dictionary--39, GitHub--40) ran in a Chrome the operator had signed
   in to beforehand; nobody acted during any task.
7. **Judging.** The pinned `evaluation/auto_eval.py` with GPT-5.5: task, answer and the final screenshot,
   `SUCCESS` or `NOT SUCCESS`, no reference answers. Three more models score the same trajectories with the same
   prompt.
8. **Attempts.** One main run of all 615 tasks. Tasks that failed under a judge were run again after fixes to the
   harness (never to browser-cmd); the latest attempt counts whatever its verdict. 21 tasks count a later attempt,
   and every earlier attempt is published in `attempts/`.

The exact configuration is pinned in [`browser-cmd.lock.json`](browser-cmd.lock.json) and each run's
`manifest.json`.

## Tasks

| Layer | Tasks | Changes |
| --- | ---: | --- |
| Original WebVoyager | 643 | — |
| Alumnium cleaned | 619 | 24 stale tasks removed, 85 prompts updated (by Alumnium) |
| Top entry's layer, `benchmark/data/current/` | 615 | 11 prompt edits, 4 tasks excluded (by omxyz/webvoyager) |
| **As run**, `benchmark/data/browser-cmd/` | **615** | **49 dates rolled forward one year; nothing else** |

Our only change to any task is the date roll on Booking and Google Flights, which cannot search a date in the past.
Every changed task, before and after, is listed in [TASK_UPDATES.md](TASK_UPDATES.md).

## Verify it

```sh
python3 scripts/verify.py
```

Recounts all four scores from the judges' raw outputs and checks that every counted attempt has its answer,
screenshot, prompt and trajectory. No API key, no network, a few seconds.

To re-judge with the leaderboard judge:

```sh
pip install -r requirements-webvoyager.txt
OPENAI_API_KEY=... python3 evaluation/auto_eval.py \
  --results results/runs/codex-gpt-6.1-sol/results.json \
  --task-data benchmark/data/browser-cmd/WebVoyager_data.jsonl \
  --model gpt-5.5 --max-attached-imgs 1 --max-completion-tokens 2000
```

## Layout

| Path | Contents |
| --- | --- |
| `results/runs/codex-gpt-6.1-sol/` | `results.json`, `judgments.json` and `summary.json` in the leaderboard judge's format |
| `results/runs/codex-gpt-6.1-sol/tasks/<task id>/` | The counted attempt: prompt, full Codex trajectory, answer, final screenshot, notes, reviewer verdicts, token usage |
| `results/runs/codex-gpt-6.1-sol/llm-judge-openai-gpt-5.5-alumnium-vanilla/` | The leaderboard judge's prompt, raw response and verdict per task |
| `results/runs/codex-gpt-6.1-sol/cross-judges/` | gpt-5.6-sol, Claude Opus 5.5 and Gemini 3.8 Flash verdicts |
| `results/runs/codex-gpt-6.1-sol/attempts/` | Every superseded attempt, with `attempts.json` saying which one counts |
| `results/reports/` | The full report |
| `benchmark/data/` | `current/`: the 615-task layer as published by the top entry; `browser-cmd/`: as run |
| `TASK_UPDATES.md` | Every change to a task, before and after |
| `browser-cmd.lock.json` | The evaluated system and judge, pinned by checksum |
| `evaluation/` | The pinned judge |
| `harness/` | The runner, reviewer and date roll used for the run |
| `snapshot/` | The evaluated browser-cmd source with its checksum |

Raw Codex event logs and intermediate screenshots (0.9 GB compressed) are attached to the
[release](https://github.com/elmyx-labs/browser-cmd-webvoyager/releases).

## License

`harness/` and `scripts/` are Apache-2.0. `benchmark/` and `evaluation/` come from
[omxyz/webvoyager](https://github.com/omxyz/webvoyager). Screenshots and page text in `results/` are captures
of third-party websites, published as evaluation evidence.

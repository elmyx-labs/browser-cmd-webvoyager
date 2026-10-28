# Runner

`run.py` runs task rows (`id`, `web_name`, `ques`, `web`) with Claude Code or Codex driving browser-cmd: one
actor, daemon and profile per task, a manifest with the hashes of everything the result depends on. Task
sets: `../webvoyager` (615 tasks, the default) and `../validation`.

## Run

Needs Chrome, Rust, Claude Code or Codex signed in, and Python 3.

```sh
cd bench/runner

python3 run.py --out runs/smoke --ids Allrecipes--0,GitHub--13   # a quick check
python3 run.py --out runs/final                                  # all 615 tasks
python3 run.py --out runs/final --resume     # after a rate limit or execution errors

OPENAI_API_KEY=... python3 ../webvoyager/judge.py runs/final
python3 ../webvoyager/score.py runs/final    # per-site table
```

`run.py` builds the release binary into the run, rolls the dates, and writes a
`manifest.json` with the hashes of the binary, plugin and tasks; `--resume` refuses
to continue if any of them changed. When the plan's limit is hit, the remaining
tasks are left for `--resume`.

Options: `--host` (`claude` or `codex`), `--model` (default `claude-opus-5`, Codex
`gpt-5.6-sol`), `--effort` (host default; Codex `high`), `--web-tools`, `--workers` (4),
`--timeout` seconds per task (900), `--budget-per-task` USD (3, Claude Code only), `--sites`,
`--ids`, `--limit`, `--as-of`, `--timezone`, `--auto-compact` tokens (Codex, 300000; 0 keeps the Codex default).

**Codex.** `--host codex` runs `codex exec` in a fresh `CODEX_HOME` that links only the
signed-in account, with the user's skills, bundled skills and extra tools (agents, goals,
images, plugins, browser and computer use) switched off. It gets the lean skill
(`skills/lean/SKILL.md`: interface and hard boundaries) by default; `--skill PATH` gives another,
e.g. the plugin's, or `skills/once/SKILL.md` (the answer written once at the end, notes as the
running record). `--review MODEL` has MODEL read the answer and final screenshot when the actor stops
and name what to fix; the actor checks those points in the browser and rewrites the answer, at
most twice (`review.py`; every verdict, OK or REVISE or why there is none, is kept with its token usage as
`review_N.json`). `--subagents` lets it hand independent reading to at most three subagents, each
in a browser session of its own; their logs are kept beside the task's. Its sandbox writes only the working directory and reaches the daemon on
loopback. Codex does not run untrusted hooks; `--stop-check` makes the runner apply the plugin's
stop check itself, resuming the session once with its reason when it would block. No USD cap:
the timeout is the only bound.

**Web tools.** By default the actor has no web tool but browser-cmd. `--web-tools` adds
the host's own web search and fetch, limited by the prompt to discovery (no `site:`, never
the task's own website, not evidence by itself). `python3 audit.py runs/X` reports per task
how they were used, shell network access, benchmark material and unexpected tools.

Sites that refuse the machine's own address (Transfermarkt, Target, Walmart; the list
is `PROXY_HOSTS` in `run.py`) go through a proxy when `BROWSER_CMD_PROXY` is set; every
other site is reached directly. WebVoyager tasks on sites that refuse it (ESPN, GitHub,
Cambridge Dictionary, Allrecipes) and two tasks whose route leads to one (`PROXY_SITES`,
`PROXY_TASKS`) go through it whole. A `{session}` placeholder in the proxy URL becomes a
fresh id per task, pinning one exit address for the task. `BROWSER_CMD_PROXY_HOSTS`
overrides the list and `BROWSER_CMD_TIMEZONE` the browser's zone; all are recorded in
the manifest.

```sh
BROWSER_CMD_PROXY='http://USER:PASS_session-{session}_lifetime-30m@PROXY:PORT' python3 run.py --out runs/final
```

**Prepared browser.** `--cdp URL` attaches every task to a Chrome the operator started and
prepared beforehand, signed in where tasks lead, as a user's own browser would be (Chrome 136+
takes a DevTools port only with a profile of its own, or from `chrome://inspect/#remote-debugging`,
whose endpoint is `ws://127.0.0.1:9222/devtools/browser`). Tasks run one at a time
(`--workers 1`) through the browser's own network, no proxy; each starts in a session of its
own, and when it ends the runner closes that session's tabs, kept ones too, and gives back any
it borrowed, so the operator's own tabs stay as they were. The manifest records the attachment.

```sh
python3 run.py --out runs/prepared --cdp ws://127.0.0.1:9222/devtools/browser --workers 1 --ids GitHub--40
```

## Actor session

- **Shared prefix.** Each worker runs its tasks in one fixed directory,
  `workers/wN`, emptied before every task; after the task its contents move to
  `task_N/work` (answer, screenshot, `.browser-cmd/CHECK.md`, media). Per-task
  paths (profile, daemon address, RPC token) reach the actor only through the
  environment, and `--add-dir` is no longer passed, so the system prompt is the
  same from task to task. `--exclude-dynamic-system-prompt-sections` also moves
  cwd and git status out of the system prompt, so workers share one prefix.
- **Only the browser-cmd plugin.** `--setting-sources ''` reads no user, project
  or local settings; Claude Code 2.1.303 gates `~/.claude/skills`, `@skills-dir`
  and synced skills, user-enabled plugins and hooks, and the user `CLAUDE.md` on
  the user source. With `--strict-mcp-config`, an empty MCP config,
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` and `--plugin-dir ../../plugin`, the actor
  sees Claude Code's built-ins and browser-cmd only. `~/.claude` is not modified.
  This was established by reading the 2.1.303 binary, not by a model run; check
  the first transcript's `init` event (`skills`, `plugins`) on the next run.
- **Prompt cache.** `CLAUDE_CODE_PROMPT_CACHE_TTL=5m` (Claude Code's documented
  setting; unset means 1 hour on a subscription, whose cache writes cost more).
- **Time zone.** `--timezone ZONE` (default `BROWSER_CMD_TIMEZONE`, else the host's
  zone) sets `TZ` and `BROWSER_CMD_TIMEZONE` for the daemon and the actor alike and
  is recorded in `manifest.json` with `prompt_cache_ttl` and `actor_isolation`. A
  resumed run keeps its recorded zone.
- **Stop check.** The runner sets `BROWSER_CMD_ANSWER_FILE=ANSWER.txt`; the plugin's
  stop hook then asks for one validation pass only when `.browser-cmd/CHECK.md` is
  missing or has a `fail`/`unknown` row, or `ANSWER.txt` is missing.

Tests (no browser, network or model; fake daemon and actor):
`python3 -m unittest bench.runner.test_run bench.runner.test_stop_check`
from the repository root.

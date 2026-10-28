#!/usr/bin/env python3
"""Alumnium-style OpenAI auto-eval for packaged WebVoyager results.

This adapts Alumnium's vanilla screenshot/response SUCCESS vs NOT SUCCESS
evaluator to this repo's compact `results.json` format. It intentionally does
not use reference answers or a partial-credit judge policy.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import re
import sys
import time
from datetime import datetime
from typing import Any

from openai import OpenAI


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "results/runs/fable-5/results.json"

SYSTEM_PROMPT = """As an evaluator, you will be presented with three primary components to assist you in your role:

1. Web Task Instruction: This is a clear and specific directive provided in natural language, detailing the online activity to be carried out. These requirements may include conducting searches, verifying information, comparing prices, checking availability, or any other action relevant to the specified web service (such as Amazon, Apple, ArXiv, BBC News, Booking etc).

2. Result Screenshots: This is a visual representation of the screen showing the result or intermediate state of performing a web task. It serves as visual proof of the actions taken in response to the instruction.

3. Result Response: This is a textual response obtained after the execution of the web task. It serves as textual result in response to the instruction.

-- You DO NOT NEED to interact with web pages or perform actions such as booking flights or conducting searches on websites.
-- You SHOULD NOT make assumptions based on information not presented in the screenshot when comparing it to the instructions.
-- Your primary responsibility is to conduct a thorough assessment of the web task instruction against the outcome depicted in the screenshot and in the response, evaluating whether the actions taken align with the given instructions.
-- NOTE that the instruction may involve more than one task, for example, locating the garage and summarizing the review. Failing to complete either task, such as not providing a summary, should be considered unsuccessful.
-- NOTE that the screenshot is authentic, but the response provided by LLM is generated at the end of web browsing, and there may be discrepancies between the text and the screenshots.
-- Note the difference: 1) Result response may contradict the screenshot, then the content of the screenshot prevails, 2) The content in the Result response is not mentioned on the screenshot, choose to believe the content.

Current year is 2026. You should evaluate the task based on the current web environment and not rely on any prior knowledge or assumptions about the web pages.

You should elaborate on how you arrived at your final evaluation and then provide a definitive verdict on whether the task has been successfully accomplished, either as 'SUCCESS' or 'NOT SUCCESS'."""

USER_PROMPT = """TASK: <task>
Result Response: <answer>
<num> screenshots at the end: """


def safe_name(task_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", task_id)


def load_results(path: pathlib.Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f"expected list results: {path}")
    return data


def load_task_data(path: pathlib.Path | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    tasks: dict[str, dict[str, Any]] = {}
    with path.open() as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                tasks[row["id"]] = row
    return tasks


def load_id_file(path: pathlib.Path | None) -> set[str]:
    if not path:
        return set()
    ids: set[str] = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            ids.add(line)
    return ids


def resolve_path(path_value: str | None, roots: list[pathlib.Path]) -> pathlib.Path | None:
    if not path_value:
        return None
    p = pathlib.Path(path_value)
    candidates = [p] if p.is_absolute() else [root / p for root in roots]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def resolve_screenshot(path_value: str | None, roots: list[pathlib.Path]) -> pathlib.Path | None:
    resolved = resolve_path(path_value, roots)
    if resolved and resolved.is_file():
        return resolved
    return None


def collect_screenshots(
    row: dict[str, Any],
    raw_screenshot: str | None,
    roots: list[pathlib.Path],
    max_attached: int,
) -> list[pathlib.Path]:
    """Collect final evidence screenshots without changing judge semantics.

    Alumnium's evaluator receives result screenshots from the browsing trace.
    This repo stores a final screenshot plus per-browser-control-call after.png
    captures. Use the latest call screenshots and final screenshot as end-state
    visual evidence, capped by --max-attached-imgs.
    """
    screenshots: list[pathlib.Path] = []
    task_dir = resolve_path(row.get("out_dir"), roots)
    if task_dir and task_dir.is_dir():
        call_dir = task_dir / "browser-control-calls"
        if call_dir.is_dir():
            screenshots.extend(
                sorted(call_dir.glob("*/after.png"), key=lambda p: p.stat().st_mtime)
            )

    final = resolve_screenshot(raw_screenshot, roots)
    if final:
        screenshots.append(final)

    unique: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for screenshot in screenshots:
        key = screenshot.resolve()
        if key in seen or not screenshot.exists():
            continue
        seen.add(key)
        unique.append(screenshot)
    return unique[-max_attached:] if max_attached > 0 else []


def encode_image(path: pathlib.Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def final_answer(row: dict[str, Any]) -> str:
    claude = row.get("claude") or {}
    answer = claude.get("final_answer") or claude.get("result_text") or ""
    return str(answer).strip()


def task_for_row(row: dict[str, Any], task_data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    task = dict(row.get("task") or {})
    override = task_data.get(task.get("id"))
    if override:
        task.update(override)
    return task


def build_messages(task: str, answer: str, screenshots: list[pathlib.Path]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": USER_PROMPT.replace("<task>", task)
            .replace("<answer>", answer)
            .replace("<num>", str(len(screenshots))),
        }
    ]
    for screenshot in screenshots:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encode_image(screenshot)}"},
            }
        )
    content.append({"type": "text", "text": "Your verdict:\n"})
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]


def parse_result(text: str) -> int | None:
    lower = text.lower()
    idx = lower.rfind("verdict")
    verdict_section = text[idx:] if idx >= 0 else text
    upper = verdict_section.upper()
    if "NOT SUCCESS" in upper:
        return 0
    if "SUCCESS" in upper:
        return 1
    return None


def call_openai(
    client: OpenAI,
    model: str,
    messages: list[dict[str, Any]],
    timeout: int,
    max_completion_tokens: int,
) -> Any:
    base_kwargs = {
        "model": model,
        "messages": messages,
        "seed": 42,
        "temperature": 0,
        "timeout": timeout,
    }
    token_params = (
        ["max_completion_tokens", "max_tokens"]
        if model.startswith("gpt-5") or "5.5" in model
        else ["max_tokens", "max_completion_tokens"]
    )
    attempts = []
    for token_param in token_params:
        attempts.append((token_param, base_kwargs))
        attempts.append((token_param, {k: v for k, v in base_kwargs.items() if k != "temperature"}))
    last_exc: Exception | None = None
    for token_param, kwargs in attempts:
        try:
            return client.chat.completions.create(
                **{token_param: max_completion_tokens}, **kwargs
            )
        except Exception as exc:
            last_exc = exc
            text = str(exc)
            if token_param == "max_tokens" and "max_tokens" in text:
                continue
            if token_param == "max_completion_tokens" and "max_completion_tokens" in text:
                continue
            if "temperature" in text and "Unsupported" in text:
                continue
            raise
    raise last_exc or RuntimeError("OpenAI call failed")


def message_text(raw_response: dict[str, Any]) -> str:
    choices = raw_response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text") or item.get("content")
                if isinstance(value, str):
                    parts.append(value)
                elif isinstance(value, dict) and isinstance(value.get("value"), str):
                    parts.append(value["value"])
            elif isinstance(item, str):
                parts.append(item)
        text = "\n".join(parts)
    else:
        text = ""
    if text.strip():
        return text
    for key in ("refusal", "reasoning_content"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def write_summary(out_dir: pathlib.Path, judgments: list[dict[str, Any]], total: int) -> dict[str, Any]:
    judged = [j for j in judgments if j.get("result") is not None]
    success = sum(1 for j in judgments if j.get("result") == 1)
    not_success = sum(1 for j in judgments if j.get("result") == 0)
    unknown = sum(1 for j in judgments if j.get("result") is None)
    missing_screenshot = sum(1 for j in judgments if not j.get("screenshots"))
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": total,
        "judged": len(judged),
        "success": success,
        "not_success": not_success,
        "unknown": unknown,
        "pass_rate": round(success / total, 4) if total else 0.0,
        "missing_screenshot": missing_screenshot,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    lines = [
        "# Alumnium-Style Judge Report",
        "",
        f"- Total: {summary['total']}",
        f"- Judged: {summary['judged']}",
        f"- SUCCESS: {summary['success']}",
        f"- NOT SUCCESS: {summary['not_success']}",
        f"- Unknown verdict: {summary['unknown']}",
        f"- Pass rate: {summary['pass_rate']:.2%}",
        f"- Missing screenshots: {summary['missing_screenshot']}",
        "",
        "## Non-Success",
    ]
    bad = [j for j in judgments if j.get("result") != 1]
    if bad:
        for j in bad:
            verdict = "UNKNOWN" if j.get("result") is None else "NOT SUCCESS"
            lines.append(f"- `{j['id']}` {verdict}: {j.get('reason_short', '')}")
    else:
        lines.append("- none")
    (out_dir / "JUDGE_REPORT.md").write_text("\n".join(lines) + "\n")
    return summary


def normalize_run_model_label(label: str) -> str:
    aliases = {
        "claude-fable-5": "fable-5",
        "fable": "fable-5",
        "claude-opus-4-8": "opus-4.8",
        "opus-4-8": "opus-4.8",
    }
    return aliases.get(label, label)


def infer_run_model(rows: list[dict[str, Any]], fallback: str) -> str:
    for row in rows:
        usage = (row.get("claude") or {}).get("model_usage") or {}
        if isinstance(usage, dict) and usage:
            return normalize_run_model_label(str(next(iter(usage.keys()))))
    return normalize_run_model_label(fallback)


def publish_bundle_summary(bundle_dir: pathlib.Path) -> None:
    models: dict[str, dict[str, Any]] = {}
    for child in sorted(bundle_dir.iterdir() if bundle_dir.exists() else []):
        if not child.is_dir():
            continue
        summary_path = child / "summary.json"
        if not summary_path.exists():
            continue
        try:
            summary = json.loads(summary_path.read_text())
        except json.JSONDecodeError:
            continue
        model = normalize_run_model_label(str(summary.get("model") or child.name))
        models[model] = {
            "path": str(child),
            "judge": summary.get("judge"),
            "total": summary.get("total"),
            "judged": summary.get("judged"),
            "success": summary.get("success"),
            "not_success": summary.get("not_success"),
            "unknown": summary.get("unknown"),
            "pass_rate": summary.get("pass_rate"),
            "missing_screenshot": summary.get("missing_screenshot"),
        }
    if not models:
        return
    bundle = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "layout": "run bundle with one directory per model",
        "models": models,
    }
    (bundle_dir / "summary.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2))


def publish_to_run_dir(
    run_dir: pathlib.Path,
    judge_dir: pathlib.Path,
    selected: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    summary: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    """Publish canonical judge/index files next to a run's results.json."""
    model_label = (
        normalize_run_model_label(args.run_model_label)
        if args.run_model_label
        else infer_run_model(selected, args.model)
    )

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "judgments.json").write_text(
        json.dumps(judgments, ensure_ascii=False, indent=2)
    )
    published_summary = {
        **summary,
        "model": model_label,
        "judge": "OpenAI Alumnium vanilla screenshot/response evaluator",
        "results": str(args.results),
        "judge_dir": str(judge_dir),
    }
    (run_dir / "summary.json").write_text(
        json.dumps(published_summary, ensure_ascii=False, indent=2)
    )
    publish_bundle_summary(run_dir.parent)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=pathlib.Path, default=DEFAULT_RESULTS)
    ap.add_argument("--out-dir", type=pathlib.Path)
    ap.add_argument("--model", default="gpt-5-chat")
    ap.add_argument("--task-data", type=pathlib.Path)
    ap.add_argument("--exclude-task-file", action="append", type=pathlib.Path, default=[])
    ap.add_argument("--exclude-task-id", action="append", default=[])
    ap.add_argument("--include-task-file", type=pathlib.Path)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--max-attached-imgs", type=int, default=1)
    ap.add_argument("--max-completion-tokens", type=int, default=2000)
    ap.add_argument("--browser-control-root", type=pathlib.Path)
    ap.add_argument(
        "--publish-to-run-dir",
        action="store_true",
        help=(
            "Also write canonical judgments.json and summary.json next to "
            "the judged results.json."
        ),
    )
    ap.add_argument("--run-model-label", help="Model label for published summaries.")
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    task_data = load_task_data(args.task_data)
    include_ids = load_id_file(args.include_task_file) if args.include_task_file else set(task_data)
    exclude_ids = set(args.exclude_task_id or [])
    for path in args.exclude_task_file:
        exclude_ids.update(load_id_file(path))

    rows = load_results(args.results)
    selected = []
    for row in rows:
        task_id = (row.get("task") or {}).get("id")
        if not task_id:
            continue
        if include_ids and task_id not in include_ids:
            continue
        if task_id in exclude_ids:
            continue
        selected.append(row)
    if args.limit:
        selected = selected[: args.limit]

    run_dir = args.results.parent
    out_dir = args.out_dir or (
        run_dir / f"llm-judge-openai-{args.model}-alumnium-vanilla-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    )
    tasks_dir = out_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    roots = [pathlib.Path.cwd(), ROOT, run_dir]
    if args.browser_control_root:
        roots.insert(0, args.browser_control_root)

    config = {
        "results": str(args.results),
        "model": args.model,
        "run_model_label": args.run_model_label,
        "task_data": str(args.task_data) if args.task_data else None,
        "include_task_file": str(args.include_task_file) if args.include_task_file else None,
        "exclude_task_file": [str(p) for p in args.exclude_task_file],
        "exclude_task_id": args.exclude_task_id,
        "total_selected": len(selected),
        "max_attached_imgs": args.max_attached_imgs,
        "max_completion_tokens": args.max_completion_tokens,
        "publish_to_run_dir": args.publish_to_run_dir,
        "judge": "alumnium vanilla screenshot/response SUCCESS evaluator",
    }
    (out_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2))

    client = OpenAI()
    judgments: list[dict[str, Any]] = []
    if args.resume:
        for path in sorted(tasks_dir.glob("*.eval.json")):
            judgments.append(json.loads(path.read_text()))
    done = {j["id"] for j in judgments}
    print(f"judge out: {out_dir}")
    print(f"selected: {len(selected)} done: {len(done)} todo: {len(selected) - len(done)}")

    for index, row in enumerate(selected, start=1):
        task = task_for_row(row, task_data)
        task_id = task["id"]
        if task_id in done:
            continue
        answer = final_answer(row)
        screenshot_value = (row.get("browser_artifacts") or {}).get("screenshot")
        screenshots = collect_screenshots(row, screenshot_value, roots, args.max_attached_imgs)
        messages = build_messages(task["ques"], answer, screenshots)

        task_path = tasks_dir / f"{safe_name(task_id)}.eval.json"
        prompt_path = tasks_dir / f"{safe_name(task_id)}.prompt.json"
        raw_path = tasks_dir / f"{safe_name(task_id)}.raw.json"
        prompt_path.write_text(
            json.dumps(
                {
                    "id": task_id,
                    "task": task["ques"],
                    "answer": answer,
                    "screenshots": [str(s) for s in screenshots],
                    "raw_screenshot": screenshot_value,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print(f"[{index}/{len(selected)}] {task_id}", flush=True)
        t0 = time.time()
        try:
            response = call_openai(
                client,
                args.model,
                messages,
                args.timeout,
                args.max_completion_tokens,
            )
        except Exception as exc:
            task_path.with_suffix(".error.txt").write_text(str(exc))
            print(f"ERROR {task_id}: {exc}", file=sys.stderr, flush=True)
            (out_dir / "judgments.json").write_text(json.dumps(judgments, ensure_ascii=False, indent=2))
            summary = write_summary(out_dir, judgments, len(selected))
            if args.publish_to_run_dir:
                publish_to_run_dir(run_dir, out_dir, selected, judgments, summary, args)
            return 2

        raw = response.model_dump(mode="json")
        raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
        text = message_text(raw)
        if not text.strip():
            try:
                response = call_openai(
                    client,
                    args.model,
                    messages,
                    args.timeout,
                    args.max_completion_tokens * 2,
                )
                raw = response.model_dump(mode="json")
                raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2))
                text = message_text(raw)
            except Exception:
                pass
        result = parse_result(text)
        reason_short = " ".join(text.strip().split())[:240]
        judgment = {
            "id": task_id,
            "result": result,
            "pass": result == 1,
            "verdict": "SUCCESS" if result == 1 else "NOT SUCCESS" if result == 0 else "UNKNOWN",
            "task": task["ques"],
            "answer": answer,
            "response": text,
            "reason_short": reason_short,
            "screenshots": [str(s) for s in screenshots],
            "raw_screenshot": screenshot_value,
            "source_result": row.get("out_dir"),
            "usage": raw.get("usage"),
            "elapsed_seconds": round(time.time() - t0, 2),
        }
        task_path.write_text(json.dumps(judgment, ensure_ascii=False, indent=2))
        judgments.append(judgment)
        (out_dir / "judgments.json").write_text(json.dumps(judgments, ensure_ascii=False, indent=2))
        summary = write_summary(out_dir, judgments, len(selected))
        if args.publish_to_run_dir:
            publish_to_run_dir(run_dir, out_dir, selected, judgments, summary, args)
        print(
            f"done {task_id}: {judgment['verdict']} "
            f"success={summary['success']}/{summary['judged']} not_success={summary['not_success']}",
            flush=True,
        )

    summary = write_summary(out_dir, judgments, len(selected))
    if args.publish_to_run_dir:
        publish_to_run_dir(run_dir, out_dir, selected, judgments, summary, args)
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

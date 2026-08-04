#!/usr/bin/env python3
"""
fetch_failures.py — One-shot Cekura result → kept-failure summary.

Replaces the manual two-step `results_retrieve` + `runs_bulk_retrieve` fetch
prescribed in `phases/optimization/collect.md` (Step COLLECT.2). Produces a
single consolidated markdown report covering every kept failure with all five
signals (especially Signal 5: `metadata.ended_reason`) wired up so the
orchestrator can hand off straight to early-end-call-diagnose.

The script wraps the same Cekura REST endpoints that the `Cekura` MCP
tools (`results_retrieve`, `runs_bulk_retrieve`) sit on top of:

    GET /test_framework/v2/results/{result_id}/      (Step A — minimal scan)
    GET /test_framework/v2/runs/bulk/?run_ids=…      (Step B — per-run shape)

By doing both fetches in one process we make it structurally impossible to skip
Step B and lose `metadata.ended_reason`, which is the failure mode that
motivated this helper.

USAGE
    CEKURA_API_KEY=… python3 fetch_failures.py <result_id> [--out FILE] [--json]
    CEKURA_API_KEY=… python3 fetch_failures.py 123456
    CEKURA_API_KEY=… python3 fetch_failures.py 123456 --out /tmp/r123456.md
    CEKURA_API_KEY=… python3 fetch_failures.py 123456 --json > runs.json

EXIT CODES
    0  success — kept-failure summary written
    1  fetch error (network / 4xx / 5xx)
    2  bad input (missing API key, malformed result_id)
    3  zero failures kept (success or all-reviewed-success — caller should
        skip Optimization per orchestrator rules)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_API_BASE = "https://api.cekura.ai"
KEEP_VERDICTS = {"failure", "reviewed_failure"}
DROP_VERDICTS = {"success", "reviewed_success"}


def _http_get(url: str, api_key: str, timeout: int = 60) -> Any:
    req = urllib.request.Request(
        url,
        headers={"X-CEKURA-API-KEY": api_key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:400]
        sys.stderr.write(f"HTTP {e.code} on {url}\n  body: {body}\n")
        raise
    except urllib.error.URLError as e:
        sys.stderr.write(f"Network error on {url}: {e}\n")
        raise


def fetch_result_run_index(api_base: str, api_key: str, result_id: int) -> tuple[list[dict], dict[str, int]]:
    """Step A — minimal scan of /results/{id}/. Returns (run_index, funnel)."""
    url = f"{api_base}/test_framework/v2/results/{result_id}/"
    data = _http_get(url, api_key)
    runs_field = data.get("runs") if isinstance(data, dict) else None
    index: list[dict] = []
    if isinstance(runs_field, dict):
        for key, run in runs_field.items():
            if not isinstance(run, dict):
                continue
            index.append(
                {
                    "id": run.get("id") or int(key),
                    "evaluation_status": run.get("evaluation_status"),
                    "scenario_name": (run.get("scenario") or {}).get("name")
                    if isinstance(run.get("scenario"), dict)
                    else None,
                }
            )
    elif isinstance(runs_field, list):
        for run in runs_field:
            if isinstance(run, dict):
                index.append(
                    {
                        "id": run.get("id"),
                        "evaluation_status": run.get("evaluation_status"),
                        "scenario_name": (run.get("scenario") or {}).get("name")
                        if isinstance(run.get("scenario"), dict)
                        else None,
                    }
                )

    funnel = {
        "total": len(index),
        "failure": sum(1 for r in index if r["evaluation_status"] == "failure"),
        "reviewed_failure": sum(1 for r in index if r["evaluation_status"] == "reviewed_failure"),
        "reviewed_success": sum(1 for r in index if r["evaluation_status"] == "reviewed_success"),
        "success": sum(1 for r in index if r["evaluation_status"] == "success"),
        "other": sum(1 for r in index if r["evaluation_status"] not in KEEP_VERDICTS | DROP_VERDICTS),
    }
    return index, funnel


def fetch_runs_bulk(api_base: str, api_key: str, run_ids: list[int]) -> list[dict]:
    """Step B — per-run shape (with metadata.ended_reason)."""
    if not run_ids:
        return []
    qs = urllib.parse.urlencode({"run_ids": ",".join(str(rid) for rid in run_ids)})
    url = f"{api_base}/test_framework/v2/runs/bulk/?{qs}"
    data = _http_get(url, api_key)
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        if isinstance(data.get("runs"), list):
            return [r for r in data["runs"] if isinstance(r, dict)]
        if isinstance(data.get("results"), list):
            return [r for r in data["results"] if isinstance(r, dict)]
        return [v for v in data.values() if isinstance(v, dict)]
    return []


def _flatten_transcript(run: dict) -> str:
    t = run.get("transcript_object")
    if isinstance(t, list):
        lines = []
        for turn in t:
            if not isinstance(turn, dict):
                continue
            role = turn.get("role") or turn.get("speaker") or "?"
            content = turn.get("content") or turn.get("text") or turn.get("message") or ""
            ts = turn.get("time") or turn.get("timestamp") or ""
            ts_str = f" [{ts}]" if ts else ""
            lines.append(f"  {role}{ts_str}: {content}")
        return "\n".join(lines)
    if isinstance(t, dict) and "__encrypted__" in t:
        return "[ENCRYPTED]"
    fallback = run.get("transcript") or ""
    return fallback if isinstance(fallback, str) else str(fallback)[:2000]


def _expected_outcome_bullets(run: dict) -> tuple[list[str], list[dict]]:
    """Returns (explanation_bullets, outcome_alignments)."""
    eo = run.get("expected_outcome") or {}
    if not isinstance(eo, dict):
        return [], []
    bullets = eo.get("explanation") or []
    if not isinstance(bullets, list):
        bullets = []
    aligns = eo.get("outcome_alignments") or []
    if not isinstance(aligns, list):
        aligns = []
    return bullets, aligns


def render_markdown(
    result_id: int,
    funnel: dict[str, int],
    failures: list[dict],
) -> str:
    out: list[str] = []
    kept = funnel["failure"] + funnel["reviewed_failure"]
    dropped = funnel["reviewed_success"] + funnel["success"]
    out.append(f"# Result {result_id} — kept-failure summary")
    out.append("")
    out.append(
        f"**Funnel** (per-run `evaluation_status`): "
        f"{funnel['total']} runs inspected → "
        f"{funnel['failure']} `failure` kept · "
        f"{funnel['reviewed_failure']} `reviewed_failure` kept · "
        f"{funnel['reviewed_success']} `reviewed_success` dropped (human override) · "
        f"{funnel['success']} `success` dropped"
        + (f" · {funnel['other']} other" if funnel["other"] else "")
    )
    out.append("")
    out.append(f"**Kept failures: {kept}** · **Dropped: {dropped}**")
    out.append("")
    if not failures:
        out.append("_No failures to diagnose._")
        return "\n".join(out)

    out.append("---")
    for r in failures:
        rid = r.get("id")
        scn = r.get("scenario_name") or (
            r.get("scenario", {}).get("name") if isinstance(r.get("scenario"), dict) else None
        )
        ev_status = r.get("evaluation_status")
        meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
        ended_reason = meta.get("ended_reason") if isinstance(meta, dict) else None
        if not ended_reason:
            ended_reason = "unavailable"
        duration = r.get("duration")
        error_message = r.get("error_message")
        scenario_instructions = r.get("scenario_instructions")

        out.append("")
        out.append(f"## Run {rid} — {scn or '(no scenario name)'}")
        out.append("")
        out.append(f"- **evaluation_status**: `{ev_status}`")
        out.append(f"- **metadata.ended_reason**: `{ended_reason}`  _(Signal 5)_")
        if duration:
            out.append(f"- **duration**: {duration}")
        if error_message:
            out.append(f"- **error_message**: `{error_message}`")
        if scenario_instructions:
            out.append(f"- **scenario_instructions**: {scenario_instructions}")

        bullets, aligns = _expected_outcome_bullets(r)
        if bullets:
            out.append("")
            out.append("**Expected-outcome bullets**:")
            for b in bullets:
                out.append(f"  - {b}")
        if aligns:
            fail_aligns = [a for a in aligns if isinstance(a, dict) and a.get("aligned") == "no"]
            if fail_aligns:
                out.append("")
                out.append("**Failed alignments** (`aligned: no`):")
                for a in fail_aligns:
                    out.append(f"  - outcome: {a.get('outcome')!r}")
                    out.append(f"    - prompt_part: {a.get('prompt_part')!r}")

        out.append("")
        out.append("**Transcript**:")
        out.append("```")
        out.append(_flatten_transcript(r))
        out.append("```")
        out.append("")
        out.append("---")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a Cekura result and emit a kept-failure summary.")
    parser.add_argument("result_id", type=int, help="Cekura result_id (integer)")
    parser.add_argument(
        "--api-base",
        default=os.environ.get("CEKURA_API_BASE", DEFAULT_API_BASE),
        help=f"API base URL (default: {DEFAULT_API_BASE}, or $CEKURA_API_BASE)",
    )
    parser.add_argument("--out", help="Write report to file instead of stdout")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON bundle instead of markdown")
    args = parser.parse_args()

    api_key = os.environ.get("CEKURA_API_KEY")
    if not api_key:
        sys.stderr.write("error: CEKURA_API_KEY env var is required\n")
        return 2

    try:
        index, funnel = fetch_result_run_index(args.api_base, api_key, args.result_id)
    except Exception:
        return 1

    kept_ids = [r["id"] for r in index if r["evaluation_status"] in KEEP_VERDICTS and r["id"] is not None]

    if not kept_ids:
        # Funnel-only summary; orchestrator should skip the rest of Optimization.
        report = render_markdown(args.result_id, funnel, [])
        _write(args, report, {"result_id": args.result_id, "funnel": funnel, "failures": []})
        sys.stderr.write("note: zero kept failures — orchestrator should stop the loop.\n")
        return 3

    try:
        bulk_runs = fetch_runs_bulk(args.api_base, api_key, kept_ids)
    except Exception:
        return 1

    # Stable order: bulk ascending by id
    bulk_runs.sort(key=lambda r: r.get("id") or 0)
    # Backfill scenario_name from index where bulk run lacks one
    index_by_id = {r["id"]: r for r in index}
    for r in bulk_runs:
        if not r.get("scenario_name") and r.get("id") in index_by_id:
            r["scenario_name"] = index_by_id[r["id"]]["scenario_name"]

    report = render_markdown(args.result_id, funnel, bulk_runs)
    bundle = {
        "result_id": args.result_id,
        "funnel": funnel,
        "failures": bulk_runs,
    }
    _write(args, report, bundle)
    return 0


def _write(args, report: str, bundle: dict) -> None:
    payload = json.dumps(bundle, default=str, indent=2) if args.json else report
    if args.out:
        with open(args.out, "w") as f:
            f.write(payload)
        sys.stderr.write(f"wrote {args.out}\n")
    else:
        sys.stdout.write(payload)
        if not payload.endswith("\n"):
            sys.stdout.write("\n")


if __name__ == "__main__":
    sys.exit(main())

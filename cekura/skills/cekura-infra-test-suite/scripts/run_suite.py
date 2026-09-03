#!/usr/bin/env python3
"""Run a Cekura Tests-as-Code suite and gate CI on the result.

Posts the committed spec to Cekura, polls every run to completion, writes a
markdown report, and exits non-zero if anything failed. Python 3 standard
library only — no pip install on the runner.

    # free: validate and price the file, create nothing
    CEKURA_API_KEY=... python3 cekura/run_suite.py --dry-run --agent-id 42

    # real run, gates the build
    CEKURA_API_KEY=... python3 cekura/run_suite.py --agent-id 42

Environment:
    CEKURA_API_KEY            required
    CEKURA_API_URL            default https://api.cekura.ai
    CEKURA_AGENT_ID           the agent to test, if --agent-id is not passed
    CEKURA_CHANNEL            voice (default), text, elevenlabs, livekit_v2, pipecat_v2
    CEKURA_PIPECAT_AGENT_NAME pipecat_v2 only — point the run at this deployment
    CEKURA_LIVEKIT_AGENT_NAME livekit_v2 only
    CEKURA_LIVEKIT_URL        livekit_v2 only

Exit codes: 0 everything passed, 1 a case failed or errored, 2 bad configuration.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

RUN_PATH = "/test_framework/v1/scenarios/run_scenarios_json/"
BULK_PATH = "/test_framework/v2/runs/bulk/"
TERMINAL_BAD = {"failed", "error", "cancelled", "timeout"}


def api(method, path, key, base, payload=None, params=None):
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"X-CEKURA-API-KEY": key}
    if body:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            pass
        raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {detail[:2000]}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {path} -> {exc.reason}") from None


def load_spec(path):
    try:
        with open(path) as handle:
            spec = json.load(handle)
    except OSError as exc:
        sys.exit(f"cannot read {path}: {exc}")
    except json.JSONDecodeError as exc:
        sys.exit(f"{path} is not valid JSON: {exc}")
    cases = spec.get("scenarios")
    if not isinstance(cases, list) or not cases:
        sys.exit(f"{path} has no test cases")
    return spec, cases


def build_payload(spec, args):
    payload = {"spec": spec, "agent_id": int(args.agent_id), "channel": args.channel}
    if args.name:
        payload["name"] = args.name
    if args.channel == "pipecat_v2":
        agent_name = os.environ.get("CEKURA_PIPECAT_AGENT_NAME")
        if agent_name:
            payload["pipecat_data"] = {"pipecat_agent_name": agent_name}
    elif args.channel == "livekit_v2":
        livekit = {}
        if os.environ.get("CEKURA_LIVEKIT_AGENT_NAME"):
            livekit["agent_name"] = os.environ["CEKURA_LIVEKIT_AGENT_NAME"]
        if os.environ.get("CEKURA_LIVEKIT_URL"):
            livekit["url"] = os.environ["CEKURA_LIVEKIT_URL"]
        if livekit:
            payload["livekit_data"] = livekit
    return payload


def dry_run(payload, key, base):
    """Validate and price without creating or charging anything."""
    try:
        response = api("POST", RUN_PATH, key, base, payload, {"dry_run": "true"})
    except RuntimeError as exc:
        print(str(exc))
        print("\nThe spec was rejected. Every problem is reported at once, keyed by its "
              "location in the file — fix them all, then re-run.")
        return 1

    plan = response.get("plan") or {}
    print(f"valid:  {response.get('valid')}")
    print(f"suite:  {plan.get('suite_name')}")
    print(f"agent:  {plan.get('agent_id')}  project: {plan.get('project_id')}  "
          f"channel: {plan.get('channel')}")
    print(f"cases:  {plan.get('scenario_count')}   runs: {plan.get('total_runs')}   "
          f"estimated cost: {plan.get('estimated_cost')}")
    print()
    for case in plan.get("scenarios") or []:
        profile = case.get("test_profile") or {}
        personality = case.get("personality") or {}
        print(f"  {case.get('name')}  [{case.get('type')}]")
        print(f"      metrics: {case.get('metric_ids')}   "
              f"personality: {personality.get('mode')}   "
              f"test_profile: {profile.get('mode') or 'none'}")
    print("\nCheck two things before spending anything: every case lists the metrics you "
          "intended, and any case with inline test data reports test_profile mode 'inline'.")
    return 0 if response.get("valid") else 1


def poll(run_ids, result_id, key, base, timeout, interval):
    deadline = time.time() + timeout
    runs = {}
    while time.time() < deadline:
        try:
            fetched = api("GET", BULK_PATH, key, base, params={
                "run_ids": ",".join(str(r) for r in run_ids),
                "result_id": result_id,
            })
        except RuntimeError as exc:
            print(f"  poll error: {exc}")
            time.sleep(interval)
            continue

        for run in fetched if isinstance(fetched, list) else fetched.get("results", []):
            runs[run.get("id")] = run

        pending = [r for r in runs.values() if not settled(r)]
        if len(runs) >= len(run_ids) and not pending:
            return runs
        print(f"  {len(runs) - len(pending)}/{len(run_ids)} settled; waiting {interval}s")
        time.sleep(interval)

    print(f"  timed out after {timeout}s with {len(run_ids) - len(runs)} run(s) never fetched")
    return runs


def settled(run):
    status = run.get("status")
    if status in TERMINAL_BAD:
        return True
    return status == "completed" and run.get("success") is not None


def verdict(run):
    if run is None:
        return "ERROR", "no result — the run was never created or never fetched"
    status = run.get("status", "unknown")
    if status in TERMINAL_BAD:
        return "ERROR", run.get("error_message") or f"run ended with status {status}"
    if status != "completed":
        return "TIMEOUT", f"still {status} when polling gave up"
    if run.get("success") is True:
        return "PASS", "all metrics passed"
    if run.get("success") is False:
        return "FAIL", lowest_scores(run) or "see the run in Cekura for the transcript"
    return "INCOMPLETE", "evaluation had not finished"


def lowest_scores(run, limit=3):
    """The weakest metrics, reported as measured. `success` is the verdict; this is
    context for it, so no pass threshold is assumed here."""
    metrics = (run.get("evaluation") or {}).get("metrics") or []
    scored = [(m.get("score"), m.get("name", "?")) for m in metrics
              if isinstance(m.get("score"), (int, float))]
    parts = [f"{name} {score}" for score, name in sorted(scored)[:limit]]
    parts += [f"{m.get('name', '?')} {m.get('value')}" for m in metrics
              if m.get("value") not in (None, "")][:limit]
    return "lowest: " + ", ".join(parts) if parts else ""


def write_report(path, rows, result_id, base):
    lines = ["# Cekura suite results", ""]
    if result_id:
        lines += [f"Result `{result_id}` — full transcripts and scores are in Cekura.", ""]
    lines += ["| Case | Run | Status | Detail |", "|---|---|---|---|"]
    icons = {"PASS": "✅", "FAIL": "❌"}
    for row in rows:
        icon = icons.get(row["status"], "⚠️")
        lines.append(f"| {row['name']} | {row['run_id'] or '—'} | {icon} {row['status']} "
                     f"| {row['detail']} |")
    passed = sum(1 for r in rows if r["status"] == "PASS")
    lines += ["", f"**{passed}/{len(rows)} passed**"]
    with open(path, "w") as handle:
        handle.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--spec", default="cekura.tests.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate and price the spec; create nothing, charge nothing")
    parser.add_argument("--agent-id", default=os.environ.get("CEKURA_AGENT_ID"))
    parser.add_argument("--channel", default=os.environ.get("CEKURA_CHANNEL", "voice"))
    parser.add_argument("--name", default=None, help="label for this run in Cekura")
    parser.add_argument("--timeout", type=int, default=900, help="seconds to wait for all runs")
    parser.add_argument("--poll-interval", type=int, default=15)
    parser.add_argument("--report", default="cekura-report.md")
    parser.add_argument("--json-out", default=None, help="also write raw results here")
    args = parser.parse_args()

    key = os.environ.get("CEKURA_API_KEY")
    if not key:
        print("CEKURA_API_KEY is not set", file=sys.stderr)
        sys.exit(2)
    if not args.agent_id:
        print("no agent id: pass --agent-id or set CEKURA_AGENT_ID", file=sys.stderr)
        sys.exit(2)
    base = (os.environ.get("CEKURA_API_URL") or "https://api.cekura.ai").rstrip("/")

    spec, cases = load_spec(args.spec)
    payload = build_payload(spec, args)
    print(f"suite {args.spec}: {len(cases)} case(s) → agent {args.agent_id} "
          f"on {args.channel} via {base}")

    if args.dry_run:
        sys.exit(dry_run(payload, key, base))

    try:
        response = api("POST", RUN_PATH, key, base, payload)
    except RuntimeError as exc:
        print(str(exc))
        sys.exit(1)

    result_id = response.get("id")
    runs = response.get("runs") or []
    names = {}
    for index, run in enumerate(runs):
        names[run.get("id")] = run.get("scenario_name") or (
            cases[index].get("name") if index < len(cases) else "unknown")
    print(f"result {result_id}: {len(runs)} run(s) started")

    run_ids = [r.get("id") for r in runs if r.get("id") is not None]
    polled = poll(run_ids, result_id, key, base, args.timeout, args.poll_interval) \
        if run_ids else {}

    rows = []
    for run_id in run_ids:
        status, detail = verdict(polled.get(run_id))
        rows.append({"name": names.get(run_id, "unknown"), "run_id": run_id,
                     "status": status, "detail": detail})
        print(f"  {rows[-1]['name']}: {status} — {detail}")
    for case in cases:
        if case.get("name") not in {r["name"] for r in rows}:
            rows.append({"name": case.get("name"), "run_id": None, "status": "ERROR",
                         "detail": "no run was created for this case"})
            print(f"  {case.get('name')}: ERROR — no run was created for this case")

    write_report(args.report, rows, result_id, base)
    if args.json_out:
        with open(args.json_out, "w") as handle:
            json.dump({"result_id": result_id, "results": rows}, handle, indent=2)

    failed = [r for r in rows if r["status"] != "PASS"]
    print(f"\n{len(rows) - len(failed)}/{len(rows)} passed  (report: {args.report})")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

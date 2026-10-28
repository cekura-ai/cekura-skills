"""python3 -m experiments.scenario_skills --help"""
import argparse
import json
from pathlib import Path

from .common import ROOT, private_dir, read, write
from .dataset import load
from .experiment import report, repeat, run
from .preflight import preflight


def main():
    parser = argparse.ArgumentParser(description="Cekura authoring smoke; never accesses production tools")
    parser.add_argument("command", choices=("preflight", "run", "repeat", "report", "validate-fixtures", "validate-catalog", "fixture-review", "capture-catalog", "capture-codex-catalog", "image-prepare", "image-probe", "modal-image-probe", "modal-gateway-probe", "codex-gateway-probe", "claude-prepare"))
    parser.add_argument("--config", type=Path, default=ROOT / "config.example.json")
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--task")
    parser.add_argument("--candidate", choices=("baseline", "candidate-1", "candidate-2"))
    parser.add_argument("--reason")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--source-ref")
    parser.add_argument("--image")
    parser.add_argument("--guard-image")
    parser.add_argument("--pi-settings", type=Path)
    parser.add_argument("--image-metadata", type=Path)
    parser.add_argument("--cost-evidence", type=Path)
    parser.add_argument("--budget-ledger", type=Path)
    parser.add_argument("--probe-skill", type=Path)
    parser.add_argument("--credential-env", default="CEKURA_BENCHMARK_MCP_TOKEN")
    parser.add_argument("--credential-type", choices=("oauth", "api-key"), default="oauth")
    parser.add_argument("--ssh-host", default="cekura-claude-workspace")
    parser.add_argument("--server-name", default="cekura")
    parser.add_argument("--status-json", type=Path)
    parser.add_argument("--catalog", type=Path)
    args = parser.parse_args()
    if args.command == "capture-codex-catalog":
        if not args.artifacts:
            parser.error("capture-codex-catalog requires private --artifacts")
        from .codex_catalog import capture
        print(capture(args.artifacts, args.server_name, args.status_json))
        return 0
    elif args.command == "validate-catalog":
        if not args.artifacts or not args.catalog:
            parser.error("validate-catalog requires original --catalog and private --artifacts")
        from .contract_probe import probe
        result = probe(read(args.catalog), args.artifacts)
        print(json.dumps({"passed": result["passed"], "tasks_checked": len(result["tasks"]),
                          "failed_tasks": [r for r in result["tasks"] if not r["grade"]["score"]],
                          "catalog_sha256": result["catalog_sha256"], "model_turns": 0, "production_tool_calls": 0}, indent=2))
        return int(not result["passed"])
    elif args.command == "claude-prepare":
        if not args.artifacts:
            parser.error("claude-prepare requires private --artifacts")
        from .remote_claude import remote_call
        result = remote_call(args.ssh_host, {"operation": "prepare"})
        write(private_dir(args.artifacts) / "claude-preparation.json", result)
        print(json.dumps(result, indent=2))
        return int(result["auth"].get("loggedIn") is not True)
    elif args.command == "capture-catalog":
        if not args.artifacts:
            parser.error("capture-catalog requires private --artifacts")
        from .catalog_capture import capture
        print(capture(args.artifacts, args.credential_env, credential_type=args.credential_type))
        return 0
    elif args.command == "codex-gateway-probe":
        if not args.artifacts:
            parser.error("codex-gateway-probe requires private --artifacts")
        from .gateway_probe import codex_probe
        result = codex_probe(read(args.config), args.artifacts)
        print(json.dumps(result, indent=2))
        return int(not result["passed"])
    elif args.command == "modal-gateway-probe":
        if not args.artifacts or not args.budget_ledger:
            parser.error("modal-gateway-probe requires private --artifacts and --budget-ledger")
        from .gateway_probe import modal_probe
        result = modal_probe(read(args.config), args.artifacts, args.budget_ledger)
        print(__import__("json").dumps(result, indent=2))
        return int(not result["passed"])
    elif args.command == "fixture-review":
        if not args.artifacts:
            parser.error("fixture-review requires a private --artifacts directory")
        from .fixture_review import packet
        print(packet(private_dir(args.artifacts)))
        return 0
    elif args.command == "modal-image-probe":
        if not all((args.image, args.source, args.artifacts, args.image_metadata, args.cost_evidence, args.budget_ledger)):
            parser.error("modal-image-probe requires --image, --source, --artifacts, --image-metadata, --cost-evidence and --budget-ledger")
        from .modal_probe import run_modal_probe
        flags = read(args.config)["target"]["snapshot"]["runtime_env"]
        directory = private_dir(args.artifacts)
        if (directory / "infrastructure-allocation.json").exists():
            parser.error("An infrastructure allocation already exists; reconcile it before retrying")
        result = run_modal_probe(args.image, args.source, read(args.image_metadata), flags, read(args.cost_evidence), directory,
                                 args.budget_ledger, read(args.catalog) if args.catalog else None)
        print(json.dumps({k: result.get(k) for k in ("passed", "image_id", "production_image_verified", "inference_requests", "terminated", "error")}, indent=2))
        return int(not result["passed"])
    elif args.command == "image-probe":
        if not all((args.image, args.source, args.artifacts)):
            parser.error("image-probe requires --image, --source (prepared context), and --artifacts")
        from .image_probe import run_probe
        flags = read(args.config).get("target", {}).get("snapshot", {}).get("runtime_env")
        result = run_probe(args.image, args.source, private_dir(args.artifacts), args.guard_image, flags, args.probe_skill)
        print(json.dumps({k: result[k] for k in ("passed", "image", "production_match_verified", "inference_requests")}, indent=2))
        return int(not result["passed"])
    elif args.command == "image-prepare":
        if not all((args.source, args.source_ref, args.artifacts)):
            parser.error("image-prepare requires --source, --source-ref and --artifacts")
        from .runtime_image import prepare_image
        result = prepare_image(args.source, private_dir(args.artifacts), args.source_ref, args.pi_settings)
        print(json.dumps({"status": "source_replica_prepared", "production_match_verified": False,
                          "python_packages": result["python_packages"], "build_arguments": result["build_arguments"]}, indent=2))
    elif args.command == "validate-fixtures":
        tasks = load()
        print("24 synthetic tasks / 12 packs; training 12, validation 6, sealed 6; frozen expectations verified")
    elif args.command == "preflight":
        result = preflight(read(args.config))
        if args.artifacts:
            write(private_dir(args.artifacts) / "preflight.json", result)
        print(json.dumps({k: v for k, v in result.items() if k != "configuration"}, indent=2))
        return int(not result["ready"])
    else:
        if args.artifacts is None:
            parser.error("--artifacts must be a private directory outside this checkout")
        if args.command == "run":
            state = run(read(args.config), args.artifacts)
            print(json.dumps({k:state[k] for k in ("status", "selected", "failures", "reason") if k in state}, indent=2))
            return int(state["status"] in ("preflight_failed", "stopped", "sealed_regression"))
        if args.command == "repeat":
            if not all((args.task, args.candidate, args.reason)):
                parser.error("repeat requires --task, --candidate, --reason")
            result = repeat(read(args.config), args.artifacts, args.task, args.candidate, args.reason)
            print(json.dumps({"status": result["status"], "failed_checks": result["grade"]["failed_checks"]}))
            return int(result["status"] != "complete")
        from .budget import Ledger
        directory = private_dir(args.artifacts)
        state = read(directory / "experiment.json")
        report(directory, state, Ledger(Path(state.get("budget_ledger_path") or directory / "budget.json"), state.get("budget_policy")))
        print(str(directory / "comparison.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""python -m experiments.scenario_skills.v2 --help

Preparation (no inference): authorize-budget → prepare-claude → prepare-generator → prepare →
contract-probe → transport-probe → smoke → preflight. After the fixture/gold signoff and launch
approval, ``run`` goes to the terminal report in one command. ``accept`` exports a patch only
after a named reviewer signs the blinded final packet.
"""
import argparse
import copy
import os
import subprocess
from pathlib import Path

from .. import budget
from ..common import ROOT, digest, private_dir, read, write

OLD_EVIDENCE = "/private/tmp/cekura-runtime-image-2026-10-22"
OLD_RUN = "/private/tmp/cekura-scenario-optimization-v2-final"


def translate(value, evidence, artifacts):
    """Old artifacts carry source-machine paths as provenance; point them at the transferred copies."""
    if isinstance(value, dict):
        return {k: translate(v, evidence, artifacts) for k, v in value.items()}
    if isinstance(value, list):
        return [translate(v, evidence, artifacts) for v in value]
    if isinstance(value, str):
        return value.replace(OLD_EVIDENCE, str(evidence)).replace(OLD_RUN, str(artifacts))
    return value


def load_env(path, names):
    """Read only the named credentials, without shell expansion or printing values."""
    for line in Path(path).read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            name, value = line.split("=", 1)
            if name.strip() in names:
                os.environ[name.strip()] = value.strip().strip('"').strip("'")


def main():
    parser = argparse.ArgumentParser(description="72-task authoring optimization against the isolated real backend")
    parser.add_argument("command", choices=("validate", "authorize-budget", "extend-budget", "prepare-claude", "prepare-generator", "prepare", "prepare-v3", "reinstrument",
                                            "contract-probe", "transport-probe", "smoke", "preflight", "run", "report", "accept"))
    parser.add_argument("--artifacts", type=Path, default=Path.home() / "cekura-scenario-v2-run")
    parser.add_argument("--base-config", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--pricing", type=Path, help="Verified generator rates/token limits and sandbox rates, with sources")
    parser.add_argument("--historical", type=Path, nargs="*", help="Historical ledgers to reconcile once")
    parser.add_argument("--historical-usd", default="29.13728485")
    parser.add_argument("--authorization", help="extend-budget: the user's stated authorization for the raise")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--backend-source", type=Path, help="Extracted pinned backend 650297f source tree")
    parser.add_argument("--benchmark", type=int, choices=(2, 3), default=2, help="Task set to prepare or validate (v3: product-chat-derived)")
    parser.add_argument("--from", dest="source", type=Path, help="prepare-v3: an already prepared v2 artifacts directory to reuse")
    args = parser.parse_args()
    if args.command == "validate" and args.benchmark == 3:
        from ..v3.dataset import load as load_v3
        tasks = load_v3()
        print("%d v3 tasks; 18 templates x 4 domains split by domain (36/18/18); 36 draft gold examples. Human approval is separate." % len(tasks))
        return 0
    if args.command == "validate":
        from .dataset import load
        load()
        print("72 tasks / 48 packs; training 36, validation 12, sealed 24; 48 draft gold examples. Human approval is separate.")
        return 0
    directory = private_dir(args.artifacts)
    config_path = directory / "config.json"
    if args.env_file:
        load_env(args.env_file, {"MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "FIREWORKS_API_KEY", "GEMINI_API_KEY"})
    if args.command == "extend-budget":
        extension = budget.extend(args.authorization)
        if config_path.exists():
            # The target's admission evidence states the remaining allowance; keep it equal to the new limit.
            cfg = read(config_path)
            cfg["target"]["admission"]["hard_cap"]["remaining_usd"] = float(budget.EXTENDED_LIMITS["target"])
            write(config_path, cfg)
        print({"limits": extension["limits"], "charged_at_extension_usd": extension["charged_at_extension_usd"]})
        return 0
    if args.command == "authorize-budget":
        if not args.historical:
            parser.error("authorize-budget needs --historical ledgers")
        policy = budget.authorize(args.historical, args.historical_usd,
                                  "User authorized one cumulative $150 scenario-skill experiment, superseding all earlier per-run allowances.")
        spent = budget.Ledger(budget.wallet_path(), policy).total()
        print({"wallet": str(budget.wallet_path()), "historical_usd": policy["historical"]["total_usd"], "remaining_usd": str(150 - spent)})
        return 0
    if args.command == "prepare-claude":
        from ..remote_claude import prepare as prepare_image
        result = prepare_image()  # Builds the CLI-only image and checks auth/subscription; no inference.
        write(directory / "claude-preparation.json", dict(result, isolation=result["isolation"]))
        print({k: result[k] for k in ("image", "cli_version")}, "extra usage enabled:", result["subscription"]["extra_usage_enabled"])
        return 0
    if args.command == "prepare-generator":
        from .backend_stack import Infrastructure, image_id
        from .generator.instrument import build_image, instrument
        from .generator.pinned import build_sandbox_image, MODAL_SECRET
        if not args.backend_source:
            parser.error("prepare-generator needs --backend-source")
        record = instrument(args.backend_source, directory / "generator-instrumented")
        record = build_image(directory / "generator-instrumented", "cekura-backend-instrumented:650297f")
        infra = Infrastructure(directory / "backend").ensure()
        # Building the pinned sandbox recipe in Modal is billed compute: reserve its bound first.
        ledger = budget.Ledger(budget.wallet_path(), read(budget.wallet_path())["authorization"])
        key = "preparation/generator-sandbox-image-build"
        if key not in ledger.state["entries"]:
            ledger.reserve(key, "target", "0.50", infrastructure_only=True, scope="preparation")
        try:
            sandbox_image = build_sandbox_image()
        finally:
            ledger.transition(key, "bounded_infrastructure_pending_billing")
        subprocess.run([str(Path(os.sys.executable).with_name("modal")), "secret", "create", "--force", MODAL_SECRET,
                        "CEKURA_EXPERIMENT_SECRET=holds-no-credentials"], check=True, capture_output=True)
        write(directory / "generator-preparation.json", {"deviation_sha256": record["record_sha256"], "backend_image": record["image_id"],
              "pinned_image": record["base_image_id"], "sandbox_image": sandbox_image, "openapi_sha256": infra.state["openapi_sha256"],
              "images": {"postgres": image_id("postgres:15-alpine"), "redis": image_id("redis:7-alpine"), "object_store": image_id("cekura-object-store:moto-5.1.4")}})
        print({"backend_image": record["image_id"], "sandbox_image": sandbox_image})
        return 0
    if args.command == "prepare":
        if not args.base_config or not args.evidence_root or not args.pricing:
            parser.error("prepare needs --base-config, --evidence-root and --pricing")
        from .generator.pinned import generator_config
        from .review import prepare as prepare_review
        cfg = translate(copy.deepcopy(read(args.base_config)), args.evidence_root, directory)
        wallet = read(budget.wallet_path())
        claude, generator = read(directory / "claude-preparation.json"), read(directory / "generator-preparation.json")
        cfg.update(experiment_version=2, benchmark_version=args.benchmark, execution_goal="acceptance", fixture_review_mode="human",
                   budget_ledger_path=str(budget.CANONICAL_WALLET), budget_policy=wallet["authorization"])
        for role in ("proposer", "judge"):
            section = cfg[role]
            section.pop("ssh_host", None)
            section.update(transport="local", image=claude["image"], cli_version=claude["cli_version"], cli_sha256=claude["cli_sha256"],
                           subscription=claude["subscription"], preparation_path=str(directory / "claude-preparation.json"))
        cfg["judge"]["read_training_files"] = False
        target = cfg["target"]
        target["gateway_probe_path"] = str(directory / "transport-probe/gateway-probe.json")
        target["v2_contract_probe_path"] = str(directory / "v2-contract-probe.json")
        target["admission"]["hard_cap"].update(code_sha256=digest(ROOT / "gateway.py"), remaining_usd=float(budget.CUMULATIVE_LIMITS["target"]),
            evidence="Every request is admitted before forwarding against the canonical cumulative wallet (%s)." % budget.CANONICAL_WALLET)
        if os.environ.get(target["credential_env"]):
            target["admission"]["hard_cap"]["credential_sha256"] = digest(os.environ[target["credential_env"]].encode())
        cfg["backend"] = {"generator": generator_config(read(args.pricing), generator["sandbox_image"]),
                          "deviation_path": str(directory / "generator-instrumented/deviation.json"), "deviation_sha256": generator["deviation_sha256"],
                          "images": dict(generator["images"], backend=generator["backend_image"], pinned=generator["pinned_image"]),
                          "openapi_sha256": generator["openapi_sha256"], "infrastructure_state": str(directory / "backend/backend-infrastructure.json")}
        cfg.pop("review_authorization", None)
        if args.benchmark == 3:
            cfg["max_repeats"] = 72  # Every held-out task, both arms, a second time.
        if config_path.exists() and read(config_path) != cfg:
            raise ValueError("A different experiment is already prepared here; use a new artifacts directory")
        write(config_path, cfg)
        prepare_review(directory, args.benchmark)
        print("Prepared %s; review human-review.md, then sign fixture-and-gold-signoff.json. No inference started." % directory)
        return 0
    if args.command == "prepare-v3":
        # Reuses the v2 preparation (images, infrastructure, probes, credentials) read-only; only the task set changes.
        from .review import prepare as prepare_review
        if not args.source or not (args.source / "config.json").is_file():
            parser.error("prepare-v3 needs --from <prepared v2 artifacts directory>")
        cfg = read(args.source / "config.json")
        if cfg.get("benchmark_version", 2) != 2:
            parser.error("--from must name a prepared v2 directory")
        cfg.update(benchmark_version=3, max_repeats=72)
        from ..remote_claude import subscription_status
        status = subscription_status()  # Re-verified now: extra usage must still be off; no inference.
        if status["extra_usage_enabled"] is not False:
            parser.error("Claude extra usage is enabled; v3 requires subscription-only sessions")
        for role in ("proposer", "judge"):
            cfg[role]["subscription"] = status
        cfg["target"]["v3_replay_proof_path"] = str(directory / "v3-replay-proof.json")
        # The transport probe binds the runtime code; v3 re-proves it here and leaves the v2 evidence untouched.
        cfg["target"]["gateway_probe_path"] = str(directory / "transport-probe/gateway-probe.json")
        if config_path.exists() and read(config_path) != cfg:
            raise ValueError("A different experiment is already prepared here; use a new artifacts directory")
        write(config_path, cfg)
        prepare_review(directory, 3)
        print("Prepared v3 in %s from %s; next: contract-probe --benchmark 3, preflight, signoff. No inference started." % (directory, args.source))
        return 0
    if args.command == "reinstrument":
        # Rebuild the instrumented worker image after a metering-transport fix, recorded in this run's directory.
        # The generator sandbox image and the v2 evidence are untouched; preflight re-verifies the new record.
        from .generator.instrument import build_image, instrument
        if not args.backend_source:
            parser.error("reinstrument needs --backend-source")
        cfg = read(config_path)
        output = directory / "generator-instrumented"
        instrument(args.backend_source, output)
        record = build_image(output, "cekura-backend-instrumented:650297f")
        cfg["backend"].update(deviation_path=str(output / "deviation.json"), deviation_sha256=record["record_sha256"])
        cfg["backend"]["images"]["backend"] = record["image_id"]
        write(config_path, cfg)
        print({"backend_image": record["image_id"], "deviation_sha256": record["record_sha256"]})
        return 0
    cfg = read(config_path)
    ledger = budget.Ledger(Path(cfg["budget_ledger_path"]), cfg["budget_policy"])
    if args.command == "contract-probe" and cfg.get("benchmark_version") == 3:
        from ..v3.replay import prove
        result = prove(cfg, cfg["target"]["v3_replay_proof_path"])
        print({"passed": result["passed"], "tasks": len(result["replayed"]), "model_requests": 0})
        return int(not result["passed"])
    if args.command == "contract-probe":
        from .contract_probe import probe
        result = probe(read(cfg["target"]["catalog_path"]), directory / "v2-contract-probe.json")
        print({"passed": result["passed"], "tasks": len(result["rows"]), "model_requests": 0})
        return int(not result["passed"])
    if args.command == "transport-probe":
        from .probe import probe
        import time
        # Each probe run gets its own directory and wallet scope; earlier runs stay as evidence.
        result = probe(cfg, directory / ("v2-transport-probe-%d" % time.time()), ledger)
        if result["passed"]:
            write(directory / "transport-probe/gateway-probe.json", result)
        print({"passed": result["passed"], "inference_requests": 0, "terminated": result["terminated"]})
        return int(not result["passed"])
    if args.command == "smoke":
        from .smoke import smoke
        result = smoke(cfg, directory, ledger)
        print({k: v for k, v in result.items() if k != "code"})
        return int(not result["passed"])
    if args.command == "preflight":
        from ..preflight import preflight
        from .review import gate
        result = preflight(cfg)
        write(directory / "preflight.json", {k: v for k, v in result.items() if k != "configuration"})
        print({"ready": result["ready"], "failures": result["failures"], "fixture_signoff": gate(directory)})
        return int(not result["ready"])
    if args.command == "run":
        from .experiment import run
        state = run(cfg, directory)
        print({"status": state["status"], "finalist": state.get("finalist"), "reason": state.get("reason")})
        return int(state["status"] in ("preflight_failed", "stopped", "inconclusive_execution"))
    if args.command == "report":
        from .experiment import report
        report(directory, read(directory / "experiment.json"), ledger, cfg)
        print(directory / "comparison.md")
        return 0
    # accept: the named reviewer's blinded final signoff is the only route to an exported patch.
    from ..experiment import export_patch
    from ..selection import human_gate
    state = read(directory / "experiment.json")
    if state.get("status") != "recommendation_pending_final_review" or not human_gate(directory, "final"):
        raise SystemExit("No recommendation, or the final review packet is not signed by a named reviewer")
    export_patch(directory, (directory / (state["finalist"] + ".md")).read_bytes())
    write(directory / "experiment.json", dict(state, status="accepted_patch_exported"))
    print("Exported the accepted patch for repository review; nothing was committed or published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

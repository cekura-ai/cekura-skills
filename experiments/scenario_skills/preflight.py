"""No inference during preflight. Effective deployment facts must be attested."""
from __future__ import annotations

import ast
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

from .common import PROPOSER, ROOT, dependencies, digest, read
from .fixture import OPERATIONS, PREFIX


def preflight(config):
    failures = []
    cfg = __import__("copy").deepcopy(config)
    from .budget import BudgetError, policy_limits
    try:
        limits = policy_limits(cfg.get("budget_policy"))
    except BudgetError as error:
        failures.append(str(error))
        limits = {"target": "20", "proposer": "5"}
    if cfg.get("execution_goal", "acceptance") not in ("acceptance", "suggestions"):
        failures.append("Unknown execution goal")
    review = cfg.get("fixture_review_mode", "human")
    if review not in ("human", "engineering") or (review == "engineering" and (
            cfg.get("execution_goal") != "suggestions" or not cfg.get("review_authorization"))):
        failures.append("Engineering fixture review requires an authorized unapproved-suggestions run")
    proposer = cfg.get("proposer", {})
    target = cfg.get("target", {})
    modal_adapter = target.get("adapter") == "modal"
    remote_claude = proposer.get("adapter") == "remote_claude"
    installed = dependencies()
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        if "==" in line:
            name, version = line.split("==")
            if installed[name] != version:
                failures.append("Pinned benchmark dependency unavailable or different: " + name)
    if remote_claude:
        from .remote_claude import cli_args
        from .proposer import SCHEMA
        try:
            cli_args(proposer, SCHEMA)
        except (ValueError, KeyError) as error:
            failures.append("Claude configuration: " + str(error))
        preparation_path = Path(proposer.get("preparation_path") or "")
        if not preparation_path.is_file():
            failures.append("Isolated EC2 Claude preparation evidence missing")
        else:
            preparation = read(preparation_path)
            if (any(preparation.get(k) != proposer.get(k) for k in ("image", "cli_version", "cli_sha256"))
                    or preparation.get("auth", {}).get("loggedIn") is not True
                    or preparation.get("isolation") != {"read_only": True, "model_tools": [],
                        "host_repository_mounted": False, "offline_network": "none"}):
                failures.append("Isolated EC2 Claude preparation differs from configured runtime")
        if proposer.get("provider") != "claude.ai" or proposer.get("accounting") != "bounded_cli":
            failures.append("Remote Claude requires the explicitly selected claude.ai bounded CLI adapter")
        if proposer.get("hard_cost_bound_verified") is not True or not proposer.get("cost_bound_evidence"):
            failures.append("Claude hard request/session cost bound unverified; CLI budget flag alone is insufficient")
        if proposer.get("billing_usage_verified") is not True:
            failures.append("Claude Team incremental billing and usage reporting unverified")
        if proposer.get("subscription_only"):
            usage = proposer.get("subscription", {})
            if (usage.get("extra_usage_enabled") is not False or not usage.get("checked_at")
                    or not usage.get("credential_sha256")
                    or usage.get("source") != "https://api.anthropic.com/api/oauth/usage"):
                failures.append("Claude subscription-only execution requires verified disabled extra usage")
        probe_path = Path(proposer.get("connectivity_probe_path") or "")
        if proposer.get("transport") == "local":
            pass  # The structured-output and read-capability probes run as the experiment's first bounded step.
        elif not probe_path.is_file():
            failures.append("Actual isolated Claude structured-output probe missing")
        else:
            probe = read(probe_path)
            if (probe.get("passed") is not True or probe.get("model") != proposer.get("model")
                    or probe.get("image") != proposer.get("image") or probe.get("cli_version") != proposer.get("cli_version")):
                failures.append("Claude structured-output probe differs from configured proposer")
    elif {k: proposer.get(k) for k in PROPOSER} != PROPOSER:
        failures.append("Codex proposer must remain gpt-6.1-sol / azure / high")
    if remote_claude:
        if proposer.get("transport") != "local" and not shutil.which("ssh"):
            failures.append("SSH client unavailable for the EC2 proposer")
    elif not shutil.which(proposer.get("binary", "codex")):
        failures.append("codex exec binary unavailable")
    elif proposer.get("cli_version"):
        version = subprocess.run([proposer.get("binary", "codex"), "--version"], capture_output=True, text=True, timeout=30)
        if version.returncode or version.stdout.strip() != proposer["cli_version"]:
            failures.append("Codex CLI differs from the pinned version")
    else:
        failures.append("Codex CLI version has not been pinned")
    if not remote_claude and not Path("/usr/bin/sandbox-exec").exists():
        failures.append("Verified proposer filesystem sandbox unavailable")
    for kind, section in (("target", target), ("proposer", proposer)):
        if kind == "proposer" and remote_claude:
            if section.get("auth_verified") is not True or section.get("model_available_verified") is not True:
                failures.append("Claude model availability and authentication have not been verified")
            continue
        env = section.get("credential_env")
        if not env or not os.environ.get(env):
            failures.append(kind + " credential unavailable")
        if section.get("auth_verified") is not True or section.get("model_available_verified") is not True:
            failures.append(kind + " model availability and authentication have not been verified")
        rates = section.get("rates", {})
        required = ["input_per_million", "output_per_million", "cached_input_per_million"]
        if kind == "target" and not modal_adapter:
            required.extend(["cache_write_per_million", "infrastructure_per_second"])
        if not rates.get("source") or not rates.get("verified_at") or any(
                not isinstance(rates.get(k), (int, float)) or not math.isfinite(rates[k]) or rates[k] < 0 for k in required):
            failures.append(kind + " billing rates and usage semantics unverified")
        if section.get("accounting") == "per_request":
            from .gateway import validate_admission
            failures.extend(validate_admission(section, kind, float(limits[kind])))
            probe_path = Path(section.get("gateway_probe_path") or "")
            if not probe_path.is_file():
                failures.append(kind + " TLS gateway transport probe missing")
            else:
                probe = read(probe_path)
                identity = {"model": section.get("model", section.get("snapshot", {}).get("model")),
                            "endpoint": section.get("model_base_url", section.get("snapshot", {}).get("model_base_url"))}
                if probe.get("passed") is not True or probe.get("identity") != identity or probe.get("code_sha256") != digest(Path(__file__).with_name("gateway.py")):
                    failures.append(kind + " TLS gateway probe is stale or mismatched")
                if kind == "target" and modal_adapter and (probe.get("image") != target.get("image")
                        or probe.get("runtime_env") != target.get("snapshot", {}).get("runtime_env")
                        or probe.get("adapter_sha256") != digest(Path(__file__).with_name("modal_runtime.py"))
                        or probe.get("relay_sha256") != digest(Path(__file__).with_name("relay.py"))):
                    failures.append("Modal gateway probe does not match image, flags or transport code")
                if kind == "proposer" and probe.get("proposer_sha256") != digest(Path(__file__).with_name("proposer.py")):
                    failures.append("Codex gateway probe does not match the isolated launcher")
        else:
            bound = section.get("max_cost_usd")
            if not isinstance(bound, (int, float)) or not math.isfinite(bound) or bound <= 0 or not section.get("cost_bound_evidence"):
                failures.append(kind + " conservative cost bound unavailable")
    if not remote_claude and not proposer.get("provider_config"):
        failures.append("Explicit Azure provider configuration unavailable (no global config inheritance)")
    if modal_adapter:
        if target.get("accounting") != "per_request" or (not remote_claude and proposer.get("accounting") != "per_request"):
            failures.append("Modal experiment requires request admission for both target and proposer")
        if not re.fullmatch(r"im-[A-Za-z0-9]+", target.get("image", "")):
            failures.append("Exact captured Modal image ID missing")
        try:
            from importlib.metadata import version
            if version("modal") != "1.4.1":
                failures.append("Modal controller must use pinned SDK 1.4.1")
        except __import__("importlib").metadata.PackageNotFoundError:
            failures.append("Pinned Modal controller unavailable")
        for env in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"):
            if not os.environ.get(env):
                failures.append("Host Modal credential unavailable: " + env)
        try:
            from .modal_runtime import infrastructure_bound
            infrastructure_bound(target.get("infrastructure_rates", {}))
        except ValueError as error:
            failures.append(str(error))
        probe_path = Path(target.get("offline_probe_path") or "")
        if not probe_path.is_file():
            failures.append("Exact Modal image offline probe missing")
        else:
            probe = read(probe_path)
            if (probe.get("passed") is not True or probe.get("image_id") != target["image"]
                    or probe.get("production_image_verified") is not True
                    or probe.get("runtime_env") != (target.get("snapshot") or {}).get("runtime_env")
                    or probe.get("fixture_sha256") != digest(ROOT / "fixture.py")
                    or probe.get("catalog_sha256") != (target.get("snapshot") or {}).get("catalog_sha256")):
                failures.append("Exact Modal offline probe does not match the pinned runtime")
    elif not re.fullmatch(r"sha256:[0-9a-f]{64}", target.get("image", "")):
        failures.append("Pinned local Cekura runtime image unavailable")
    elif not shutil.which("docker"):
        failures.append("Docker CLI unavailable for the pinned Cekura runtime")
    else:
        try:
            inspected = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", target["image"]],
                                       capture_output=True, text=True, timeout=30)
            if inspected.returncode or inspected.stdout.strip() != target["image"]:
                failures.append("Pinned Cekura runtime image is not present in the local Docker daemon")
        except (OSError, subprocess.TimeoutExpired):
            failures.append("Local Docker runtime image inspection failed")
    snapshot = target.get("snapshot")
    guard_image = target.get("network_guard_image") if not modal_adapter else None
    if guard_image:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", guard_image):
            failures.append("Native network guard image must be pinned")
        else:
            try:
                inspected = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", guard_image],
                                           capture_output=True, text=True, timeout=30)
                if inspected.returncode or inspected.stdout.strip() != guard_image:
                    failures.append("Native network guard image is not present locally")
            except (OSError, subprocess.TimeoutExpired):
                failures.append("Native network guard inspection failed")
        probe_path = Path(target.get("offline_probe_path") or "")
        if not probe_path.is_file():
            failures.append("Native network guard requires a completed image probe")
        else:
            probe = read(probe_path)
            if (probe.get("passed") is not True or probe.get("image") != target.get("image") or
                    probe.get("network_guard_image") != guard_image or probe.get("runtime_env") != (snapshot or {}).get("runtime_env")):
                failures.append("Offline image probe does not match the pinned transport/configuration")
    if not isinstance(snapshot, dict) or snapshot.get("confirmed_effective") is not True or not snapshot.get("deployment_ref"):
        failures.append("Effective current Cekura target configuration has not been captured")
    else:
        required = ("model", "model_base_url", "reasoning_effort", "system_prompt_sha256", "runtime_env", "catalog_sha256", "runner_sha256", "extension_sha256", "pi_settings_sha256", "image", "skill_max_chars")
        if any(not snapshot.get(k) for k in required):
            failures.append("Target snapshot is incomplete")
        if snapshot.get("image") != target.get("image"):
            failures.append("Target image differs from the effective configuration")
        if not snapshot.get("proxy_transport_verified"):
            failures.append("Pinned target image proxy transport is unverified")
        if (snapshot.get("runtime_env") or {}).get("CEKURA_AGENT_HARNESS") != "pi":
            failures.append("Adapter requires the captured Pi runtime; other effective runtimes are not substituted")
        if not snapshot.get("tool_schema_provenance"):
            failures.append("Original Cekura tool schema provenance missing")
        for name in ("runner", "extension"):
            path = Path(target.get(name) or "")
            if not path.is_file() or digest(path) != snapshot.get(name + "_sha256"):
                failures.append("Target " + name + " does not match the effective snapshot")
        pi_settings = Path(target.get("pi_settings_path") or "")
        if not pi_settings.is_file():
            failures.append("Captured Pi global settings missing")
        elif digest(pi_settings) != snapshot.get("pi_settings_sha256"):
            failures.append("Pi global settings differ from the effective snapshot")
        if Path(target.get("runner") or "").is_file():
            values = {}
            for node in ast.parse(Path(target["runner"]).read_text()).body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    try:
                        values[node.targets[0].id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        pass
            if (values.get("KIMI_MODEL") != snapshot.get("model") or values.get("KIMI_REASONING_EFFORT") != snapshot.get("reasoning_effort")
                    or values.get("KIMI_BASE_URL") != snapshot.get("model_base_url")):
                failures.append("Target model/endpoint/effort differ from the captured runner")
            if values.get("_SKILL_MAX_CHARS") != snapshot.get("skill_max_chars"):
                failures.append("Effective skill loading cap differs from the captured runner")
        catalog_path = Path(target.get("catalog_path") or "")
        if not catalog_path.is_file():
            failures.append("Captured tool catalog missing")
        else:
            target["catalog"] = read(catalog_path)
            if any(t["name"].startswith("mcp__") for t in target["catalog"]):
                failures.append("Captured MCP catalog must contain original leaf names, not client-qualified names")
            if digest(target["catalog"]) != snapshot.get("catalog_sha256"):
                failures.append("Tool schemas differ from effective snapshot")
            from .contract_probe import identity
            contract_path = Path(target.get("contract_probe_path") or "")
            if not contract_path.is_file():
                failures.append("Captured-schema fixture contract probe missing")
            else:
                contract = read(contract_path)
                if contract.get("passed") is not True or any(contract.get(k) != v for k, v in identity(target["catalog"]).items()):
                    failures.append("Captured-schema fixture contract probe failed or is stale")
            supported = set(OPERATIONS) | {PREFIX + op for op in OPERATIONS}
            writes = [t["name"] for t in target["catalog"] if re.search(r"_(create|update|destroy|delete|generate_bg|run_\w+)$", t["name"]) and t["name"] not in supported]
            # Unsupported operations are denied, but the unchanged schema still reaches the model.
            target["unsupported_fixture_writes"] = writes
    source = ROOT / "vendor/stanford/meta_harness.py.source"
    if digest(source) != "47d89e7fc48499a2d574491bcc84e35342a6c07ff29f7a25cc13dbd0a6ed853c":
        failures.append("Stanford Meta-Harness pinned source changed")
    if cfg.get("experiment_version") == 2:
        from .v2.dataset import load
        from .v2.preflight import real_backend
        failures.extend(real_backend(cfg))
        judge = cfg.get("judge", {})
        if (judge.get("subscription_only") is not True or judge.get("read_training_files") is not False or
                any(judge.get(k) != proposer.get(k) for k in ("model", "image", "cli_sha256", "reasoning_effort", "transport", "subscription"))):
            failures.append("Fixed separate judge configuration is missing or differs from the qualified Claude transport")
        if cfg.get("benchmark_version") == 3:
            from .modal_runtime import V3_LIFETIME, infrastructure_bound
            from .v3.replay import proof_hashes
            try:
                infrastructure_bound(target.get("infrastructure_rates", {}), V3_LIFETIME)
            except ValueError as error:
                failures.append("v3 rollout lifetime: " + str(error))
            path = Path(target.get("v3_replay_proof_path") or "")
            proof = read(path) if path.is_file() else {}
            if proof.get("passed") is not True or any(proof.get(k) != v for k, v in proof_hashes().items()):
                failures.append("v3 real-backend replay proof is missing, failed or stale (run contract-probe --benchmark 3)")
        path = Path(target.get("v2_contract_probe_path") or "")
        if cfg.get("benchmark_version") == 3:
            pass  # The v3 replay proof above replaces the v2 task contract probe.
        elif not path.is_file():
            failures.append("72-task captured-schema contract probe missing")
        else:
            proof = read(path)
            wanted = {"catalog_sha256": (snapshot or {}).get("catalog_sha256"), "tasks_sha256": digest(load()),
                      "fixture_sha256": digest(ROOT / "v2/fixture.py"), "grader_sha256": digest(ROOT / "v2/grader.py"),
                      "contract_code_sha256": digest(ROOT / "v2/contract_probe.py")}
            if proof.get("passed") is not True or any(proof.get(k) != v for k, v in wanted.items()):
                failures.append("72-task captured-schema contract probe is stale or failed")
        path = Path(target.get("gateway_probe_path") or "")
        if path.is_file():
            proof = read(path)
            if (proof.get("full_skill_loader_verified") is not True or proof.get("production_history_format_verified") is not True or
                    proof.get("probe_sha256") != digest(ROOT / "v2/probe.py") or proof.get("fixture_sha256") != digest(ROOT / "v2/fixture.py")):
                failures.append("Three-turn original skill-loader delivery probe is stale or failed")
    return {"ready": not failures, "failures": failures, "configuration": cfg}

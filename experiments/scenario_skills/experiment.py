"""The bounded 66-rollout experiment; checkpoints survive normal interrupted runs."""
from __future__ import annotations

import difflib
import fcntl
import json
import re
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from jsonschema.exceptions import ValidationError as SchemaValidationError

from .budget import BudgetError, Ledger
from .common import REPO, ROOT, dependencies, digest, private_dir, read, write
from .dataset import load
from .evaluator import Evaluator
from .meta_harness import search
from .preflight import preflight
from .proposer import CodexProposer
from .selection import human_gate, qualifies, review_packet, select
from .skill import SKILL, candidate, material, manifest, split


def all_results(directory):
    return [read(path) for path in sorted((directory / "rollouts").glob("*/result.json"))]


def budget_path(config, directory):
    path = Path(config.get("budget_ledger_path") or directory / "budget.json").resolve()
    private_dir(path.parent)
    return path


def report(directory, state, ledger):
    results = all_results(directory)
    grouped = {}
    for result in results:
        key = (result["candidate_sha256"], result["split"], result["family"])
        grouped.setdefault(key, []).append(result)
    rows = ["# Scenario-authoring smoke comparison", "", "Status: " + state["status"], "",
            "Automated scores measure authoring contracts. Semantic grounding requires human domain signoff.", "",
            "| Candidate hash | Split | Family | Pass / executions | Incomplete |", "|---|---|---|---|---|"]
    for (candidate_hash, split_name, family), group in sorted(grouped.items()):
        rows.append("| %s | %s | %s | %d / %d | %d |" % (candidate_hash[:12], split_name, family,
                    sum(r["grade"]["score"] for r in group), len(group), sum(r["status"] != "complete" for r in group)))
    if not results:
        rows += ["", "No model rollouts executed."]
    rows += ["", "Charged/reserved spend: $%s target/infrastructure, $%s proposer; $%s total (active ceiling $%s, authorized ceiling $%s)." %
             (ledger.total("target"), ledger.total("proposer"), ledger.total(), ledger.state["limits"]["total"], ledger.authorized_limits["total"]), "",
             "Usage and elapsed time are recorded per rollout in private result.json and proposer JSON event logs.", "",
             "Failures:", ""]
    rows += ["- " + failure for failure in state.get("failures", [])]
    if state.get("reason"):
        rows.append("- " + state["reason"])
    for result in results:
        if result["grade"]["failed_checks"]:
            rows.append("- %s / %s: %s" % (result["candidate_sha256"][:12], result["task_id"], ", ".join(result["grade"]["failed_checks"])))
    for stage in ("validation", "sealed"):
        signoff = directory / (stage + "-signoff.json")
        if signoff.exists():
            rows += ["", stage.title() + " semantic findings:", json.dumps(read(signoff), indent=2)]
    rows += ["", "Limitations: 24 synthetic tasks in 12 independent packs; no production failure-rate estimate, "
             "voice execution, generator optimization, activation changes, or production tool writes."]
    (directory / "comparison.md").write_text("\n".join(rows) + "\n")
    if state.get("execution_goal") == "suggestions":
        suggestion_report(directory, state, results)


def suggestion_report(directory, state, results):
    """Export reviewable unapproved diffs; never invoke accepted-patch packaging."""
    baseline = SKILL.read_bytes()
    candidates = []
    for number in (1, 2):
        name = "candidate-%d" % number
        path = directory / (name + ".md")
        if not path.exists():
            continue
        data = path.read_bytes()
        candidate(baseline, split(data)[1].decode(), forbidden_material(load()))
        diff = "".join(difflib.unified_diff(baseline.decode().splitlines(True), data.decode().splitlines(True),
                                         "baseline/SKILL.md", name + "/SKILL.md"))
        (directory / (name + ".unapproved.diff")).write_text(diff)
        evidence = [r for r in results if r["candidate_sha256"] == digest(data)]
        scores = {stage: {"passes": sum(r["grade"]["score"] for r in evidence if r["split"] == stage),
                          "executions": sum(r["split"] == stage for r in evidence)} for stage in ("training", "validation")}
        candidates.append({"name": name, "sha256": digest(data), "bytes": len(data), "scores": scores,
            "rationale": read(directory / (name + ".rationale.json"))["rationale"],
            "measured_cost_usd": sum(r.get("cost_usd") or 0 for r in evidence),
            "recommended_for_human_review": state.get("selected") == name})
    summary = {"status": state["status"], "selected": state.get("selected"), "approved": False,
               "semantic_status": "pending_human_review", "candidates": candidates,
               "reason": state.get("reason"), "baseline_sha256": digest(baseline)}
    write(directory / "suggestions.json", summary)
    rows = ["# Suggested skill edits", "", "Status: " + state["status"], "",
            "All candidates are unapproved. Automated scores measure authoring contracts; human semantic review and sealed evaluation are required before patch acceptance.", ""]
    if state.get("selected"):
        rows += ["Recommended for human review: **" + state["selected"] + "**", ""]
    elif state["status"] == "no_candidate_qualifies":
        rows += ["Neither candidate meets strict validation improvement without regression. Recommend no skill patch.", ""]
    elif state["status"] == "baseline_already_passes":
        rows += ["Baseline passes all targeted checks. No measured fix is necessary.", ""]
    else:
        rows += ["No supported recommendation is available yet.", ""]
    for item in candidates:
        rows += ["## " + item["name"], "", item["rationale"], "",
                 "Training: %d / %d; validation: %d / %d." % (item["scores"]["training"]["passes"], item["scores"]["training"]["executions"],
                     item["scores"]["validation"]["passes"], item["scores"]["validation"]["executions"]), "",
                 "[Unapproved diff](" + item["name"] + ".unapproved.diff)", ""]
    if state.get("reason"):
        rows += ["Execution stopped: " + state["reason"], ""]
    (directory / "suggestions.md").write_text("\n".join(rows))


def checkpoint(directory, state, stage, task=None):
    state.update(stage=stage, current_task=task)
    write(directory / "experiment.json", state)
    print(json.dumps({"stage": stage, "task": task}), flush=True)


def evaluate_stage(evaluator, data, tasks, directory, state, stage):
    results = []
    for task in tasks:
        checkpoint(directory, state, stage, task["id"])
        result = evaluator.evaluate(data, task)
        results.append(result)
        print(json.dumps({"task": task["id"], "status": result["status"], "score": result["grade"]["score"],
                          "cost_usd": result.get("cost_usd"), "cache_hit": result.get("cache_hit", False)}), flush=True)
    return results


def forbidden_material(tasks):
    # Protected facts are vetted by the parent, never shown to the proposer as a list.
    tokens = []
    for task in tasks:
        agent = task["fixture"]["agent"]
        tokens.extend([task["id"], task["pack_id"], agent["name"], str(agent["id"]), str(agent["project"])])
        tokens.append(task["id"].split("-")[0])
        tokens.extend(str(v) for v in agent.get("required_variables", {}).values())
        tokens.extend(agent.get("required_variables", {}).keys())
        tokens.extend(str(row["id"]) for kind in ("profiles", "folders") for row in task["fixture"]["resources"][kind])
        tokens.extend(str(row["id"]) for row in task["fixture"]["personalities"])
        for row in task["fixture"]["resources"]["scenarios"]:
            tokens.extend([str(row["id"]), row["name"]])
        sources = [agent["description"]] + [d["content"] for d in task.get("documents", [])]
        for text in sources:
            words = re.findall(r"[\w:.-]+", text)
            tokens.extend(" ".join(words[i:i+5]) for i in range(max(0, len(words)-4)))
            tokens.extend(re.findall(r"\b\d[\d:]*\s+\w+(?:\s+\w+)?", text))
    return tokens


def export_patch(directory, candidate_bytes):
    """Prepare packaging in a disposable copy; do not modify or stage the user's tree."""
    with tempfile.TemporaryDirectory(prefix="cekura-accepted-patch-") as temporary:
        copy = Path(temporary) / "repo"
        shutil.copytree(REPO, copy, ignore=shutil.ignore_patterns(".git", ".claude", "node_modules", "__pycache__", ".pytest_cache"))
        before = {str(p.relative_to(copy)): p.read_bytes() for p in copy.rglob("*") if p.is_file()}
        target = copy / SKILL.relative_to(REPO)
        target.write_bytes(candidate_bytes)
        # Patch release keeps activation frontmatter and the minor plugin acknowledgement exact.
        subprocess.run(["python3", "scripts/bump_version.py", "--patch"], cwd=copy, check=True, capture_output=True)
        version = read(copy / "package.json")["version"]
        changelog = copy / "CHANGELOG.md"
        text = changelog.read_text()
        entry = "\n## %s\n\n- Improve scenario authoring guidance after synthetic authoring-contract and human semantic acceptance gates.\n" % version
        first_break = text.index("\n")
        changelog.write_text(text[:first_break + 1] + entry + text[first_break + 1:])
        subprocess.run(["python3", "cekura/scripts/build_bundles.py"], cwd=copy, check=True, capture_output=True)
        checks = []
        for script, arguments in (("validate_skills.py", []), ("validate_ack_tags.py", []), ("build_bundles.py", ["--check"])):
            command = ["python3", "cekura/scripts/" + script] + arguments
            result = subprocess.run(command, cwd=copy, capture_output=True, text=True, check=True)
            checks.append({"command": command, "output": result.stdout})
        if split(target.read_bytes())[0] != split(candidate_bytes)[0]:
            raise ValueError("Packaging changed protected skill frontmatter")
        if tuple(int(n) for n in version.split(".")) <= tuple(int(n) for n in json.loads(before["package.json"])["version"].split(".")):
            raise ValueError("Plugin version was not bumped")
        patches = []
        for path in sorted(copy.rglob("*")):
            if not path.is_file():
                continue
            name = str(path.relative_to(copy))
            old, new = before.get(name, b""), path.read_bytes()
            if old != new:
                patches.extend(difflib.unified_diff(old.decode().splitlines(True), new.decode().splitlines(True), "a/" + name, "b/" + name))
        (directory / "accepted-skill.patch").write_text("".join(patches))
        write(directory / "patch-verification.json", {"checks": checks, "version": version, "candidate_sha256": digest(candidate_bytes)})


def run(config, artifact_path):
    directory = private_dir(artifact_path)
    with (directory / "experiment.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run(config, directory)


def repeat(config, artifact_path, task_id, candidate_name, reason):
    if not reason:
        raise ValueError("Targeted repeat requires an inconsistency or unresolved evidence reason")
    directory = private_dir(artifact_path)
    with (directory / "experiment.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = read(directory / "experiment.json")
        identity = experiment_identity(config, directory)
        if any(state.get(key) != value for key, value in identity.items()):
            raise ValueError("Repeat must use the same experiment configuration, dataset, material and controller")
        cfg = preflight(config)
        if not cfg["ready"]:
            raise ValueError("Repeat preflight failed")
        task = next(t for t in load() if t["id"] == task_id)
        if task["split"] == "sealed" and (not state.get("selected") or not human_gate(directory, "validation")):
            raise ValueError("Sealed repeats require frozen selection and validation signoff")
        if candidate_name not in ("baseline", "candidate-1", "candidate-2"):
            raise ValueError("Unknown candidate")
        data = SKILL.read_bytes() if candidate_name == "baseline" else (directory / (candidate_name + ".md")).read_bytes()
        if task["split"] == "sealed" and candidate_name not in ("baseline", state.get("selected")):
            raise ValueError("Only the selected candidate can see sealed cases")
        candidate(SKILL.read_bytes(), split(data)[1].decode(), forbidden_material(load()))
        ledger = Ledger(budget_path(config, directory), config.get("budget_policy"))
        index = 1 + sum(e.get("repeat", 0) != 0 for e in ledger.state["entries"].values())
        try:
            result = Evaluator(cfg["configuration"], directory, ledger).evaluate(data, task, index)
            write(directory / ("repeat-%d.reason.json" % index), {"task": task_id, "candidate": candidate_name, "reason": reason})
            state["status"] = "repeat_requires_gate_recheck"
            return result
        finally:
            write(directory / "experiment.json", state)
            report(directory, state, ledger)


def experiment_identity(config, directory, baseline=None, tasks=None):
    baseline = SKILL.read_bytes() if baseline is None else baseline
    tasks = load() if tasks is None else tasks
    return {"configuration_sha256": digest(config), "dataset_sha256": digest(tasks), "baseline_sha256": digest(baseline),
                "budget_ledger_path": str(budget_path(config, directory)),
                "budget_policy": config.get("budget_policy"), "execution_goal": config.get("execution_goal", "acceptance"),
                "material_sha256": manifest(material()),
                "benchmark_code_sha256": {str(p.relative_to(ROOT)):digest(p) for p in sorted(
                    [*ROOT.glob("*.py"), *(ROOT / "proposal_transport").glob("*.py")])},
                "controller_environment": {"python":platform.python_version(),"dependencies":dependencies(),
                                           "dependency_lock_sha256":digest(ROOT / "requirements.txt")}}


def _run(config, directory):
    tasks = load()
    baseline = SKILL.read_bytes()
    state_path = directory / "experiment.json"
    identity = experiment_identity(config, directory, baseline, tasks)
    state = read(state_path) if state_path.exists() else dict(identity, status="preflight", selected=None)
    if any(state.get(k) != v for k, v in identity.items()):
        raise ValueError("Experiment configuration/dataset/loaded material changed; use a new experiment")
    ledger = Ledger(budget_path(config, directory), config.get("budget_policy"))
    try:
        checks = preflight(config)
        write(directory / "preflight.json", checks)
        if not checks["ready"]:
            state["status"] = "preflight_failed"
            state["failures"] = checks["failures"]
            return state
        cfg = checks["configuration"]
        from .fixture_review import packet, gate, engineering_gate
        packet(directory)
        reviewed = engineering_gate(directory, cfg) if cfg.get("fixture_review_mode") == "engineering" else gate(directory)
        if not reviewed:
            state["status"] = "awaiting_fixture_domain_signoff"
            return state
        state["status"] = "running"
        state.pop("reason", None)
        state.pop("failures", None)
        evaluator = Evaluator(cfg, directory, ledger)
        if cfg["proposer"].get("adapter") == "remote_claude":
            from .remote_claude import ClaudeProposer
            proposer = ClaudeProposer(cfg["proposer"], directory, ledger)
        else:
            proposer = CodexProposer(cfg["proposer"], directory, ledger)
        training = [t for t in tasks if t["split"] == "training"]
        validation = [t for t in tasks if t["split"] == "validation"]
        sealed = [t for t in tasks if t["split"] == "sealed"]
        # First two baseline tasks are reused in the 24 baseline total.
        smoke = [training[0], next(t for t in training if t["family"] == "variables")]
        for result in evaluate_stage(evaluator, baseline, smoke, directory, state, "baseline_smoke"):
            if result["status"] != "complete":
                raise RuntimeError("Baseline smoke did not finish conclusively")
        # Each request is admitted against the remaining allowance. The approved
        # policy permits an incomplete budget-stopped report, never an inference
        # request without a conservative reservation and verified hard caps.
        before = evaluate_stage(evaluator, baseline, tasks, directory, state, "baseline")
        if any(r["status"] != "complete" for r in before):
            raise RuntimeError("Baseline contains inconclusive executions")
        if all(r["grade"]["score"] for r in before):
            state["status"] = "baseline_already_passes"
            return state
        if not state.get("selected"):
            candidates = search(baseline, training, evaluator, proposer, directory, forbidden_material(tasks),
                                progress=lambda stage, task: checkpoint(directory, state, stage, task))
            # Both candidates are frozen before independent validation starts.
            validation_results = {}
            for number, data in enumerate(candidates, 1):
                validation_results["candidate-%d" % number] = (data, evaluate_stage(evaluator, data, validation, directory, state, "candidate-%d_validation" % number))
            baseline_val = [r for r in before if r["split"] == "validation"]
            chosen = select(baseline_val, validation_results, [t["id"] for t in validation])
            if not chosen:
                state["status"] = "no_candidate_qualifies"
                return state
            state["selected"] = chosen
            write(state_path, state)  # freeze selection before any human/test inspection
        chosen = state["selected"]
        data = (directory / (chosen + ".md")).read_bytes()
        # Revalidate candidate bytes and all observed repeats before any acceptance/export.
        candidate(baseline, split(data)[1].decode(), forbidden_material(tasks))
        records = all_results(directory)
        baseline_val = [r for r in records if r["candidate_sha256"] == digest(baseline) and r["split"] == "validation"]
        candidate_val = [r for r in records if r["candidate_sha256"] == digest(data) and r["split"] == "validation"]
        if not qualifies(baseline_val, candidate_val, [t["id"] for t in validation]):
            raise ValueError("Validation selection gate no longer passes")
        review_packet(directory, "validation", validation, baseline_val, candidate_val)
        if cfg.get("execution_goal") == "suggestions":
            state["status"] = "suggestions_ready"
            return state
        if not human_gate(directory, "validation"):
            state["status"] = "awaiting_validation_domain_signoff"
            return state
        after_sealed = [evaluator.evaluate(data, task) for task in sealed]
        records = all_results(directory)
        baseline_test = [r for r in records if r["candidate_sha256"] == digest(baseline) and r["split"] == "sealed"]
        candidate_test = [r for r in records if r["candidate_sha256"] == digest(data) and r["split"] == "sealed"]
        if not qualifies(baseline_test, candidate_test, [t["id"] for t in sealed], require_gain=False):
            state["status"] = "sealed_regression"
            return state
        review_packet(directory, "sealed", sealed, baseline_test, candidate_test)
        if not human_gate(directory, "sealed"):
            state["status"] = "awaiting_sealed_domain_signoff"
            return state
        export_patch(directory, data)
        state["status"] = "accepted_patch_exported"
        return state
    except (BudgetError, RuntimeError, ValueError, SchemaValidationError) as error:
        state["status"] = "stopped"
        state["reason"] = error.message if isinstance(error, SchemaValidationError) else str(error)
        return state
    finally:
        write(state_path, state)
        report(directory, state, ledger)

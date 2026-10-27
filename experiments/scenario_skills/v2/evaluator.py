"""Real-backend rollouts: the pinned target in Modal, a fresh isolated backend per attempt.

Execution evidence and semantic judgments are cached separately. A scored record is
always recomputed from the raw execution, the cached judgment and any human
adjudication, so a criterion-level change rescores every gate without new inference.
"""
from __future__ import annotations

import copy
import difflib
import platform
import time
from decimal import Decimal
from pathlib import Path

from ..common import ROOT, dependencies, digest, read, write
from ..runtime import delivered_skill
from ..skill import SKILL, manifest, material, split
from .backend_stack import Infrastructure, Stack, docker
from .bridge import Bridge, operations
from .grader import combine, grade
from .judge import packet
from .probe import skill_evidence
from .seed import readback, seed

ATTEMPTS = 3  # One trial plus at most two retries, and only after infrastructure failure.
MAX_CORE, MAX_REPEATS = 216, 24


# Code a rollout's execution or grading depends on. Controller, proposer, judge, review and authoring
# modules are excluded, so changing them never invalidates (and re-bills) cached rollouts.
ROLLOUT_CODE = ("common.py", "fixture.py", "runtime.py", "relay.py", "gateway.py", "budget.py", "network_guard.py", "modal_runtime.py",
                "skill.py", "v2/bridge.py", "v2/bridge_client.py", "v2/backend_stack.py", "v2/seed.py", "v2/metering.py", "v2/evaluator.py",
                "v2/grader.py", "v2/fixture.py", "v3/bridge.py", "v3/checks.py", "v3/grader.py", "v3/followups.py")
# Configuration keys only the controller reads.
CONTROLLER_KEYS = ("budget_policy", "v3_protocol", "proposer", "judge", "search", "max_repeats", "preflight_observations",
                   "execution_goal", "fixture_review_mode")


def code_identity():
    files = [ROOT / name for name in ROLLOUT_CODE] + sorted((ROOT / "v2/generator").glob("*.py"))
    return {str(p.relative_to(ROOT)): digest(p) for p in files if p.exists()}


def delivery(bodies, candidate, cap):
    """What the target actually received: correlated Skill/read results and which edits they carried.

    Installed bytes prove nothing about receipt. Each changed baseline hunk is reported as
    inside or beyond the loader's character cap and as observed or absent in real tool results.
    """
    exact = delivered_skill(candidate, cap).decode()
    observed = skill_evidence(bodies, exact)
    texts = []
    import json
    for body in bodies:
        calls = {}
        for message in json.loads(body).get("messages", []):
            for block in message.get("content", []) if isinstance(message.get("content"), list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    calls[block["id"]] = block
                if isinstance(block, dict) and block.get("type") == "tool_result" and "cekura-eval-design" in json.dumps(calls.get(block.get("tool_use_id"), {}).get("input", {})):
                    value = block.get("content", "")
                    texts.append(value if isinstance(value, str) else "\n".join(b.get("text", "") for b in value if isinstance(b, dict)))
    baseline = SKILL.read_text().splitlines(True)
    proposed = candidate.decode().splitlines(True)
    hunks, offset = [], 0
    starts = [0]
    for line in proposed:
        starts.append(starts[-1] + len(line))
    for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, baseline, proposed, autojunk=False).get_opcodes():
        if tag == "equal" or j1 == j2:
            continue
        # A hunk counts as received only when every substantial line of it was observed;
        # one straddling the loader cap is partially received, not received.
        probes = [line.strip() for line in proposed[j1:j2] if len(line.strip()) >= 12] or ["".join(proposed[j1:j2]).strip()]
        seen = [bool(probe) and any(probe in t for t in texts) for probe in probes]
        hunks.append({"lines": [j1 + 1, j2], "characters": [starts[j1], starts[j2]], "within_loader_cap": starts[j2] <= cap,
                      "observed_in_tool_results": all(seen), "partially_observed": any(seen) and not all(seen)})
    return {"observed_results": observed, "loader_cap": cap, "installed_characters": len(candidate.decode()),
            "full_loader_content_observed": any(r["full_loader_content"] for r in observed),
            "edited_hunks": hunks, "unreceived_hunks": sum(not h["observed_in_tool_results"] for h in hunks)}


class Evaluator:
    def __init__(self, config, directory, ledger, judge, runtime=None, infrastructure=None, stack_factory=Stack):
        self.config, self.directory, self.ledger, self.judge = config, Path(directory), ledger, judge
        target = dict(config["target"], catalog=config["target"].get("catalog") or read(config["target"]["catalog_path"]))
        self.target = target
        if runtime is None:
            from ..modal_runtime import ModalRuntime
            runtime = ModalRuntime(target, ledger)
        self.runtime = runtime
        self.generator = config["backend"]["generator"]
        # The prepared infrastructure preflight verified (a v3 run reuses the v2 preparation), else this run's own.
        state = config.get("backend", {}).get("infrastructure_state")
        # ensure() is idempotent: it restarts the tmpfs Postgres and re-migrates the template if the host lost them.
        self.infra = infrastructure or Infrastructure(Path(state).parent if state else self.directory / "backend").ensure()
        self.base_material = material()
        self.environment = {"configuration": {k: v for k, v in config.items() if k not in CONTROLLER_KEYS},
                            "python": platform.python_version(), "code": code_identity(), "dependencies": dependencies(),
                            "generator_deviation_sha256": config["backend"]["deviation_sha256"],
                            "backend_images": config["backend"]["images"], "openapi_sha256": config["backend"]["openapi_sha256"]}
        self.environment_hash = digest(self.environment)
        self.grader_hash = digest(ROOT / "v2/grader.py")
        self.v3_grader_hash = digest({"grader": digest(ROOT / "v3/grader.py"), "checks": digest(ROOT / "v3/checks.py")})
        self.stack_factory = stack_factory
        self.records = []

    def key(self, candidate, task, repeat):
        files = dict(self.base_material, **{"SKILL.md": candidate})
        return digest({"candidate": digest(candidate), "task": task, "environment": self.environment_hash,
                       "material": manifest(files), "grader": self._grader(task)[1], "repeat": repeat})

    def _grader(self, task):
        if task.get("benchmark_version") == 3:
            from ..v3.grader import grade as grade_v3
            return grade_v3, self.v3_grader_hash
        return grade, self.grader_hash

    def _bridge(self, task):
        if task.get("benchmark_version") == 3:
            from ..v3.bridge import Bridge as BridgeV3
            return BridgeV3
        return Bridge

    def execute(self, candidate, task, repeat=0):
        """Cached complete execution, else up to ATTEMPTS fresh attempts, each with its own scope."""
        key = self.key(candidate, task, repeat)
        last = None
        for attempt in range(ATTEMPTS):
            directory = self.directory / "rollouts" / ("%s-a%d" % (key[:32], attempt))
            path = directory / "result.json"
            if path.exists():
                last = read(path)
                if last["status"] == "complete":
                    return dict(last, cache_hit=True)
                continue
            if directory.exists():
                self.recover(directory.name)
                last = {"status": "infrastructure_failure", "error": "controller interrupted; attempt abandoned", "attempt": attempt}
                write(path, last)
                continue
            last = self._attempt(candidate, task, repeat, key, attempt, directory)
            if last["status"] == "complete" or last["status"] in ("timeout", "inconclusive"):
                return last  # Only infrastructure failures are retried; a timeout is a result.
        return last

    def _limits(self, repeat):
        rollouts = self.ledger.rollouts()
        if repeat and sum(e.get("repeat", 0) != 0 for e in rollouts) >= self.config.get("max_repeats", MAX_REPEATS) * ATTEMPTS:
            raise ValueError("Repeat allowance reached")
        if not repeat and len({e.get("trial") for e in rollouts if not e.get("repeat")}) >= MAX_CORE:
            raise ValueError("Core rollout allowance reached")

    def _attempt(self, candidate, task, repeat, key, attempt, directory):
        self._limits(repeat)
        files = dict(self.base_material, **{"SKILL.md": candidate})
        scope = directory.name
        self.ledger.start(scope, "target", entry_type="rollout", repeat=repeat, trial=key)
        directory.mkdir(parents=True, mode=0o700)
        write(directory / "environment.json", self.environment)
        write(directory / "checkpoint.json", {"status": "running", "candidate": digest(candidate), "task": task["id"], "started": time.time()})
        stack = self.stack_factory(self.infra, scope, directory / "backend", self.generator, self.ledger)
        run, initial, final, raw, bridge = {"status": "infrastructure_failure", "messages": [], "events": [], "usage": []}, {}, {}, [], None
        try:
            with stack:
                session = seed(stack, task, self.generator["settings"])
                initial, _ = readback(stack, task["fixture"]["agent"]["project"])
                bridge = self._bridge(task)(task, stack.base_url, session, self.target["catalog"], files, operations(read(self.infra.spec_path)))
                bridge.initial_ids = {r["id"] for r in initial["scenarios"]}
                bridge.initial_state = initial
                bridge.state_reader = lambda: readback(stack, task["fixture"]["agent"]["project"])[0]
                write(directory / "seed.json", {k: v for k, v in session.items() if k != "token"})
                run = self.runtime.run(task, files, bridge, None, directory)
                final, raw = readback(stack, task["fixture"]["agent"]["project"])
        except Exception as error:
            run = dict(run, status="infrastructure_failure", error=type(error).__name__ + ": " + str(error)[:2000])
        teardown = stack.teardown
        bodies = [p.read_text() for p in sorted((directory / "gateway").glob("request-*/request.body"))]
        generator_cost = stack.metering.cost() if getattr(stack, "metering", None) else None
        sandboxes = sum((Decimal(s["reserved_usd"]) for s in getattr(stack, "metering", None) and stack.metering.sandboxes or []), Decimal(0))
        status = run["status"] if teardown.get("terminated") else "infrastructure_failure"
        result = dict(run, status=status, attempt=attempt, scope=scope, candidate_sha256=digest(candidate), candidate_body=split(candidate)[1].decode(),
                      task_id=task["id"], pack_id=task.get("pack_id"), split=task["split"], family=task["family"], repeat=repeat,
                      request=task["request"], followups=task.get("followups", []), context=task.get("context", {}), documents=task.get("documents", []),
                      environment_sha256=self.environment_hash, material_sha256=manifest(files), grader_sha256=self._grader(task)[1],
                      initial_state=initial, final_state=final, raw_backend_scenarios=raw, trace=bridge.trace if bridge else [],
                      id_mapping="identity: seeded rows keep fixture IDs; created rows keep backend-assigned IDs",
                      backend_teardown=teardown, generator_cost_usd=float(generator_cost) if generator_cost is not None else None,
                      generator_requests=stack.metering.requests if getattr(stack, "metering", None) else [],
                      generator_denied=stack.metering.denied if getattr(stack, "metering", None) else [],
                      infrastructure_reserved_usd=float(run.get("infrastructure_reserved_usd", 0)) + float(sandboxes),
                      cost_usd=run.get("model_cost_usd"), cache_hit=False)
        try:
            result["delivery"] = delivery(bodies, candidate, self.target["snapshot"]["skill_max_chars"])
        except Exception as error:
            result["delivery"] = {"error": type(error).__name__ + ": " + str(error)[:500]}
        if result["generator_cost_usd"] is None and result["status"] == "complete":
            result["status"] = "infrastructure_failure"  # Unsettled generator usage cannot support a comparison.
        result["grade"] = self._grader(task)[0](task, result["trace"], initial, final, run.get("messages", []), result["status"])
        write(directory / "result.json", result)
        for name, data in files.items():
            target = directory / "installed_material" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.ledger.settle(scope, 0)  # Requests, generator calls and sandboxes carry the charges.
        return result

    def recover(self, scope):
        """A controller died mid-attempt: stop leftover work and settle open reservations at their bounds."""
        for container in docker("ps", "-aq", "--filter", "label=cekura_scope=" + scope, check=False).split():
            docker("rm", "-f", container, check=False)
        try:
            import modal
            app = modal.App.lookup(self.generator["modal_app"], create_if_missing=False)
            for sb in modal.Sandbox.list(app_id=app.app_id, tags={"cekura_scope": scope}):
                sb.terminate()
        except Exception:
            pass  # Modal sandboxes also expire at their reserved lifetime.
        with self.ledger.transaction():
            open_entries = [k for k, e in self.ledger.state["entries"].items() if (k == scope or k.startswith(scope + "/")) and e["status"] == "running"]
        for key in open_entries:
            entry = self.ledger.state["entries"][key]
            if entry.get("infrastructure_only"):
                self.ledger.transition(key, "bounded_infrastructure_pending_billing")
            else:
                self.ledger.settle(key, entry["reserved"])
                self.ledger.transition(key, "complete", charged_at_bound="crash_recovery")

    def evaluate(self, candidate, task, repeat=0):
        if not self.judge.qualified():
            raise ValueError("Qualified Claude judge required before target execution")
        result = self.execute(candidate, task, repeat)
        if result["status"] != "complete":
            self.records.append(result)
            return result
        record = score(result, task, self.judge)
        path = self.directory / "scored" / (digest({"candidate": digest(candidate), "task": task["id"], "repeat": repeat, "judge": self.judge.identity}) + ".json")
        write(path, record)
        self.records.append(record)
        return record


def score(result, task, judge):
    """Contract grade plus the (adjudicated) semantic judgment, recomputed on every call."""
    semantic = judge.judge(packet(task, result))
    return dict(result, contract_grade=result["grade"], semantic=semantic, grade=combine(result["grade"], semantic))


def results(directory):
    return [read(p) for p in sorted((directory / "scored").glob("*.json"))]

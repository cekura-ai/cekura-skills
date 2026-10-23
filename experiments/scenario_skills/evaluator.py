"""evaluate(candidate, task): artifact-backed integration scoring and exact evidence."""
from __future__ import annotations

import copy
import time
import platform

from .common import dependencies, digest, read, write
from .fixture import FixtureServer, Store
from .grader import grade
from .runtime import CekuraRuntime, target_cost
from .skill import manifest, material, split


class Evaluator:
    def __init__(self, config, artifacts, ledger, runtime=None):
        self.config, self.artifacts, self.ledger = config, artifacts, ledger
        if runtime is None and config["target"].get("adapter") == "modal":
            from .modal_runtime import ModalRuntime
            runtime = ModalRuntime(config["target"], ledger)
        if runtime is None and config["target"].get("adapter") != "modal":
            from .budget import require_cumulative
            require_cumulative(ledger)  # The local runtime forwards to the paid model.
        self.runtime = runtime or CekuraRuntime(config["target"])
        from .common import ROOT
        code_files = [*ROOT.glob("*.py"), *(ROOT / "proposal_transport").glob("*.py")]
        if config.get("experiment_version") == 2:
            code_files.extend((ROOT / "v2").glob("*.py"))
        self.environment = {"configuration": config, "python": platform.python_version(),
                            "code": {str(p.relative_to(ROOT)): digest(p) for p in sorted(code_files)},
                            "fixed_skill_catalog": {name: digest(data) for name, data in getattr(self.runtime, "fixed_skill_material", {}).items()},
                            "dependencies": dependencies()}
        self.environment_hash = digest(self.environment)
        self.grader_hash = digest(ROOT / ("v2/grader.py" if config.get("experiment_version") == 2 else "grader.py"))
        self.base_material = material()
        self.records = []

    def evaluate(self, candidate, task, repeat=0):
        version2 = self.config.get("experiment_version") == 2
        if not 0 <= repeat <= (24 if version2 else 12):
            raise ValueError("Repeat index outside smoke limits")
        files = dict(self.base_material, **{"SKILL.md": candidate})
        key = digest({"candidate": digest(candidate), "task": task, "environment": self.environment_hash,
                      "material": manifest(files), "grader": self.grader_hash, "repeat": repeat})
        directory = self.artifacts / "rollouts" / key
        result_path = directory / "result.json"
        if result_path.exists():
            result = read(result_path)
            if result["status"] == "complete":
                cached = dict(result, cache_hit=True)
                self.records.append(cached)
                return cached
            raise RuntimeError("Incomplete rollout cannot be reused as evidence; use a targeted repeat")
        target_entries = self.ledger.rollouts()
        maximum, repeats, core = (288, 24, 264) if version2 else (78, 12, 66)
        if len(target_entries) >= maximum or (repeat and sum(e.get("repeat", 0) != 0 for e in target_entries) >= repeats) or (not repeat and sum(e.get("repeat", 0) == 0 for e in target_entries) >= core):
            raise ValueError("Maximum rollout/repeat allowance reached")
        per_request = getattr(self.runtime, "request_accounting", False)
        if per_request:
            self.ledger.start(key, "target", entry_type="rollout", repeat=repeat)
        else:
            self.ledger.reserve(key, "target", self.config["target"]["max_cost_usd"], repeat=repeat)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        write(directory / "environment.json", self.environment)
        write(directory / "checkpoint.json", {"status": "running", "candidate": digest(candidate), "task": task["id"], "started": time.time()})
        store_type, grade_fn = Store, grade
        if version2:
            from .v2.fixture import Store as store_type
            from .v2.grader import grade as grade_fn
        store = store_type(task, files, self.config["target"]["catalog"])
        try:
            with FixtureServer(store) as server:
                run = self.runtime.run(task, files, store, server.url, directory)
        except Exception as error:
            run = {"status": "infrastructure_failure", "events": [], "messages": [], "usage": [], "error": str(error)}
        result = dict(run, candidate_sha256=digest(candidate), candidate_body=split(candidate)[1].decode(),
                      task_id=task["id"], pack_id=task.get("pack_id"), split=task["split"], family=task["family"], repeat=repeat,
                      request=task["request"], followups=task.get("followups", []), context=task.get("context", {}), documents=task.get("documents", []),
                      environment_sha256=self.environment_hash, material_sha256=manifest(files), grader_sha256=self.grader_hash,
                      initial_state=store.initial, final_state=copy.deepcopy(store.state), trace=store.trace, cache_hit=False)
        result["grade"] = grade_fn(task, store.trace, store.initial, store.state, run["messages"], run["status"])
        result["cost_usd"] = run.get("model_cost_usd") if per_request else target_cost(run["usage"], self.config["target"]["rates"])
        if result["cost_usd"] is not None and not per_request:
            result["cost_usd"] += run.get("elapsed_seconds", 600) * self.config["target"]["rates"]["infrastructure_per_second"]
        if per_request:
            result["infrastructure_reserved_usd"] = run.get("infrastructure_reserved_usd", 0)
        # Save evidence before settling: unknown billing must not destroy the failure trace.
        write(result_path, result)
        for name, data in files.items():
            path = directory / "installed_material" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.records.append(result)
        # Request and infrastructure entries already carry the charge; do not bill twice.
        self.ledger.settle(key, 0 if per_request and result["cost_usd"] is not None else result["cost_usd"])
        return result

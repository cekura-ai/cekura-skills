"""Stateful synthetic responses with external events and complete source evidence."""
import copy

from ..common import digest
from ..fixture import Store as SmokeStore, ValidationError


class Store(SmokeStore):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.applied_events = set()
        self.dispatch_counts = {}

    def apply_events(self, turn, boundary="before_turn", operation=None):
        for index, event in enumerate(self.task.get("events", [])):
            if index in self.applied_events or event.get("turn") != turn or event.get("boundary", "before_turn") != boundary:
                continue
            if event.get("operation") and event["operation"] != operation:
                continue
            self.applied_events.add(index)
            kind = event["kind"]
            if kind == "external_delete":
                ids = event.get("ids", [])
                if event.get("created_only"):
                    original = {r["id"] for r in self.initial["scenarios"]}
                    ids = [r["id"] for r in self.state["scenarios"] if r["id"] not in original]
                self.state["scenarios"] = [r for r in self.state["scenarios"] if r["id"] not in ids]
                self.trace.append({"kind": kind, "turn": turn, "ids": ids, "sequence": len(self.trace)})
            elif kind == "cancel":
                self.trace.append({"kind": kind, "turn": turn, "sequence": len(self.trace)})
            else:
                raise ValueError("Unsupported external event: " + kind)
        return any(e.get("kind") == "cancel" and e.get("turn") == turn for e in self.trace)

    def call(self, name, arguments):
        response = super().call(name, arguments)
        op = name.removeprefix("mcp__cekura__")
        if op == "scenarios_generate_bg" and not response["isError"]:
            docs = {d["name"]: d for d in self.task.get("documents", [])}
            resolved = []
            for filename in arguments.get("generation_files", []):
                doc = docs.get(filename.rsplit("/", 1)[-1])
                if doc:
                    resolved.append({"name": doc["name"], "sha256": digest(doc["content"].encode()), "content": doc["content"]})
            self.trace[-1]["resolved_sources"] = resolved
        self.apply_events(self.turn, "after_call", op)
        return response

    def _dispatch(self, op, args):
        self.dispatch_counts[op] = self.dispatch_counts.get(op, 0) + 1
        faults = self.task.get("faults", {}).get(op, [])
        n = self.dispatch_counts[op] - 1
        if n < len(faults) and faults[n]:
            # Validation defects apply to bad input, not automatically to a valid first request.
            invalid_sound = op == "scenarios_create" and "coughy" in __import__("json").dumps(args)
            invalid_xml = op == "scenarios_generate_bg" and any(str(f).endswith(".xml") for f in args.get("generation_files", []))
            if invalid_sound or invalid_xml or op not in ("scenarios_create", "scenarios_generate_bg"):
                raise ValidationError(faults[n])
        if op in ("aiagents_list", "aiagents_retrieve"):
            agents = copy.deepcopy([self.agent] + self.task["fixture"].get("other_agents", []))
            for agent in agents:
                # Desired caller values belong to the private fixture oracle. The
                # target may read registered variable definitions, not missing values.
                agent.pop("required_variables", None)
            if op == "aiagents_list":
                return {"results": agents}
            agent = next((a for a in agents if a["id"] == args.get("id")), None)
            if agent is None:
                raise ValidationError("404: unknown agent")
            return agent
        if op == "metrics_list":
            return {"results": copy.deepcopy(self.task["fixture"].get("metrics", []))}
        if op == "projects_retrieve":
            if args.get("id") != self.agent["project"]:
                raise ValidationError("404: unknown project")
            return {"id": self.agent["project"], "default_scenario_type": self.agent.get("default_scenario_type", "instruction"),
                    "supported_scenario_types": ["instruction", "conditional_actions"]}
        if op == "cekura_load_skill":
            requested = args.get("skill_name", "cekura-eval-design").split(":")[-1]
            if requested != "cekura-eval-design":
                from ..common import REPO
                path = REPO / "cekura/skills" / requested / "SKILL.md"
                if not path.is_file():
                    from pathlib import Path
                    path = Path("/home/agent/.claude/plugins/marketplaces/cekura-skills/cekura/skills") / requested / "SKILL.md"
                if requested not in ("cekura-generate-scenarios", "cekura-personality-design", "cekura-metric-design", "cekura-coordinator") or not path.is_file():
                    raise ValidationError("404: fixed skill unavailable")
                return {"skill_content": path.read_text(), "sha256": digest(path)}
        if op == "scenarios_generate_bg" and self.task.get("generation_jobs"):
            if args.get("agent_id", args.get("agent")) != self.agent["id"]:
                raise ValidationError("400: wrong agent")
            script = self.task["generation_jobs"][min(n, len(self.task["generation_jobs"]) - 1)]
            if args.get("num_scenarios") != script["requested_count"]:
                raise ValidationError("400: requested batch count differs from scripted job")
            progress = "fixture-job-" + str(self._id())
            self.jobs[progress] = {"polls": 0, "arguments": copy.deepcopy(args), "templates": script.get("rows", []), "rows": None, "script": script}
            return {"progress_id": progress}
        if op == "scenarios_generate_progress":
            job = self.jobs.get(args.get("progress_id"))
            if job and "script" in job:
                job["polls"] += 1
                s = job["script"]
                if job["polls"] <= s.get("processing_polls", 1):
                    return {"status": "processing", "completed_scenarios": 0, "total_scenarios": s["requested_count"]}
                if s.get("status") == "failed":
                    return {"status": "failed", "error": s["error"], "scenarios_list": [], "failed_scenarios": s["requested_count"]}
                if job["rows"] is None:
                    rows = []
                    for template in job["templates"]:
                        row = dict(copy.deepcopy(template), agent=self.agent["id"])
                        row.setdefault("folder_path", job["arguments"].get("folder_path"))
                        row.setdefault("personality", self.task["fixture"]["personalities"][0]["id"])
                        row.setdefault("test_profile", self.state["profiles"][0]["id"])
                        rows.append(self._create(row))
                    job["rows"] = rows
                return {"status": "completed", "total_scenarios": s["requested_count"], "completed_scenarios": len(job["rows"]),
                        "failed_scenarios": s["requested_count"] - len(job["rows"]), "errors": s.get("errors", []), "scenarios_list": copy.deepcopy(job["rows"])}
        return super()._dispatch(op, args)

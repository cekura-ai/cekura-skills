"""v3 bridge: the v2 real-backend bridge plus result reads, a non-dialing run stub and conditional follow-ups.

Real authoring sessions read past results and launch runs. Reads go to the isolated
backend unchanged. Every execution tool (``scenarios_run_*``, ``results_rerun_create``) is
answered by a recorded stub that never dials, never reaches a provider and returns a queued
result, so the size and consent of each requested run stay gradable. The simulated user's
next message is chosen here, from stored state, by the task's follow-up script.
"""
from __future__ import annotations

import copy
import json

from ..fixture import PREFIX
from ..v2.bridge import Bridge as V2Bridge, ToolError
from . import checks
from .followups import decide

READS = {"aiagents_list", "aiagents_retrieve", "scenarios_list", "scenarios_retrieve", "scenarios_folders_list", "test_profiles_list",
         "test_profiles_retrieve", "personalities_list", "personalities_retrieve", "metrics_list", "metrics_retrieve", "tools_list",
         "tools_retrieve", "projects_retrieve", "results_list", "results_retrieve", "runs_retrieve", "runs_bulk_retrieve",
         "scenarios_generate_progress", "cekura_load_skill", "cekura_skill_started"}
ALLOWED = READS | checks.WRITES


def is_run(op):
    return op.startswith("scenarios_run_") or op == "results_rerun_create"


class Bridge(V2Bridge):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed = ALLOWED
        self.state_reader, self.initial_state = None, None
        self.stub_results, self.position = {}, {"step": 0, "clarifications": 0}
        self.matched = set()

    def _dispatch(self, op, arguments):
        tool = self.catalog.get(op)
        if tool is not None and is_run(op):
            return self._stub_run(op, self._validated(tool, arguments))
        if op == "results_retrieve" and arguments.get("id") in self.stub_results:
            return copy.deepcopy(self.stub_results[arguments["id"]]), {"stub_result": arguments["id"]}, None
        for index, injection in enumerate(self.task.get("injections", [])):
            # A conditional injection fires on the first call whose arguments match, whenever it comes.
            if injection["operation"] == op and injection["occurrence"] == "first_matching" and index not in self.matched:
                args = self._validated(tool, arguments) if tool else arguments
                when = injection.get("when", "")
                if when.startswith("contains:") and when.split(":", 1)[1] in json.dumps(args):
                    self.matched.add(index)
                    return self._inject_before(injection, args)
        return super()._dispatch(op, arguments)

    def _validated(self, tool, arguments):
        import jsonschema
        try:
            jsonschema.validate(arguments, tool["inputSchema"])
        except jsonschema.ValidationError as error:
            raise ToolError("400: " + error.message)
        return {k: v for k, v in arguments.items() if k in tool["inputSchema"].get("properties", {}) and k != "skill_ack"}

    def _stub_run(self, op, args):
        state = self.state_reader() if self.state_reader else {"scenarios": [], "configuration": {"agents": []}}
        agents = {a["id"] for a in state.get("configuration", {}).get("agents", [])}
        rows = {r["id"]: r for r in state.get("scenarios", [])}
        if op == "results_rerun_create":
            raise ToolError("400: rerun is only available for results created in this workspace")
        agent = args.get("agent_id")
        if agent is None or agent not in agents:
            raise ToolError("400: {\"agent_id\": [\"A valid agent_id is required.\"]}")
        if args.get("scenarios"):
            selected = [int(i) for i in args["scenarios"] if str(i).isdigit()]
            unknown = [i for i in selected if i not in rows or rows[i]["agent"] != agent]
            if unknown:
                raise ToolError("400: {\"scenarios\": [\"Invalid scenario ids for this agent: %s\"]}" % ", ".join(map(str, unknown)))
        else:
            selected = [i for i, r in rows.items() if r["agent"] == agent
                        and (not args.get("folder_path") or str(r.get("folder_path", "")).startswith(str(args["folder_path"]).replace("/", ".")))
                        and (not args.get("tags") or set(args["tags"]) & set(r.get("tags") or []))]
        if not selected:
            raise ToolError("400: no scenarios match the request")
        multiplier = max(1, len(args.get("personality_ids") or [])) * max(1, len(args.get("test_profile_ids") or [])) * max(1, int(args.get("frequency") or 1))
        rid = 990000 + len(self.stub_results)
        value = {"id": rid, "status": "in_queue", "agent": agent, "total_runs": len(selected) * multiplier,
                 "runs": [{"scenario": i, "status": "in_queue"} for i in selected],
                 "message": "Runs queued. Results usually arrive within 10-20 minutes."}
        self.stub_results[rid] = dict(value, status="running")
        stub = {"operation": op, "agent": agent, "scenarios": selected, "calls": len(selected) * multiplier, "result_id": rid}
        return value, {"stub_run": stub, "dialled": False}, None

    # --- conditional follow-ups ----------------------------------------------------------------
    def next_prompt(self, turn, final_type, messages):
        with self.lock:
            ctx = {"task": self.task, "initial": self.initial_state, "final": self.state_reader(), "trace": self.trace,
                   "messages": messages, "final_type": final_type}
            message, decision = decide(self.task, self.position, ctx, turn)
            self.trace.append(dict(decision, sequence=len(self.trace)))
            return message

    def endpoint(self, method, path, body):
        if method == "POST" and path == "/followup":
            return {"message": self.next_prompt(int(body["turn"]), body.get("final_type"), body.get("messages", []))}, 200
        return super().endpoint(method, path, body)

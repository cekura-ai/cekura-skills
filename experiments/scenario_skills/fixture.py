"""Stateful local MCP fixture. No operation forwards to a real Cekura endpoint."""
from __future__ import annotations

import copy
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .common import digest

PREFIX = "mcp__cekura__"
OPERATIONS = (
    "cekura_load_skill", "cekura_skill_started", "aiagents_retrieve", "aiagents_list",
    "scenarios_list", "scenarios_retrieve", "scenarios_create", "scenarios_partial_update",
    "scenarios_generate_bg", "scenarios_generate_progress", "scenarios_destroy",
    "scenarios_duplicate_create", "scenarios_bulk_update", "scenarios_bulk_delete",
    "scenarios_folder_create", "scenarios_folders_list", "test_profiles_list",
    "test_profiles_retrieve", "test_profiles_create", "test_profiles_partial_update",
    "test_profiles_destroy", "personalities_list", "metrics_list", "tools_list", "tools_retrieve",
)


class ValidationError(ValueError):
    pass


def main_agent_variables(information):
    """Sectioned profiles send only main_agent_variables to the target agent."""
    if "main_agent_variables" in information or "testing_agent_variables" in information:
        return information.get("main_agent_variables", {})
    return information


def offline_catalog():
    """Protocol-test catalog only. Paid runs require the captured real schemas."""
    return [{"name": name, "description": "Offline fixture: " + name,
             "inputSchema": {"type": "object", "additionalProperties": True}} for name in OPERATIONS]


class Store:
    def __init__(self, task, files, catalog=None):
        self.task = copy.deepcopy(task)
        self.files = files
        fixture = task["fixture"]
        initial = task.get("starting_resources", fixture["resources"])
        self.state = copy.deepcopy(initial)
        for key in ("scenarios", "profiles", "folders"):
            self.state.setdefault(key, [])
        self.initial = copy.deepcopy(self.state)
        self.agent = copy.deepcopy(fixture["agent"])
        self.catalog = catalog if catalog is not None else offline_catalog()
        self.strict_schemas = catalog is not None
        self.trace = []
        self.jobs = {}
        self.next_id = fixture["next_id"]
        self.turn = 0
        self.lock = threading.Lock()

    def _id(self):
        self.next_id += 1
        return self.next_id

    def _record(self, kind, identifier):
        for row in self.state[kind]:
            if str(row["id"]) == str(identifier):
                return row
        raise ValidationError("404: Resource does not exist or was deleted")

    def _validate(self, row):
        if row.get("agent") != self.agent["id"]:
            raise ValidationError("400: agent does not belong to fixture scope")
        if row.get("project", self.agent["project"]) != self.agent["project"]:
            raise ValidationError("400: incorrect project scope")
        folder = row.get("folder_path", row.get("folder"))
        if not folder:
            raise ValidationError("400: select a folder")
        if not any(f["path"] == folder for f in self.state["folders"]):
            raise ValidationError("400: folder does not exist; create it before use")
        if row.get("personality") is not None:
            personality = next((p for p in self.task["fixture"]["personalities"] if p["id"] == row["personality"]), None)
            if personality is None or personality["language"] != row.get("scenario_language", self.agent["language"]):
                raise ValidationError("400: personality unavailable or language mismatch")
        if row.get("scenario_type", "instruction") == "conditional_actions":
            body = row.get("conditional_actions")
            if not isinstance(body, dict) or not body.get("conditions") or not row.get("scenario_language"):
                raise ValidationError("400: conditional_actions.conditions and scenario_language required")
            if row.get("instructions"):
                raise ValidationError("400: use conditional_actions or instructions, not both")
        elif not isinstance(row.get("instructions"), str) or not row["instructions"].strip():
            raise ValidationError("400: instructions must be a nonempty string")
        required = self.agent.get("required_variables", {})
        if required:
            profile = self._record("profiles", row.get("test_profile"))
            if profile.get("agent") != self.agent["id"] and profile.get("project") != self.agent["project"]:
                raise ValidationError("400: profile belongs to another agent")
            values = main_agent_variables(profile.get("information", {}))
            for name, value in required.items():
                if values.get(name) != value:
                    raise ValidationError("400: Missing or invalid case-sensitive profile variable: " + name)

    def _create(self, args):
        row = copy.deepcopy(args)
        row.pop("skill_ack", None)
        row["id"] = self._id()
        row.setdefault("scenario_type", "instruction")
        self._validate(row)
        self.state["scenarios"].append(row)
        return copy.deepcopy(row)

    def _update(self, args):
        row = self._record("scenarios", args.get("id"))
        merged = dict(row, **{k: copy.deepcopy(v) for k, v in args.items() if k not in ("id", "skill_ack")})
        self._validate(merged)
        row.clear()
        row.update(merged)
        return copy.deepcopy(row)

    def call(self, name, arguments):
        """Serialize mutations and capture full arguments/results, including errors."""
        with self.lock:
            operation = name.removeprefix(PREFIX)
            try:
                tool = next((t for t in self.catalog if t["name"].removeprefix(PREFIX) == operation), None)
                if tool is None:
                    raise ValidationError("403: tool unavailable in captured catalog")
                if self.strict_schemas:
                    import jsonschema
                    schema = tool["inputSchema"]
                    try:
                        jsonschema.validate(arguments, schema)
                    except jsonschema.ValidationError as error:
                        raise ValidationError("400: " + error.message) from error
                    # The server binds declared arguments; extra schema-permitted
                    # keys must not acquire invented fixture behavior.
                    effective = {k: v for k, v in arguments.items() if k in schema.get("properties", {})}
                else:
                    effective = arguments
                result = self._dispatch(operation, effective)
                response = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": False}
            except (ValidationError, KeyError, TypeError) as error:
                response = {"content": [{"type": "text", "text": str(error)}], "isError": True}
            self.trace.append({"sequence": len(self.trace), "turn": self.turn, "name": PREFIX + operation, "wire_name": name,
                               "arguments": copy.deepcopy(arguments), "response": copy.deepcopy(response)})
            return response

    def _dispatch(self, op, args):
        if op == "cekura_load_skill":
            if args.get("skill_name", "cekura-eval-design").split(":")[-1] != "cekura-eval-design":
                raise ValidationError("404: only selected skill is installed in this body experiment")
            return {"skill_content": self.files["SKILL.md"].decode(), "sha256": digest(self.files["SKILL.md"])}
        if op == "cekura_skill_started":
            return {"recorded_locally": True}
        if op in ("aiagents_retrieve", "aiagents_list"):
            if op.endswith("retrieve") and str(args.get("id")) != str(self.agent["id"]):
                raise ValidationError("404: unknown fixture agent")
            agent = copy.deepcopy(self.agent)
            return agent if op.endswith("retrieve") else {"results": [agent]}
        if op == "personalities_list":
            return {"results": copy.deepcopy(self.task["fixture"]["personalities"])}
        if op == "metrics_list":
            return {"results": []}
        if op in ("tools_list", "tools_retrieve"):
            tools = self.agent.get("mock_tools", [])
            if op == "tools_retrieve":
                tool = next((t for t in tools if t.get("id") == args["id"]), None)
                if tool is None:
                    raise ValidationError("404: unknown fixture mock tool")
                return copy.deepcopy(tool)
            return {"results": copy.deepcopy(tools)}
        if op == "scenarios_list":
            rows = self.state["scenarios"]
            agent = args.get("agent_id", args.get("agent"))
            if agent is not None:
                rows = [r for r in rows if str(r["agent"]) == str(agent)]
            if args.get("project_id", self.agent["project"]) != self.agent["project"]:
                rows = []
            if "folder_path" in args:
                rows = [r for r in rows if r.get("folder_path", r.get("folder")) == args["folder_path"]]
            return {"count": len(rows), "results": copy.deepcopy(rows)}
        if op == "scenarios_retrieve":
            return copy.deepcopy(self._record("scenarios", args["id"]))
        if op == "scenarios_create":
            return self._create(args)
        if op == "scenarios_partial_update":
            return self._update(args)
        if op == "scenarios_duplicate_create":
            if args["project"] != self.agent["project"] or args["copy_to_project"] != self.agent["project"]:
                raise ValidationError("403: cross-project duplication is outside this fixture")
            originals = [copy.deepcopy(self._record("scenarios", identifier)) for identifier in args["scenarios"]]
            folder = args.get("folder_path")
            if folder and not any(f["path"] == folder for f in self.state["folders"]):
                parent, _, name = folder.rpartition(".")
                self._dispatch("scenarios_folder_create", {"project_id": self.agent["project"], "name": name, "parent_path": parent})
            rows = []
            for row in originals:
                row.pop("id")
                row["name"] = "Copy of " + row["name"]
                if folder:
                    row["folder_path"] = folder
                if "scenario_agent" in args:
                    row["agent"] = args["scenario_agent"]
                rows.append(self._create(row))
            return rows
        if op == "scenarios_bulk_update":
            if args.get("agent") != self.agent["id"] and args.get("project") != self.agent["project"]:
                raise ValidationError("400: bulk update requires matching agent or project")
            # Validate the complete transaction before mutating any resource.
            updates = []
            for identifier in args["scenarios"]:
                row = copy.deepcopy(self._record("scenarios", identifier))
                row.update({k: copy.deepcopy(v) for k, v in args.items() if k not in (
                    "scenarios", "skill_ack", "append_instruction", "metric_ids_to_add", "metric_ids_to_remove", "tool_ids_to_add", "tool_ids_to_remove")})
                if "append_instruction" in args:
                    row["instructions"] = row.get("instructions", "") + args["append_instruction"]
                for field, prefix in (("metrics", "metric_ids"), ("tool_ids", "tool_ids")):
                    if prefix + "_to_add" in args or prefix + "_to_remove" in args:
                        row[field] = list(dict.fromkeys(row.get(field, []) + args.get(prefix + "_to_add", [])))
                        row[field] = [v for v in row[field] if v not in args.get(prefix + "_to_remove", [])]
                self._validate(row)
                updates.append(row)
            return [self._update(row) for row in updates]
        if op in ("scenarios_destroy", "scenarios_bulk_delete"):
            ids = args["scenarios"] if op == "scenarios_bulk_delete" else [args["id"]]
            if op == "scenarios_bulk_delete" and args.get("agent_id") != self.agent["id"] and args.get("project_id") != self.agent["project"]:
                raise ValidationError("400: bulk delete requires matching agent or project")
            rows = [self._record("scenarios", identifier) for identifier in ids]
            for row in rows:
                self.state["scenarios"].remove(row)
            return {"deleted": ids}
        if op == "scenarios_folder_create":
            if args.get("project_id") != self.agent["project"]:
                raise ValidationError("400: wrong project")
            name, parent = args["name"], args.get("parent_path", "")
            if not re.fullmatch(r"[\w ()-]+", name):
                raise ValidationError("400: invalid folder name")
            if parent and ("." in parent or not any(f["path"] == parent for f in self.state["folders"])):
                raise ValidationError("400: parent folder missing or nesting exceeds one level")
            path = parent + "." + name if parent else name
            if any(f["path"] == path for f in self.state["folders"]):
                raise ValidationError("400: folder already exists")
            row = {"id": self._id(), "name": name, "path": path}
            self.state["folders"].append(row)
            return copy.deepcopy(row)
        if op == "scenarios_folders_list":
            rows = self.state["folders"] if args.get("project_id") == self.agent["project"] else []
            if "parent_path" in args:
                rows = [r for r in rows if r["path"].rpartition(".")[0] == args["parent_path"]]
            if args.get("search"):
                rows = [r for r in rows if args["search"].lower() in r["name"].lower()]
            return {"results": copy.deepcopy(rows)}
        if op == "scenarios_generate_bg":
            if args.get("agent_id", args.get("agent")) != self.agent["id"]:
                raise ValidationError("400: wrong agent")
            templates = self.task.get("generator_response", [])
            if args.get("num_scenarios") != len(templates):
                raise ValidationError("400: fixed generator fixture requires the requested scenario count")
            progress = "fixture-job-" + str(self._id())
            self.jobs[progress] = {"polls": 0, "arguments": copy.deepcopy(args), "templates": templates, "rows": None}
            return {"progress_id": progress}
        if op == "scenarios_generate_progress":
            job = self.jobs.get(args.get("progress_id"))
            if job is None:
                raise ValidationError("404: unknown generation job")
            job["polls"] += 1
            if job["polls"] == 1:
                return {"status": "processing", "completed_scenarios": 0, "total_scenarios": len(job["templates"])}
            if job["rows"] is None:
                created = []
                for template in job["templates"]:
                    payload = copy.deepcopy(template)
                    payload.setdefault("agent", self.agent["id"])
                    payload.setdefault("folder_path", job["arguments"].get("folder_path"))
                    payload.setdefault("personality", self.task["fixture"]["personalities"][0]["id"])
                    payload.setdefault("test_profile", job["arguments"].get("test_profile", self.task["fixture"]["resources"]["profiles"][0]["id"]))
                    created.append(self._create(payload))
                job["rows"] = created
            return {"status": "completed", "total_scenarios": len(job["rows"]), "completed_scenarios": len(job["rows"]),
                    "failed_scenarios": 0, "scenarios_list": copy.deepcopy(job["rows"])}
        if op.startswith("test_profiles_"):
            action = op[len("test_profiles_"):]
            if action == "list":
                rows = self.state["profiles"]
                if "agent_id" in args:
                    rows = [r for r in rows if r.get("agent") == args["agent_id"] or r.get("project") == self.agent["project"] and args["agent_id"] == self.agent["id"]]
                if "project_id" in args:
                    rows = [r for r in rows if args["project_id"] == self.agent["project"]]
                if args.get("ids"):
                    rows = [r for r in rows if str(r["id"]) in args["ids"].split(",")]
                if args.get("search"):
                    rows = [r for r in rows if args["search"].lower() in r.get("name", "").lower() or args["search"] == str(r["id"])]
                return {"results": copy.deepcopy(rows)}
            if action == "retrieve":
                return copy.deepcopy(self._record("profiles", args["id"]))
            if action == "destroy":
                self.state["profiles"].remove(self._record("profiles", args["id"]))
                return {"deleted": args["id"]}
            if action == "create":
                if (args.get("agent") != self.agent["id"] and args.get("project") != self.agent["project"]) or not isinstance(args.get("information"), dict):
                    raise ValidationError("400: profile agent and information required")
                row = dict(copy.deepcopy(args), id=self._id())
                row.pop("skill_ack", None)
                self.state["profiles"].append(row)
                return copy.deepcopy(row)
            if action == "partial_update":
                row = self._record("profiles", args["id"])
                row.update({k: copy.deepcopy(v) for k, v in args.items() if k not in ("id", "skill_ack")})
                return copy.deepcopy(row)
        raise ValidationError("403: unsupported fixture operation; no production fallback")


class FixtureServer:
    def __init__(self, store, host="127.0.0.1"):
        self.store = store
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                try:
                    if self.path != "/mcp":
                        self.send_error(404)
                        return
                    request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    method = request["method"]
                    if method == "initialize":
                        result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                                  "serverInfo": {"name": "cekura-synthetic-fixture", "version": "1"}}
                    elif method.startswith("notifications/"):
                        self.send_response(202)
                        self.end_headers()
                        return
                    elif method == "tools/list":
                        result = {"tools": owner.store.catalog}
                    elif method == "tools/call":
                        params = request["params"]
                        result = owner.store.call(params["name"], params.get("arguments", {}))
                    else:
                        raise ValidationError("Unknown MCP method")
                    payload = json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": result}, ensure_ascii=False).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (ValueError, KeyError, TypeError):
                    self.send_error(400)

        self.server = ThreadingHTTPServer((host, 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self):
        return "http://127.0.0.1:%d/mcp" % self.server.server_port

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

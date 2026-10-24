"""Host-side MCP bridge from the target's tool calls to the isolated real backend.

The production MCP server (outside this repository) turns tool calls into REST requests
against the API. This bridge reproduces that layer from the pinned backend's own OpenAPI
operations: arguments are validated against the captured tool schemas, path and query
parameters go where the operation declares them, the rest is the JSON body, and the
caller is the seeded owner with the product chat's MCP token and conversation header.
It is a reconstruction of the MCP layer, not its code; the REST handlers, persistence,
Celery jobs and generator behind it are the pinned backend's.

Only the operations the synthetic fixture supports are reachable; everything else,
including any voice execution, is refused identically for every arm. Exceptional
conditions come only from the task's frozen ``injections`` and ``events`` and every
application is recorded in the trace.
"""
from __future__ import annotations

import copy
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import jsonschema

from ..common import REPO, digest
from ..fixture import OPERATIONS, PREFIX
from ..gateway import read_request

ALLOWED = set(OPERATIONS) | {"projects_retrieve"}
LOCAL = {"cekura_load_skill", "cekura_skill_started"}
FIXED_SKILLS = ("cekura-generate-scenarios", "cekura-personality-design", "cekura-metric-design", "cekura-coordinator")


def operations(spec):
    """Tool name → (method, path template, path params, query params) from the pinned OpenAPI spec."""
    table = {}
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if not isinstance(op, dict) or not op.get("x-mcp-expose"):
                continue
            name = op.get("x-mcp-tool-name") or op["operationId"].replace("-", "_")
            params = op.get("parameters", [])
            table[name] = {"method": method.upper(), "path": path,
                           "path_params": [p["name"] for p in params if p["in"] == "path"],
                           "query_params": [p["name"] for p in params if p["in"] == "query"]}
    return table


def finished(progress):
    status = str(progress.get("status", "")).lower()
    total, done, failed = (progress.get(k) or 0 for k in ("total_scenarios", "completed_scenarios", "failed_scenarios"))
    return status in ("completed", "failed") or (total and done + failed >= total)


class Bridge:
    def __init__(self, task, base_url, session, catalog, files, table):
        self.task, self.base_url, self.session = copy.deepcopy(task), base_url, session
        self.catalog = {t["name"]: t for t in catalog}
        self.files, self.table = files, table
        self.trace, self.turn, self.lock = [], 0, threading.Lock()
        self.counts, self.applied, self.rewrites, self.injected_jobs = {}, set(), {}, {}
        self.initial_ids = set()
        self.allowed = ALLOWED
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # --- REST ---------------------------------------------------------------------------
    def rest(self, method, path, query=None, body=None):
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode({k: (",".join(map(str, v)) if isinstance(v, list) else v) for k, v in query.items()})
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": "Bearer " + self.session["token"], "X-Cekura-Conversation-Id": self.session["conversation"],
            "Content-Type": "application/json", "Accept": "application/json"})
        started = time.monotonic()
        try:
            with self.http.open(request, timeout=120) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        text = raw.decode("utf-8", "replace")
        try:
            value = json.loads(text) if text.strip() else {}
        except ValueError:
            value = {"non_json_body": text[:4000]}
        return status, value, {"method": method, "path": path, "query": query or {}, "status": status, "elapsed": round(time.monotonic() - started, 3)}

    # --- MCP tools ----------------------------------------------------------------------
    def call(self, name, arguments, turn):
        with self.lock:
            self.turn = turn
            op = name.removeprefix(PREFIX)
            record = {"sequence": len(self.trace), "turn": turn, "name": PREFIX + op, "wire_name": name, "arguments": copy.deepcopy(arguments)}
            try:
                result, backend, injection = self._dispatch(op, arguments)
                response = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": False}
            except ToolError as error:
                response, backend, injection = {"content": [{"type": "text", "text": str(error)}], "isError": True}, error.backend, error.injection
            record.update(response=response, backend=backend)
            if injection:
                record["injection"] = injection
            if op == "scenarios_generate_bg" and not response["isError"]:
                docs = {d["name"]: d for d in self.task.get("documents", [])}
                record["resolved_sources"] = [{"name": d["name"], "sha256": digest(d["content"].encode())} for f in arguments.get("generation_files", [])
                                              if (d := docs.get(str(f).rsplit("/", 1)[-1]))]
            self.trace.append(record)
            self.apply_events(turn, "after_call", op)
            return response, any(e.get("kind") == "cancel" and e.get("turn") == turn for e in self.trace)

    def _dispatch(self, op, arguments):
        tool = self.catalog.get(op)
        if tool is None or op not in self.allowed:
            raise ToolError("403: operation unavailable in the isolated experiment")
        schema = tool["inputSchema"]
        try:
            jsonschema.validate(arguments, schema)
        except jsonschema.ValidationError as error:
            raise ToolError("400: " + error.message)
        args = {k: v for k, v in arguments.items() if k in schema.get("properties", {}) and k != "skill_ack"}
        if op in LOCAL:
            return self._local(op, args), None, None
        n = self.counts[op] = self.counts.get(op, 0) + 1
        for injection in self.task.get("injections", []):
            if injection["operation"] == op and injection["occurrence"] == n - 1:
                early = self._inject_before(injection, args)
                if early is not None:
                    return early
                break
        else:
            injection = None
        if injection and injection["effect"] not in ("drop_last", "override_field"):
            injection = None  # A request-time injection whose condition did not match.
        if op == "scenarios_generate_progress" and args.get("progress_id") in self.injected_jobs:
            job = self.injected_jobs[args["progress_id"]]
            return job["progress"], None, job["injection"]
        spec = self.table.get(op)
        if spec is None:
            raise ToolError("403: operation unavailable in the isolated experiment")
        path = spec["path"]
        for name in spec["path_params"]:
            if name not in args:
                raise ToolError("400: missing path parameter " + name)
            path = path.replace("{%s}" % name, urllib.parse.quote(str(args.pop(name)), safe=""))
        query = {k: args.pop(k) for k in list(args) if k in spec["query_params"]}
        body = args if spec["method"] in ("POST", "PATCH", "PUT") else None
        status, value, backend = self.rest(spec["method"], path, query, body)
        if status >= 400:
            raise ToolError("%d: %s" % (status, json.dumps(value, ensure_ascii=False)[:4000]), backend)
        if op == "scenarios_generate_bg" and injection:
            self.rewrites[value.get("progress_id")] = injection
            injection = dict(injection, applied="pending completion")
        if op == "scenarios_generate_progress" and query.get("progress_id") in self.rewrites and finished(value):
            value, injection = self._rewrite(query["progress_id"], value)
        return value, backend, injection

    def _inject_before(self, injection, args):
        """Injections decided at request time; ``None`` lets the real request proceed."""
        effect = injection["effect"]
        if effect == "reject":
            when = injection.get("when", "")
            matched = (when == "xml_attachment" and any(str(f).lower().endswith(".xml") for f in args.get("generation_files", []))) or (
                when.startswith("contains:") and when.split(":", 1)[1] in json.dumps(args))
            if matched:
                raise ToolError(injection["error"], injection=dict(injection, applied="rejected before forwarding"))
            return None
        if effect == "fail_job":
            progress_id = "injected-" + digest([self.task["id"], injection, len(self.injected_jobs)])[:24]
            count = args.get("num_scenarios", injection["requested_count"])
            self.injected_jobs[progress_id] = {"injection": dict(injection, applied="generation not forwarded"), "progress": {
                "agent_id": self.task["fixture"]["agent"]["id"], "status": "failed", "total_scenarios": count, "completed_scenarios": 0,
                "failed_scenarios": count, "scenarios_list": [], "errors": [injection["error"]], "session_id": None}}
            return {"progress_id": progress_id, "session_id": None}, None, self.injected_jobs[progress_id]["injection"]
        return None  # drop_last and override_field act on the real job's completion

    def _rewrite(self, progress_id, value):
        """Apply a completion-time injection once through the real API, then report it consistently."""
        injection = self.rewrites[progress_id]
        if "applied_at" not in injection:
            rows = value.get("scenarios_list") or []
            changes = []
            if injection["effect"] == "drop_last":
                for row in rows[-injection["count"]:]:
                    status, _, backend = self.rest("DELETE", "/test_framework/v2/scenarios/%d/" % row["id"])
                    changes.append({"deleted": row["id"], "status": status})
                injection["dropped_ids"] = [row["id"] for row in rows[-injection["count"]:]]
            elif injection["effect"] == "override_field" and len(rows) > injection["index"]:
                row = rows[injection["index"]]
                status, _, backend = self.rest("PATCH", "/test_framework/v2/scenarios/%d/" % row["id"], body={injection["field"]: injection["value"]})
                changes.append({"patched": row["id"], "field": injection["field"], "status": status})
                injection["patched_id"] = row["id"]
            injection.update(applied_at=time.time(), changes=changes)
        value = copy.deepcopy(value)
        rows = value.get("scenarios_list") or []
        if injection["effect"] == "drop_last":
            value["scenarios_list"] = [r for r in rows if r.get("id") not in injection.get("dropped_ids", [])]
            dropped = len(rows) - len(value["scenarios_list"])
            value["completed_scenarios"] = max(0, (value.get("completed_scenarios") or 0) - dropped)
            value["failed_scenarios"] = (value.get("failed_scenarios") or 0) + dropped
            value["errors"] = list(value.get("errors") or []) + injection.get("errors", [])
        elif injection["effect"] == "override_field":
            for r in rows:
                if r.get("id") == injection.get("patched_id"):
                    r[injection["field"]] = injection["value"]
        return value, dict(injection)

    def _local(self, op, args):
        """MCP-server-level tools: they never reached the backend in production either."""
        if op == "cekura_skill_started":
            return {"recorded_locally": True}
        requested = args.get("skill_name", "cekura-eval-design").split(":")[-1]
        if requested == "cekura-eval-design":
            return {"skill_content": self.files["SKILL.md"].decode(), "sha256": digest(self.files["SKILL.md"])}
        path = REPO / "cekura/skills" / requested / "SKILL.md"
        if requested not in FIXED_SKILLS or not path.is_file():
            raise ToolError("404: fixed skill unavailable")
        return {"skill_content": path.read_text(), "sha256": digest(path)}

    # --- external events ----------------------------------------------------------------
    def apply_events(self, turn, boundary="before_turn", operation=None):
        for index, event in enumerate(self.task.get("events", [])):
            if index in self.applied or event.get("turn") != turn or event.get("boundary", "before_turn") != boundary:
                continue
            if event.get("operation") and event["operation"] != operation:
                continue
            self.applied.add(index)
            if event["kind"] == "external_delete":
                ids = event.get("ids", [])
                if event.get("created_only"):
                    project = self.task["fixture"]["agent"]["project"]
                    _, listing, _ = self.rest("GET", "/test_framework/v2/scenarios/", {"project_id": project, "page_size": 200})
                    rows = listing.get("results", listing) if isinstance(listing, dict) else listing
                    ids = [r["id"] for r in rows if r["id"] not in self.initial_ids]
                results = [self.rest("DELETE", "/test_framework/v2/scenarios/%d/" % i)[0] for i in ids]
                self.trace.append({"kind": "external_delete", "turn": turn, "ids": ids, "statuses": results, "sequence": len(self.trace)})
            elif event["kind"] == "cancel":
                self.trace.append({"kind": "cancel", "turn": turn, "sequence": len(self.trace)})
            else:
                raise ValueError("Unsupported external event: " + event["kind"])
        return any(e.get("kind") == "cancel" and e.get("turn") == turn for e in self.trace)

    # --- relay endpoint -----------------------------------------------------------------
    def handle(self, connection):
        """One JSON request per connection from the in-sandbox forwarding store."""
        connection.settimeout(300)
        stream = connection.makefile("rb")
        try:
            request = read_request(stream)
            if request is None:
                return
            (method, path, _), headers = request
            body = json.loads(stream.read(int(headers.get("content-length", "0"))) or b"{}")
            value, status = self.endpoint(method, path, body)
            data = json.dumps(value, ensure_ascii=False).encode()
            connection.sendall(b"HTTP/1.1 %d X\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % (status, len(data)) + data)
        finally:
            stream.close()


    def endpoint(self, method, path, body):
        if method != "POST" or path not in ("/call", "/events"):
            return {"error": "unknown bridge endpoint"}, 404
        if path == "/call":
            response, cancel = self.call(body["name"], body.get("arguments", {}), int(body["turn"]))
            return {"response": response, "cancel": cancel}, 200
        return {"cancel": self.apply_events(int(body["turn"]), body.get("boundary", "before_turn"))}, 200


class ToolError(Exception):
    def __init__(self, message, backend=None, injection=None):
        super().__init__(message)
        self.backend, self.injection = backend, injection

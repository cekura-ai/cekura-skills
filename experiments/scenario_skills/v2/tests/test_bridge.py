"""Bridge routing, recorded injections and the two-service relay, against an in-memory REST fake."""
import asyncio
import copy
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.scenario_skills.common import ROOT
from experiments.scenario_skills.modal_runtime import relay_connections
from experiments.scenario_skills.skill import material
from experiments.scenario_skills.v2.bridge import Bridge
from experiments.scenario_skills.v2.dataset import load

TABLE = {
    "scenarios_generate_bg": {"method": "POST", "path": "/test_framework/v2/scenarios/generate-bg/", "path_params": [], "query_params": []},
    "scenarios_generate_progress": {"method": "GET", "path": "/test_framework/v2/scenarios/generate-progress/", "path_params": [], "query_params": ["progress_id"]},
    "scenarios_create": {"method": "POST", "path": "/test_framework/v2/scenarios/", "path_params": [], "query_params": []},
    "scenarios_list": {"method": "GET", "path": "/test_framework/v2/scenarios/", "path_params": [], "query_params": ["project_id", "agent_id"]},
    "scenarios_retrieve": {"method": "GET", "path": "/test_framework/v2/scenarios/{id}/", "path_params": ["id"], "query_params": []}}
CATALOG = [{"name": name, "inputSchema": {"type": "object", "properties": props, "required": required}} for name, props, required in (
    ("scenarios_generate_bg", {"agent_id": {"type": "integer"}, "num_scenarios": {"type": "integer"}, "extra_instructions": {"type": "string"},
                               "generation_files": {"type": "array", "items": {"type": "string"}}, "skill_ack": {"type": "string"}}, ["agent_id"]),
    ("scenarios_generate_progress", {"progress_id": {"type": "string"}}, ["progress_id"]),
    ("scenarios_create", {"agent": {"type": "integer"}, "name": {"type": "string"}, "instructions": {"type": "string"}}, ["agent"]),
    ("scenarios_list", {"project_id": {"type": "integer"}}, []),
    ("scenarios_retrieve", {"id": {"type": "integer"}}, ["id"]),
    ("scenarios_run_voice", {"scenarios": {"type": "array"}}, []),
    ("cekura_load_skill", {"skill_name": {"type": "string"}}, []))]


class FakeBackend(Bridge):
    """Real Bridge logic; only HTTP is replaced by an in-memory backend that completes jobs on the second poll."""
    def __init__(self, task):
        super().__init__(task, "http://backend.invalid", {"token": "t", "conversation": "c"}, CATALOG, material(), TABLE)
        self.rows, self.jobs, self.calls, self.next = {}, {}, [], 900

    def rest(self, method, path, query=None, body=None):
        self.calls.append((method, path, query, body))
        meta = {"method": method, "path": path, "status": 200}
        if path.endswith("generate-bg/"):
            self.jobs["job-%d" % len(self.jobs)] = {"n": body["num_scenarios"], "polls": 0, "ids": []}
            return 200, {"progress_id": "job-%d" % (len(self.jobs) - 1), "session_id": None}, meta
        if path.endswith("generate-progress/"):
            job = self.jobs[query["progress_id"]]
            job["polls"] += 1
            if job["polls"] < 2:
                return 200, {"total_scenarios": job["n"], "completed_scenarios": 0, "failed_scenarios": 0, "scenarios_list": []}, meta
            while len(job["ids"]) < job["n"]:
                self.next += 1
                self.rows[self.next] = {"id": self.next, "expected_outcome_prompt": "Generated outcome"}
                job["ids"].append(self.next)
            return 200, {"total_scenarios": job["n"], "completed_scenarios": job["n"], "failed_scenarios": 0,
                         "scenarios_list": [copy.deepcopy(self.rows[i]) for i in job["ids"] if i in self.rows]}, meta
        if method == "DELETE":
            self.rows.pop(int(path.rstrip("/").rsplit("/", 1)[1]), None)
            return 204, {}, meta
        if method == "PATCH":
            row = self.rows[int(path.rstrip("/").rsplit("/", 1)[1])]
            row.update(body)
            return 200, row, meta
        if method == "GET" and path.endswith("/scenarios/"):
            return 200, {"results": list(self.rows.values())}, meta
        if method == "POST":
            self.next += 1
            self.rows[self.next] = dict(body, id=self.next)
            return 201, self.rows[self.next], meta
        return 404, {"detail": "not found"}, meta


class TextProcess:
    """Modal exec streams are text; asyncio subprocess pipes are bytes."""
    def __init__(self, process):
        self.process, self.stdin = process, self

    def write(self, line):
        self.process.stdin.write(line.encode() if isinstance(line, str) else line)

    async def drain(self):
        await self.process.stdin.drain()

    @property
    def stdout(self):
        async def lines():
            async for line in self.process.stdout:
                yield line.decode()
        return lines()


def task(task_id):
    return copy.deepcopy(next(t for t in load() if t["id"] == task_id))


def text(response):
    return json.loads(response["content"][0]["text"])


class BridgeTests(unittest.TestCase):
    def test_partial_batch_is_applied_through_the_api_and_recorded(self):
        bridge = FakeBackend(task("repair-0"))
        progress = text(bridge.call("mcp__cekura__scenarios_generate_bg", {"agent_id": 103200, "num_scenarios": 3}, 0)[0])["progress_id"]
        bridge.call("scenarios_generate_progress", {"progress_id": progress}, 0)
        done = text(bridge.call("scenarios_generate_progress", {"progress_id": progress}, 0)[0])
        self.assertEqual((done["completed_scenarios"], done["failed_scenarios"], len(done["scenarios_list"])), (2, 1, 2))
        self.assertIn("missing application evidence", done["errors"][0])
        self.assertEqual(len(bridge.rows), 2)  # The dropped row was deleted through the real API.
        again = text(bridge.call("scenarios_generate_progress", {"progress_id": progress}, 0)[0])
        self.assertEqual(again["scenarios_list"], done["scenarios_list"])
        self.assertEqual([c["injection"]["effect"] for c in bridge.trace if c.get("injection")], ["drop_last", "drop_last", "drop_last"])
        # The retry is ordinary real generation: occurrence 1 has no injection.
        progress = text(bridge.call("scenarios_generate_bg", {"agent_id": 103200, "num_scenarios": 1}, 1)[0])["progress_id"]
        bridge.call("scenarios_generate_progress", {"progress_id": progress}, 1)
        self.assertEqual(text(bridge.call("scenarios_generate_progress", {"progress_id": progress}, 1)[0])["completed_scenarios"], 1)
        self.assertFalse(bridge.trace[-1].get("injection"))

    def test_failed_job_is_never_forwarded_and_reports_terminal_failure(self):
        bridge = FakeBackend(task("repair-2"))
        progress = text(bridge.call("scenarios_generate_bg", {"agent_id": 103300, "num_scenarios": 1}, 0)[0])["progress_id"]
        state = text(bridge.call("scenarios_generate_progress", {"progress_id": progress}, 0)[0])
        self.assertEqual((state["status"], state["failed_scenarios"]), ("failed", 1))
        self.assertFalse(any(c[1].endswith("generate-bg/") for c in bridge.calls))

    def test_rejection_only_when_condition_matches_and_bad_output_override_is_visible(self):
        bridge = FakeBackend(task("sources-2"))
        response, _ = bridge.call("scenarios_generate_bg", {"agent_id": 101700, "num_scenarios": 1, "generation_files": ["/app/uploads/policy.xml"]}, 0)
        self.assertTrue(response["isError"])
        self.assertIn("XML", response["content"][0]["text"])
        response, _ = bridge.call("scenarios_generate_bg", {"agent_id": 101700, "num_scenarios": 1, "extra_instructions": "converted"}, 0)
        self.assertFalse(response["isError"])
        bridge = FakeBackend(task("grounding-0"))
        progress = text(bridge.call("scenarios_generate_bg", {"agent_id": 102000, "num_scenarios": 1}, 0)[0])["progress_id"]
        bridge.call("scenarios_generate_progress", {"progress_id": progress}, 0)
        done = text(bridge.call("scenarios_generate_progress", {"progress_id": progress}, 0)[0])
        self.assertIn("guaranteed appointment", done["scenarios_list"][0]["expected_outcome_prompt"])
        self.assertIn("guaranteed appointment", next(iter(bridge.rows.values()))["expected_outcome_prompt"])

    def test_external_deletion_and_unsupported_or_invalid_calls(self):
        bridge = FakeBackend(task("lifecycle-0"))
        bridge.rows[101211] = {"id": 101211}
        bridge.initial_ids = {101211}
        bridge.call("scenarios_create", {"agent": 101200, "name": "x", "instructions": "y"}, 0)
        bridge.apply_events(1)
        self.assertEqual(set(bridge.rows), {101211})
        self.assertEqual(bridge.trace[-1]["kind"], "external_delete")
        for name, args in (("scenarios_run_voice", {}), ("unknown_tool", {}), ("scenarios_create", {"name": 3})):
            response, _ = bridge.call(name, args, 1)
            self.assertTrue(response["isError"])
        self.assertTrue(all("generate-bg" not in c[1] for c in bridge.calls))
        self.assertIn("skill_content", text(bridge.call("cekura_load_skill", {"skill_name": "cekura:cekura-eval-design"}, 1)[0]))

    def test_skill_ack_is_recorded_but_not_forwarded(self):
        bridge = FakeBackend(task("routing-0"))
        bridge.call("scenarios_generate_bg", {"agent_id": 100000, "num_scenarios": 2, "skill_ack": "ack:x"}, 0)
        self.assertNotIn("skill_ack", bridge.calls[0][3])
        self.assertEqual(bridge.trace[0]["arguments"]["skill_ack"], "ack:x")

    def test_two_service_relay_reaches_gateway_and_bridge(self):
        bridge = FakeBackend(task("routing-0"))
        served = []

        class Gateway:
            def handle(self, stream):
                served.append(stream.recv(100))
                stream.sendall(b"model-ok")

        async def scenario():
            process = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / "relay.py"), "--services", "model,mcp",
                                                           stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            ready = asyncio.get_running_loop().create_future()
            relay = asyncio.create_task(relay_connections(TextProcess(process), Gateway(), ready, bridge))
            ports = await asyncio.wait_for(ready, 10)

            def client():
                import socket
                from experiments.scenario_skills.v2.bridge_client import ForwardingStore
                with patch.dict(os.environ, {"BENCHMARK_BRIDGE_PORT": str(ports["mcp"])}):
                    store = ForwardingStore({}, {}, CATALOG)
                    store.turn = 2
                    response = store.call("scenarios_generate_bg", {"agent_id": 100000, "num_scenarios": 2})
                    store.apply_events(2)
                s = socket.create_connection(("127.0.0.1", ports["model"]))
                s.sendall(b"tls-bytes")
                reply = s.recv(100)
                s.close()
                return response, reply
            response, reply = await asyncio.to_thread(client)
            process.stdin.close()
            process.kill()
            await process.wait()
            relay.cancel()
            await asyncio.gather(relay, return_exceptions=True)
            return response, reply
        response, reply = asyncio.run(scenario())
        self.assertEqual(text(response)["progress_id"], "job-0")
        self.assertEqual((reply, served), (b"model-ok", [b"tls-bytes"]))
        self.assertEqual(bridge.trace[0]["turn"], 2)


if __name__ == "__main__":
    unittest.main()

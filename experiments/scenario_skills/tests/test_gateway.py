"""Offline tests of actual TLS transport and spending admission, never inference."""
import copy
import io
import json
import socket
import ssl
import tempfile
import threading
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, ProxyHandler, HTTPSHandler, build_opener

from experiments.scenario_skills.budget import BudgetError, Ledger
from experiments.scenario_skills.common import digest, read, write
from experiments.scenario_skills.gateway import AdmissionGateway, body_section, extract_usage, request_bound, usage_charge, validate_admission
from experiments.scenario_skills.modal_runtime import infrastructure_bound
from experiments.scenario_skills.modal_probe import RATES
from experiments.scenario_skills.preflight import preflight


def section():
    return {"model": "fixed-model", "credential_env": "CEKURA_GATEWAY_TEST_KEY", "billing_usage_verified": True,
            "rates": {"input_per_million": 4.5, "cached_input_per_million": .45, "output_per_million": 22.5},
            "admission": {"input_token_limit": 256000, "output_token_limit": 32000,
                          "token_bound_evidence": "Synthetic provider limit for offline tests",
                          "hard_cap": {"verified": True, "experiment_exclusive": True, "remaining_usd": 20,
                                       "evidence": "Synthetic exclusive allocation", "credential_sha256": digest(b"test")}}}


class Response(io.BytesIO):
    status, reason = 200, "OK"

    def getheaders(self):
        return [("Content-Type", "text/event-stream")]

    def getheader(self, name, default=None):
        return dict(self.getheaders()).get(name, default)


class Transport:
    def __init__(self, body, received):
        self.body, self.received = body, received

    def request(self, method, path, body, headers):
        self.received.append({"body": body, "path": path, "headers": headers})

    def getresponse(self):
        return Response(self.body)

    def close(self):
        pass


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cekura-gateway-tests-")
        self.directory = Path(self.temporary.name)
        self.ledger = Ledger(self.directory / "budget.json")
        self.received = []

    def tearDown(self):
        self.temporary.cleanup()

    def gateway(self, response, **kwargs):
        return AdmissionGateway("model.example", "/inference/v1/chat/completions", "chat", section(), self.ledger,
                                "task", self.directory / "gateway", transport=lambda: Transport(response, self.received), **kwargs)

    def call(self, gateway, payload, auth_header=b"Authorization: Bearer test"):
        # Establish the same CONNECT + trusted TLS handshake as the runtime.
        sock = socket.create_connection(("127.0.0.1", gateway.port), timeout=5)
        sock.sendall(b"CONNECT model.example:443 HTTP/1.1\r\nHost: model.example:443\r\n\r\n")
        stream = sock.makefile("rb")
        self.assertIn(b"200", stream.readline())
        self.assertEqual(stream.readline(), b"\r\n")
        stream.close()
        ctx = ssl.create_default_context(cafile=str(gateway.ca))
        with ctx.wrap_socket(sock, server_hostname="model.example") as tls:
            request = (b"POST /inference/v1/chat/completions HTTP/1.1\r\nHost: model.example\r\n"
                       b"Content-Type: application/json\r\n" + auth_header + b"\r\nContent-Length: "
                       + str(len(payload)).encode() + b"\r\n\r\n" + payload)
            tls.sendall(request)
            data = bytearray()
            while True:
                chunk = tls.recv(65536)
                if not chunk:
                    break
                data.extend(chunk)
            return bytes(data)

    def test_tls_stream_preserves_large_json_request_and_response_usage(self):
        usage = {"prompt_tokens": 1000, "completion_tokens": 50, "prompt_tokens_details": {"cached_tokens": 500}}
        response = b'data: {"choices":[{"delta":{"content":"saved"}}]}\n\n' + b"data: " + json.dumps({"usage": usage}).encode() + b"\n\ndata: [DONE]\n\n"
        payload = json.dumps({"model": "fixed-model", "messages": [{"role": "user", "content": "é" * 70000}], "stream": True}, ensure_ascii=False).encode()
        with self.gateway(response) as gateway, patch.dict("os.environ", {"CEKURA_GATEWAY_TEST_KEY": "test"}):
            result = self.call(gateway, payload)
        self.assertIn(b"saved", result)
        self.assertEqual(self.received[0]["body"], payload)
        self.assertEqual(read(self.directory / "gateway/request-1/request.json")["body_sha256"], digest(payload))
        self.assertNotIn("authorization", read(self.directory / "gateway/request-1/request.json")["headers"])
        self.assertEqual(gateway.cost, Decimal("0.003600"))
        self.assertEqual((self.directory / "gateway/request-1/response.body").read_bytes(), response)

    def test_budget_exhaustion_never_opens_upstream(self):
        self.ledger.reserve("prior", "target", 19.5)  # Leaves less than one body-sized request.
        payload = b'{"model":"fixed-model","messages":[]}'
        with self.gateway(b"", verify=False) as gateway:
            self.assertIn(b"402", self.call(gateway, payload))
        self.assertEqual(self.received, [])
        self.assertIn("budget_admission_denied", gateway.errors)

    def test_missing_usage_retains_request_reservation_and_blocks_retries(self):
        payload = b'{"model":"fixed-model","messages":[]}'
        with self.gateway(b'data: {"choices":[]}\n\ndata: [DONE]\n\n', verify=False) as gateway:
            self.call(gateway, payload)
            self.assertIn(b"402", self.call(gateway, payload))
        self.assertIsNone(gateway.cost)
        self.assertTrue(self.ledger.state["blocked"])
        self.assertEqual(len(self.received), 1)
        # Reserved from the body (bytes + template tokens), not the 256k context limit.
        self.assertEqual(self.ledger.total(), request_bound(json.loads(payload), body_section(section(), payload)))
        self.assertLess(self.ledger.total(), Decimal("1.872"))

    def test_wrong_model_and_production_host_are_not_forwarded(self):
        with self.gateway(b"", verify=False) as gateway:
            self.assertIn(b"403", self.call(gateway, b'{"model":"other"}'))
            with socket.create_connection(("127.0.0.1", gateway.port)) as sock:
                sock.sendall(b"CONNECT api.cekura.ai:443 HTTP/1.1\r\n\r\n")
                self.assertIn(b"403", sock.recv(100))
        self.assertEqual(self.received, [])

    def test_inclusive_cache_usage_and_response_api_events(self):
        cfg = section()
        usage = {"input_tokens": 100, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 50}}
        response = b'data: {"type":"response.completed","response":' + json.dumps({"usage": usage}).encode() + b"}\n\n"
        self.assertEqual(extract_usage(response, "text/event-stream", "responses"), usage)
        self.assertEqual(usage_charge(usage, cfg["rates"], "responses"), Decimal("0.0006975"))
        self.assertIsNone(usage_charge(dict(usage, input_tokens=-1), cfg["rates"], "responses"))
        self.assertIsNone(usage_charge(dict(usage, input_tokens_details={"cached_tokens": 101}), cfg["rates"], "responses"))

    def test_bounds_cover_original_defaults_without_changing_payload(self):
        payload = {"model": "fixed-model", "messages": []}
        self.assertEqual(request_bound(payload, section()), Decimal("1.872"))
        self.assertEqual(payload, {"model": "fixed-model", "messages": []})
        with self.assertRaises(BudgetError):
            request_bound(dict(payload, max_tokens=32001), section())

    def test_anthropic_stream_combines_usage_and_keeps_cache_tokens_exclusive(self):
        events = [{"type": "message_start", "message": {"usage": {
            "input_tokens": 100, "output_tokens": 0, "cache_read_input_tokens": 500,
            "cache_creation_input_tokens": 200}}},
            {"type": "message_delta", "usage": {"output_tokens": 50}}, {"type": "message_stop"}]
        body = b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events)
        usage = extract_usage(body, "text/event-stream", "anthropic")
        rates = dict(section()["rates"], cache_write_per_million=5.625)
        self.assertEqual(usage_charge(usage, rates, "anthropic"), Decimal("0.002925"))
        self.assertIsNone(usage_charge(usage, section()["rates"], "anthropic"))
        incomplete = b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events[:-1])
        self.assertIsNone(extract_usage(incomplete, "text/event-stream", "anthropic"))

    def test_anthropic_key_and_payload_survive_forwarding_without_secret_capture(self):
        events = [{"type": "message_start", "message": {"usage": {"input_tokens": 100, "output_tokens": 0}}},
                  {"type": "message_delta", "usage": {"output_tokens": 50}}, {"type": "message_stop"}]
        response = b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events)
        gateway = AdmissionGateway("model.example", "/inference/v1/chat/completions", "anthropic", section(),
            self.ledger, "task", self.directory / "gateway", transport=lambda: Transport(response, self.received))
        payload = b'{"model":"fixed-model","max_tokens":32000,"messages":[]}'
        with gateway, patch.dict("os.environ", {"CEKURA_GATEWAY_TEST_KEY": "test"}):
            self.call(gateway, payload, auth_header=b"x-api-key: test")
        self.assertEqual(self.received[0]["body"], payload)
        self.assertEqual(self.received[0]["headers"]["x-api-key"], "test")
        self.assertNotIn("x-api-key", read(self.directory / "gateway/request-1/request.json")["headers"])
        self.assertEqual(gateway.cost, Decimal("0.001575"))

    def test_concurrent_reservations_and_checkpoint_resume_do_not_overspend(self):
        def reserve(number):
            try:
                # Independent instances reproduce concurrent controller/probe access.
                Ledger(self.ledger.path).reserve(str(number), "target", 2, entry_type="request")
                return True
            except BudgetError:
                return False
        with ThreadPoolExecutor(max_workers=12) as pool:
            self.assertEqual(sum(pool.map(reserve, range(12))), 10)
        resumed = Ledger(self.ledger.path)
        self.assertEqual(resumed.total(), 20)
        with self.assertRaises(BudgetError):
            resumed.reserve("retry", "target", .01)

    def test_infrastructure_and_requests_do_not_consume_rollout_slots(self):
        self.ledger.reserve("offline", "target", .1, infrastructure_only=True)
        self.ledger.start("task", "target", entry_type="rollout", repeat=0)
        self.ledger.reserve("request", "target", 1, entry_type="request", scope="task")
        self.assertEqual(len(self.ledger.rollouts()), 1)
        self.assertLess(infrastructure_bound({"source": "https://modal.com/pricing", "verified_at": "synthetic", "rates": RATES}), .1)

    def test_shared_or_mismatched_cap_and_unverified_usage_fail_preflight(self):
        cfg = section()
        self.assertEqual(validate_admission(cfg, "target"), [])
        cfg["admission"]["hard_cap"]["experiment_exclusive"] = False
        self.assertTrue(validate_admission(cfg, "target"))
        cfg = section()
        with patch.dict("os.environ", {"CEKURA_GATEWAY_TEST_KEY": "another"}):
            self.assertTrue(any("different credential" in f for f in validate_admission(cfg, "target")))
        cfg["billing_usage_verified"] = False
        self.assertTrue(any("semantics" in f for f in validate_admission(cfg, "target")))

    def test_gateway_can_enforce_exclusive_experiment_allowance_on_existing_key(self):
        from experiments.scenario_skills.common import ROOT
        cfg = section()
        cap = cfg["admission"]["hard_cap"]
        cap.update(enforcement="admission_gateway", code_sha256=digest(ROOT / "gateway.py"),
                   evidence="Conservative per-request reservations against the experiment-only locked ledger")
        self.assertEqual(validate_admission(cfg, "target"), [])
        cap["code_sha256"] = "changed"
        self.assertTrue(any("different gateway code" in f for f in validate_admission(cfg, "target")))

    def test_fixture_review_is_required_and_bound_to_frozen_expectations(self):
        from experiments.scenario_skills.fixture_review import packet, gate
        packet(self.directory)
        self.assertFalse(gate(self.directory))
        signoff = read(self.directory / "fixture-signoff.template.json")
        signoff.update(reviewer="Synthetic domain reviewer", domain_signoff=True, policies_and_expectations_reviewed=True)
        write(self.directory / "fixture-signoff.json", signoff)
        self.assertTrue(gate(self.directory))
        value = read(self.directory / "fixture-review.json")
        value["tasks"][0]["request"] = "changed expectation"
        write(self.directory / "fixture-review.json", value)
        self.assertFalse(gate(self.directory))

    @unittest.skipUnless(sys.platform == "darwin", "The retired Codex proposer sandbox uses macOS sandbox-exec")
    def test_request_proposer_sandbox_denies_other_loopback_ports(self):
        import subprocess
        from experiments.scenario_skills.proposer import sandbox_profile
        workspace = self.directory / "workspace"
        (workspace / "artifacts").mkdir(parents=True)
        with socket.socket() as allowed, socket.socket() as denied:
            allowed.bind(("127.0.0.1", 0)); allowed.listen()
            denied.bind(("127.0.0.1", 0)); denied.listen()
            profile = workspace / "isolation.sb"
            profile.write_text(sandbox_profile(workspace, "/usr/bin/python3", allowed.getsockname()[1]))
            script = "import socket; s=socket.create_connection(('127.0.0.1',%d),timeout=2); s.close()"
            prefix = ["/usr/bin/sandbox-exec", "-f", str(profile), "/usr/bin/python3", "-c"]
            good = subprocess.run(prefix + [script % allowed.getsockname()[1]], capture_output=True, cwd=workspace)
            bad = subprocess.run(prefix + [script % denied.getsockname()[1]], capture_output=True, cwd=workspace)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertNotEqual(bad.returncode, 0)

    def test_modal_preflight_requires_matching_real_transport_evidence(self):
        from experiments.scenario_skills.common import ROOT
        cfg = read(ROOT / "config.example.json")
        cfg["target"].update(adapter="modal", image="im-Synthetic", accounting="per_request")
        cfg["proposer"]["accounting"] = "per_request"
        failures = preflight(cfg)["failures"]
        self.assertIn("target experiment-specific hard spending cap unverified", failures)
        self.assertIn("target TLS gateway transport probe missing", failures)
        self.assertIn("Exact Modal image offline probe missing", failures)

    def test_catalog_protocol_decoder_accepts_json_and_stream_events(self):
        from experiments.scenario_skills.catalog_capture import message
        value = {"jsonrpc": "2.0", "id": 2, "result": {"tools": []}}
        self.assertEqual(message(json.dumps(value).encode()), value)
        self.assertEqual(message(b"event: message\ndata: " + json.dumps(value).encode() + b"\n\n"), value)
        with self.assertRaises(ValueError):
            message(b"event: ping\n\n")

    def test_catalog_api_key_auth_only_initializes_and_lists_tools(self):
        from experiments.scenario_skills.catalog_capture import capture
        calls = []
        class Reply(io.BytesIO):
            headers = {}
        def respond(request, timeout):
            body = json.loads(request.data)
            calls.append((body["method"], {k.lower():v for k,v in request.header_items()}))
            result = {"tools": [{"name": "aiagents_retrieve", "inputSchema": {"type": "object"}}]} if body["method"] == "tools/list" else {}
            return Reply(json.dumps({"result":result}).encode())
        with patch.dict("os.environ", {"CEKURA_SCHEMA_TEST_KEY":"offline-key"}), patch(
                "experiments.scenario_skills.catalog_capture.urlopen", side_effect=respond):
            capture(self.directory, "CEKURA_SCHEMA_TEST_KEY", credential_type="api-key")
        self.assertEqual([c[0] for c in calls], ["initialize", "notifications/initialized", "tools/list"])
        self.assertTrue(all(c[1]["x-cekura-api-key"] == "offline-key" for c in calls))
        self.assertNotIn("offline-key", (self.directory / "catalog-provenance.json").read_text())


if __name__ == "__main__":
    unittest.main()

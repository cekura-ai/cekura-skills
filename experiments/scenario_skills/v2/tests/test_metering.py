"""Nested generator metering with fake providers only; no request leaves this host."""
import io
import json
import os
import socket
import ssl
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from experiments.scenario_skills import budget
from experiments.scenario_skills.common import read
from experiments.scenario_skills.tests.helpers import cumulative_ledger
from experiments.scenario_skills.v2.metering import GEMINI_PATH, Metering, client_hello_sni, validate_generator

RATES = {"input_per_million": 1.0, "cached_input_per_million": .1, "output_per_million": 4.0,
         "source": "synthetic", "verified_at": "2026-10-23"}
ADMISSION = {"input_token_limit": 100000, "output_token_limit": 1000, "token_bound_evidence": "synthetic"}


def config():
    model = {"rates": RATES, "admission": ADMISSION}
    return {"endpoints": [
        {"host": "api.fireworks.ai", "credential_env": "CEKURA_FAKE_FIREWORKS",
         "routes": [{"path": "/inference/v1/messages", "api": "anthropic", "query": {"beta": ["true"]}},
                    {"path": "/inference/v1/chat/completions", "api": "chat"}],
         "models": {"accounts/fireworks/routers/glm-5p3-fast": model, "accounts/fireworks/models/deepseek-v4p1-flash": model}},
        {"host": "generativelanguage.googleapis.com", "credential_env": "CEKURA_FAKE_GEMINI",
         "routes": [{"pattern": GEMINI_PATH, "api": "gemini", "query": {"alt": ["sse"]}}], "models": {"gemini-3.7-flash": model}}],
        "passthrough": ["api.modal.com"],
        "sandbox": {"rates": {"source": "synthetic", "cpu_core_second": .0001, "memory_gib_second": .00001},
                    "max_lifetime_seconds": 600, "teardown_grace_seconds": 60}}


class Response(io.BytesIO):
    status, reason = 200, "OK"

    def __init__(self, body, content_type, delay=0, chunks=1, gate=None):
        super().__init__(body)
        self.content_type, self.delay, self.size, self.gate = content_type, delay, max(1, len(body) // chunks), gate

    def getheaders(self):
        return [("Content-Type", self.content_type)]

    def getheader(self, name, default=None):
        return self.content_type if name.lower() == "content-type" else default

    def read1(self, n=-1):
        if self.gate:
            self.gate.wait(30)
        if self.delay:
            time.sleep(self.delay)
        if self.closed:
            raise ValueError("closed")
        return self.read(self.size)


class Provider:
    """Records exactly what would have reached a provider."""
    def __init__(self, body=None, content_type="application/json", delay=0, chunks=1, gate=None):
        self.received, self.body, self.content_type, self.delay, self.chunks, self.gate = [], body, content_type, delay, chunks, gate

    def __call__(self, host):
        owner = self

        class Connection:
            def request(self, method, target, body, headers):
                owner.received.append({"host": host, "target": target, "headers": headers, "body": json.loads(body)})

            def getresponse(self):
                self.response = Response(owner.body, owner.content_type, owner.delay, owner.chunks, owner.gate)
                return self.response

            def close(self):
                if hasattr(self, "response"):
                    self.response.close()
        return Connection()


ANTHROPIC = (b"event: message_start\ndata: " + json.dumps({"type": "message_start", "message": {"usage": {"input_tokens": 1000, "output_tokens": 0}}}).encode()
             + b"\n\nevent: message_delta\ndata: " + json.dumps({"type": "message_delta", "usage": {"output_tokens": 100}}).encode()
             + b"\n\nevent: message_stop\ndata: {\"type\": \"message_stop\"}\n\n")
GEMINI = b"data: " + json.dumps({"candidates": [{"finishReason": "STOP"}], "usageMetadata": {
    "promptTokenCount": 2000, "cachedContentTokenCount": 1000, "candidatesTokenCount": 50, "thoughtsTokenCount": 50}}).encode() + b"\n\n"


class MeteringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cekura-metering-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.ledger = cumulative_ledger(self, self.directory, "29.13728485")
        env = patch.dict(os.environ, {"CEKURA_FAKE_FIREWORKS": "real-fireworks-key", "CEKURA_FAKE_GEMINI": "real-gemini-key"})
        env.start()
        self.addCleanup(env.stop)

    def start(self, provider, **kwargs):
        kwargs.setdefault("splice", lambda host: (_ for _ in ()).throw(OSError("no pass-through in this test")))
        metering = Metering(config(), self.ledger, "rollout-a", self.directory / "metering", transport=provider, **kwargs)
        metering.__enter__()
        self.addCleanup(metering.close, "test finished")
        self.client = ssl.create_default_context(cafile=str(metering.ca))
        return metering

    def tls(self, metering, host, mode="connect", wrap=True):
        raw = socket.create_connection(("127.0.0.1", metering.port("connect" if mode == "connect" else "tls")), timeout=10)
        if mode == "connect":
            raw.sendall(("CONNECT %s:443 HTTP/1.1\r\nHost: %s:443\r\n\r\n" % (host, host)).encode())
            reply = raw.recv(4096)
            if b" 200 " not in reply:
                raw.close()
                return reply
        return self.client.wrap_socket(raw, server_hostname=host) if wrap else raw

    def post(self, metering, host, path, payload, headers, mode="connect"):
        connection = self.tls(metering, host, mode)
        if isinstance(connection, bytes):
            return connection
        body = json.dumps(payload).encode()
        head = "POST %s HTTP/1.1\r\nHost: %s\r\nContent-Length: %d\r\nContent-Type: application/json\r\n" % (path, host, len(body))
        head += "".join("%s: %s\r\n" % item for item in headers.items())
        connection.sendall(head.encode() + b"\r\n" + body)
        data = b""
        try:
            while True:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                data += chunk
        except (OSError, ssl.SSLError):
            pass
        connection.close()
        return data

    def test_pinned_requests_are_admitted_before_forwarding_and_settled_from_usage(self):
        provider = Provider(ANTHROPIC, "text/event-stream")
        metering = self.start(provider)
        reply = self.post(metering, "api.fireworks.ai", "/inference/v1/messages?beta=true",
                          {"model": "accounts/fireworks/routers/glm-5p3-fast", "max_tokens": 500, "messages": []},
                          {"x-api-key": metering.placeholder}, mode="direct")
        self.assertIn(b" 200 ", reply)
        self.assertEqual(provider.received[0]["headers"]["x-api-key"], "real-fireworks-key")
        entry = self.ledger.state["entries"][next(k for k in self.ledger.state["entries"] if k.endswith("/generator-request-1"))]
        body = len(json.dumps({"model": "accounts/fireworks/routers/glm-5p3-fast", "max_tokens": 500, "messages": []}).encode())
        # Input bound: request bytes plus template tokens (not the 100k context), then 500 output tokens.
        self.assertEqual(Decimal(entry["reserved"]), (Decimal(body + 4096) * 1 + 500 * 4) / Decimal(1_000_000))
        self.assertEqual(Decimal(entry["charged"]), Decimal("0.0014"))
        provider.body, provider.content_type = GEMINI, "text/event-stream"
        reply = self.post(metering, "generativelanguage.googleapis.com", "/v1beta/models/gemini-3.7-flash:streamGenerateContent?alt=sse",
                          {"contents": []}, {"x-goog-api-key": metering.placeholder})
        self.assertIn(b" 200 ", reply)
        self.assertEqual(provider.received[1]["headers"]["x-goog-api-key"], "real-gemini-key")
        self.assertEqual(metering.cost(), Decimal("0.0014") + Decimal("0.0015"))

    def test_fallback_to_unpinned_models_or_hosts_fails_closed(self):
        provider = Provider(ANTHROPIC, "text/event-stream")
        metering = self.start(provider)
        for host, path, payload, headers in (
                ("api.fireworks.ai", "/inference/v1/messages", {"model": "accounts/fireworks/routers/kimi-k3-fast", "max_tokens": 1}, {"x-api-key": metering.placeholder}),
                ("generativelanguage.googleapis.com", "/v1beta/models/gemini-3.6-flash:generateContent", {}, {"x-goog-api-key": metering.placeholder}),
                ("api.fireworks.ai", "/inference/v1/models", {}, {"x-api-key": metering.placeholder}),
                ("generativelanguage.googleapis.com", "/v1beta/models/gemini-3.7-flash:generateContent?key=leak", {}, {})):
            self.assertIn(b" 403 ", self.post(metering, host, path, payload, headers))
        for host in ("api.anthropic.com", "bedrock-runtime.us-east-1.amazonaws.com", "pass.wafer.ai", "inference.baseten.co"):
            self.assertIn(b" 403 ", self.tls(metering, host))
            with self.assertRaises((ssl.SSLError, OSError)):
                self.tls(metering, host, mode="direct").sendall(b"x")
        self.assertEqual(provider.received, [])
        self.assertFalse([k for k in self.ledger.state["entries"] if k.startswith("rollout-a/")])
        self.assertGreaterEqual(len(metering.denied), 12)

    def test_real_or_missing_credentials_are_never_forwarded(self):
        provider = Provider(ANTHROPIC, "text/event-stream")
        metering = self.start(provider)
        payload = {"model": "accounts/fireworks/routers/glm-5p3-fast", "max_tokens": 1}
        for headers in ({}, {"x-api-key": "real-fireworks-key"}, {"x-api-key": metering.placeholder, "authorization": "Bearer other"}):
            self.assertIn(b" 403 ", self.post(metering, "api.fireworks.ai", "/inference/v1/messages", payload, headers))
        self.assertEqual(provider.received, [])

    def test_concurrent_requests_respect_stage_and_wallet_caps(self):
        gate = threading.Event()
        provider = Provider(ANTHROPIC, "text/event-stream", gate=gate)
        metering = self.start(provider)
        payload = {"model": "accounts/fireworks/routers/glm-5p3-fast", "max_tokens": 1000, "messages": []}
        bound = (Decimal(len(json.dumps(payload).encode()) + 4096) + 4000) / Decimal(1_000_000)
        with self.ledger.staged("cost-discovery", str(bound * Decimal("4.5"))):
            with ThreadPoolExecutor(12) as pool:
                futures = [pool.submit(self.post, metering, "api.fireworks.ai", "/inference/v1/messages", payload,
                                       {"x-api-key": metering.placeholder}) for _ in range(12)]
                deadline = time.monotonic() + 30
                while metering.errors.count("budget_admission_denied") < 8 and time.monotonic() < deadline:
                    time.sleep(.05)
                # Every admitted stream is still open, so all four reservations count at their bound.
                staged = [e for e in self.ledger.state["entries"].values() if e.get("stage") == "cost-discovery"]
                self.assertLessEqual(sum(Decimal(e["charged"]) for e in staged), bound * Decimal("4.5"))
                gate.set()
                replies = [f.result() for f in futures]
        self.assertEqual(sum(b" 200 " in r for r in replies), 4)
        self.assertEqual(sum(b" 402 " in r for r in replies), 8)
        self.assertEqual(len(provider.received), 4)

    def test_cancellation_aborts_streams_refuses_new_work_and_charges_the_bound(self):
        provider = Provider(ANTHROPIC, "text/event-stream", delay=.4, chunks=20)
        metering = self.start(provider)
        payload = {"model": "accounts/fireworks/routers/glm-5p3-fast", "max_tokens": 1000, "messages": []}
        result = {}
        thread = threading.Thread(target=lambda: result.update(reply=self.post(
            metering, "api.fireworks.ai", "/inference/v1/messages", payload, {"x-api-key": metering.placeholder})))
        thread.start()
        time.sleep(1)
        started = time.monotonic()
        metering.close("rollout cancelled")
        thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertLess(time.monotonic() - started, 5)
        self.assertNotIn(b"0\r\n\r\n", result["reply"])
        entry = self.ledger.state["entries"][next(k for k in self.ledger.state["entries"] if k.endswith("/generator-request-1"))]
        self.assertEqual((entry["status"], entry["charged"]), ("complete", entry["reserved"]))
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", metering.port("connect")), timeout=2).sendall(b"CONNECT api.fireworks.ai:443 HTTP/1.1\r\n\r\n")
        self.assertTrue(read(self.directory / "metering" / "metering.json")["closed"])

    def test_modal_control_plane_is_spliced_without_decryption(self):
        echo = socket.socket()
        echo.bind(("127.0.0.1", 0))
        echo.listen(1)

        def serve():
            connection, _ = echo.accept()
            connection.sendall(b"modal:" + connection.recv(100))
            connection.close()
        threading.Thread(target=serve, daemon=True).start()
        metering = self.start(Provider(), splice=lambda host: socket.create_connection(echo.getsockname()))
        connection = self.tls(metering, "api.modal.com", wrap=False)
        connection.sendall(b"opaque-grpc-bytes")
        self.assertEqual(connection.recv(100), b"modal:opaque-grpc-bytes")
        self.assertEqual(metering.spliced[0]["host"], "api.modal.com")

    def test_sandbox_infrastructure_is_reserved_before_creation(self):
        metering = self.start(Provider())

        def control(path, body, token):
            raw = socket.create_connection(("127.0.0.1", metering.port("control")), timeout=5)
            data = json.dumps(body).encode()
            raw.sendall(b"POST %s HTTP/1.1\r\nx-cekura-control: %s\r\nContent-Length: %d\r\n\r\n" % (path.encode(), token.encode(), len(data)) + data)
            reply = raw.recv(4096)
            raw.close()
            return reply
        self.assertIn(b" 403 ", control("/sandbox/reserve", {}, "wrong"))
        reply = control("/sandbox/reserve", {"lifetime": 43200, "cpu": .125, "memory": 128}, metering.placeholder)
        self.assertEqual(json.loads(reply.split(b"\r\n\r\n", 1)[1])["lifetime"], 600)
        entry = self.ledger.state["entries"][next(k for k in self.ledger.state["entries"] if k.endswith("/generator-sandbox-1"))]
        self.assertEqual(Decimal(entry["reserved"]), Decimal("0.0726"))  # 660 s at one core and 1 GiB

    def test_error_replies_charge_their_bound_without_blocking_and_media_keeps_full_limit(self):
        provider = Provider(b'{"error": "overloaded"}', "application/json")
        provider_response = Response
        metering = self.start(provider)
        with patch.object(Response, "status", 503):
            reply = self.post(metering, "api.fireworks.ai", "/inference/v1/messages",
                              {"model": "accounts/fireworks/routers/glm-5p3-fast", "max_tokens": 1, "messages": []}, {"x-api-key": metering.placeholder})
        self.assertIn(b" 503 ", reply)
        entry = self.ledger.state["entries"][next(k for k in self.ledger.state["entries"] if k.endswith("/generator-request-1"))]
        self.assertEqual((entry["status"], entry["charged"]), ("complete", entry["reserved"]))
        self.assertFalse(read(budget.wallet_path())["blocked"])
        from experiments.scenario_skills.v2.metering import body_section
        section = {"admission": ADMISSION, "rates": RATES}
        self.assertEqual(body_section(section, b'{"x": 1}')["admission"]["input_token_limit"], 8 + 4096)
        self.assertEqual(body_section(section, b'{"type": "image", "source": {}}')["admission"]["input_token_limit"], 100000)

    def test_live_upstreams_require_the_canonical_wallet(self):
        from experiments.scenario_skills.budget import BudgetError
        with self.assertRaises(BudgetError):
            Metering(config(), self.ledger, "live", self.directory / "live")

    def test_sni_parser_and_configuration_validation(self):
        context = ssl.create_default_context()
        incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
        client = context.wrap_bio(incoming, outgoing, server_hostname="generativelanguage.googleapis.com")
        with self.assertRaises(ssl.SSLWantReadError):
            client.do_handshake()
        self.assertEqual(client_hello_sni(outgoing.read()), "generativelanguage.googleapis.com")
        self.assertEqual(validate_generator(config()), [])
        broken = config()
        del broken["endpoints"][0]["models"]["accounts/fireworks/routers/glm-5p3-fast"]["rates"]
        broken["endpoints"][0]["models"]["accounts/fireworks/routers/glm-5p3-fast"] = {"admission": ADMISSION}
        self.assertTrue(validate_generator(broken))


class RelayAttach(unittest.TestCase):
    def test_the_pump_reads_the_same_stream_iterator_as_the_ready_line(self):
        """Modal hands a process's output to one iterator; a second iteration would never see the relay's events."""
        import importlib
        from unittest import mock
        from experiments.scenario_skills.v2.generator import cekura_metering
        events = [json.dumps({"type": "ready", "port": 4100}) + "\n", json.dumps({"type": "close", "id": 1}) + "\n"]
        class Stream:
            def __init__(self):
                self.iterators = 0
            def __iter__(self):
                self.iterators += 1
                return iter(events) if self.iterators == 1 else iter(())
        stream = Stream()
        process = mock.Mock(stdout=stream)
        sandbox = mock.Mock(object_id="sb-1", exec=mock.Mock(return_value=process))
        with mock.patch.dict(os.environ, {"CEKURA_METERING_CA": __file__, "CEKURA_METERING_CONNECT": "127.0.0.1:1"}), \
                mock.patch.object(Path, "read_text", return_value="relay source"):
            self.assertEqual(cekura_metering.attach(sandbox), 4100)
        import time
        time.sleep(0.2)
        self.assertEqual(stream.iterators, 1)
        cekura_metering._attached.pop("sb-1", None)


if __name__ == "__main__":
    unittest.main()

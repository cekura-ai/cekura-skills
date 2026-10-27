"""Experiment-owned metering for every nested generator request, probe and sandbox.

The isolated backend reaches providers only through this host service:

* Worker containers sit on an internal Docker network. Pinned provider and Modal names
  resolve to an edge forwarder whose port 443 lands on ``tls_port`` here; every other
  name fails to resolve and no external route exists.
* The generator's Modal sandbox is created with its network blocked. Its only egress is a
  stdio relay through the worker, whose connections arrive at ``connect_port``.

Provider traffic is decrypted with an ephemeral CA, matched to a pinned route and model,
admitted against the canonical wallet *before* forwarding, and settled from authoritative
usage. Clients hold a per-run placeholder credential; real keys exist only in this
process. Modal control-plane names are spliced unchanged. Anything else is denied and
recorded, so a fallback to an unpinned model or provider fails instead of escaping.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import socket
import socketserver
import ssl
import subprocess
import threading
import time
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from ..budget import BudgetError, require_cumulative
from ..common import digest, write
from ..gateway import MAX_BODY, TEMPLATE_TOKENS, body_section, extract_usage, read_request, request_bound, usage_charge

GEMINI_PATH = r"^/v1beta/models/(?P<model>[A-Za-z0-9._-]+):(?:generateContent|streamGenerateContent)$"
SPLICE_LIMIT = 256 * 1024 * 1024


def certificates_for(directory, hostnames):
    """Ephemeral CA and one server certificate naming every metered host."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    ca, key, cert = directory / "ca.pem", directory / "server.key", directory / "server.pem"
    extension = directory / "extensions.cnf"
    # Strict X.509 verification (Python 3.13+, current Node) needs explicit CA usage and key identifiers.
    extension.write_text("subjectAltName=" + ",".join("DNS:" + h for h in hostnames) +
                         "\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n"
                         "extendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n")
    for command in (
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=Cekura generator metering CA",
             "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign",
             "-addext", "subjectKeyIdentifier=hash", "-keyout", str(directory / "ca.key"), "-out", str(ca)],
            ["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=Cekura metered provider",
             "-keyout", str(key), "-out", str(directory / "server.csr")],
            ["openssl", "x509", "-req", "-in", str(directory / "server.csr"), "-CA", str(ca), "-CAkey", str(directory / "ca.key"),
             "-CAcreateserial", "-days", "2", "-extfile", str(extension), "-out", str(cert)]):
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for path in directory.iterdir():
        path.chmod(0o600)
    ca.chmod(0o644)
    return ca, cert, key


MODAL_CONTROL = {"api.modal.com"}
# Sandbox exec and filesystem calls dial task-<id>.w.modal.host directly (modal >= 1.x command router).
MODAL_TASK_SUFFIX = ".w.modal.host"


def client_hello_sni(data):
    """Server name from a TLS ClientHello, or None. Never decrypts anything."""
    try:
        if len(data) < 5 or data[0] != 0x16:
            return None
        end = 5 + int.from_bytes(data[3:5], "big")
        if len(data) < end or data[5] != 0x01:
            return None
        i = 5 + 4 + 2 + 32
        i += 1 + data[i]
        i += 2 + int.from_bytes(data[i:i + 2], "big")
        i += 1 + data[i]
        stop = i + 2 + int.from_bytes(data[i:i + 2], "big")
        i += 2
        while i + 4 <= stop:
            kind, size = int.from_bytes(data[i:i + 2], "big"), int.from_bytes(data[i + 2:i + 4], "big")
            if kind == 0:
                j = i + 4 + 2
                if data[j] == 0:
                    return data[j + 3:j + 3 + int.from_bytes(data[j + 1:j + 3], "big")].decode("ascii").lower()
            i += 4 + size
    except (IndexError, UnicodeDecodeError):
        pass
    return None


def gemini_usage(body, content_type):
    """Last usageMetadata of a complete Gemini response, or None when it cannot be trusted."""
    try:
        if "text/event-stream" in content_type:
            events = [json.loads(line[5:].strip()) for line in body.decode().replace("\r\n", "\n").split("\n") if line.startswith("data:") and line[5:].strip()]
        else:
            value = json.loads(body)
            events = value if isinstance(value, list) else [value]
    except (ValueError, UnicodeError):
        return None
    if not events or not any(c.get("finishReason") for c in (events[-1].get("candidates") or [])):
        return None  # A truncated stream may under-report usage.
    return events[-1].get("usageMetadata")


def gemini_charge(usage, rates):
    if not isinstance(usage, dict):
        return None
    names = ("promptTokenCount", "cachedContentTokenCount", "candidatesTokenCount", "thoughtsTokenCount", "toolUsePromptTokenCount")
    values = [usage.get(n, 0) for n in names]
    if usage.get("promptTokenCount") is None or any(type(v) is not int or v < 0 for v in values) or values[1] > values[0]:
        return None
    prompt, cached, candidates, thoughts, tool = values
    return ((Decimal(prompt - cached + tool) * Decimal(str(rates["input_per_million"]))
             + Decimal(cached) * Decimal(str(rates["cached_input_per_million"]))
             + Decimal(candidates + thoughts) * Decimal(str(rates["output_per_million"]))) / Decimal(1_000_000))


def gemini_bound(payload, section):
    maximum = section["admission"]["output_token_limit"]
    requested = (payload.get("generationConfig") or {}).get("maxOutputTokens")
    if requested is not None:
        if type(requested) is not int or not 0 < requested <= maximum:
            raise BudgetError("Gemini output limit exceeds the verified bound")
        maximum = requested
    rates = section["rates"]
    rate = max(Decimal(str(rates["input_per_million"])), Decimal(str(rates["cached_input_per_million"])))
    return (Decimal(section["admission"]["input_token_limit"]) * rate + Decimal(maximum) * Decimal(str(rates["output_per_million"]))) / Decimal(1_000_000)


def validate_generator(config):
    """Every pinned model needs verified rates and token limits; nothing is inferred."""
    failures = []
    for endpoint in config.get("endpoints", []):
        if not endpoint.get("credential_env") or not endpoint.get("routes") or not endpoint.get("models"):
            failures.append("Generator endpoint incomplete: " + str(endpoint.get("host")))
        for model, section in endpoint.get("models", {}).items():
            rates, admission = section.get("rates", {}), section.get("admission", {})
            if not rates.get("source") or not rates.get("verified_at") or any(
                    not isinstance(rates.get(k), (int, float)) or rates[k] < 0 for k in ("input_per_million", "cached_input_per_million", "output_per_million")):
                failures.append("Generator rates unverified: " + model)
            if any(type(admission.get(k)) is not int or admission[k] <= 0 for k in ("input_token_limit", "output_token_limit")) or not admission.get("token_bound_evidence"):
                failures.append("Generator token bounds unverified: " + model)
    rates = config.get("sandbox", {}).get("rates", {})
    if not rates.get("source") or not all(isinstance(rates.get(k), (int, float)) for k in ("cpu_core_second", "memory_gib_second")):
        failures.append("Generator sandbox rates unverified")
    return failures


class Metering:
    def __init__(self, config, ledger, scope, directory, bind="127.0.0.1", transport=None, splice=None, placeholder=None):
        if transport is None or splice is None:
            require_cumulative(ledger, live=True)  # Real providers or Modal: canonical wallet only.
        self.config, self.ledger, self.scope = config, ledger, scope
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.endpoints = {e["host"]: e for e in config["endpoints"]}
        self.passthrough = set(config.get("passthrough", []))
        self.placeholder = placeholder or "cekura-metered-" + os.urandom(12).hex()
        self.transport = transport or (lambda host: http.client.HTTPSConnection(host, timeout=180))
        self.splice_to = splice or (lambda host: socket.create_connection((host, 443), timeout=30))
        self.ca, cert, key = certificates_for(self.directory / "tls", sorted(self.endpoints))
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(cert, key)
        self.context.set_alpn_protocols(["http/1.1"])
        self.requests, self.denied, self.errors, self.spliced, self.sandboxes = [], [], [], [], []
        self.closed = threading.Event()
        self.live, self.upstreams, self.lock, self.counter = set(), set(), threading.Lock(), 0
        self.instance = os.urandom(4).hex()  # Keys and evidence never collide with an earlier run of a scope.
        owner = self

        def server(handler):
            class Handler(socketserver.BaseRequestHandler):
                def handle(self):
                    owner._track(self.request, handler)

            class Server(socketserver.ThreadingTCPServer):
                daemon_threads, allow_reuse_address = True, True
            return Server((bind, 0), Handler)

        self.servers = {"tls": server(self._direct), "connect": server(self._connect), "control": server(self._control)}
        self.threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in self.servers.values()]

    def port(self, name):
        return self.servers[name].server_address[1]

    def __enter__(self):
        for thread in self.threads:
            thread.start()
        return self

    def __exit__(self, *args):
        self.close("metering stopped")

    def close(self, reason):
        """Refuse new work and abort every in-flight connection, including upstream streams."""
        if self.closed.is_set():
            return
        self.closed.set()
        self.close_reason = reason
        for s in self.servers.values():
            s.shutdown()
            s.server_close()
        with self.lock:
            live, upstreams = list(self.live), list(self.upstreams)
        for upstream in upstreams:
            try:
                upstream.close()
            except Exception:
                pass
        for connection in live:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        write(self.directory / "metering.json", self.evidence())

    def evidence(self):
        return {"scope": self.scope, "closed": self.closed.is_set(), "close_reason": getattr(self, "close_reason", None),
                "requests": self.requests, "denied": self.denied, "errors": self.errors, "spliced": self.spliced,
                "sandboxes": self.sandboxes, "cost_usd": str(self.cost()) if self.cost() is not None else None}

    def cost(self):
        with self.ledger.transaction():
            entries = [e for e in self.ledger.state["entries"].values() if e.get("scope") == self.scope and e.get("entry_type") == "generator_request"]
        if any(e["status"] != "complete" for e in entries):
            return None
        return sum((Decimal(e["charged"]) for e in entries), Decimal(0))

    def _track(self, connection, handler):
        with self.lock:
            self.live.add(connection)
        try:
            connection.settimeout(300)
            handler(connection)
        except Exception as error:
            self.errors.append(type(error).__name__ + ": " + str(error)[:200])
        finally:
            with self.lock:
                self.live.discard(connection)
            connection.close()

    def _deny(self, connection, reason, tls=None):
        self.denied.append({"at": time.time(), "reason": reason})
        try:
            (tls or connection).sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        except OSError:
            pass

    def _direct(self, connection):
        """Edge-forwarded TLS: route on the ClientHello name without consuming it."""
        data, deadline = b"", time.monotonic() + 10
        while time.monotonic() < deadline:
            data = connection.recv(16384, socket.MSG_PEEK)
            if len(data) >= 5 and len(data) >= 5 + int.from_bytes(data[3:5], "big"):
                break
            time.sleep(.01)
        host = client_hello_sni(data)
        self._route(connection, host, direct=True)

    def _connect(self, connection):
        """Sandbox relay connections speak HTTP CONNECT first."""
        stream = connection.makefile("rb")
        request = read_request(stream)
        stream.close()
        target = request[0][1] if request and request[0][0] == "CONNECT" else ""
        host, _, port = target.rpartition(":")
        if port != "443" or not (host in self.endpoints or self.is_passthrough(host)):
            self.denied.append({"at": time.time(), "reason": "CONNECT denied: " + target[:120]})
            connection.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            return
        if self.closed.is_set():
            return self._deny(connection, "scope closed: " + host)
        connection.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        self._route(connection, host.lower(), direct=False)

    def _route(self, connection, host, direct):
        if self.closed.is_set():
            self.denied.append({"at": time.time(), "reason": "scope closed: " + str(host)})
            return
        if self.is_passthrough(host):
            return self._splice(connection, host)
        if host not in self.endpoints:
            self.denied.append({"at": time.time(), "reason": "unmetered host denied: " + str(host)})
            return  # Closing without a handshake fails the client's TLS verification.
        with self.context.wrap_socket(connection, server_side=True) as secure:
            with self.lock:
                self.live.add(secure)
            with secure.makefile("rb") as incoming:
                request = read_request(incoming)
                if request is not None:
                    self._request(secure, incoming, host, request)

    def is_passthrough(self, host):
        """Modal control plane: configured names, plus Modal's per-task sandbox command routers."""
        host = str(host or "").lower()
        return host in self.passthrough or (bool(self.passthrough & MODAL_CONTROL) and host.endswith(MODAL_TASK_SUFFIX))

    def _splice(self, connection, host):
        """Modal control plane: unchanged TLS bytes; infrastructure, not inference."""
        upstream = self.splice_to(host)
        with self.lock:
            self.live.add(upstream)
        record = {"host": host, "bytes": 0, "started": time.time()}
        self.spliced.append(record)

        def pump(source, sink):
            try:
                while True:
                    chunk = source.recv(65536)
                    if not chunk:
                        break
                    record["bytes"] += len(chunk)
                    if record["bytes"] > SPLICE_LIMIT:
                        raise ValueError("Pass-through transfer bound exhausted")
                    sink.sendall(chunk)
            except OSError:
                pass
            finally:
                for s in (source, sink):
                    try:
                        s.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
        other = threading.Thread(target=pump, args=(upstream, connection), daemon=True)
        other.start()
        pump(connection, upstream)
        other.join(30)
        with self.lock:
            self.live.discard(upstream)
        upstream.close()

    def _request(self, secure, incoming, host, request):
        (method, target, _), headers = request
        endpoint = self.endpoints[host]
        parts = urlsplit(target)
        query = parse_qsl(parts.query, keep_blank_values=True)
        route, model = None, None
        for candidate in endpoint["routes"]:
            match = re.fullmatch(candidate.get("pattern") or re.escape(candidate["path"]), parts.path)
            if match:
                route, model = candidate, match.groupdict().get("model")
                break
        if method != "POST" or route is None:
            return self._deny(secure, "route denied: %s %s %s" % (host, method, parts.path[:120]), secure)
        allowed = route.get("query", {})
        if any(v not in allowed.get(k, ()) for k, v in query):
            return self._deny(secure, "query denied: %s %s" % (host, parts.query[:80]), secure)  # e.g. a key= credential
        if headers.get("transfer-encoding") or headers.get("content-encoding") or "expect" in headers:
            return self._deny(secure, "unbounded request framing denied", secure)
        length = int(headers.get("content-length", "-1"))
        if not 0 < length <= MAX_BODY:
            return self._deny(secure, "request size outside bound", secure)
        body = incoming.read(length)
        payload = json.loads(body)
        api = route["api"]
        model = model or payload.get("model")
        section = endpoint["models"].get(model)
        if section is None:
            return self._deny(secure, "unpinned model denied: %s %s" % (host, str(model)[:120]), secure)
        auth = {"x-api-key": headers.get("x-api-key"), "authorization": headers.get("authorization"), "x-goog-api-key": headers.get("x-goog-api-key")}
        presented = [k for k, v in auth.items() if v in (self.placeholder, "Bearer " + self.placeholder)]
        if not presented or any(v and k not in presented for k, v in auth.items()):
            return self._deny(secure, "unexpected credential denied: " + host, secure)
        if self.closed.is_set():
            return self._deny(secure, "scope closed: " + host, secure)
        try:
            bounded = body_section(section, body)
            bound = gemini_bound(payload, bounded) if api == "gemini" else request_bound(payload, bounded)
        except BudgetError as error:
            return self._deny(secure, str(error), secure)
        with self.lock:
            self.counter += 1
            number = self.counter
        key = "%s/%s/generator-request-%d" % (self.scope, self.instance, number)
        try:
            self.ledger.reserve(key, "target", bound, entry_type="generator_request", scope=self.scope, host=host, model=model, api=api)
        except BudgetError as error:
            self.errors.append("budget_admission_denied")
            secure.sendall(b"HTTP/1.1 402 Budget Exhausted\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            return
        folder = self.directory / ("request-%s-%d" % (self.instance, number))
        folder.mkdir(mode=0o700)
        (folder / "request.body").write_bytes(body)
        record = {"key": key, "host": host, "path": parts.path, "model": model, "api": api, "reserved_usd": str(bound),
                  "request_sha256": digest(body), "status": "incomplete"}
        self.requests.append(record)
        real = os.environ[endpoint["credential_env"]]
        forwarded = {k: v for k, v in headers.items() if k not in ("connection", "proxy-connection", "proxy-authorization", "x-api-key", "authorization", "x-goog-api-key")}
        for name in presented:
            forwarded[name] = ("Bearer " + real) if name == "authorization" else real
        upstream, response_bytes, actual, cancelled, failed = None, bytearray(), None, False, False
        try:
            upstream = self.transport(host)
            with self.lock:
                self.upstreams.add(upstream)
            if self.closed.is_set():
                raise OSError("scope closed before forwarding")
            upstream.request(method, target, body=body, headers=forwarded)
            response = upstream.getresponse()
            content_type = response.getheader("Content-Type", "")
            record.update(http_status=response.status)
            disconnected = False
            try:
                secure.sendall(("HTTP/1.1 %d %s\r\n" % (response.status, response.reason)).encode())
                for name, value in response.getheaders():
                    if name.lower() not in ("transfer-encoding", "content-length", "connection", "set-cookie"):
                        secure.sendall((name + ": " + value + "\r\n").encode("latin1"))
                secure.sendall(b"Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n")
            except OSError:
                # The client timed out before the provider answered (the pinned generator gives slow providers ~30 s).
                # The provider still bills the completed request: drain it so the charge is its real usage.
                disconnected = True
            while True:
                if self.closed.is_set():
                    cancelled = True
                    break
                chunk = response.read1(65536)
                if not chunk:
                    break
                response_bytes.extend(chunk)
                if len(response_bytes) > MAX_BODY:
                    raise ValueError("Response exceeded bounded capture")
                if not disconnected:
                    try:
                        secure.sendall(("%x\r\n" % len(chunk)).encode() + chunk + b"\r\n")
                    except OSError:
                        disconnected = True  # Keep draining: the final event carries authoritative usage.
            if not cancelled:
                if not disconnected:
                    try:
                        secure.sendall(b"0\r\n\r\n")
                    except OSError:
                        pass
                usage = gemini_usage(bytes(response_bytes), content_type) if api == "gemini" else extract_usage(bytes(response_bytes), content_type, api)
                actual = gemini_charge(usage, section["rates"]) if api == "gemini" else usage_charge(usage, section["rates"], api)
        except (OSError, ValueError, http.client.HTTPException) as error:
            cancelled = self.closed.is_set()
            if not cancelled:
                failed = True
                record.update(upstream_error=type(error).__name__ + ": " + str(error)[:300])
                raise
        finally:
            if upstream:
                with self.lock:
                    self.upstreams.discard(upstream)
                upstream.close()
            (folder / "response.body").write_bytes(bytes(response_bytes))
            if cancelled and actual is None:
                # A deliberately aborted stream may still be billed; charge its hard bound.
                actual = bound
                record.update(charged_at_bound="cancelled")
            elif failed and actual is None:
                # The upstream connection broke mid-request; the provider may still bill it, so charge its hard bound.
                actual = bound
                record.update(charged_at_bound="upstream_failure")
            elif actual is None and record.get("http_status", 200) >= 400:
                # An error reply reports no usage; charge the bound rather than assume it was free.
                actual = bound
                record.update(charged_at_bound="error_response")
            record.update(status="complete" if actual is not None else "usage_unknown", charged_usd=str(actual) if actual is not None else None)
            write(folder / "usage.json", record)
            self.ledger.settle(key, actual)

    def _control(self, connection):
        """Worker-only control plane: reserve and register generator sandboxes before creation."""
        stream = connection.makefile("rb")
        request = read_request(stream)
        (method, path, _), headers = request
        body = json.loads(stream.read(int(headers.get("content-length", "0"))) or b"{}")
        stream.close()
        if headers.get("x-cekura-control") != self.placeholder or method != "POST":
            return self._deny(connection, "control request denied")
        if path == "/sandbox/reserve":
            if self.closed.is_set():
                return self._deny(connection, "scope closed: sandbox")
            rates = self.config["sandbox"]["rates"]
            limit = self.config["sandbox"]["max_lifetime_seconds"]
            cpu, memory = max(float(body.get("cpu") or 0), 1.0), max(float(body.get("memory") or 0), 1024) / 1024
            lifetime = min(int(body.get("lifetime") or limit), limit)
            bound = Decimal(str((lifetime + self.config["sandbox"]["teardown_grace_seconds"]) * (cpu * rates["cpu_core_second"] + memory * rates["memory_gib_second"])))
            key = "%s/%s/generator-sandbox-%d" % (self.scope, self.instance, len(self.sandboxes) + 1)
            try:
                self.ledger.reserve(key, "target", bound, infrastructure_only=True, scope=self.scope, generator_sandbox=True)
            except BudgetError as error:
                return self._reply(connection, 402, {"error": str(error)})
            self.sandboxes.append({"key": key, "lifetime": lifetime, "reserved_usd": str(bound), "object_id": None})
            return self._reply(connection, 200, {"key": key, "lifetime": lifetime, "scope": self.scope})
        if path == "/sandbox/created":
            row = next((s for s in self.sandboxes if s["key"] == body.get("key")), None)
            if row is None:
                return self._reply(connection, 404, {})
            row["object_id"] = body.get("object_id")
            return self._reply(connection, 200, {})
        return self._reply(connection, 404, {})

    def _reply(self, connection, status, value):
        data = json.dumps(value).encode()
        connection.sendall(b"HTTP/1.1 %d X\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % (status, len(data)) + data)

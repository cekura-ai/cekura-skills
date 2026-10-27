"""Private HTTP/1 TLS gateway: unchanged JSON payloads, bounded request admission.

Never trusts target-reported costs. No provider key is persisted in evidence.
The same connection handler can run on localhost or a Modal stdio relay.
"""
from __future__ import annotations

import http.client
import json
import os
import socketserver
import ssl
import subprocess
import threading
from decimal import Decimal
from pathlib import Path

from .budget import BudgetError, require_cumulative
from .common import digest, write

MAX_BODY = 8 * 1024 * 1024


def validate_admission(section, kind, allowance=None):
    failures = []
    admission = section.get("admission", {})
    for name in ("input_token_limit", "output_token_limit"):
        value = admission.get(name)
        if type(value) is not int or value <= 0:
            failures.append(kind + " request token bound missing: " + name)
    if not admission.get("token_bound_evidence"):
        failures.append(kind + " provider token-limit evidence missing")
    cap = admission.get("hard_cap", {})
    allowance = (5 if kind == "proposer" else 20) if allowance is None else allowance
    value = cap.get("remaining_usd")
    if (cap.get("verified") is not True or cap.get("experiment_exclusive") is not True
            or not cap.get("evidence") or not cap.get("credential_sha256")
            or not isinstance(value, (int, float)) or not 0 < value <= allowance):
        failures.append(kind + " experiment-specific hard spending cap unverified")
    if cap.get("enforcement") == "admission_gateway" and cap.get("code_sha256") != digest(Path(__file__)):
        failures.append(kind + " admission spending-cap evidence belongs to different gateway code")
    env = section.get("credential_env")
    if env and os.environ.get(env) and cap.get("credential_sha256") and cap["credential_sha256"] != digest(os.environ[env].encode()):
        failures.append(kind + " hard cap belongs to a different credential")
    if section.get("billing_usage_verified") is not True:
        failures.append(kind + " authoritative request usage semantics unverified")
    return failures


def request_bound(payload, section):
    """Use provider-enforced context/default output limits, never a guess tokenizer."""
    cfg = section["admission"]
    maximum = cfg["output_token_limit"]
    for key in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
        if key in payload:
            if type(payload[key]) is not int or not 0 < payload[key] <= maximum:
                raise BudgetError("Request output limit exceeds the verified provider bound")
            maximum = min(maximum, payload[key])
    rates = section["rates"]
    # Reserve all input uncached; cache pricing can only reduce the charge.
    rate_keys = ["input_per_million", "cached_input_per_million"]
    if "cache_write_per_million" in rates and rates["cache_write_per_million"] is not None:
        rate_keys.append("cache_write_per_million")
    input_rate = max(Decimal(str(rates[k])) for k in rate_keys)
    return (Decimal(cfg["input_token_limit"]) * input_rate
            + Decimal(maximum) * Decimal(str(rates["output_per_million"]))) / Decimal(1_000_000)


TEMPLATE_TOKENS = 4096


def body_section(section, body):
    """Byte-level BPE never yields more tokens than bytes; chat templates add a bounded number.

    The input bound is therefore the request's byte length plus TEMPLATE_TOKENS, never above
    the provider's verified context limit. Image or audio parts would break the premise, so
    requests containing them keep the full limit.
    """
    if any(marker in body for marker in (b'"image', b'"inlineData"', b'"inline_data"', b'"input_audio"', b'"document"')):
        return section
    admission = dict(section["admission"], input_token_limit=min(section["admission"]["input_token_limit"], len(body) + TEMPLATE_TOKENS))
    return dict(section, admission=admission)


def usage_charge(usage, rates, api):
    """Preserve each API's inclusive/exclusive cache token accounting."""
    if not isinstance(usage, dict):
        return None
    if api == "anthropic":
        keys = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
        values = [usage.get(k, 0) if k.startswith("cache_") else usage.get(k) for k in keys]
        if any(type(v) is not int or v < 0 for v in values):
            return None
        incoming, outgoing, cached, created = values
        creation_rate = rates.get("cache_write_per_million")
        if created and creation_rate is None:
            return None
        # Anthropic input_tokens excludes cache reads and cache creation.
        return (Decimal(incoming) * Decimal(str(rates["input_per_million"]))
                + Decimal(outgoing) * Decimal(str(rates["output_per_million"]))
                + Decimal(cached) * Decimal(str(rates["cached_input_per_million"]))
                + Decimal(created) * Decimal(str(creation_rate or 0))) / Decimal(1_000_000)
    incoming, outgoing, details = (("prompt_tokens", "completion_tokens", "prompt_tokens_details")
                                  if api == "chat" else ("input_tokens", "output_tokens", "input_tokens_details"))
    values = (usage.get(incoming), usage.get(outgoing), (usage.get(details) or {}).get("cached_tokens", 0))
    if any(type(v) is not int or v < 0 for v in values) or values[2] > (values[0] or 0):
        return None
    inp, out, cache = values
    return ((Decimal(inp - cache) * Decimal(str(rates["input_per_million"]))
             + Decimal(cache) * Decimal(str(rates["cached_input_per_million"]))
             + Decimal(out) * Decimal(str(rates["output_per_million"]))) / Decimal(1_000_000))


def extract_usage(body, content_type, api):
    try:
        events = []
        if "text/event-stream" in content_type:
            for group in body.decode().replace("\r\n", "\n").split("\n\n"):
                data = "\n".join(line[5:].lstrip() for line in group.splitlines() if line.startswith("data:"))
                if data and data != "[DONE]":
                    events.append(json.loads(data))
        else:
            events = [json.loads(body)]
        if api == "anthropic":
            if "text/event-stream" in content_type and (not events or events[-1].get("type") != "message_stop"):
                return None
            combined = {}
            for event in events:
                usage = (event.get("message") or {}).get("usage") if event.get("type") == "message_start" else event.get("usage")
                if isinstance(usage, dict):
                    combined.update(usage)
            return combined or None
        for event in reversed(events):
            usage = event.get("usage") if api == "chat" else (event.get("response") or event).get("usage")
            if usage is not None:
                return usage
    except (ValueError, UnicodeError, AttributeError):
        pass
    return None


def certificates(directory, hostname):
    """Ephemeral CA; only its public certificate is copied into the target."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    ca, key, cert = directory / "ca.pem", directory / "server.key", directory / "server.pem"
    commands = [
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=Cekura private benchmark CA",
         "-keyout", str(directory / "ca.key"), "-out", str(ca)],
        ["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=Cekura benchmark model endpoint",
         "-keyout", str(key), "-out", str(directory / "server.csr")],
    ]
    extension = directory / "extensions.cnf"
    extension.write_text("subjectAltName=DNS:" + hostname + "\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n")
    commands.append(["openssl", "x509", "-req", "-in", str(directory / "server.csr"), "-CA", str(ca),
                     "-CAkey", str(directory / "ca.key"), "-CAcreateserial", "-days", "1", "-extfile", str(extension), "-out", str(cert)])
    for command in commands:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for path in directory.iterdir():
        path.chmod(0o600)
    return ca, cert, key


def read_request(stream):
    line = stream.readline(8193)
    if not line:
        return None
    if len(line) > 8192:
        raise ValueError("Request line too large")
    parts = line.decode("ascii").strip().split()
    if len(parts) != 3:
        raise ValueError("Malformed HTTP request")
    headers, size = {}, 0
    while True:
        line = stream.readline(8193)
        size += len(line)
        if size > 65536 or len(line) > 8192 or not line:
            raise ValueError("Malformed HTTP headers")
        if line == b"\r\n":
            break
        name, value = line.decode("latin1").split(":", 1)
        name = name.lower()
        if name in headers:
            raise ValueError("Duplicate HTTP header")
        headers[name] = value.strip()
    return parts, headers


class AdmissionGateway:
    def __init__(self, hostname, path, api, section, ledger, scope, directory, transport=None, verify=True):
        if verify:
            kind = "target" if api in ("chat", "anthropic") else "proposer"
            failures = validate_admission(section, kind, float(ledger.authorized_limits[kind]))
            if failures:
                raise BudgetError("; ".join(failures))
        if transport is None:
            require_cumulative(ledger, live=True)  # A live upstream spends money.
        self.hostname, self.path, self.api = hostname, path, api
        self.section, self.ledger, self.scope = section, ledger, scope
        self.verify = verify
        self.kind = "target" if api in ("chat", "anthropic") else "proposer"
        self.directory = Path(directory)
        self.ca, cert, key = certificates(self.directory / "tls", hostname)
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(cert, key)
        self.context.set_alpn_protocols(["http/1.1"])
        self.transport = transport or (lambda: http.client.HTTPSConnection(hostname, timeout=120))
        self.requests, self.denied, self.errors, self.auxiliary_denied = [], [], [], []
        self.counter, self.lock = 0, threading.Lock()
        owner = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                owner.handle(self.request)

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = False
            block_on_close = True

        self.server = Server(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def port(self):
        return self.server.server_address[1]

    @property
    def cost(self):
        entries = [e for e in self.ledger.state["entries"].values() if e.get("scope") == self.scope and e.get("entry_type") == "request"]
        if any(e["status"] != "complete" for e in entries):
            return None
        return sum((Decimal(e["charged"]) for e in entries), Decimal(0))

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def handle(self, connection):
        connection.settimeout(120)
        stream = connection.makefile("rb")
        try:
            request = read_request(stream)
            if request and request[0][:2] == ["CONNECT", "pi.dev:443"]:
                # Management catalogs cannot override the explicitly registered
                # custom target. Keep this blocked identically for every run.
                self.auxiliary_denied.append("pi.dev:443")
                connection.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                return
            if not request or request[0][:2] != ["CONNECT", self.hostname + ":443"]:
                self.denied.append("CONNECT endpoint denied: " + (request[0][1].split("?")[0] if request else "empty request"))
                connection.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                return
            connection.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            stream.close()
            with self.context.wrap_socket(connection, server_side=True) as secure:
                with secure.makefile("rb") as incoming:
                    while True:
                        request = read_request(incoming)
                        if request is None:
                            break
                        self._request(secure, incoming, request)
                        # One request per connection simplifies interruption accounting.
                        break
        except Exception as error:
            self.errors.append(type(error).__name__)
        finally:
            stream.close()

    def _request(self, secure, incoming, request):
        (method, path, _), headers = request
        if method != "POST" or path != self.path or headers.get("host") not in (self.hostname, self.hostname + ":443"):
            self.denied.append("Model request endpoint denied: " + method + " " + path.split("?")[0])
            secure.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            return
        if headers.get("transfer-encoding") or headers.get("content-encoding") or "expect" in headers:
            raise ValueError("Unsupported request framing; never forward unbounded payloads")
        length = int(headers.get("content-length", "-1"))
        if not 0 < length <= MAX_BODY:
            raise ValueError("Request body outside bounded capture")
        body = incoming.read(length)
        if len(body) != length:
            raise ValueError("Incomplete request body")
        payload = json.loads(body)
        if payload.get("model") != self.section.get("model", self.section.get("snapshot", {}).get("model")):
            self.denied.append("Unpinned model denied")
            secure.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            return
        expected = os.environ.get(self.section.get("credential_env", ""))
        auth_matches = headers.get("authorization") == "Bearer " + expected if expected else False
        auth_matches = auth_matches or (self.api == "anthropic" and headers.get("x-api-key") == expected)
        if self.verify and expected and not auth_matches:
            raise ValueError("Unexpected provider credential")
        with self.lock:
            self.counter += 1
            number = self.counter
            key = self.scope + "/request-%d" % number
        bound = request_bound(payload, body_section(self.section, body))
        try:
            self.ledger.reserve(key, self.kind, bound, entry_type="request", scope=self.scope)
        except BudgetError:
            self.errors.append("budget_admission_denied")
            secure.sendall(b"HTTP/1.1 402 Budget Exhausted\r\nContent-Length: 0\r\n\r\n")
            return
        directory = self.directory / ("request-%d" % number)
        directory.mkdir(mode=0o700)
        (directory / "request.body").write_bytes(body)
        write(directory / "request.json", {"method": method, "path": path, "body_sha256": digest(body),
              "reserved_usd": str(bound), "headers": {k:v for k,v in headers.items() if k not in ("authorization", "x-api-key", "cookie", "proxy-authorization")}})
        upstream, actual, usage = None, None, None
        response_bytes = bytearray()
        record = {"key": key, "request_sha256": digest(body), "status": "incomplete"}
        self.requests.append(record)
        try:
            upstream = self.transport()
            forwarded = {k:v for k,v in headers.items() if k not in ("connection", "proxy-connection", "proxy-authorization")}
            upstream.request(method, path, body=body, headers=forwarded)
            response = upstream.getresponse()
            content_type = response.getheader("Content-Type", "")
            secure.sendall(("HTTP/1.1 %d %s\r\n" % (response.status, response.reason)).encode())
            for name, value in response.getheaders():
                if name.lower() not in ("transfer-encoding", "content-length", "connection", "set-cookie"):
                    secure.sendall((name + ": " + value + "\r\n").encode("latin1"))
            secure.sendall(b"Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n")
            disconnected = False
            while True:
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
                        disconnected = True  # Drain upstream to recover authoritative usage.
            if not disconnected:
                secure.sendall(b"0\r\n\r\n")
            usage = extract_usage(bytes(response_bytes), content_type, self.api)
            actual = usage_charge(usage, self.section["rates"], self.api)
            record.update(status="complete" if actual is not None else "usage_unknown", http_status=response.status)
        finally:
            if upstream:
                upstream.close()
            (directory / "response.body").write_bytes(response_bytes)
            write(directory / "usage.json", {"usage": usage, "cost_usd": str(actual) if actual is not None else None})
            self.ledger.settle(key, actual)

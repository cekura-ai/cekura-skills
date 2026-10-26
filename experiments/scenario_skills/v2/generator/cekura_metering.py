"""Experiment transport for the pinned generator's sandbox. Installed as app/cekura_metering.py.

Only transport changes: the sandbox is reserved with the host metering service before it
exists, created with its network blocked from the experiment-owned image and secret, and
given a stdio relay whose connections the worker pumps to the metering CONNECT port. The
generator's prompts, models, phases and parsing are untouched. Without CEKURA_METERING=1
this module does nothing.
"""
import base64
import json
import os
import socket
import threading
import urllib.request

ACTIVE = os.environ.get("CEKURA_METERING") == "1"
_permit = threading.local()
_attached = {}
RELAY = "/app/.cekura_relay.py"
CA = "/app/.cekura_ca.pem"


def _control(path, body):
    host, port = os.environ["CEKURA_METERING_CONTROL"].rsplit(":", 1)
    data = json.dumps(body).encode()
    request = urllib.request.Request("http://%s:%s%s" % (host, port, path), data=data, method="POST", headers={
        "content-type": "application/json", "x-cekura-control": os.environ["CEKURA_METERING_TOKEN"]})
    # The control address is a literal internal IP; never route it through a proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=30) as response:
        return json.load(response)


def _backend():
    if os.environ.get("CEKURA_SANDBOX_BACKEND") == "local-docker":
        from app import cekura_local_sandbox
        return cekura_local_sandbox
    import modal
    return modal


def guard_sandbox_creation():
    """Refuse every sandbox the metered path did not reserve (installed by sitecustomize)."""
    import modal
    original = modal.Sandbox.create

    def create(*args, **kwargs):
        if not getattr(_permit, "granted", False):
            raise RuntimeError("Unmetered sandbox creation refused by the experiment instrumentation")
        return original(*args, **kwargs)
    modal.Sandbox.create = create


def create_sandbox(app, name, image, secrets, workdir, idle_timeout, timeout, **extra):
    """Replaces modal.Sandbox.create on the generator path. Arguments it overrides are recorded."""
    grant = _control("/sandbox/reserve", {"lifetime": timeout, "cpu": extra.get("cpu"), "memory": extra.get("memory")})
    backend = _backend()
    pinned = backend.Image.from_id(os.environ["CEKURA_GENERATOR_IMAGE"])
    _permit.granted = True
    try:
        sb = backend.Sandbox.create(app=app, name=name, image=pinned,
                                    secrets=[backend.Secret.from_name(os.environ["CEKURA_GENERATOR_SECRET"])],
                                    workdir=workdir, idle_timeout=min(idle_timeout, grant["lifetime"]),
                                    timeout=grant["lifetime"], block_network=True, **extra)
    finally:
        _permit.granted = False
    try:
        sb.set_tags({"cekura_scope": grant["scope"]})
    finally:
        _control("/sandbox/created", {"key": grant["key"], "object_id": sb.object_id})
    attach(sb)
    return sb


def attach(sb):
    """Start the in-sandbox relay and pump its connections to the metering CONNECT port."""
    if getattr(sb, "object_id", None) in _attached:
        return _attached[sb.object_id]
    from pathlib import Path
    sb.filesystem.write_text(Path(__file__).with_name("cekura_relay.py").read_text(), RELAY)
    sb.filesystem.write_text(Path(os.environ["CEKURA_METERING_CA"]).read_text(), CA)
    process = sb.exec("python3", RELAY, bufsize=1)
    # One reader for the whole stream: Modal delivers output to a single iterator, so a second
    # iteration (e.g. a fresh `for` over process.stdout in the pump) never receives the relay's events.
    lines = iter(process.stdout)
    ready = json.loads(next(lines))
    if ready.get("type") != "ready":
        raise RuntimeError("Generator relay did not start")
    host, port = os.environ["CEKURA_METERING_CONNECT"].rsplit(":", 1)
    connections, lock = {}, threading.Lock()

    def send(event):
        with lock:
            process.stdin.write(json.dumps(event) + "\n")
            process.stdin.drain()

    def upstream(identifier, connection):
        try:
            while True:
                data = connection.recv(32768)
                if not data:
                    break
                send({"type": "data", "id": identifier, "data": base64.b64encode(data).decode()})
        except OSError:
            pass
        finally:
            connections.pop(identifier, None)
            connection.close()
            try:
                send({"type": "close", "id": identifier})
            except Exception:
                pass

    def pump():
        try:
            for line in lines:
                event = json.loads(line)
                if event["type"] == "open":
                    connection = socket.create_connection((host, int(port)), timeout=300)
                    connections[event["id"]] = connection
                    threading.Thread(target=upstream, args=(event["id"], connection), daemon=True).start()
                elif event["type"] == "data" and event["id"] in connections:
                    connections[event["id"]].sendall(base64.b64decode(event["data"], validate=True))
                elif event["type"] == "close" and event["id"] in connections:
                    try:
                        connections[event["id"]].shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
        finally:
            for connection in list(connections.values()):
                connection.close()
    threading.Thread(target=pump, daemon=True, name="cekura-relay-pump").start()
    _attached[sb.object_id] = ready["port"]
    return ready["port"]


def exec_kwargs(sb):
    """Proxy and trust settings for the generator process; children inherit them."""
    if not ACTIVE:
        return {}
    proxy = "http://127.0.0.1:%d" % attach(sb)
    return {"env": {"HTTPS_PROXY": proxy, "https_proxy": proxy, "HTTP_PROXY": proxy, "http_proxy": proxy,
                    "NO_PROXY": "localhost,127.0.0.1", "NODE_USE_ENV_PROXY": "1", "NODE_EXTRA_CA_CERTS": CA,
                    "SSL_CERT_FILE": CA, "REQUESTS_CA_BUNDLE": CA}}

"""Isolated real-backend stack: pinned handlers, persistence, Celery jobs and metered generation.

Per experiment: one internal Docker network (no external route, no external DNS) and a
Postgres server holding a fully migrated template database. Per rollout: a database
cloned from the template, fresh Redis and object store, the host metering service, an
edge forwarder that owns the provider and Modal names, and the instrumented pinned
backend's web and worker containers. Backend processes receive placeholder credentials
only. Teardown closes metering first, then removes every container and sandbox tagged
with the rollout scope.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import time
import urllib.request
from pathlib import Path

from ..common import digest, write
from .metering import Metering

POSTGRES, REDIS = "postgres:15-alpine", "redis:7-alpine"
OBJECT_STORE = "cekura-object-store:moto-5.1.4"
BACKEND = "cekura-backend-instrumented:650297f"
TEMPLATE = "cekura_template"
# Names the backend or its sandbox may try. Metered and pass-through names reach metering;
# the rest resolve to the edge too, so any attempt is denied and recorded, never silent.
KNOWN_PROVIDER_HOSTS = ("api.anthropic.com", "bedrock-runtime.us-east-1.amazonaws.com", "bedrock-runtime.us-west-2.amazonaws.com",
                        "pass.wafer.ai", "inference.baseten.co", "api.deepinfra.com", "aiplatform.googleapis.com",
                        "us-aiplatform.googleapis.com", "oauth2.googleapis.com", "api.openai.com", "api.groq.com",
                        "api.autoloops.ai", "api.vapi.ai", "raw.githubusercontent.com", "statsig.anthropic.com",
                        "deb.nodesource.com", "registry.npmjs.org", "pypi.org")
# Modal's sandbox exec/filesystem path dials per-task hosts (task-....w.modal.host). Docker's
# embedded DNS cannot hold a wildcard, so the edge also answers DNS for Modal's task domain
# with its own address; containers use it as their upstream resolver. Everything else gets
# NXDOMAIN (container and alias names are answered by Docker before reaching it).
DNS_SUFFIX = ".modal.host"


def dns_answer(packet, ip, suffix=DNS_SUFFIX):
    """One DNS reply: A records for names under ``suffix``; empty NOERROR for their other types; NXDOMAIN otherwise."""
    if len(packet) < 12:
        return None
    labels, i = [], 12
    while i < len(packet) and packet[i]:
        labels.append(packet[i + 1:i + 1 + packet[i]].decode("ascii", "replace"))
        i += 1 + packet[i]
    question_end = i + 5
    if question_end > len(packet):
        return None
    name, qtype = ".".join(labels).lower(), int.from_bytes(packet[i + 1:i + 3], "big")
    ours = ("." + name).endswith(suffix)
    answer = b""
    if ours and qtype == 1:
        answer = b"\xc0\x0c" + (1).to_bytes(2, "big") + (1).to_bytes(2, "big") + (30).to_bytes(4, "big") + (4).to_bytes(2, "big") + bytes(int(x) for x in ip.split("."))
    flags = 0x8180 if ours else 0x8183
    header = packet[:2] + flags.to_bytes(2, "big") + (1).to_bytes(2, "big") + (1 if answer else 0).to_bytes(2, "big") + b"\x00\x00\x00\x00"
    return header + packet[12:question_end] + answer


EDGE = """import socket, sys, threading
target = (sys.argv[1], int(sys.argv[2]))
def pipe(a, b):
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try: s.shutdown(socket.SHUT_RDWR)
            except OSError: pass
def serve(client):
    try:
        upstream = socket.create_connection(target, timeout=30)
    except OSError:
        client.close(); return
    threading.Thread(target=pipe, args=(upstream, client), daemon=True).start()
    pipe(client, upstream)
def dns():
    own = socket.gethostbyname(socket.gethostname())
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); udp.bind(("0.0.0.0", 53))
    while True:
        packet, peer = udp.recvfrom(2048)
        reply = dns_answer(packet, own)
        if reply:
            udp.sendto(reply, peer)
threading.Thread(target=dns, daemon=True).start()
server = socket.socket(); server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", 443)); server.listen(64)
while True:
    connection, _ = server.accept()
    threading.Thread(target=serve, args=(connection,), daemon=True).start()
"""


def docker(*args, check=True, capture=True, timeout=600, stdin=None):
    result = subprocess.run(["docker", *args], capture_output=capture, text=True, timeout=timeout, input=stdin)
    if check and result.returncode:
        raise RuntimeError("docker %s failed: %s" % (args[0], (result.stderr or "")[-800:]))
    return result.stdout.strip() if capture else ""


def image_id(name):
    return docker("image", "inspect", "--format", "{{.Id}}", name)


def base_environment(database, network_names):
    """Explicit allowlist. Nothing is inherited from a production .env or the host."""
    return {
        "DB_HOST": network_names["postgres"], "DB_NAME": database, "DB_USER": "postgres", "DB_PASSWORD": network_names["db_password"],
        "DB_PORT": "5432", "REDIS_URL": "redis://%s:6379/0" % network_names["redis"],
        "SECRET_KEY": network_names["secret_key"], "STORAGE_BACKEND": "aws", "AWS_S3_BUCKET_NAME": "cekura-experiment",
        "AWS_ACCESS_KEY_ID": "isolated-object-store", "AWS_SECRET_ACCESS_KEY": "isolated-object-store",
        "AWS_DEFAULT_REGION": "us-east-1", "AWS_ENDPOINT_URL": "http://%s:9000" % network_names["object_store"],
        "CUSTOM_CODE_EXECUTION": "local", "ENVIRONMENT": "cekura-experiment",
        "VERTEX_PROJECT_ID": "cekura-experiment-offline", "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        "DD_TRACE_ENABLED": "false", "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "false", "DISABLE_DD_LOGGING": "True",
        "PYTHONUNBUFFERED": "1",
        # Seeded run transcripts are encrypted fields; never the repository's default key.
        "CRYPTO_KEY": base64.urlsafe_b64encode(hashlib.sha256(("crypto:" + network_names["secret_key"]).encode()).digest()).decode()}


def offline_vertex_credentials(directory):
    """Import-time Vertex client construction needs a parseable service account; this one is inert."""
    path = Path(directory) / "vertex.json"
    if not path.exists():
        key = subprocess.check_output(["openssl", "genrsa", "2048"], stderr=subprocess.DEVNULL, text=True)
        write(path, {"type": "service_account", "project_id": "cekura-experiment-offline", "private_key_id": "offline",
                     "private_key": key, "client_email": "offline@cekura-experiment-offline.iam.gserviceaccount.com",
                     "client_id": "0", "token_uri": "https://oauth2.googleapis.com/token"})
    return path.read_text()


class Infrastructure:
    """One internal network and migrated template per experiment run directory."""
    def __init__(self, directory, name=None):
        self.directory = Path(directory)
        self.name = name or "cekura-exp-" + digest(str(self.directory.resolve()))[:12]
        self.state_path = self.directory / "backend-infrastructure.json"
        self.spec_path = self.directory / "backend-openapi.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}

    def names(self):
        return {"network": self.name, "postgres": self.name + "-pg", "db_password": self.state["db_password"],
                "secret_key": self.state["secret_key"]}

    def ensure(self):
        if not self.state:
            self.state = {"db_password": secrets.token_hex(16), "secret_key": secrets.token_hex(32)}
            write(self.state_path, self.state)
        if not docker("network", "ls", "-q", "--filter", "name=^%s$" % self.name):
            docker("network", "create", "--internal", "--label", "cekura_experiment=" + self.name, self.name)
        self.gateway = docker("network", "inspect", self.name, "-f", "{{(index .IPAM.Config 0).Gateway}}")
        pg = self.names()["postgres"]
        if not docker("ps", "-q", "--filter", "name=^%s$" % pg):
            docker("rm", "-f", pg, check=False)
            docker("run", "-d", "--name", pg, "--network", self.name, "--label", "cekura_experiment=" + self.name,
                   "-e", "POSTGRES_PASSWORD=" + self.state["db_password"], "--tmpfs", "/var/lib/postgresql/data", POSTGRES)
            for _ in range(60):
                if docker("exec", pg, "pg_isready", "-U", "postgres", check=False).endswith("accepting connections"):
                    break
                time.sleep(1)
            docker("exec", pg, "psql", "-U", "postgres", "-c", "CREATE ROLE authenticated NOLOGIN", "-c", "CREATE DATABASE " + TEMPLATE)
            self.state.pop("template_migrated", None)
        if not self.state.get("template_migrated"):
            env = base_environment(TEMPLATE, dict(self.names(), redis="unused", object_store="unused"))
            env.update(VERTEX_CREDS=offline_vertex_credentials(self.directory), GEMINI_AUTHORIZATION="migration-has-no-provider-access")
            args = ["run", "--rm", "--network", self.name]
            for k, v in env.items():
                args += ["-e", k + "=" + v]
            log = docker(*args, BACKEND, "python", "manage.py", "migrate", "--noinput", timeout=1800)
            (self.directory / "backend-migrate.log").write_text(log)
            self.state.update(template_migrated=True, backend_image=image_id(BACKEND))
            write(self.state_path, self.state)
        if not self.spec_path.exists():
            # The bridge's tool→REST operations come from the pinned backend's own schema, generated offline.
            env = base_environment(TEMPLATE, dict(self.names(), redis="unused", object_store="unused"))
            env.update(VERTEX_CREDS=offline_vertex_credentials(self.directory), GEMINI_AUTHORIZATION="schema-has-no-provider-access")
            args = ["run", "--rm", "--network", "none"]
            for k, v in env.items():
                args += ["-e", k + "=" + v]
            spec = docker(*args, BACKEND, "sh", "-c", "python manage.py spectacular --format openapi-json --file /tmp/openapi.json "
                          ">/dev/null 2>&1 && cat /tmp/openapi.json", timeout=600)
            self.spec_path.write_text(spec)
            self.state["openapi_sha256"] = digest(self.spec_path)
            write(self.state_path, self.state)
        return self

    def database(self, scope):
        name = "rollout_" + re.sub(r"[^a-z0-9]", "", scope.lower())[:40]
        pg = self.names()["postgres"]
        docker("exec", pg, "psql", "-U", "postgres", "-c", "DROP DATABASE IF EXISTS %s" % name, "-c", "CREATE DATABASE %s TEMPLATE %s" % (name, TEMPLATE))
        return name

    def drop(self, database):
        docker("exec", self.names()["postgres"], "psql", "-U", "postgres", "-c", "DROP DATABASE IF EXISTS %s WITH (FORCE)" % database, check=False)

    def destroy(self):
        for container in docker("ps", "-aq", "--filter", "label=cekura_experiment=" + self.name).split():
            docker("rm", "-f", container, check=False)
        docker("network", "rm", self.name, check=False)


class Stack:
    """One rollout's backend. Use as a context manager; exit always tears everything down."""
    def __init__(self, infrastructure, scope, directory, generator, ledger, transport=None, sandbox_backend="modal", workers=4):
        self.infra, self.scope, self.directory = infrastructure, scope, Path(directory)
        self.generator, self.ledger, self.transport = generator, ledger, transport
        self.sandbox_backend, self.workers = sandbox_backend, workers
        self.label = "cekura_scope=" + scope
        self.containers, self.teardown = {}, {}

    def _run(self, role, image, command=(), env=None, aliases=(), extra=()):
        name = "%s-%s-%s" % (self.infra.name, role, digest(self.scope)[:10])
        docker("rm", "-f", name, check=False)
        args = ["run", "-d", "--name", name, "--network", self.infra.name, "--label", self.label,
                "--label", "cekura_experiment=" + self.infra.name, "--network-alias", name]
        for alias in aliases:
            args += ["--network-alias", alias]
        for k, v in (env or {}).items():
            args += ["-e", k + "=" + v]
        self.containers[role] = docker(*args, *extra, image, *command)
        return name

    def __enter__(self):
        try:
            return self.start()
        except BaseException:
            self.stop("startup failed")
            raise

    def __exit__(self, *args):
        self.stop("rollout finished" if args[0] is None else "rollout aborted: " + args[0].__name__)

    def start(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.database = self.infra.database(self.scope)
        names = dict(self.infra.names(), redis=self._run("redis", REDIS), object_store=self._run("s3", OBJECT_STORE))
        splice = None
        if self.sandbox_backend == "local-docker":
            def splice(host):
                raise OSError("Offline drill: Modal pass-through disabled for " + host)
        self.metering = Metering(self.generator, self.ledger, self.scope, self.directory / "metering",
                                 bind=self.infra.gateway, transport=self.transport, splice=splice)
        self.metering.__enter__()
        hosts = sorted(set(self.metering.endpoints) | self.metering.passthrough | set(KNOWN_PROVIDER_HOSTS))
        import inspect
        edge_source = "DNS_SUFFIX = %r\n" % DNS_SUFFIX + inspect.getsource(dns_answer) + EDGE
        edge = self._run("edge", BACKEND, ["python", "-c", edge_source, self.infra.gateway, str(self.metering.port("tls"))], aliases=hosts)
        resolver = ["--dns", docker("inspect", "-f", "{{(index .NetworkSettings.Networks \"%s\").IPAddress}}" % self.infra.name, edge)]
        ca = self.directory / "metering" / "trust"
        ca.mkdir(exist_ok=True)
        # Public roots stay trusted for the Modal pass-through; provider names terminate at metering.
        (ca / "bundle.pem").write_text(Path("/etc/ssl/certs/ca-certificates.crt").read_text() + self.metering.ca.read_text())
        (ca / "ca.pem").write_text(self.metering.ca.read_text())
        os.chmod(ca, 0o755)
        for path in ca.iterdir():
            path.chmod(0o644)
        env = base_environment(self.database, names)
        env.update(self.generator["backend_env"])
        env.update({"VERTEX_CREDS": offline_vertex_credentials(self.infra.directory),
                    "FIREWORKS_API_KEY": self.metering.placeholder, "GEMINI_AUTHORIZATION": self.metering.placeholder,
                    "GEMINI_API_KEY": self.metering.placeholder, "SSL_CERT_FILE": "/cekura/trust/bundle.pem",
                    "REQUESTS_CA_BUNDLE": "/cekura/trust/bundle.pem", "CEKURA_METERING": "1", "CEKURA_SCOPE": self.scope,
                    "CEKURA_METERING_CONTROL": "%s:%d" % (self.infra.gateway, self.metering.port("control")),
                    "CEKURA_METERING_CONNECT": "%s:%d" % (self.infra.gateway, self.metering.port("connect")),
                    "CEKURA_METERING_TOKEN": self.metering.placeholder, "CEKURA_METERING_CA": "/cekura/trust/ca.pem",
                    "CEKURA_GENERATOR_IMAGE": self.generator["sandbox_image"], "CEKURA_GENERATOR_SECRET": self.generator["modal_secret"],
                    "MODAL_SECRET_NAME": self.generator["modal_secret"], "CEKURA_SANDBOX_BACKEND": self.sandbox_backend})
        mounts = ["-v", "%s:/cekura/trust:ro" % ca]
        if self.sandbox_backend == "local-docker":
            # Offline drills only: the local sandbox stand-in creates sibling containers.
            secrets_file = self.directory / "local-secrets.json"
            write(secrets_file, {self.generator["modal_secret"]: self.generator.get("sandbox_secret_env", {})})
            secrets_file.chmod(0o644)
            mounts += ["-v", "/var/run/docker.sock:/var/run/docker.sock", "-v", "%s:/cekura/local-secrets.json:ro" % secrets_file]
            env["CEKURA_LOCAL_SECRETS"] = "/cekura/local-secrets.json"
        else:
            env.update({"MODAL_TOKEN_ID": os.environ["MODAL_TOKEN_ID"], "MODAL_TOKEN_SECRET": os.environ["MODAL_TOKEN_SECRET"]})
        self.env_sha256 = digest({k: v for k, v in env.items() if k not in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "DB_PASSWORD", "SECRET_KEY")})
        self.web = self._run("web", BACKEND, ["gunicorn", "synth_voice.asgi:application", "-k", "uvicorn_worker.UvicornWorker",
                                             "--bind", "0.0.0.0:8000", "--timeout", "600", "--workers", "2"], env, extra=mounts + resolver)
        self._run("worker", BACKEND, ["celery", "-A", "synth_voice", "worker", "--loglevel=info", "--pool=threads",
                                      "--concurrency=%d" % self.workers, "-Q", self.generator.get("queues", "simulation-eval")], env, extra=mounts + resolver)
        docker("exec", names["object_store"], "python", "-c",
               "import urllib.request;urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:9000/cekura-experiment',method='PUT'))")
        self.base_url = "http://%s:8000" % docker("inspect", "-f", "{{(index .NetworkSettings.Networks \"%s\").IPAddress}}" % self.infra.name, self.web)
        deadline = time.time() + 180
        while time.time() < deadline:
            try:
                urllib.request.build_opener(urllib.request.ProxyHandler({})).open(self.base_url + "/", timeout=5)
                break
            except urllib.error.HTTPError:
                break  # Any HTTP answer means the server is accepting requests.
            except OSError:
                time.sleep(2)
        else:
            raise RuntimeError("Backend web server did not start")
        self.env = env
        return self

    def manage(self, script, role="worker", timeout=300):
        """Run ORM code inside the rollout's own backend container (seeding, readback, events)."""
        # On stdin: a seeded v3 workspace is far larger than the kernel's argument limit.
        return docker("exec", "-i", self.containers[role], "python", "manage.py", "shell", timeout=timeout, stdin=script)

    def sandboxes(self):
        if self.sandbox_backend == "local-docker":
            return docker("ps", "-aq", "--filter", "label=" + self.label, "--filter", "label=cekura_sandbox_name").split()
        return [s["object_id"] for s in self.metering.sandboxes if s.get("object_id")]

    def stop(self, reason):
        """Stop spend first, then nested work, then the containers that could start more."""
        evidence = {"reason": reason, "started": time.time()}
        if getattr(self, "metering", None):
            self.metering.close(reason)
            evidence["metering_closed"] = True
        evidence["sandboxes"] = self._terminate_sandboxes()
        for role in ("worker", "web", "edge", "redis", "s3"):
            if role in self.containers:
                docker("rm", "-f", self.containers.pop(role), check=False)
        if getattr(self, "database", None):
            self.infra.drop(self.database)
        evidence["remaining_containers"] = docker("ps", "-aq", "--filter", "label=" + self.label, check=False).split()
        evidence["terminated"] = not evidence["remaining_containers"] and all(s["terminated"] for s in evidence["sandboxes"])
        evidence["finished"] = time.time()
        self.teardown = evidence
        write(self.directory / "teardown.json", evidence)
        return evidence

    def _terminate_sandboxes(self):
        rows = []
        if self.sandbox_backend == "local-docker":
            for container in docker("ps", "-aq", "--filter", "label=" + self.label, "--filter", "label=cekura_sandbox_name", check=False).split():
                docker("rm", "-f", container, check=False)
                rows.append({"id": container, "terminated": True})
            return rows
        import modal
        # Registered IDs plus a tag search: a worker may die between creation and registration.
        identifiers = {row["object_id"] for row in (getattr(self, "metering", None) and self.metering.sandboxes or []) if row.get("object_id")}
        try:
            app = modal.App.lookup(self.generator["modal_app"], create_if_missing=False)
            identifiers |= {sb.object_id for sb in modal.Sandbox.list(app_id=app.app_id, tags={"cekura_scope": self.scope})}
        except Exception as error:
            rows.append({"id": None, "terminated": False, "error": "tag search failed: " + type(error).__name__})
        for identifier in sorted(identifiers):
            try:
                modal.Sandbox.from_id(identifier).terminate()
                rows.append({"id": identifier, "terminated": True})
            except Exception as error:
                rows.append({"id": identifier, "terminated": False, "error": type(error).__name__})
        return rows

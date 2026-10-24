"""Exact-image evaluator, isolated MCP state and host-side model cost admission."""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import shutil
import socket
import tarfile
import time
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlparse

from .common import ROOT, REPO, digest, read, write
from .gateway import AdmissionGateway
from .runtime import delivered_skill, pin_runtime_files

LIFETIME = 600
CPU, MEMORY = (1.0, 1.0), (1024, 1024)
INFRA_RESERVATION = .10
MAX_TRANSFER = 64 * 1024 * 1024


def infrastructure_bound(evidence):
    from .modal_probe import RATES
    if evidence.get("source") != "https://modal.com/pricing" or not evidence.get("verified_at") or evidence.get("rates") != RATES:
        raise ValueError("Verified Modal sandbox rates are required")
    bound = LIFETIME * (RATES["cpu_core_second"] + RATES["memory_gib_second"]) + MAX_TRANSFER / 1024**3 * RATES["egress_gib"]
    if bound >= INFRA_RESERVATION:
        raise ValueError("Infrastructure bound cannot fit its reservation")
    return bound


def archive_files(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o444
            archive.addfile(info, io.BytesIO(data))
    return stream.getvalue()


async def relay_connections(process, gateway, ready, bridge=None):
    """Multiplex TLS bytes without decrypting them inside the target sandbox.

    Model connections go to the admission gateway; ``mcp`` connections, when a real-backend
    bridge is attached, go to that bridge on the host.
    """
    connections, pumps, threads = {}, [], []
    send_lock = asyncio.Lock()
    loop = asyncio.get_running_loop()
    transferred = 0

    async def send(event):
        nonlocal transferred
        line = (json.dumps(event) + "\n").encode()
        async with send_lock:
            transferred += len(line)
            if transferred > MAX_TRANSFER:
                raise ValueError("Relay transfer bound exhausted")
            process.stdin.write(line)
            await process.stdin.drain()

    async def pump(identifier, stream):
        try:
            while True:
                data = await loop.sock_recv(stream, 32768)
                if not data:
                    break
                await send({"type": "data", "id": identifier, "data": base64.b64encode(data).decode()})
        finally:
            connections.pop(identifier, None)
            stream.close()
            await send({"type": "close", "id": identifier})

    def serve(handler, stream):
        try:
            handler(stream)
        finally:
            stream.close()

    try:
        async for line in process.stdout:
            transferred += len(line.encode())
            if transferred > MAX_TRANSFER or len(line) > 65536:
                raise ValueError("Relay transfer bound exhausted")
            event = json.loads(line)
            if event["type"] == "ready":
                ready.set_result(event.get("ports", {"model": event["port"]}))
            elif event["type"] == "open":
                identifier = event["id"]
                a, b = socket.socketpair()
                a.setblocking(False)
                connections[identifier] = a
                import threading
                handler = bridge.handle if bridge is not None and event.get("service") == "mcp" else gateway.handle
                thread = threading.Thread(target=serve, args=(handler, b), daemon=True)
                thread.start()
                threads.append(thread)
                pumps.append(asyncio.create_task(pump(identifier, a)))
            elif event["type"] == "data" and event["id"] in connections:
                try:
                    await loop.sock_sendall(connections[event["id"]], base64.b64decode(event["data"], validate=True))
                except OSError:
                    await send({"type": "close", "id": event["id"]})
            elif event["type"] == "close" and event["id"] in connections:
                with suppress(OSError):
                    connections[event["id"]].shutdown(socket.SHUT_WR)
    finally:
        for stream in connections.values():
            stream.close()
        for task in pumps:
            task.cancel()
        await asyncio.gather(*pumps, return_exceptions=True)
        await asyncio.gather(*(asyncio.to_thread(thread.join, 125) for thread in threads))


class ModalRuntime:
    request_accounting = True

    def __init__(self, config, ledger, offline=False, offline_factory=None):
        self.config, self.ledger, self.offline = config, ledger, offline
        self.offline_factory = offline_factory or offline_transport
        root = REPO / "cekura/skills"
        self.fixed_skill_material = {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}

    def run(self, task, files, store, fixture_url, directory):
        from modal._utils.async_utils import synchronizer
        return synchronizer.create_blocking(_transaction)(self, task, files, store, directory)

    async def _run(self, task, files, store, directory):
        from modal.app import _App
        from modal.client import _Client
        from modal.image import _Image
        from modal.sandbox import _Sandbox
        from modal._utils.async_utils import synchronizer
        from modal.exception import SandboxFilesystemNotFoundError
        from modal_proto import api_pb2
        cfg, scope = self.config, directory.name
        bridge = store if hasattr(store, "handle") else None  # Real-backend bridge instead of the local fixture.
        infrastructure_bound(cfg["infrastructure_rates"])
        infra_key = scope + "/infrastructure"
        endpoint = urlparse(cfg["snapshot"]["model_base_url"])
        gateway = AdmissionGateway(endpoint.hostname, endpoint.path.rstrip("/") + "/v1/messages", "anthropic", cfg,
                                   self.ledger, scope, directory / "gateway",
                                   transport=self.offline_factory if self.offline else None, verify=not self.offline)
        # Relay calls the gateway connection handler directly; no localhost listener is needed.
        pinned = pin_runtime_files(cfg, directory / "runtime_material")
        upload = {"app/agent_runner.py": (pinned / "agent_runner.py").read_bytes(),
                  "app/pi_extension.ts": (pinned / "pi_extension.ts").read_bytes(),
                  "home/agent/.pi/agent/settings.json": (pinned / ".benchmark_pi_settings.json").read_bytes(),
                  "app/.context.json": json.dumps(task.get("context", {})).encode(),
                  "root/benchmark/task.json": json.dumps(sandbox_task(task)).encode(), "root/benchmark/catalog.json": json.dumps(cfg["catalog"]).encode(),
                  "root/benchmark/runtime-config.json": json.dumps({"snapshot": cfg["snapshot"]}).encode(),
                  "app/benchmark-ca.pem": gateway.ca.read_bytes(),
                  "opt/benchmark/experiments/__init__.py": b"", "opt/benchmark/experiments/scenario_skills/__init__.py": b""}
        all_skills = dict(self.fixed_skill_material)
        all_skills.update({"cekura-eval-design/" + k:v for k,v in files.items()})
        for name, data in all_skills.items():
            upload["home/agent/.claude/plugins/marketplaces/cekura-skills/cekura/skills/" + name] = data
        for name in ("common.py", "fixture.py", "runtime.py", "dataset.py", "network_guard.py", "modal_runtime.py", "relay.py", "gateway.py", "budget.py"):
            upload["opt/benchmark/experiments/scenario_skills/" + name] = (ROOT / name).read_bytes()
        if task.get("benchmark_version") == 2:
            for path in (ROOT / "v2").glob("*.py"):
                upload["opt/benchmark/experiments/scenario_skills/v2/" + path.name] = path.read_bytes()
        uploaded = {}
        for document in task.get("documents", []):
            name = Path(document["name"]).name
            upload["app/uploads/" + name] = document["content"].encode()
            uploaded[name] = {"path": "/app/uploads/" + name, "filename": name}
        upload["app/.session_files.json"] = json.dumps(list(uploaded)).encode()
        archive = archive_files(upload)
        write(directory / "transport-material.json", {name:digest(data) for name,data in upload.items()})
        if len(archive) > MAX_TRANSFER // 2:
            raise ValueError("Runtime installation exceeded transfer bound")
        self.ledger.reserve(infra_key, "target", INFRA_RESERVATION, infrastructure_only=True, scope=scope)
        client = await _Client.from_credentials(os.environ["MODAL_TOKEN_ID"], os.environ["MODAL_TOKEN_SECRET"])
        sandbox, relay, relay_task, relay_stderr = None, None, None, None
        start = time.monotonic()
        run = {"status": "infrastructure_failure", "messages": [], "events": [], "usage": []}
        try:
            write(directory / "phase.json", {"phase": "app_lookup"})
            app = await _App.lookup("cekura-scenario-skill-evaluation", client=client, create_if_missing=True)
            image = synchronizer._translate_in(_Image.from_id(cfg["image"], client=client))
            sandbox = await _Sandbox.create("sleep", str(LIFETIME), image=image, app=app, client=client,
                cpu=CPU, memory=MEMORY, timeout=LIFETIME, block_network=True,
                env=cfg["snapshot"]["runtime_env"], include_oidc_identity_token=False)
            write(directory / "phase.json", {"phase": "sandbox_created"})
            write(directory / "sandbox.json", {"id": sandbox.object_id, "image": cfg["image"], "timeout": LIFETIME})
            response = await client.stub.SandboxList(api_pb2.SandboxListRequest(app_id=app.app_id, include_finished=False))
            actual = next(s for s in response.sandboxes if s.id == sandbox.object_id)
            if (actual.image_id != cfg["image"] or actual.timeout_secs != LIFETIME
                    or actual.resource_info.milli_cpu_max != 1000 or actual.resource_info.memory_mb_max != 1024):
                raise ValueError("Modal image or hard resource limits differ from the pinned allocation")
            await sandbox.filesystem.write_bytes(archive, "/tmp/benchmark.tar.gz")
            setup = await sandbox.exec("python3", "-c", "import tarfile,os; tarfile.open('/tmp/benchmark.tar.gz').extractall('/'); os.chmod('/root/benchmark',0o700); os.chmod('/opt/benchmark',0o700); os.chmod('/app',0o1777)", timeout=20)
            await setup.wait()
            if setup.returncode:
                raise RuntimeError("Fixture installation failed")
            write(directory / "phase.json", {"phase": "installed"})
            services = ("--services", "model,mcp") if bridge is not None else ()
            relay = await sandbox.exec("python3", "-m", "experiments.scenario_skills.relay", *services, env={"PYTHONPATH": "/opt/benchmark"}, timeout=LIFETIME, bufsize=1)
            relay_stderr = asyncio.create_task(relay.stderr.read())
            ready = asyncio.get_running_loop().create_future()
            relay_task = asyncio.create_task(relay_connections(relay, gateway, ready, bridge))
            ports = await asyncio.wait_for(ready, 20)
            port = ports["model"]
            write(directory / "phase.json", {"phase": "relay_ready"})
            env = {"PYTHONPATH": "/opt/benchmark", "BENCHMARK_PROXY_PORT": str(port),
                   cfg["credential_env"]: "offline-transport-probe" if self.offline else os.environ[cfg["credential_env"]]}
            if bridge is not None:
                env["BENCHMARK_BRIDGE_PORT"] = str(ports["mcp"])
            remaining = max(1, int(LIFETIME - (time.monotonic() - start)))
            if self.offline:
                remaining = min(remaining, 90)
            process = await sandbox.exec("python3", "-m", "experiments.scenario_skills.modal_runtime", "--in-container", env=env, workdir="/app", timeout=remaining)
            runner_task = asyncio.ensure_future(asyncio.gather(process.stdout.read(), process.stderr.read(), process.wait()))
            done, _ = await asyncio.wait((runner_task, relay_task), timeout=remaining, return_when=asyncio.FIRST_COMPLETED)
            if relay_task in done:
                runner_task.cancel()
                await asyncio.gather(runner_task, return_exceptions=True)
                relay_task.result()  # Propagate transport errors immediately.
                raise RuntimeError("Model relay exited before the target runner finished")
            if runner_task not in done:
                runner_task.cancel()
                await asyncio.gather(runner_task, return_exceptions=True)
                raise asyncio.TimeoutError()
            stdout, stderr, _ = runner_task.result()
            (directory / "controller.stdout").write_text(stdout)
            (directory / "controller.stderr").write_text(stderr)
            write(directory / "phase.json", {"phase": "runner_finished", "returncode": process.returncode})
        except (asyncio.TimeoutError, TimeoutError):
            run["status"] = "timeout"
        except Exception as error:
            run["error"] = type(error).__name__ + ": " + str(error)
        finally:
            try:
                if sandbox:
                    transferred = len(archive)
                    paths = [("/root/benchmark/run.json", "run.json"), ("/root/benchmark/state.json", "state.json"),
                             ("/app/.pi_system_prompt.txt", "effective_system_prompt.txt")]
                    if task.get("benchmark_version") == 2:
                        paths.append(("/app/history.txt", "saved_history.txt"))
                    paths += [("/root/benchmark/turn-%d.%s" % (turn, suffix), "turn-%d.%s" % (turn, suffix))
                              for turn in range(8 if task.get("benchmark_version") == 2 else 4) for suffix in ("events.jsonl", "stderr")]
                    for remote, local in paths:
                        try:
                            data = await sandbox.filesystem.read_text(remote)
                            transferred += len(data.encode())
                            if transferred > MAX_TRANSFER:
                                raise ValueError("Artifact transfer bound exhausted")
                            (directory / local).write_text(data)
                        except (FileNotFoundError, SandboxFilesystemNotFoundError):
                            pass
            finally:
                try:
                    if sandbox:
                        await sandbox.terminate()
                        write(directory / "teardown.json", {"sandbox": sandbox.object_id, "terminated": True})
                finally:
                    if relay_task:
                        relay_task.cancel()
                        relay_result = await asyncio.gather(relay_task, return_exceptions=True)
                        write(directory / "relay-status.json", {"error": str(relay_result[0]) if isinstance(relay_result[0], Exception) else None})
                    if relay:
                        try:
                            (directory / "relay.stderr").write_text(await asyncio.wait_for(relay_stderr, 5))
                        except Exception as error:
                            write(directory / "relay-capture-error.json", {"error": type(error).__name__})
                    await client._close()
                    gateway.server.server_close()
                    self.ledger.transition(infra_key, "bounded_infrastructure_pending_billing")
        if (directory / "run.json").exists() and run["status"] != "timeout":
            run = read(directory / "run.json")
        if (directory / "state.json").exists() and bridge is None:
            # With a bridge the host trace and backend readback are authoritative, not the sandbox's copy.
            state = read(directory / "state.json")
            store.state, store.trace = state["state"], state["trace"]
        loaded = [e.get("path") for e in run["events"] if e.get("type") == "skill_file_read"]
        if loaded:
            exact = delivered_skill(files["SKILL.md"], cfg["snapshot"]["skill_max_chars"])
            (directory / "delivered_skill.txt").write_bytes(exact)
            write(directory / "skill_delivery.json", {"installed_sha256": digest(files["SKILL.md"]),
                  "delivered_sha256": digest(exact), "truncated": exact != files["SKILL.md"]})
        elif not any(e.get("name", "").endswith("cekura_load_skill") and not e["response"]["isError"] for e in store.trace):
            run["status"] = "inconclusive" if run["status"] == "complete" else run["status"]
        prompt = directory / "effective_system_prompt.txt"
        if not prompt.exists() or digest(prompt) != cfg["snapshot"]["system_prompt_sha256"]:
            run["status"] = "inconclusive" if run["status"] == "complete" else run["status"]
        if gateway.denied or gateway.errors:
            run["status"] = "infrastructure_failure"
        run.update(elapsed_seconds=time.monotonic() - start, request_accounting=True,
                   model_cost_usd=float(gateway.cost) if gateway.cost is not None else None,
                   infrastructure_reserved_usd=INFRA_RESERVATION,
                   gateway={"requests": gateway.requests, "errors": gateway.errors, "denied": gateway.denied,
                            "auxiliary_denied": gateway.auxiliary_denied})
        return run


async def _transaction(runtime, task, files, store, directory):
    return await runtime._run(task, files, store, directory)


def offline_transport():
    """Fixed local API response. This factory cannot open a provider connection."""
    class Response(io.BytesIO):
        status, reason = 200, "OK"

        def getheaders(self):
            return [("Content-Type", "text/event-stream")]

        def getheader(self, name, default=None):
            return dict(self.getheaders()).get(name, default)

    class Transport:
        def request(self, method, path, body, headers):
            pass

        def getresponse(self):
            events = [
                {"type": "message_start", "message": {"id": "offline-probe", "type": "message", "role": "assistant",
                    "model": "accounts/fireworks/routers/kimi-k3-fast", "content": [], "stop_reason": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0}}},
                {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Offline transport verified."}},
                {"type": "content_block_stop", "index": 0},
                {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 0}},
                {"type": "message_stop"}]
            return Response(b"".join(b"event: " + e["type"].encode() + b"\ndata: " + json.dumps(e).encode() + b"\n\n" for e in events))

        def close(self):
            pass
    return Transport()


def sandbox_task(task):
    """v3 follow-ups, expectations and plants stay on the host; the sandbox needs only the opening turn."""
    if task.get("benchmark_version") != 3:
        return task
    return {k: task[k] for k in ("id", "benchmark_version", "request", "documents", "context") if k in task}


def run_inside():
    """Root owns fixture evidence; original runner drops itself to uid 1000."""
    import subprocess
    import sys
    from .fixture import FixtureServer, Store
    evidence, app = Path("/root/benchmark"), Path("/app")
    task, cfg = read(evidence / "task.json"), read(evidence / "runtime-config.json")
    version2 = task.get("benchmark_version") in (2, 3)
    version3 = task.get("benchmark_version") == 3
    if version3 and not os.environ.get("BENCHMARK_BRIDGE_PORT"):
        raise SystemExit("v3 tasks run only against the real-backend bridge")
    if version2:
        from .v2.fixture import Store
    if os.environ.get("BENCHMARK_BRIDGE_PORT"):
        from .v2.bridge_client import ForwardingStore as Store
    skills = Path("/home/agent/.claude/plugins/marketplaces/cekura-skills/cekura/skills/cekura-eval-design")
    files = {str(p.relative_to(skills)): p.read_bytes() for p in skills.rglob("*") if p.is_file()}

    class CheckpointStore(Store):
        def call(self, *args):
            result = super().call(*args)
            if version2 and any(e.get("kind") == "cancel" and e.get("turn") == self.turn for e in self.trace):
                (app / ".cancel").touch()
            write(evidence / "state.json", {"state": self.state, "trace": self.trace})
            return result

    store = CheckpointStore(task, files, read(evidence / "catalog.json"))
    write(evidence / "state.json", {"state": store.state, "trace": store.trace})
    run = {"status": "complete", "messages": [], "events": [], "usage": []}
    history, prompt, start = [], task["request"], time.monotonic()
    if task.get("documents"):
        prompt += "\nAttached files are available in /app/uploads/."
    with FixtureServer(store) as fixture:
        settings = app / ".claude/settings.json"
        write(settings, {"mcpServers": {"cekura": {"type": "http", "url": fixture.url, "headers": {}}}})
        settings.parent.chmod(0o755); settings.chmod(0o644)
        # Override every agent-readable settings path; none may inherit a server.
        for path in (Path("/home/agent/.claude.json"), Path("/home/agent/.claude/settings.json")):
            path.parent.mkdir(parents=True, exist_ok=True)
            write(path, read(settings)); path.parent.chmod(0o755); path.chmod(0o644)
        proxy = "http://127.0.0.1:" + os.environ["BENCHMARK_PROXY_PORT"]
        env = dict(os.environ, HTTP_PROXY=proxy, HTTPS_PROXY=proxy, NO_PROXY="localhost,127.0.0.1",
                   NODE_USE_ENV_PROXY="1", NODE_EXTRA_CA_CERTS="/app/benchmark-ca.pem")
        env.pop("PYTHONPATH", None)
        max_turns = 12 if version3 else 8 if version2 else 4
        followup_index = 0
        run["user_turns"] = []
        for turn in range(max_turns):
            store.turn = turn
            if version2:
                store.apply_events(turn)
                (app / ".cancel").unlink(missing_ok=True)
            # The production runner owns history serialization and tool-call footers.
            # Preserve its saved history on v2 continuation, including cancelled turns.
            inputs = [("prompt.txt", prompt)]
            if not version2 or turn == 0:
                inputs.append(("history.txt", "\n".join(history)))
            for name, text in inputs:
                path = app / name
                path.write_text(text); path.chmod(0o644); os.chown(path, 1000, 1000)
            run["user_turns"].append(prompt)
            stdout = evidence / ("turn-%d.events.jsonl" % turn)
            with stdout.open("w") as out, (evidence / ("turn-%d.stderr" % turn)).open("w") as err:
                proc = subprocess.Popen([sys.executable, "/app/agent_runner.py", "--prompt-file", "/app/prompt.txt"],
                                        stdout=out, stderr=err, env=env, start_new_session=True)
                try:
                    proc.wait(timeout=max(1, LIFETIME - (time.monotonic() - start)))
                except subprocess.TimeoutExpired:
                    import signal
                    os.killpg(proc.pid, signal.SIGKILL); proc.wait()
                    run["status"] = "timeout"
            try:
                events = [json.loads(line) for line in stdout.read_text().splitlines() if line.strip()]
            except ValueError:
                run["status"] = "infrastructure_failure"; break
            run["events"].extend(dict(event, benchmark_turn=turn) for event in events)
            run["usage"].extend(e["usage"] for e in events if e.get("type") in ("assistant_complete", "needs_clarification", "error", "cancelled") and "usage" in e)
            if run["status"] != "complete":
                break
            if proc.returncode or any(e.get("type") == "error" for e in events):
                run["status"] = "infrastructure_failure"; break
            final = next((e for e in reversed(events) if e.get("type") in ("assistant_complete", "needs_clarification", "cancelled")), None)
            if not final:
                run["status"] = "inconclusive"; break
            message = final.get("full_content", final.get("clean_text", ""))
            run["messages"].append(message)
            history.extend(["user: " + prompt, "assistant: " + message])
            write(evidence / "run.json", run)
            next_followup = task.get("followups", [])[followup_index] if followup_index < len(task.get("followups", [])) else None
            if version3:
                # Conditional follow-ups: the host bridge decides from stored state.
                prompt = store.followup(turn, final["type"], run["messages"])
                if prompt is None:
                    break
            elif version2 and final["type"] == "needs_clarification" and not (next_followup and next_followup.get("reply_to_clarification")):
                prompt = task["clarification_reply"]
            elif version2 and next_followup:
                prompt = next_followup["message"]
                followup_index += 1
            elif not version2 and turn < len(task.get("followups", [])):
                prompt = task["followups"][turn]["message"]
            elif final["type"] == "needs_clarification" and turn < max_turns - 1:
                prompt = task["clarification_reply"]
            else:
                break
    for name, field in (("agent_runner.py", "runner_sha256"), ("pi_extension.ts", "extension_sha256")):
        if digest(app / name) != cfg["snapshot"][field]:
            run["status"] = "inconclusive"
    write(evidence / "run.json", run)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] != ["--in-container"]:
        raise SystemExit("Use the experiment controller")
    run_inside()

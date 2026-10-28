"""Run the original product-chat runner in a pinned image with restricted egress.

The image must contain the deployed Python/Node/Pi dependencies and iptables.
This adapter never replaces the Cekura target with a text-only model call.
"""
from __future__ import annotations

import json
import os
import select
import shutil
import socket
import socketserver
import subprocess
import threading
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlparse

from .common import ROOT, REPO, digest, write
from .dataset import visible
from .network_guard import NetworkGuard


def delivered_skill(data, maximum):
    """Mirror the pinned loader's character cap, including its exact suffix."""
    text = data.decode()
    return (text[:maximum] + "\n\n[Skill truncated.]" if len(text) > maximum else text).encode()


def pin_runtime_files(config, directory):
    """Snapshot runtime files for immutable mounts across all follow-up turns."""
    directory.mkdir()
    for key, name, hash_key in (("runner", "agent_runner.py", "runner_sha256"),
                                ("extension", "pi_extension.ts", "extension_sha256"),
                                ("pi_settings_path", ".benchmark_pi_settings.json", "pi_settings_sha256")):
        target = directory / name
        shutil.copyfile(config[key], target)
        if digest(target) != config["snapshot"][hash_key]:
            raise ValueError("Captured runtime file changed after preflight: " + key)
        target.chmod(0o644)
    return directory


class ModelProxy:
    """Only the fixed model host is reachable through the HTTPS CONNECT proxy."""
    def __init__(self, hostname, forward=True):
        self.hostname = hostname
        self.denied = []
        self.attempts = []
        owner = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                line = self.rfile.readline(8192).decode("ascii", "replace").strip().split()
                while self.rfile.readline(8192) not in (b"\r\n", b"\n", b""):
                    pass
                if len(line) != 3 or line[:2] != ["CONNECT", owner.hostname + ":443"]:
                    owner.denied.append(line[:2])
                    self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                    return
                owner.attempts.append(line[1])
                if not forward:
                    self.wfile.write(b"HTTP/1.1 502 Offline Probe\r\nContent-Length: 0\r\n\r\n")
                    return
                upstream = socket.create_connection((owner.hostname, 443), timeout=20)
                self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                self.wfile.flush()
                try:
                    self.connection.settimeout(20)
                    deadline = time.monotonic() + 600
                    while time.monotonic() < deadline:
                        ready, _, _ = select.select([self.connection, upstream], [], [], 1)
                        for stream in ready:
                            chunk = stream.recv(65536)
                            if not chunk:
                                return
                            (upstream if stream is self.connection else self.connection).sendall(chunk)
                finally:
                    upstream.close()

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True

        self.server = Server(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def port(self):
        return self.server.server_address[1]

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class CekuraRuntime:
    def __init__(self, config):
        self.config = config
        root = REPO / "cekura/skills"
        self.fixed_skill_material = {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}

    def run(self, task, files, store, fixture_url, directory):
        """Ten minutes for the complete multi-turn task, identical for every candidate."""
        cfg = self.config
        app = directory / "app"
        skills = directory / "installed/cekura-eval-design"
        app.mkdir()
        os.chmod(app, 0o777)  # disposable container uid 1000; enclosing private dir is 0700
        for name, data in self.fixed_skill_material.items():
            path = directory / "installed" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for name, data in files.items():
            target = skills / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        pinned = pin_runtime_files(cfg, directory / "runtime_material")
        for path in pinned.iterdir():
            shutil.copyfile(path, app / path.name)
        write(app / ".context.json", task.get("context", {}))
        uploads = app / "uploads"
        uploads.mkdir()
        uploaded = {}
        for document in task.get("documents", []):
            name = Path(document["name"]).name
            (uploads / name).write_text(document["content"])
            uploaded[name] = {"path": "/app/uploads/" + name, "filename": name}
        write(app / ".session_files.json", list(uploaded))
        for path in app.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o644)
        events, messages, history = [], [], []
        status = "complete"
        start = time.monotonic()
        model_host = urlparse(cfg["snapshot"]["model_base_url"]).hostname
        with ModelProxy(model_host) as proxy, ExitStack() as guards:
            fixture_port = urlparse(fixture_url).port
            if cfg.get("network_guard_image"):
                guard = guards.enter_context(NetworkGuard(cfg["network_guard_image"], fixture_port, proxy.port, directory / "network-guard"))
                network_args = guard.target_args()
            else:
                network_args = ["--cap-add=NET_ADMIN", "--cap-add=NET_RAW", "--add-host=host.docker.internal:host-gateway"]
            settings = {"mcpServers": {"cekura": {"type": "http", "url": "http://host.docker.internal:%d/mcp" % fixture_port, "headers": {}}}}
            write(app / ".claude/settings.json", settings)
            os.chmod(app / ".claude", 0o755)
            os.chmod(app / ".claude/settings.json", 0o644)
            prompt = task["request"]
            if task.get("documents"):
                prompt += "\nAttached files are available in /app/uploads/."
            for turn in range(4):
                store.turn = turn
                (app / "prompt.txt").write_text(prompt)
                (app / "history.txt").write_text("\n".join(history))
                remaining = 600 - (time.monotonic() - start)
                if remaining <= 0:
                    status = "timeout"
                    break
                container_name = "cekura-authoring-" + digest([str(directory), turn])[:16]
                command = ["docker", "run", "--rm", "--pull=never", "--name", container_name,
                           "--cap-drop=ALL", "--cap-add=SETUID", "--cap-add=SETGID",
                           "--security-opt=no-new-privileges", "--platform", "linux/amd64",
                           "--read-only", "--tmpfs", "/tmp:rw,nosuid,size=256m", "--user", "0",
                           "--tmpfs", "/home/agent:rw,uid=1000,gid=1000,mode=0755,size=256m",
                           "-v", str(app) + ":/app:rw",
                           "-v", str(pinned / "agent_runner.py") + ":/app/agent_runner.py:ro",
                           "-v", str(pinned / "pi_extension.ts") + ":/app/pi_extension.ts:ro",
                           "-v", str(pinned / ".benchmark_pi_settings.json") + ":/app/.benchmark_pi_settings.json:ro",
                           "-v", str(directory / "installed") + ":/home/agent/.claude/skills:ro",
                           "-v", str(directory / "installed") + ":/home/agent/.claude/plugins/marketplaces/cekura-skills/cekura/skills:ro",
                           "-v", str(ROOT / "container_bootstrap.py") + ":/benchmark/bootstrap.py:ro",
                           "-e", cfg["credential_env"], "-e", "BENCHMARK_FIXTURE_PORT=" + str(fixture_port),
                           "-e", "BENCHMARK_PROXY_PORT=" + str(proxy.port),
                           "-e", "BENCHMARK_PI_SETTINGS_PATH=/app/.benchmark_pi_settings.json"]
                for key, value in cfg["snapshot"]["runtime_env"].items():
                    command += ["-e", key + "=" + value]
                command += network_args
                command += ["--entrypoint", "python3", cfg["image"], "/benchmark/bootstrap.py"]
                stdout_path = directory / ("turn-%d.events.jsonl" % turn)
                with stdout_path.open("w") as stdout, (directory / ("turn-%d.stderr" % turn)).open("w") as stderr:
                    proc = subprocess.Popen(command, stdout=stdout, stderr=stderr)
                    try:
                        proc.wait(timeout=remaining)
                    except subprocess.TimeoutExpired:
                        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=30)
                        proc.kill()
                        proc.wait()
                        status = "timeout"
                    except BaseException:
                        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=30)
                        proc.kill()
                        proc.wait()
                        raise
                turn_events = []
                for line in stdout_path.read_text().split("\n"):
                    if not line.strip():
                        continue
                    try:
                        turn_events.append(json.loads(line))
                    except ValueError:
                        status = "infrastructure_failure"
                events.extend(dict(event, benchmark_turn=turn) for event in turn_events)
                if status != "complete":
                    break
                if proc.returncode or any(e.get("type") == "error" for e in turn_events):
                    status = "infrastructure_failure"
                    break
                final = next((e for e in reversed(turn_events) if e.get("type") in ("assistant_complete", "needs_clarification")), None)
                if final is None:
                    status = "inconclusive"
                    break
                message = final.get("full_content", final.get("clean_text", ""))
                messages.append(message)
                history.extend(["user: " + prompt, "assistant: " + message])
                followups = task.get("followups", [])
                if turn < len(followups):
                    prompt = followups[turn]["message"]
                elif final["type"] == "needs_clarification" and turn < 3:
                    prompt = task["clarification_reply"]
                else:
                    break
            if proxy.denied:
                status = "infrastructure_failure"
                events.append({"type": "blocked_egress", "attempts": proxy.denied})
        loaded = [e.get("path") for e in events if e.get("type") == "skill_file_read"]
        expected_paths = {"/home/agent/.claude/skills/cekura-eval-design/SKILL.md",
                          "/home/agent/.claude/plugins/marketplaces/cekura-skills/cekura/skills/cekura-eval-design/SKILL.md"}
        if not expected_paths.intersection(loaded) and not any(e["name"].endswith("cekura_load_skill") and not e["response"]["isError"] for e in store.trace):
            status = "inconclusive"
        if expected_paths.intersection(loaded):
            exact = delivered_skill(files["SKILL.md"], cfg["snapshot"]["skill_max_chars"])
            (directory / "delivered_skill.txt").write_bytes(exact)
            write(directory / "skill_delivery.json", {"installed_sha256": digest(files["SKILL.md"]),
                  "delivered_sha256": digest(exact), "source": "Immutable mounted file and pinned _run_skill implementation",
                  "truncated": exact != files["SKILL.md"]})
        system_prompt = app / ".pi_system_prompt.txt"
        if not system_prompt.exists() or digest(system_prompt) != cfg["snapshot"]["system_prompt_sha256"]:
            status = "inconclusive"
        elif system_prompt.exists():
            shutil.copyfile(system_prompt, directory / "effective_system_prompt.txt")
        # The runtime emits skill_file_read after reading its immutable mount. Save those bytes.
        write(directory / "loaded_paths.json", loaded)
        return {"status": status, "events": events, "messages": messages,
                "elapsed_seconds": time.monotonic() - start,
                "usage": [e["usage"] for e in events if e.get("type") in ("assistant_complete", "needs_clarification", "error", "cancelled") and "usage" in e]}


def target_cost(usage, rates):
    if not usage:
        return None
    total = 0
    for row in usage:
        fields = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
        if any(row.get(field) is None or row[field] < 0 for field in fields):
            return None
        # Charge cache writes at the conservative verified maximum across TTL tiers.
        total += (row["input_tokens"] * rates["input_per_million"] + row["output_tokens"] * rates["output_per_million"]
                  + row["cache_read_input_tokens"] * rates["cached_input_per_million"]
                  + row["cache_creation_input_tokens"] * rates["cache_write_per_million"]) / 1_000_000
    return total

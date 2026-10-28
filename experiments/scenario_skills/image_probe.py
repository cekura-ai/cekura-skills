"""Exercise a real runtime image without inference or production tool access."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from types import SimpleNamespace
from contextlib import ExitStack
from pathlib import Path


async def container_probe():
    sys.path.insert(0, "/app")
    import agent_runner as runner  # Original import drops root privileges.
    import httpx

    assert os.getuid() == 1000
    capabilities = next(line.split()[1] for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("CapEff:"))
    assert int(capabilities, 16) == 0, "Runner retained bootstrap capabilities"
    data = json.loads(Path("/app/probe-input.json").read_text())
    hosted = data.get("transport") == "modal-blocked"
    manifest_path = Path("/app/probe-source.json") if hosted else Path("/opt/runtime-image/image-source.json")
    manifest = json.loads(manifest_path.read_text())
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == data["manifest_sha256"]
    for name in ("agent_runner.py", "pi_extension.ts"):
        expected_hash = manifest["source_sha256"][name]
        assert hashlib.sha256(Path("/app", name).read_bytes()).hexdigest() == expected_hash
        if not hosted:
            assert hashlib.sha256(Path("/opt/cekura-runtime", name).read_bytes()).hexdigest() == expected_hash
    settings = Path("/home/agent/.pi/agent/settings.json").read_bytes()
    assert hashlib.sha256(settings).hexdigest() == manifest["pi_settings_sha256"]
    node_executable = str(Path(runner.PI_NODE_BIN_DIR) / "node")
    node_version = subprocess.check_output([node_executable, "--version"], text=True).strip()
    assert node_version == "v" + manifest["node_version"]
    for pin in manifest["python_packages"]:
        package, version = pin.split("==")
        assert importlib.metadata.version(package.split("[")[0]) == version
    skill_path = runner._skill_file("cekura-eval-design")
    original = Path(skill_path).read_bytes()
    delivered = await runner._run_skill({"skill": "cekura-eval-design"})
    expected = original.decode()
    if len(expected) > runner._SKILL_MAX_CHARS:
        expected = expected[:runner._SKILL_MAX_CHARS] + "\n\n[Skill truncated.]"
    assert delivered == expected
    Path("/app/probe-loaded-skill.txt").write_text(delivered)
    Path("/app/probe-installed-skill.txt").write_bytes(original)
    catalog = await asyncio.to_thread(runner.build_tool_catalog)
    assert any(t["name"] == "mcp__cekura__scenarios_create" for t in catalog)
    Path("/app/probe-runtime-catalog.json").write_text(json.dumps(catalog, ensure_ascii=False))
    if hosted:
        metadata = json.loads(Path("/app/modal-image-metadata.json").read_text())
        assert "Python " + sys.version == metadata["python_version_info"]
        for name, version in metadata["python_packages"].items():
            assert importlib.metadata.version(name) == version, name
        Path("/app/probe-python-lock.txt").write_text("\n".join(sorted(name + "==" + version for name, version in metadata["python_packages"].items())) + "\n")
        shutil.copyfile("/opt/pi/package-lock.json", "/app/probe-npm-lock.json")
        shutil.copyfile(manifest_path, "/app/probe-image-source.json")
    else:
        for name in ("python-lock.txt", "npm-lock.json", "image-source.json"):
            shutil.copyfile("/opt/runtime-image/" + name, "/app/probe-" + name)
    npm_lock = json.loads(Path("/app/probe-npm-lock.json").read_text())
    assert npm_lock["packages"]["node_modules/@earendil-works/pi-coding-agent"]["version"] == manifest["pi_version"]
    url, headers = runner._platform_mcp_endpoint()
    assert url.startswith("http://%s:" % ("127.0.0.1" if hosted else "host.docker.internal"))

    def exercise():
        with httpx.Client(timeout=10) as client:
            call_headers = runner._open_platform_mcp(client, url, headers)

            def call(name, arguments):
                content, _ = runner._platform_mcp_call(client, url, call_headers, name, arguments)
                try:
                    return json.loads(content[0]["text"])
                except ValueError:
                    return {"error": content[0]["text"]}

            payload = data["payload"]
            created = call("scenarios_create", payload)
            assert created["instructions"] == payload["instructions"]
            updated = call("scenarios_partial_update", {"id": created["id"], "name": "Updated offline probe"})
            saved = call("scenarios_retrieve", {"id": created["id"]})
            assert updated["id"] == saved["id"] == created["id"]
            assert saved["instructions"] == payload["instructions"] and saved["name"] == "Updated offline probe"
            job = call("scenarios_generate_bg", data["generation"])
            assert call("scenarios_generate_progress", job)["status"] == "processing"
            generated = call("scenarios_generate_progress", job)
            assert generated["status"] == "completed"
            assert len(generated["scenarios_list"]) == data["generation"]["num_scenarios"]
            stale = call("scenarios_partial_update", {"id": 999999999, "name": "Stale"})
            assert "error" in stale or "detail" in stale
            return {"created_id": created["id"], "generated_count": len(generated["scenarios_list"])}

    resources = await asyncio.to_thread(exercise)
    # Startup/state inspection never sends a prompt to the model.
    _, system_prompt = runner._make_options(runner._load_mode())
    async with runner._PiClient(system_prompt=system_prompt) as pi:
        pi._send({"id": "probe-state", "type": "get_state"})
        while True:
            event = await asyncio.wait_for(pi._next_event(), timeout=30)
            if event and event.get("id") == "probe-state":
                assert event.get("success") is True, event
                pi_state = event.get("data", {})
                assert pi_state.get("model", {}).get("id") == runner.KIMI_MODEL
                break
    # The host proxy rejects every allowed CONNECT, so these requests cannot
    # reach the provider. Verify the pinned Node and Python honor that proxy.
    js = "fetch('https://api.fireworks.ai/', {signal: AbortSignal.timeout(3000)}).then(()=>process.exit(1)).catch(e=>console.log(JSON.stringify({message:e.message,cause:String(e.cause)})))"
    node_result = subprocess.run([node_executable, "-e", js], capture_output=True, text=True, timeout=10)
    assert node_result.returncode == 0
    try:
        with httpx.Client(timeout=3) as client:
            client.get("https://api.fireworks.ai/")
        raise AssertionError("Offline model proxy forwarded traffic")
    except httpx.ProxyError:
        pass
    direct_blocked = False
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=1):
            pass
    except OSError:
        direct_blocked = True
    assert direct_blocked, "Direct outbound traffic escaped the firewall"
    print(json.dumps({"type": "offline_probe_complete", "uid": os.getuid(), "node_version": node_version,
                      "model": runner.KIMI_MODEL, "catalog_tools": len(catalog),
                      "installed_skill_sha256": hashlib.sha256(original).hexdigest(),
                      "delivered_skill_sha256": hashlib.sha256(delivered.encode()).hexdigest(),
                      "node_proxy_result": json.loads(node_result.stdout), "direct_egress_blocked": direct_blocked,
                      "resources": resources, "inference_requests": 0}))


def run_probe(image, prepared, directory, guard_image=None, runtime_env=None, probe_skill=None):
    from .common import ROOT, digest, write
    from .dataset import load
    from .fixture import FixtureServer, Store
    from .runtime import ModelProxy
    from .network_guard import NetworkGuard
    from .skill import candidate, material, split

    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("Use the built image ID, not a mutable tag")
    prepared, directory = Path(prepared), Path(directory)
    runtime_env = runtime_env or {"CEKURA_AGENT_HARNESS": "pi"}
    if runtime_env.get("CEKURA_AGENT_HARNESS") != "pi" or any(not k.startswith("CEKURA_") or not isinstance(v, str) for k, v in runtime_env.items()):
        raise ValueError("Probe needs captured Cekura flags and the Pi harness")
    app = directory / "app"
    app.mkdir()
    app.chmod(0o777)
    skill_tree = prepared / "skills"
    skill_files = material(skill_tree / "cekura-eval-design/SKILL.md")
    if probe_skill:
        baseline = skill_files["SKILL.md"]
        proposed = Path(probe_skill).read_bytes()
        header, body = split(proposed)
        if header != split(baseline)[0] or candidate(baseline, body.decode()) != proposed:
            raise ValueError("Delivery probe may change only the protected skill's body")
        skill_tree = directory / "installed"
        shutil.copytree(prepared / "skills", skill_tree)
        (skill_tree / "cekura-eval-design/SKILL.md").write_bytes(proposed)
        skill_files["SKILL.md"] = proposed
    for path in (prepared / "runtime").iterdir():
        shutil.copyfile(path, app / path.name)
    task = next(t for t in load() if t["id"] == "library-1")
    row = {"agent": task["fixture"]["agent"]["id"], "folder_path": task["fixture"]["resources"]["folders"][0]["path"],
           "personality": task["fixture"]["personalities"][0]["id"], "name": "Offline Unicode probe",
           "scenario_type": "instruction", "scenario_language": "en", "instructions": "é" * 70000,
           "test_profile": task["fixture"]["resources"]["profiles"][0]["id"]}
    generation = {"agent_id": row["agent"], "num_scenarios": len(task["generator_response"]), "folder_path": row["folder_path"]}
    write(app / "probe-input.json", {"payload": row, "generation": generation, "manifest_sha256": digest(prepared / "image-source.json")})
    write(app / ".context.json", task.get("context", {}))
    store = Store(task, skill_files)
    with FixtureServer(store) as fixture, ModelProxy("api.fireworks.ai", forward=False) as proxy, ExitStack() as guards:
        port = fixture.server.server_port
        if guard_image:
            guard = guards.enter_context(NetworkGuard(guard_image, port, proxy.port, directory / "network-guard"))
            network_args = guard.target_args()
        else:
            network_args = ["--cap-add=NET_ADMIN", "--cap-add=NET_RAW", "--add-host=host.docker.internal:host-gateway"]
        write(app / ".claude/settings.json", {"mcpServers": {"cekura": {"type": "http", "url": "http://host.docker.internal:%d/mcp" % port, "headers": {}}}})
        for path in app.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)
        name = "cekura-image-probe-" + digest(str(directory))[:12]
        command = ["docker", "run", "--rm", "--pull=never", "--platform", "linux/amd64", "--name", name,
                   "--cap-drop=ALL", "--cap-add=SETUID", "--cap-add=SETGID",
                   "--security-opt=no-new-privileges", "--read-only", "--user", "0",
                   "--tmpfs", "/tmp:rw,nosuid,size=256m",
                   "--tmpfs", "/home/agent:rw,uid=1000,gid=1000,mode=0755,size=256m", "-v", str(app) + ":/app:rw",
                   "-v", str(skill_tree) + ":/home/agent/.claude/plugins/marketplaces/cekura-skills/cekura/skills:ro",
                   "-v", str(prepared / "pi-settings.json") + ":/app/.benchmark_pi_settings.json:ro",
                   "-v", str(ROOT / "container_bootstrap.py") + ":/benchmark/bootstrap.py:ro",
                   "-v", str(ROOT / "image_probe.py") + ":/benchmark/image_probe.py:ro",
                   "-e", "BENCHMARK_PI_SETTINGS_PATH=/app/.benchmark_pi_settings.json",
                   "-e", "BENCHMARK_FIXTURE_PORT=" + str(port), "-e", "BENCHMARK_PROXY_PORT=" + str(proxy.port),
                   ] + network_args
        for key, value in runtime_env.items():
            command += ["-e", key + "=" + value]
        command += ["--entrypoint", "python3", image, "/benchmark/bootstrap.py", "--probe-only"]
        with (directory / "stdout.jsonl").open("w") as stdout, (directory / "stderr.txt").open("w") as stderr:
            timed_out = False
            try:
                result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=120)
            except subprocess.TimeoutExpired:
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30)
                timed_out = True
                result = SimpleNamespace(returncode=124)
            except BaseException:
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30)
                raise
        events = [json.loads(line) for line in (directory / "stdout.jsonl").read_text().splitlines() if line.strip()]
        completed = next((e for e in events if e.get("type") == "offline_probe_complete"), None)
        passed = (result.returncode == 0 and completed is not None and len(proxy.attempts) >= 2 and not proxy.denied
                  and completed["installed_skill_sha256"] == digest(skill_files["SKILL.md"]))
        report = {"passed": passed, "image": image, "image_provenance": json.loads((prepared / "image-source.json").read_text()),
                  "returncode": result.returncode, "provider_forwarding": False, "proxy_attempts": proxy.attempts,
                  "network_guard_image": guard_image,
                  "timed_out": timed_out,
                  "runtime_env": runtime_env,
                  "skill_delivery_probe": bool(probe_skill),
                  "blocked_hosts": proxy.denied, "probe": completed, "inference_requests": 0,
                  "production_match_verified": False}
        write(directory / "trace.json", store.trace)
        write(directory / "initial-state.json", store.initial)
        write(directory / "final-state.json", store.state)
        write(directory / "probe-report.json", report)
        return report


if __name__ == "__main__":
    if sys.argv[1:] != ["--in-container"]:
        raise SystemExit("Use the image-probe benchmark command")
    asyncio.run(asyncio.wait_for(container_probe(), timeout=100))

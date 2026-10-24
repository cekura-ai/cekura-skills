"""Offline probe of a captured Modal image, in a new network-blocked sandbox.

This is image verification only. It never invokes a model or production tools.
The paid evaluator still requires its complete snapshot and billing gates.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import tarfile
import traceback
from pathlib import Path

LIFETIME = 180
CPU = (1.0, 1.0)
MEMORY = (1024, 1024)
RESERVATION = .10
RATES = {"cpu_core_second": .00003942, "memory_gib_second": .00000667, "egress_gib": .04}


def allocation(evidence):
    if evidence.get("source") != "https://modal.com/pricing" or not evidence.get("verified_at") or evidence.get("rates") != RATES:
        raise ValueError("Verify published sandbox rates before allocating compute")
    maximum = LIFETIME * (CPU[1] * RATES["cpu_core_second"] + MEMORY[1] / 1024 * RATES["memory_gib_second"]) + 64 / 1024 * RATES["egress_gib"]
    if maximum >= RESERVATION:
        raise ValueError("Offline sandbox cannot fit its reserved infrastructure allowance")
    return {"reserved_usd": RESERVATION, "compute_and_transfer_bound_usd": maximum,
            "timeout_seconds": LIFETIME, "cpu": CPU, "memory_mib": MEMORY,
            "block_network": True, "rates": evidence, "actual_billed_usd": None}


def reserve_infrastructure(ledger_path, directory):
    from .common import digest, private_dir, write
    from .budget import Ledger
    ledger_path = Path(ledger_path)
    private_dir(ledger_path.parent)
    ledger = Ledger(ledger_path)
    key = "offline-image-" + digest(str(Path(directory).resolve()))
    ledger.reserve(key, "target", RESERVATION, infrastructure_only=True)
    return ledger, key


def package(prepared, metadata, catalog=None):
    """Only source, skills, transport code and one synthetic fixture are uploaded."""
    from .common import ROOT, digest
    from .dataset import load
    prepared = Path(prepared)
    manifest = json.loads((prepared / "image-source.json").read_text())
    if manifest.get("pi_settings_provenance") != "Captured bytes":
        raise ValueError("Matching image probe requires captured Pi settings")
    task = next(t for t in load() if t["id"] == "library-1")
    payload = {"agent": task["fixture"]["agent"]["id"], "folder_path": task["fixture"]["resources"]["folders"][0]["path"],
               "personality": task["fixture"]["personalities"][0]["id"], "name": "Offline Unicode probe",
               "scenario_type": "instruction", "scenario_language": "en", "instructions": "é" * 70000,
               "test_profile": task["fixture"]["resources"]["profiles"][0]["id"]}
    files = {"app/probe-source.json": (prepared / "image-source.json").read_bytes(),
             "app/modal-image-metadata.json": json.dumps(metadata).encode(),
             "app/.context.json": json.dumps(task.get("context", {})).encode(),
             "app/probe-task.json": json.dumps(task).encode(),
             "app/probe-input.json": json.dumps({"transport": "modal-blocked", "payload": payload,
                 "generation": {"agent_id": payload["agent"], "num_scenarios": len(task["generator_response"]), "folder_path": payload["folder_path"]},
                 "manifest_sha256": digest(prepared / "image-source.json")}).encode(),
             "home/agent/.pi/agent/settings.json": (prepared / "pi-settings.json").read_bytes(),
             "app/experiments/__init__.py": b"", "app/experiments/scenario_skills/__init__.py": b""}
    if catalog is not None:
        files["app/probe-catalog.json"] = json.dumps(catalog).encode()
    for name in ("agent_runner.py", "pi_extension.ts"):
        if digest(prepared / "runtime" / name) != manifest["source_sha256"][name]:
            raise ValueError("Captured runtime source changed")
        files["app/" + name] = (prepared / "runtime" / name).read_bytes()
    for name in ("common.py", "dataset.py", "fixture.py", "runtime.py", "network_guard.py", "image_probe.py", "modal_probe.py"):
        files["app/experiments/scenario_skills/" + name] = (ROOT / name).read_bytes()
    for path in (prepared / "skills").rglob("*"):
        if path.is_symlink():
            raise ValueError("Probe skill material may not contain symlinks")
        if path.is_file():
            files["home/agent/.claude/plugins/marketplaces/cekura-skills/cekura/skills/" + str(path.relative_to(prepared / "skills"))] = path.read_bytes()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name, data in files.items():
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode = len(data), 0o444
            archive.addfile(entry, io.BytesIO(data))
    return stream.getvalue()


def run_modal_probe(image_id, prepared, metadata, flags, evidence, directory, ledger_path, catalog=None):
    # Sandbox hydration creates SDK stream objects that require Modal's own
    # event loop. Keep the complete native async transaction on that loop.
    from modal._utils.async_utils import synchronizer
    return synchronizer.create_blocking(_run_modal_probe)(image_id, prepared, metadata, flags, evidence, directory, ledger_path, catalog)


async def _run_modal_probe(image_id, prepared, metadata, flags, evidence, directory, ledger_path, catalog=None):
    from .common import ROOT, digest, write
    from modal.app import _App
    from modal.client import _Client
    from modal.image import _Image
    from modal.sandbox import _Sandbox
    from modal.exception import SandboxFilesystemNotFoundError
    from modal_proto import api_pb2
    if not re.fullmatch(r"im-[A-Za-z0-9]+", image_id) or metadata.get("image_id") != image_id:
        raise ValueError("Use the exact captured Modal image ID")
    if flags.get("CEKURA_AGENT_HARNESS") != "pi" or any(not k.startswith("CEKURA_") or not isinstance(v, str) for k, v in flags.items()):
        raise ValueError("Use captured runtime flags without credentials")
    budget = allocation(evidence)
    archive = package(prepared, metadata, catalog)
    directory = Path(directory)
    ledger, reservation_key = reserve_infrastructure(ledger_path, directory)
    write(directory / "infrastructure-allocation.json", budget)
    client = await _Client.from_credentials(os.environ["MODAL_TOKEN_ID"], os.environ["MODAL_TOKEN_SECRET"])
    sandbox = None
    report = {"passed": False, "image_id": image_id, "inference_requests": 0, "infrastructure": budget,
              "runtime_env": flags, "production_image_verified": False,
              "catalog_sha256": digest(catalog) if catalog is not None else None,
              "fixture_sha256": digest(ROOT / "fixture.py")}
    try:
        report["phase"] = "app_lookup"
        app = await _App.lookup("cekura-scenario-skill-offline", client=client, create_if_missing=True)
        # from_id uses a public factory in this SDK. Translate once, then use
        # native async objects throughout to avoid crossing event loops.
        from modal._utils.async_utils import synchronizer
        report["phase"] = "image_lookup"
        image = synchronizer._translate_in(_Image.from_id(image_id, client=client))
        report["phase"] = "sandbox_create"
        sandbox = await _Sandbox.create("sleep", str(LIFETIME), image=image, app=app, client=client,
            name="cekura-offline-" + digest(str(directory.resolve()))[:16],
            cpu=CPU, memory=MEMORY, timeout=LIFETIME, block_network=True, env=flags, include_oidc_identity_token=False)
        report["sandbox_id"] = sandbox.object_id
        write(directory / "probe-report.json", report)  # checkpoint before uploads
        response = await client.stub.SandboxList(api_pb2.SandboxListRequest(app_id=app.app_id, include_finished=False))
        actual = next(s for s in response.sandboxes if s.id == sandbox.object_id)
        if actual.image_id != image_id:
            raise ValueError("New sandbox did not use the captured production image")
        resources = actual.resource_info
        if (actual.timeout_secs != LIFETIME or resources.milli_cpu_max != int(CPU[1] * 1000)
                or resources.memory_mb_max != MEMORY[1]):
            raise ValueError("Provider resource/lifetime limits differ from the infrastructure bound")
        report["verified_limits"] = {"timeout_seconds": actual.timeout_secs,
            "cpu_millicores_max": resources.milli_cpu_max, "memory_mib_max": resources.memory_mb_max}
        report["production_image_verified"] = True
        await sandbox.filesystem.write_bytes(archive, "/tmp/offline-probe.tar.gz")
        setup = await sandbox.exec("python3", "-c", "import tarfile,os; tarfile.open('/tmp/offline-probe.tar.gz').extractall('/'); os.chmod('/app',0o777); os.chmod('/home/agent/.pi/agent/settings.json',0o644)", timeout=20)
        await setup.wait()
        if setup.returncode:
            raise RuntimeError("Synthetic fixture installation failed")
        process = await sandbox.exec("python3", "-m", "experiments.scenario_skills.modal_probe", "--in-container", workdir="/app", timeout=110)
        stdout, stderr, _ = await asyncio.gather(process.stdout.read(), process.stderr.read(), process.wait())
        (directory / "stdout.jsonl").write_text(stdout)
        (directory / "stderr.txt").write_text(stderr)
        for name in ("trace.json", "initial-state.json", "final-state.json", "inner-report.json", "probe-runtime-catalog.json",
                     "probe-loaded-skill.txt", "probe-installed-skill.txt", "probe-python-lock.txt", "probe-npm-lock.json", ".pi_system_prompt.txt"):
            try:
                content = await sandbox.filesystem.read_text("/app/" + name)
                if len(content.encode()) > 4_000_000:
                    raise ValueError("Offline artifact exceeded bounded transfer allowance")
                (directory / name).write_text(content)
            except (FileNotFoundError, SandboxFilesystemNotFoundError):
                pass
        inner = json.loads((directory / "inner-report.json").read_text())
        completed = next((json.loads(line) for line in stdout.splitlines() if json.loads(line).get("type") == "offline_probe_complete"), None)
        report.update(returncode=process.returncode, checks=inner, probe=completed,
                      passed=process.returncode == 0 and inner["passed"] and completed is not None)
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
        (directory / "host-error.txt").write_text(traceback.format_exc())
    finally:
        if sandbox:
            try:
                await sandbox.terminate()
                report["terminated"] = True
            except Exception:
                report["terminated"] = False  # provider timeout still bounds lifetime
        await client._close()
        write(directory / "probe-report.json", report)
        # Keep the whole bound charged until actual provider billing is known.
        ledger.transition(reservation_key, "bounded_infrastructure_pending_billing")
    return report


async def run_inside():
    from .common import read, write
    from .fixture import FixtureServer, Store
    from .runtime import ModelProxy
    from .image_probe import container_probe
    app = Path("/app")
    task = read(app / "probe-task.json")
    skills = Path("/home/agent/.claude/plugins/marketplaces/cekura-skills/cekura/skills/cekura-eval-design")
    catalog = read(app / "probe-catalog.json") if (app / "probe-catalog.json").exists() else None
    store = Store(task, {str(p.relative_to(skills)): p.read_bytes() for p in skills.rglob("*") if p.is_file()}, catalog)
    report = {"passed": False, "inference_requests": 0}
    with FixtureServer(store) as fixture, ModelProxy("api.fireworks.ai", forward=False) as proxy:
        settings = app / ".claude/settings.json"
        write(settings, {"mcpServers": {"cekura": {"type": "http", "url": fixture.url, "headers": {}}}})
        settings.parent.chmod(0o755); settings.chmod(0o644)
        os.environ.update(HTTP_PROXY="http://127.0.0.1:%d" % proxy.port, HTTPS_PROXY="http://127.0.0.1:%d" % proxy.port,
                          NO_PROXY="localhost,127.0.0.1", NODE_USE_ENV_PROXY="1")
        try:
            await asyncio.wait_for(container_probe(), 100)
            report["passed"] = len(proxy.attempts) >= 2 and not proxy.denied
        finally:
            report.update(proxy_attempts=proxy.attempts, blocked_hosts=proxy.denied, provider_forwarding=False)
            write(app / "trace.json", store.trace)
            write(app / "initial-state.json", store.initial)
            write(app / "final-state.json", store.state)
            write(app / "inner-report.json", report)
    return report


if __name__ == "__main__":
    if sys.argv[1:] != ["--in-container"]:
        raise SystemExit("Use the documented host launcher")
    result = asyncio.run(run_inside())
    raise SystemExit(int(not result["passed"]))

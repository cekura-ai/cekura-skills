"""Prepare a private Docker replica from captured Modal sandbox source.

This captures source pins, not effective production flags or Modal image identity.
No backend code or customer workspace is committed into this repository.
"""
from __future__ import annotations

import ast
import re
import shutil
from pathlib import Path

from .common import ROOT, digest, write


def prepare_image(source, output, source_ref, pi_settings=None):
    source, output = Path(source), Path(output)
    tree = ast.parse((source / "modal_driver.py").read_text())
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    build = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_build_sandbox_image")
    calls = [n for n in ast.walk(build) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    installs = [n for n in calls if n.func.attr == "pip_install"]
    bases = [n for n in calls if n.func.attr == "debian_slim"]
    if len(installs) != 1 or len(bases) != 1:
        raise ValueError("Unrecognized sandbox build recipe; inspect it before adapting")
    packages = [ast.literal_eval(n) for n in installs[0].args]
    python_version = next(ast.literal_eval(k.value) for k in bases[0].keywords if k.arg == "python_version")
    node_version, pi_version = constants["_NODE_VERSION"], constants["_PI_VERSION"]
    if python_version != "3.11" or any(not re.fullmatch(r"\d+\.\d+\.\d+", v) for v in (node_version, pi_version)):
        raise ValueError("Unsupported Python/Node/Pi recipe; do not silently substitute")
    if any(not isinstance(p, str) or not re.fullmatch(r"[\w\[\],-]+==[\w.]+", p) for p in packages):
        raise ValueError("Sandbox Python packages must be exact source pins")
    if constants["_NODE_PREFIX"] != "/opt/node" or constants["_PI_PREFIX"] != "/opt/pi":
        raise ValueError("Captured sandbox paths differ from this Docker adapter")
    if any(output.iterdir()):
        raise ValueError("Image preparation needs an empty private artifact directory")
    (output / "python-requirements.txt").write_text("\n".join(packages) + "\n")
    skills = ROOT.parents[1] / "cekura/skills"
    shutil.copytree(skills, output / "skills")
    runtime = output / "runtime"
    runtime.mkdir()
    for name in ("agent_runner.py", "pi_extension.ts"):
        shutil.copyfile(source / name, runtime / name)
    settings = {"skills": [constants["_SANDBOX_SKILLS_DST"] + "/cekura/skills", "/home/agent/.claude/skills"]}
    if pi_settings:
        import json
        captured = Path(pi_settings).read_bytes()
        if not set(settings["skills"]).issubset(json.loads(captured).get("skills", [])):
            raise ValueError("Captured Pi settings do not load the source skill paths")
        (output / "pi-settings.json").write_bytes(captured)
    else:
        write(output / "pi-settings.json", settings)
    shutil.copyfile(ROOT / "runtime-image.Dockerfile", output / "Dockerfile")
    manifest = {
        "provenance": "Replica of captured sandbox source; production flags, base image and transitive dependencies unverified",
        "source_ref": source_ref,
        "source_sha256": {p.name: digest(p) for p in sorted(source.glob("*")) if p.is_file()},
        "python_version": python_version, "node_version": node_version, "pi_version": pi_version,
        "python_packages": packages,
        "skills_sha256": {str(p.relative_to(skills)): digest(p) for p in sorted(skills.rglob("*")) if p.is_file()},
        "pi_settings_sha256": digest(output / "pi-settings.json"),
        "pi_settings_provenance": "Captured bytes" if pi_settings else "Reconstructed from source; effective bytes unverified",
        "dockerfile_sha256": digest(output / "Dockerfile"),
        "build_arguments": {"NODE_VERSION": node_version, "PI_VERSION": pi_version},
    }
    write(output / "image-source.json", manifest)
    return manifest

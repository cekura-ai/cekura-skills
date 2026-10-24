"""Build the instrumented private generator copy and record the deviation from the pinned source.

Each edit replaces one exact, uniquely occurring fragment of a hash-pinned file, so a
different source revision fails rather than being patched approximately. The edits
change transport only: where the sandbox is created and how its traffic leaves.
"""
import difflib
import json
import shutil
import subprocess
from pathlib import Path

from ...common import digest, write

HERE = Path(__file__).parent
REVISION = "650297f5efceb98d02c4dc83976c490da4f8b48a"
BASE_IMAGE = "cekura-backend-pinned:650297f"
PINNED = {"app/claude_utils.py": "2ad1110b6583d6e6797f34de133b9d48d87e43c9f678f378151da5f86e2deb1e"}
ADDED = {"app/cekura_metering.py": HERE / "cekura_metering.py", "app/cekura_local_sandbox.py": HERE / "cekura_local_sandbox.py",
         "app/cekura_relay.py": HERE.parent.parent / "relay.py"}
EDITS = [
    ("app/claude_utils.py", "import modal\nfrom django.conf import settings\n",
     "import modal\nfrom django.conf import settings\nfrom app import cekura_metering as _cekura_metering\n",
     "Load the experiment transport; inert unless CEKURA_METERING=1."),
    ("app/claude_utils.py", "    app = modal.App.lookup(CHAT_APP, create_if_missing=True)\n    try:\n        sb = modal.Sandbox.from_name(CHAT_APP, sandbox_name)\n",
     "    _sandbox_api = _cekura_metering._backend() if _cekura_metering.ACTIVE else modal\n"
     "    app = _sandbox_api.App.lookup(CHAT_APP, create_if_missing=True)\n    try:\n        sb = _sandbox_api.Sandbox.from_name(CHAT_APP, sandbox_name)\n",
     "Offline drills resolve the same calls against the local stand-in; scored runs use Modal."),
    ("app/claude_utils.py", "        return modal.Sandbox.create(\n            app=app,\n            name=sandbox_name,\n",
     "        return (_cekura_metering.create_sandbox if _cekura_metering.ACTIVE else modal.Sandbox.create)(\n            app=app,\n            name=sandbox_name,\n",
     "Reserve the sandbox, block its network, use the pinned image and experiment secret, attach the relay."),
    ("app/claude_utils.py", '            process = sb.exec("python3", "/app/agent.py")\n            output, exit_code, stderr, _ = _run_with_cancellation(sb, process, None, "PHASED")\n',
     '            process = sb.exec("python3", "/app/agent.py", **_cekura_metering.exec_kwargs(sb))\n'
     '            output, exit_code, stderr, _ = _run_with_cancellation(sb, process, None, "PHASED")\n',
     "Give the generator process proxy and trust settings; its CLIs inherit them."),
]


def instrument(source, output):
    """Write the overlay files and return the auditable deviation record."""
    source, output = Path(source), Path(output)
    if output.exists():
        shutil.rmtree(output)
    overlay = output / "overlay"
    record = {"source_revision": REVISION, "base_image": BASE_IMAGE, "files": {}, "added": {}, "edits": [], "diff": ""}
    texts = {}
    for path, expected in PINNED.items():
        data = (source / path).read_bytes()
        if digest(data) != expected:
            raise ValueError("Pinned generator source differs: " + path)
        texts[path] = data.decode()
    patched = dict(texts)
    for path, old, new, reason in EDITS:
        if patched[path].count(old) != 1:
            raise ValueError("Instrumentation anchor is not unique in " + path)
        patched[path] = patched[path].replace(old, new)
        record["edits"].append({"file": path, "reason": reason, "removed_sha256": digest(old.encode()), "added_sha256": digest(new.encode())})
    for path, text in patched.items():
        target = overlay / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        record["files"][path] = {"before_sha256": PINNED[path], "after_sha256": digest(text.encode())}
        record["diff"] += "".join(difflib.unified_diff(texts[path].splitlines(True), text.splitlines(True), "pinned/" + path, "instrumented/" + path))
    for path, origin in ADDED.items():
        target = overlay / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
        record["added"][path] = digest(target)
    shutil.copyfile(HERE / "sitecustomize.py", output / "sitecustomize.py")
    record["added"]["sitecustomize.py"] = digest(output / "sitecustomize.py")
    (output / "Dockerfile").write_text("FROM %s\nCOPY overlay/ /app/\nCOPY sitecustomize.py /usr/local/lib/python3.13/site-packages/sitecustomize.py\n" % BASE_IMAGE)
    record["record_sha256"] = digest({k: v for k, v in record.items() if k != "diff"})
    write(output / "deviation.json", record)
    (output / "instrumentation.diff").write_text(record["diff"])
    return record


def build_image(output, tag):
    """Derived image = pinned image + overlay. Its ID becomes part of the generator identity."""
    subprocess.run(["docker", "build", "-q", "-t", tag, str(output)], check=True, capture_output=True)
    identifier = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", tag], text=True).strip()
    base = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", BASE_IMAGE], text=True).strip()
    record = json.loads((Path(output) / "deviation.json").read_text())
    record.update(image_id=identifier, base_image_id=base)
    write(Path(output) / "deviation.json", record)
    return record

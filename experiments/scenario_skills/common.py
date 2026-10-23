"""Content-addressed private artifacts. No credentials belong in JSON snapshots."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import importlib.metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
REVISION = "8123ccabe2b19fa1123090b2e5f1bacc20963ce8"
PROPOSER = {"model": "gpt-6.1-sol", "provider": "azure", "reasoning_effort": "high"}


def dependencies():
    versions = {}
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        if "==" in line:
            name = line.split("==")[0]
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = None
    return versions


def digest(value):
    if isinstance(value, Path):
        value = value.read_bytes()
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(value).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    """Atomic checkpoint; only the owner may read raw experiment evidence."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def private_dir(path):
    path = Path(path).resolve()
    if path == REPO or REPO in path.parents:
        raise ValueError("Run artifacts must be outside this checkout")
    permitted = (Path.home().resolve(), Path("/private/tmp"), Path(tempfile.gettempdir()).resolve())
    if not any(root == path or root in path.parents for root in permitted):
        raise ValueError("Private artifacts must be in the user home or an isolated temporary directory")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path

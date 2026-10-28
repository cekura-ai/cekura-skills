"""Real-backend prerequisites. No inference, no provider requests, no sandbox creation."""
import os
import re
import subprocess
from pathlib import Path

from ..budget import CANONICAL_WALLET, BudgetError, Ledger
from ..common import digest, read
from .metering import validate_generator


def real_backend(cfg):
    failures = []
    wallet = Path(cfg.get("budget_ledger_path") or "")
    if wallet.resolve() != CANONICAL_WALLET.resolve() or not wallet.is_file():
        failures.append("The canonical $150 wallet does not exist at " + str(CANONICAL_WALLET))
    else:
        try:
            if Ledger(wallet, cfg.get("budget_policy")).state["blocked"]:
                failures.append("The wallet is blocked by unknown usage or a reservation overrun")
        except BudgetError as error:
            failures.append(str(error))
    backend = cfg.get("backend", {})
    generator = backend.get("generator", {})
    failures += validate_generator(generator)
    for endpoint in generator.get("endpoints", []):
        if not os.environ.get(endpoint.get("credential_env", "")):
            failures.append("Generator credential unavailable: " + str(endpoint.get("credential_env")))
    if os.environ.get("CEKURA_SANDBOX_BACKEND") == "local-docker" or generator.get("sandbox_backend") == "local-docker":
        failures.append("The local-docker sandbox stand-in is for offline drills only")
    if not re.fullmatch(r"im-[A-Za-z0-9]+", generator.get("sandbox_image", "")) or not generator.get("modal_secret"):
        failures.append("Experiment-owned generator image and Modal secret are not recorded (run prepare-generator)")
    deviation = Path(backend.get("deviation_path") or "")
    if not deviation.is_file():
        failures.append("Generator instrumentation deviation record missing")
    else:
        record = read(deviation)
        if record.get("record_sha256") != backend.get("deviation_sha256") or record.get("image_id") != backend.get("images", {}).get("backend"):
            failures.append("Generator deviation record differs from the configured instrumented image")
    for role, identifier in backend.get("images", {}).items():
        found = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", identifier], capture_output=True, text=True)
        if found.returncode or found.stdout.strip() != identifier:
            failures.append("Pinned backend image unavailable: " + role)
    infra = Path(backend.get("infrastructure_state") or "")
    if not infra.is_file() or not read(infra).get("template_migrated") or read(infra).get("openapi_sha256") != backend.get("openapi_sha256"):
        failures.append("Migrated backend template or pinned OpenAPI operations missing (run prepare-generator)")
    return failures

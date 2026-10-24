"""Training-only Claude Code proposer on the user's existing EC2 workspace.

The controller is sent over SSH, but only the CLI and its runtime libraries
enter the container image. No repository, grader or held-out data is mounted.
Offline preparation verifies authentication without making an inference call.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import shlex
import subprocess
import tarfile
from urllib.request import Request, urlopen
from pathlib import Path

CLI = "/home/ubuntu/.local/bin/claude"
CREDENTIALS = "/home/ubuntu/.claude/.credentials.json"
LIMIT = 16 * 1024 * 1024


def container_args(image, name, network=False):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("Claude container image must be immutable")
    if not re.fullmatch(r"cekura-proposer-[a-f0-9]{16}", name):
        raise ValueError("Invalid proposer container name")
    return ["docker", "run", "-i", "--rm", "--pull=never", "--name", name,
            "--network=" + ("bridge" if network else "none"), "--cap-drop=ALL",
            "--security-opt=no-new-privileges", "--read-only", "--user=1000:1000",
            "--cpus=1", "--memory=2g", "--pids-limit=64",
            "--tmpfs=/tmp:rw,nosuid,nodev,size=128m,uid=1000,gid=1000",
            "--tmpfs=/state:rw,nosuid,nodev,size=128m,uid=1000,gid=1000",
            "--mount=type=bind,src=" + CREDENTIALS + ",dst=/state/.credentials.json,readonly",
            "--env=CLAUDE_CONFIG_DIR=/state", "--env=DISABLE_TELEMETRY=1",
            "--env=DISABLE_ERROR_REPORTING=1", "--env=DISABLE_AUTOUPDATER=1",
            "--workdir=/workspace", "--entrypoint=/bin/claude", image]


def cli_args(config, schema):
    if not re.fullmatch(r"claude-(?:opus|sonnet|fable)-[0-9][a-z0-9.-]*", config["model"]):
        raise ValueError("Pin a full Claude model ID; family aliases are not reproducible")
    if config.get("reasoning_effort") != "high":
        raise ValueError("Claude proposer reasoning must be pinned to high")
    maximum = config.get("max_cost_usd")
    if not isinstance(maximum, (int, float)) or not 0 < maximum <= 2.5:
        raise ValueError("Each of two Claude proposals must reserve at most $2.50")
    # v2 may expose only the read-only training workspace. Shell, network tools,
    # host hooks, plugins and persistent memory remain unavailable.
    read_tools = "Read,Grep,Glob" if config.get("read_training_files") else ""
    args = ["--print", "--safe-mode", "--restricted", "--tools", read_tools,
            "--disable-slash-commands", "--setting-sources", "",
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--no-chrome", "--no-session-persistence", "--permission-mode=dontAsk",
            "--permission-prompts=none", "--prompt-suggestions=false",
            "--model", config["model"], "--effort=high",
            "--output-format=stream-json",
            "--verbose", "--json-schema", json.dumps(schema, separators=(",", ":"))]
    if read_tools:
        # Claude uses // for absolute paths; a single / is settings-relative.
        # Read path rules cover file tools. Glob(path) rules never match.
        args += ["--allowedTools", "Read(//workspace/**),Grep,Glob",
                 "--settings", json.dumps({"permissions": {"blockReadsOutsideWorkingDirectories": True,
                     "deny": ["Read(/" + path + "/**)" for path in ("/state", "/tmp", "/bin", "/etc")]}})]
    # Subscription-only execution has zero incremental billing while extra
    # usage is disabled. A nominal API-cost flag can truncate a valid proposal
    # despite that billing bound; retain it only for incrementally billed runs.
    if not config.get("subscription_only"):
        args += ["--max-budget-usd", str(maximum)]
    return args


def subscription_status():
    """Read the authenticated usage service; never emit account data or tokens."""
    from datetime import datetime, timezone
    credentials = json.loads(Path(CREDENTIALS).read_text())
    token = credentials["claudeAiOauth"]["accessToken"]
    request = Request("https://api.anthropic.com/api/oauth/usage", headers={
        "Authorization": "Bearer " + token, "anthropic-beta": "oauth-2025-04-20"})
    for attempt in range(3):  # Transient errors on the status endpoint are retried; it never runs inference.
        try:
            with urlopen(request, timeout=20) as response:
                value = json.load(response)
            break
        except OSError:
            if attempt == 2:
                raise
            import time
            time.sleep(2 * (attempt + 1))
    return {"source": "https://api.anthropic.com/api/oauth/usage", "checked_at": datetime.now(timezone.utc).isoformat(),
            "credential_sha256": hashlib.sha256(token.encode()).hexdigest(),
            # Stable across token refreshes: the account's organization and plan, hashed or non-identifying.
            "organization_sha256": hashlib.sha256(str(credentials.get("organizationUuid", "")).encode()).hexdigest(),
            "subscription_type": credentials["claudeAiOauth"].get("subscriptionType"),
            "extra_usage_enabled": (value.get("extra_usage") or {}).get("is_enabled")}


def prepare():
    """Build a small image from the already installed native CLI, never auth."""
    binary = Path(CLI).resolve()
    linked = subprocess.check_output(["ldd", str(binary)], text=True)
    libraries = re.findall(r"(/[^\s()]+)", linked)
    files = {"bin/claude": binary,
             "etc/ssl/certs/ca-certificates.crt": Path("/etc/ssl/certs/ca-certificates.crt")}
    files.update({str(Path(p).relative_to("/")): Path(p).resolve() for p in libraries})
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        directories = {"workspace", "home", "home/claude", "tmp", "state"}
        directories.update(str(parent) for name in files for parent in Path(name).parents if str(parent) != ".")
        for directory in sorted(directories, key=lambda p: (len(Path(p).parts), p)):
            entry = tarfile.TarInfo(directory)
            entry.type, entry.mode, entry.uid, entry.gid = tarfile.DIRTYPE, 0o755, 1000, 1000
            archive.addfile(entry)
        for name, path in files.items():
            data = path.read_bytes()
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode = len(data), 0o644 if name.endswith(".crt") else 0o755
            archive.addfile(entry, io.BytesIO(data))
    image = subprocess.check_output(["docker", "import", "-"], input=buffer.getvalue()).decode().strip()
    name = "cekura-proposer-" + hashlib.sha256(image.encode()).hexdigest()[:16]
    version = subprocess.check_output(container_args(image, name) + ["--version"], text=True).strip()
    auth = json.loads(subprocess.check_output(container_args(image, name) + ["auth", "status"], text=True))
    # Return only allowlisted status fields, never token/account identifiers.
    return {"image": image, "cli_version": version, "cli_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "auth": {k: auth.get(k) for k in ("loggedIn", "authMethod", "apiProvider", "subscriptionType")},
            "subscription": subscription_status(),
            "isolation": {"read_only": True, "model_tools": [], "host_repository_mounted": False,
                          "offline_network": "none"}, "inference_requests": 0}


def preconditions(config):
    """Checks that must pass before any reservation or inference; a failure here never starts a session.

    The CLI that runs is the one copied into the immutable, content-addressed image at
    preparation (``cli_sha256`` records it). The host binary may auto-update afterwards
    without changing what executes, so the image digest, not the host file, is verified.
    """
    image = config["image"]
    found = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", image], capture_output=True, text=True)
    if found.returncode or found.stdout.strip() != image:
        raise ValueError("Pinned Claude image unavailable; no inference started")
    usage = subscription_status() if config.get("subscription_only") else None
    if config.get("subscription_only") and (usage["extra_usage_enabled"] is not False or not same_subscription(usage, config["subscription"])):
        raise ValueError("Claude subscription changed or extra usage is enabled; no inference started")
    return usage


def same_subscription(now, recorded):
    """Access tokens rotate on refresh; the organization and plan identify the subscription."""
    if recorded.get("organization_sha256"):
        return now["organization_sha256"] == recorded["organization_sha256"] and now["subscription_type"] == recorded.get("subscription_type")
    return now["credential_sha256"] == recorded["credential_sha256"]


class NotStarted(RuntimeError):
    """Raised before the Claude container is launched: no session ran, so nothing was used."""


def execute(request):
    """Run one Claude session. Any failure before the container launches raises ``NotStarted``."""
    config = request["config"]
    image = config["image"]
    name = "cekura-proposer-" + hashlib.sha256(request["prompt"].encode()).hexdigest()[:16]
    import tempfile
    workspace = tempfile.TemporaryDirectory(prefix="cekura-training-")
    try:
        try:
            usage = preconditions(config)
            command = container_args(image, name, network=True)
            root = Path(workspace.name)
            root.chmod(0o755)
            for filename, content in request.get("workspace", {}).items():
                relative = Path(filename)
                if relative.is_absolute() or ".." in relative.parts or not isinstance(content, str):
                    raise ValueError("Invalid allowed workspace file")
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                for parent in path.parents:
                    if parent == root.parent:
                        break
                    parent.chmod(0o755)
                path.write_text(content)
                path.chmod(0o444)
            if request.get("workspace"):
                command += ["--mount=type=bind,src=" + str(root) + ",dst=/workspace,readonly"]
            command += cli_args(config, request["schema"])
        except Exception as error:
            raise NotStarted("%s: %s" % (type(error).__name__, error)) from error
        try:
            process = subprocess.run(command, input=request["prompt"], capture_output=True, text=True, timeout=600)
            if len(process.stdout.encode()) + len(process.stderr.encode()) > LIMIT:
                raise ValueError("Claude evidence exceeded the capture limit")
            return {"returncode": process.returncode, "events": process.stdout, "stderr": process.stderr,
                    "subscription": usage, "incremental_cost_usd": 0 if usage is not None else None}
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30)
    finally:
        workspace.cleanup()


def remote_main():
    import sys
    value = json.loads(sys.stdin.buffer.read(LIMIT + 1))
    if value["operation"] == "prepare":
        result = prepare()
    elif value["operation"] == "subscription-status":
        result = subscription_status()
    elif value["operation"] == "propose":
        result = execute(value)
    else:
        raise ValueError("Unknown remote Claude operation")
    print(json.dumps(result))


def remote_call(host, payload):
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", host):
        raise ValueError("Use an existing SSH alias, not shell command text")
    source = Path(__file__).read_text()
    command = "python3 -c " + shlex.quote(source + "\nremote_main()")
    data = json.dumps(payload)
    if len(data.encode()) > LIMIT:
        raise ValueError("Training payload exceeds the transport limit")
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "-T", host, command],
                            input=data, capture_output=True, text=True, timeout=660)
    if result.returncode:
        raise RuntimeError("Remote Claude controller failed: " + result.stderr[-2000:])
    return json.loads(result.stdout)


class ClaudeProposer:
    def __init__(self, config, artifacts, ledger):
        self.config, self.artifacts, self.ledger = config, artifacts, ledger

    def propose(self, baseline, training_history, iteration, forbidden):
        from jsonschema import validate
        from .common import ROOT, digest, read, write
        from .proposer import SCHEMA, training_payload
        from .proposal_transport.history import encode
        from .skill import candidate
        if iteration not in (1, 2):
            raise ValueError("Exactly two proposal iterations are allowed")
        history = training_payload(training_history)
        encoded_history = encode(history)
        cfg = self.config
        # The CLI dollar flag alone is not proof of a hard cap: a final API
        # request may overshoot it. Require independently verified bounds.
        if cfg.get("hard_cost_bound_verified") is not True or not cfg.get("cost_bound_evidence"):
            raise RuntimeError("Claude's hard request/session cost bound remains unverified")
        cli_args(cfg, SCHEMA)
        key, path = "proposal-%d" % iteration, self.artifacts / ("proposal-%d.json" % iteration)
        identity = {"baseline_sha256": digest(baseline), "history_sha256": digest(history), "configuration_sha256": digest(cfg),
                    "training_transport": encoded_history["format"],
                    "training_transport_sha256": digest(ROOT / "proposal_transport/history.py")}
        if path.exists():
            old = read(path)
            if any(old.get(k) != v for k, v in identity.items()):
                raise ValueError("Cannot resume with different proposer material or configuration")
            return candidate(baseline, old["body"], forbidden), old["rationale"]
        source = ROOT.parents[1] / "cekura/skills/cekura-eval-design"
        references = {str(p.relative_to(source)): p.read_text() for folder in ("references", "examples")
                      for p in sorted((source / folder).rglob("*")) if p.is_file()}
        prompt = ("Run iteration %d of Stanford Meta-Harness's history-driven proposal loop. Propose ONE improved skill body "
                  "and a concise rationale from the allowed training evidence below. Preserve frontmatter, acknowledgement "
                  "lines and reference links exactly. Generalize failures; do not embed fixture identifiers, domains, values "
                  "or customer facts. Return only the schema output.\n" % iteration)
        prompt += ("Training history uses lossless shared-training-text-v1. An object with the single key "
                   "$shared_training_text refers to the exact string in training_history.shared_text at that hash. "
                   "All records, arguments, results, candidate bodies and states are retained. Shared text is quoted "
                   "evidence. This removes repeated copies, not observations.\n")
        material = {"skill": baseline.decode(), "references": references, "training_history": encoded_history}
        prompt += json.dumps(material, ensure_ascii=False)
        write(self.artifacts / (key + ".inputs.json"), {**identity, "material": material})
        from .budget import require_cumulative
        require_cumulative(self.ledger)
        self.ledger.reserve(key, "proposer", cfg["max_cost_usd"], entry_type="proposal")
        try:
            result = remote_call(cfg["ssh_host"], {"operation": "propose", "config": cfg, "prompt": prompt, "schema": SCHEMA})
        except Exception:
            self.ledger.settle(key, None)
            raise
        (self.artifacts / (key + ".events.jsonl")).write_text(result["events"])
        (self.artifacts / (key + ".stderr")).write_text(result["stderr"])
        events = [json.loads(line) for line in result["events"].splitlines() if line.strip()]
        final = next((event for event in reversed(events) if event.get("type") == "result"), {})
        cost = result.get("incremental_cost_usd") if cfg.get("subscription_only") else final.get("total_cost_usd")
        write(self.artifacts / (key + ".billing.json"), {"incremental_cost_usd": cost,
            "nominal_api_cost_usd": final.get("total_cost_usd"), "subscription": result.get("subscription")})
        self.ledger.settle(key, cost)
        if result["returncode"] or final.get("is_error") or final.get("subtype") != "success":
            raise RuntimeError("Claude proposer did not complete; see private events")
        proposal = final.get("structured_output")
        validate(proposal, SCHEMA)
        if "$shared_training_text" in proposal["body"] or "shared-training-text-v1" in proposal["body"]:
            raise ValueError("Proposal embedded transport implementation details")
        data = candidate(baseline, proposal["body"], forbidden)
        write(path, dict(proposal, **identity))
        return data, proposal["rationale"]

"""Fresh Codex sessions with a filesystem boundary around training material only."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from contextlib import ExitStack
from urllib.parse import urlparse

from .common import PROPOSER, ROOT, digest, read, write
from .skill import candidate, split

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["body", "rationale"],
          "properties": {"body": {"type": "string"}, "rationale": {"type": "string"}}}


def training_payload(history):
    """Accept only explicit training results, including full traces and candidate bytes."""
    for item in history:
        if item.get("split") != "training" or not item.get("task_id"):
            raise ValueError("Proposer evidence must consist entirely of training results")
        if not {"trace", "initial_state", "final_state", "grade", "candidate_body"} <= item.keys():
            raise ValueError("Full training evidence is required")
    # Cache reuse is operational metadata, not a changed training observation.
    # Binding it into proposal identity made interrupted search fail on resume.
    return [{key: value for key, value in item.items() if key != "cache_hit"} for item in history]


def sandbox_profile(workspace, binary, proxy_port=None):
    """macOS deny-by-default reads: a read-only Codex sandbox alone is insufficient."""
    if not Path("/usr/bin/sandbox-exec").exists():
        raise RuntimeError("A verified filesystem-isolated Codex launcher is required on this OS")
    workspace = workspace.resolve()
    paths = [str(workspace), str(Path(binary).resolve())]
    quote = lambda path: '"' + str(path).replace('\\', '\\\\').replace('"', '\\"') + '"'
    rules = ["(version 1)", "(deny default)", "(allow process*)", "(allow sysctl-read)",
             "(allow mach-lookup)",
             ('(allow network-outbound (remote ip "localhost:%d"))' % proxy_port if proxy_port else "(allow network-outbound)"),
             "(allow network-inbound (local ip \"localhost:*\"))",
             "(allow file-read-metadata)"]
    # System libraries may live on macOS cryptex/preboot paths. Permit system
    # reads while excluding all user homes and both private artifact locations.
    rules += ['(allow file-read* (require-not (require-any (subpath "/Users") (subpath "/private/tmp") (subpath "/private/var/folders"))))']
    rules += ["(allow file-read* (subpath %s))" % quote(path) for path in paths]
    if proxy_port:
        rules += ["(allow network-bind)", "(allow network-outbound (remote unix-socket))",
                  "(allow network-inbound (local unix-socket))"]
    rules += ["(allow file-write* (subpath %s))" % quote(workspace / "artifacts"),
              "(allow file-write* (literal \"/dev/null\"))"]
    return "\n".join(rules)


def usage_cost(events, rates):
    totals = []
    for event in events:
        if event.get("type") == "turn.completed":
            usage = event.get("usage", {})
            if not {"input_tokens", "output_tokens"} <= usage.keys():
                return None
            cached = usage.get("cached_input_tokens", 0)
            if min(usage["input_tokens"], usage["output_tokens"], cached) < 0 or cached > usage["input_tokens"]:
                return None
            totals.append(((usage["input_tokens"] - cached) * rates["input_per_million"]
                           + cached * rates["cached_input_per_million"]
                           + usage["output_tokens"] * rates["output_per_million"]) / 1_000_000)
    return sum(totals) if totals else None


class CodexProposer:
    def __init__(self, config, artifacts, ledger, offline_transport=None):
        self.config, self.artifacts, self.ledger = config, artifacts, ledger
        self.offline_transport = offline_transport

    def propose(self, baseline, training_history, iteration, forbidden):
        if iteration not in (1, 2):
            raise ValueError("Exactly two iterations, at most one candidate each")
        history = training_payload(training_history)
        binary = shutil.which(self.config.get("binary", "codex"))
        if binary is None:
            raise RuntimeError("codex exec is unavailable")
        key = "proposal-%d" % iteration
        result_path = self.artifacts / (key + ".json")
        if result_path.exists():
            old = read(result_path)
            if old["baseline_sha256"] != digest(baseline) or old["history_sha256"] != digest(history):
                raise ValueError("Cannot resume a proposal with different training history")
            return candidate(baseline, old["body"], forbidden), old["rationale"]
        with tempfile.TemporaryDirectory(prefix="cekura-proposal-") as temporary, ExitStack() as guards:
            workspace = Path(temporary).resolve()
            (workspace / "artifacts").mkdir()
            (workspace / "SKILL.md").write_bytes(baseline)
            # Only allowed references are copied; never copy the repository, graders, or fixtures.
            source = ROOT.parents[1] / "cekura/skills/cekura-eval-design"
            for folder in ("references", "examples"):
                shutil.copytree(source / folder, workspace / folder)
            write(workspace / "training_history.json", history)
            write(workspace / "proposal.schema.json", SCHEMA)
            gateway = None
            if self.config.get("accounting") == "per_request":
                from .gateway import AdmissionGateway
                endpoint = urlparse(self.config["model_base_url"])
                gateway = guards.enter_context(AdmissionGateway(endpoint.hostname, endpoint.path.rstrip("/") + "/responses", "responses",
                    self.config, self.ledger, key, self.artifacts / (key + ".gateway"),
                    transport=self.offline_transport, verify=self.offline_transport is None))
                shutil.copyfile(gateway.ca, workspace / "ca.pem")
            profile = workspace / "isolation.sb"
            profile.write_text(sandbox_profile(workspace, binary, gateway.port if gateway else None))
            inputs = {str(p.relative_to(workspace)): digest(p) for p in workspace.rglob("*") if p.is_file()}
            output = workspace / "artifacts/proposal.json"
            provider = self.config["provider_config"]
            # Do not load global MCP/plugin/memory configuration or resume an old session.
            args = ["/usr/bin/sandbox-exec", "-f", str(profile), binary, "exec", "--ignore-user-config",
                    "--ignore-rules", "--skip-git-repo-check", "--ephemeral", "--json", "--sandbox", "read-only",
                    "--cd", str(workspace), "--model", PROPOSER["model"],
                    "-c", 'model_provider="azure"', "-c", 'model_reasoning_effort="high"',
                    "-c", "model_providers.azure=" + provider,
                    "-c", 'history.persistence="none"',
                    "-c", 'cli_auth_credentials_store="file"',
                    "-c", 'sqlite_home="' + str(workspace / "artifacts/state") + '"',
                    "-c", 'log_dir="' + str(workspace / "artifacts/log") + '"',
                    "-c", 'web_search="disabled"', "-c", 'features.plugins=false',
                    "-c", 'features.apps=false', "-c", 'features.skip_host_skill_discovery=true',
                    "-c", 'features.daemon_auto_start=false', "-c", 'features.enable_request_compression=false',
                    "--output-schema", str(workspace / "proposal.schema.json"), "-o", str(output), "-"]
            prompt = ("Run iteration %d of Stanford Meta-Harness's history-driven proposal loop. "
                      "Read SKILL.md, allowed references, and full training_history.json. Propose ONE improved "
                      "body and a concise rationale. Preserve all acknowledgement lines and every reference "
                      "link exactly. Do not edit frontmatter or reference files. Generalize from failures; "
                      "do not embed task identifiers, domains, synthetic values or customer facts. "
                      "Return the schema output only. Filesystem writes are restricted to artifacts/." % iteration)
            env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", self.config["credential_env"])}
            if self.offline_transport:
                env[self.config["credential_env"]] = "offline-transport-probe"
            if gateway:
                (workspace / "artifacts/tmp").mkdir()
                env.update(HTTPS_PROXY="http://127.0.0.1:%d" % gateway.port,
                           HTTP_PROXY="http://127.0.0.1:%d" % gateway.port, NO_PROXY="",
                           TMPDIR=str(workspace / "artifacts/tmp"),
                           SSL_CERT_FILE=str(workspace / "ca.pem"), CODEX_CA_CERTIFICATE=str(workspace / "ca.pem"))
                self.ledger.start(key, "proposer", entry_type="proposal")
            else:
                self.ledger.reserve(key, "proposer", self.config["max_cost_usd"])
            events_path = self.artifacts / (key + ".events.jsonl")
            with events_path.open("w") as events, (self.artifacts / (key + ".stderr")).open("w") as stderr:
                proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=events, stderr=stderr,
                                        env=env, cwd=str(workspace), start_new_session=True, text=True)
                try:
                    proc.communicate(prompt, timeout=600)
                except subprocess.TimeoutExpired:
                    import signal
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.communicate()
                    self.ledger.settle(key, None)
                    raise RuntimeError("Codex proposal timed out")
            events = [__import__("json").loads(line) for line in events_path.read_text().split("\n") if line.strip()]
            if gateway:
                # Wait for stream drainage/reconciliation before examining usage.
                guards.close()
                write(self.artifacts / (key + ".billing.json"), {"requests": gateway.requests, "errors": gateway.errors,
                      "model_cost_usd": str(gateway.cost) if gateway.cost is not None else None})
                self.ledger.settle(key, 0 if gateway.cost is not None else None)
                if gateway.errors or gateway.denied:
                    raise RuntimeError("Codex billing/transport failed; see private gateway evidence")
            else:
                self.ledger.settle(key, usage_cost(events, self.config["rates"]))
            if proc.returncode or not output.exists():
                raise RuntimeError("Codex proposer failed; see private JSON events")
            proposal = read(output)
            if set(proposal) != {"body", "rationale"} or not all(isinstance(v, str) and v.strip() for v in proposal.values()):
                raise ValueError("Proposal does not match the output schema")
            data = candidate(baseline, proposal["body"], forbidden)
            # Audit all inputs after the session, even though the OS policy denies writes.
            if any(not (workspace / name).exists() or digest(workspace / name) != value for name, value in inputs.items()):
                raise ValueError("Proposer modified protected material")
            write(result_path, dict(proposal, baseline_sha256=digest(baseline), history_sha256=digest(history)))
            return data, proposal["rationale"]

"""Fresh training-only proposal sessions; no-change is an ordinary outcome."""
import json
from pathlib import Path

from ..common import ROOT, digest, write
from ..proposer import training_payload
from ..skill import SKILL, candidate, material, split
from .transport import ClaudeSession

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["status", "body", "hypothesis", "rationale", "targeted_checks"],
          "properties": {"status": {"enum": ["candidate", "no_change"]}, "body": {"type": "string"},
                         "hypothesis": {"type": "string"}, "rationale": {"type": "string"},
                         "targeted_checks": {"type": "array", "uniqueItems": True, "items": {"type": "string"}}}}


def screen(data, parent, history, rationale, previous):
    if digest(data) == digest(parent) or digest(data) in {digest(d) for d, _ in previous}:
        raise ValueError("Duplicate/no-op candidate cannot consume target evaluation")
    normalize = lambda s: " ".join(s.casefold().split())
    hypothesis = normalize(rationale.get("hypothesis", ""))
    if not hypothesis or hypothesis in {normalize(r.get("hypothesis", "")) for _, r in previous}:
        raise ValueError("Candidate needs a distinct, nonempty hypothesis")
    # Generator defects behind a correctly formed request are not a reason to grow the skill.
    failures = {c for r in history if r["candidate_sha256"] == digest(parent) for c in r["grade"]["failed_checks"]
                if r["grade"].get("attribution", {}).get(c, "authoring") == "authoring"}
    targeted = set(rationale.get("targeted_checks", []))
    if not targeted or not targeted <= failures:
        raise ValueError("Candidate must target unresolved authoring checks of its retained parent")


def training_workspace(parent, history, labels=None):
    """Read-only proposal workspace; ``labels`` names each revision's sha (baseline, candidate-N)."""
    history = training_payload(history)
    labels = labels or {}
    files = {"SKILL.md": parent.decode()}
    files.update({n: b.decode() for n, b in material().items() if n.startswith(("references/", "examples/"))})
    index = []
    def encode(value):
        if isinstance(value, str) and len(value) > 512:
            path = "training/shared/" + digest(value.encode()) + ".txt"
            files[path] = value
            return {"$text_file": path}
        if isinstance(value, list): return [encode(v) for v in value]
        if isinstance(value, dict): return {k: encode(v) for k, v in value.items()}
        return value
    for i, r in enumerate(history):
        name = "training/trace-%03d.json" % i
        files[name] = json.dumps(encode(r), ensure_ascii=False, indent=2)
        index.append({"path": name, "task": r["task_id"], "revision": labels.get(r.get("candidate_sha256"), (r.get("candidate_sha256") or "unknown")[:12]),
                      "trial": r.get("repeat", 0), "score": r["grade"]["score"], "failed_checks": r["grade"]["failed_checks"],
                      "attribution": {c: r["grade"].get("attribution", {}).get(c, "authoring") for c in r["grade"]["failed_checks"]}})
    files["training/index.json"] = json.dumps(index, ensure_ascii=False)
    # Per task: how often each revision passed and which checks failed, so one noisy trial is visible as noise.
    summary = {}
    for row in index:
        cell = summary.setdefault(row["task"], {}).setdefault(row["revision"], {"trials": 0, "passed": 0, "failed_checks": {}})
        cell["trials"] += 1
        cell["passed"] += bool(row["score"])
        for check in row["failed_checks"]:
            cell["failed_checks"][check] = cell["failed_checks"].get(check, 0) + 1
    files["training/by_task.json"] = json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True)
    return files


class Proposer:
    def __init__(self, config, directory, ledger):
        # Proposal session names repeat in every run; the namespace keeps each run's wallet entries and allowance apart.
        namespace = "run-" + digest(str(Path(directory).resolve()).encode())[:12]
        self.session = ClaudeSession(dict(config, read_training_files=True), directory / "proposal-sessions", ledger, namespace=namespace)
        self.directory = directory

    def verify(self):
        marker = "training-read-verification-" + digest(b"v2 read-only artifact probe")
        path = self.directory / "proposer-read-probe.json"
        if path.exists():
            value = __import__("json").loads(path.read_text())
            if value.get("configuration_sha256") == digest(self.session.config) and value.get("passed") is True:
                return True
        schema = {"type": "object", "additionalProperties": False, "required": ["observed"], "properties": {"observed": {"type": "string"}}}
        value = self.session("Read /workspace/training/read-probe.txt using the Read tool and return its exact contents as observed. This is a tool connectivity check, not skill optimization.",
                             {}, schema, "proposer-read-probe", workspace={"training/read-probe.txt": marker})
        response = __import__("json").loads((self.session.directory / "proposer-read-probe.response.json").read_text())
        events = [json.loads(line) for line in response["events"].splitlines() if line.strip()]
        reads = [block for event in events for block in event.get("message", {}).get("content", [])
                 if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Read"]
        passed = value["observed"] == marker and any(b.get("input", {}).get("file_path") == "/workspace/training/read-probe.txt" for b in reads)
        write(path, {"passed": passed, "configuration_sha256": digest(self.session.config)})
        if not passed:
            raise ValueError("Claude's training-file read capability was not demonstrated")
        return passed

    def propose(self, parent, history, iteration, forbidden, outcomes=()):
        if not 1 <= iteration <= 4:
            raise ValueError("At most four distinct candidates")
        previous = [(p.read_bytes(), json.loads(p.with_suffix(".rationale.json").read_text()))
                    for p in sorted(self.directory.glob("candidate-*.md"))]
        labels = {digest(SKILL): "baseline"}
        labels.update({digest(p): p.stem for p in self.directory.glob("candidate-*.md")})
        files = training_workspace(parent, history, labels)
        prompt = ("Use Stanford Meta-Harness history-driven reflection. Inspect /workspace/SKILL.md, references and training/index.json, "
                  "then read relevant complete training traces with the read-only tools. A single-key $text_file object points to its exact, "
                  "losslessly stored text in a shared file; follow these pointers as needed. Propose one targeted general improvement supported by "
                  "remaining failures, or return no_change if there is no supported change. Avoid repeating falsified hypotheses. Preserve the "
                  "frontmatter, acknowledgement lines and reference links. Return only the editable body, at most 60000 characters INCLUDING "
                  "the preserved header, and at most 500 total lines. Any compression is an evaluated edit. Never include task IDs, domain facts, "
                  "customer values, grading code or fixture-specific rules. State one hypothesis and why this edit addresses it. No held-out data is available.")
        prompt += (" List targeted_checks using the exact failed check names of the retained parent's training results; a candidate needs at least one"
                   " unresolved check. Each result's grade.attribution marks failures caused by the generation service ('backend') when the"
                   " assistant's request was correct; those are not skill defects and cannot be targeted.")
        files["training/hypotheses.json"] = json.dumps([r for _, r in previous], ensure_ascii=False)
        if outcomes:
            # Measured training outcome of every earlier attempt: tasks it fixed, consistent gains and
            # regressions, and tasks it newly failed. Training data only.
            files["training/outcomes.json"] = json.dumps(list(outcomes), ensure_ascii=False, indent=1)
            prompt += (" training/outcomes.json records how each earlier candidate measured on training (first-trial fixes, consistent gains and"
                       " regressions, repeated tasks) and training/by_task.json tallies every revision's passes and failed checks per task."
                       " Outcomes vary between identical trials, so read a single failure as weak evidence. Do not re-test a hypothesis already"
                       " measured: choose a different remaining failure family, or keep what an earlier candidate fixed while removing what made"
                       " it fail elsewhere. An edit that makes the assistant refuse or stop short of requested work is a regression.")
        value = self.session(prompt, {"iteration": iteration, "parent_sha256": digest(parent), "index": "training/index.json"}, SCHEMA,
                             "proposal-%d" % iteration, workspace=files)
        if value["status"] == "no_change":
            write(self.directory / ("proposal-%d.no-change.json" % iteration), value)
            return None, value
        body, header = value["body"], split(parent)[0].decode()
        if body.startswith(header):
            body = body[len(header):]  # The whole file came back with byte-identical frontmatter: a body-only edit.
        data = candidate(parent, body, forbidden)
        if len(data.decode()) > 60000:
            raise ValueError("Candidate would truncate under the fixed loader")
        screen(data, parent, history, value, previous)
        write(self.directory / ("candidate-%d.rationale.json" % iteration), value)
        (self.directory / ("candidate-%d.md" % iteration)).write_bytes(data)
        return data, value

"""One bounded command from approval to terminal report.

After the upfront fixture/gold signoff and launch approval, ``run`` qualifies the judge,
samples baseline costs, forecasts the complete comparison, searches on training only,
freezes one finalist, evaluates validation and then sealed tasks, runs the scheduled and
diagnostic repeats and writes the terminal report. No human gate interrupts it; final
patch acceptance is a separate step afterwards. Every decision is recomputed from cached
evidence on each invocation, so resume and criterion-level adjudication rescore all
gates without repeating inference.
"""
from __future__ import annotations

import difflib
import fcntl
import time
from decimal import Decimal
from pathlib import Path

from jsonschema import ValidationError as SchemaValidationError

from ..budget import BudgetError
from ..common import ROOT, REPO, digest, private_dir, read, write
from ..meta_harness import History
from ..preflight import preflight
from ..selection import review_packet
from ..skill import SKILL, candidate, material, manifest, split
from . import gates
from .budget import CLAUDE_SESSION_RESERVATION, COST_DISCOVERY_CAP, admit, minimum_plan, open_ledger, trial_cost
from .dataset import load, canaries
from .evaluator import results
from .judge import ClaudeJudge, packet
from .proposer import Proposer, screen
from .review import gate, prepare

DEADLINE_SECONDS = 24 * 3600
MAX_ATTEMPTS, MAX_EVALUATED = 4, 2
REPEATS = {"validation": ("variables-3", "lifecycle-3", "triggers-3"), "sealed": ("verbatim-4", "sources-4", "causal-4")}
MAX_DIAGNOSTICS = 12


class Terminal(Exception):
    """An ordinary, reportable end of the experiment (not an error)."""
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status


def identity(config):
    return {"config_sha256": digest({k: v for k, v in config.items() if k != "budget_policy"}), "tasks_sha256": digest(load()),
            "baseline_sha256": digest(SKILL), "materials": manifest(material()),
            "fixed_skills": {str(p.relative_to(REPO)): digest(p) for p in (REPO / "cekura/skills").rglob("*") if p.is_file()},
            "code": {str(p.relative_to(ROOT)): digest(p) for p in ROOT.rglob("*.py") if "tests" not in p.parts}}


def launch_gate(directory, ident):
    path = directory / "launch-approval.json"
    if not path.exists():
        return False
    value = read(path)
    return bool(value.get("reviewer")) and value.get("approved") is True and value.get("identity_sha256") == digest(ident) and value.get("ceiling_usd") == "150"


def forbidden_material(tasks):
    tokens = []
    for t in tasks:
        a = t["fixture"]["agent"]
        tokens += [t["id"], t["pack_id"], a["name"], a["name"].split()[0], str(a["id"]), str(a["project"])]
        tokens += [str(v) for v in a.get("required_variables", {}).values()]
        tokens += [str(r["id"]) for rows in t["fixture"]["resources"].values() for r in rows]
    return tokens


def authoring_failures(records, sha):
    """Checks a proposal may target: authoring failures of that revision, not generator defects."""
    return {c for r in records if r["candidate_sha256"] == sha for c in r["grade"]["failed_checks"]
            if r["grade"].get("attribution", {}).get(c, "authoring") == "authoring"}


def run(config, artifacts, evaluator=None, proposer=None, judge=None, skip_preflight=False, clock=time.time):
    directory = private_dir(artifacts)
    with (directory / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return Controller(config, directory, evaluator, proposer, judge, skip_preflight, clock).run()


class Controller:
    def __init__(self, config, directory, evaluator, proposer, judge, skip_preflight, clock):
        self.config, self.directory, self.clock = config, directory, clock
        self.evaluator, self.proposer, self.judge, self.skip_preflight = evaluator, proposer, judge, skip_preflight
        self.path = directory / "experiment.json"
        self.ident = identity(config)
        self.state = read(self.path) if self.path.exists() else {"identity": self.ident, "status": "prepared", "attempts": [], "candidates": []}
        if self.state["identity"] != self.ident:
            raise ValueError("Experiment identity changed; prepare a new run carrying the wallet, never reuse held-outs for search")
        self.ledger = open_ledger(config)
        self.tasks = load()
        self.training, self.validation, self.sealed = [[t for t in self.tasks if t["split"] == s] for s in ("training", "validation", "sealed")]
        self.baseline = SKILL.read_bytes()
        self.records = []

    def save(self, **values):
        self.state.update(values)
        write(self.path, self.state)

    def run(self):
        try:
            self._run()
        except Terminal as end:
            self.save(status=end.status, reason=str(end))
        except (BudgetError, RuntimeError, ValueError, SchemaValidationError) as error:
            self.save(status="stopped", reason=type(error).__name__ + ": " + str(error))
        finally:
            self.save()
            report(self.directory, self.state, self.ledger, self.config)
        return self.state

    # --- execution helpers ----------------------------------------------------------------
    def check_deadline(self):
        if self.state.get("deadline") and self.clock() > self.state["deadline"]:
            raise Terminal("deadline_reached", "The 24-hour overall deadline passed; results so far are reported")

    def trial(self, data, task, stage, repeat=0):
        self.check_deadline()
        self.save(status="running", stage=stage, current_task=task["id"])
        record = self.evaluator.evaluate(data, task, repeat)
        if record["status"] != "complete" or record.get("cost_usd") is None:
            raise Terminal("inconclusive_execution", "%s on %s ended %s after bounded retries; incomplete evidence cannot support a comparison"
                           % (stage, task["id"], record["status"]))
        self.records.append(record)
        print({"stage": stage, "task": task["id"], "score": record["grade"]["score"], "semantic": record["grade"].get("semantic_status")}, flush=True)
        return record

    def stage(self, data, items, name, repeat=0):
        return [self.trial(data, t, name, repeat) for t in items]

    def paired(self, finalist, items, name, repeat=0):
        """Sequential paired trials; the arm order alternates task by task."""
        before, after = [], []
        for i, task in enumerate(items):
            for arm in (("baseline", "finalist") if i % 2 == 0 else ("finalist", "baseline")):
                record = self.trial(self.baseline if arm == "baseline" else finalist, task, "%s_%s" % (name, arm), repeat)
                (before if arm == "baseline" else after).append(record)
        return before, after

    # --- protocol -------------------------------------------------------------------------
    def _run(self):
        directory = self.directory
        if not gate(directory):
            prepare(directory)
            raise Terminal("awaiting_fixture_and_gold_human_review", "Fixture/gold domain signoff is required before any inference")
        if not launch_gate(directory, self.ident):
            write(directory / "launch-approval.template.json", {"identity_sha256": digest(self.ident), "ceiling_usd": "150", "reviewer": "", "approved": False})
            raise Terminal("awaiting_launch_approval", "Launch approval bound to this experiment identity is required")
        config = self.config
        if not self.skip_preflight:
            check = preflight(config)
            write(directory / "preflight.json", {k: v for k, v in check.items() if k != "configuration"})
            if not check["ready"]:
                raise Terminal("preflight_failed", "; ".join(check["failures"]))
            config = check["configuration"]
        if not self.state.get("deadline"):
            self.save(launched_at=self.clock(), deadline=self.clock() + DEADLINE_SECONDS)
        self.judge = self.judge or ClaudeJudge(config["judge"], directory, self.ledger)
        if not self.judge.qualified():
            self.save(stage="judge_qualification")
            if not self.judge.qualify()["passed"]:
                raise Terminal("judge_not_qualified", "The judge did not meet 22/24, zero critical false passes and the paraphrase control")
        if self.evaluator is None:
            from .evaluator import Evaluator
            self.evaluator = Evaluator(config, directory, self.ledger, self.judge)
        self.proposer = self.proposer or Proposer(config["proposer"], directory, self.ledger)
        if hasattr(self.proposer, "verify"):
            self.proposer.verify()

        sample = canaries(self.training)
        try:
            with self.ledger.staged("baseline-cost-discovery", COST_DISCOVERY_CAP):
                cost_sample = self.stage(self.baseline, sample, "baseline_cost_sample")
        except BudgetError as error:
            if "Stage allowance" in str(error):
                raise Terminal("cost_discovery_cap_exhausted", "The 12 baseline canaries did not fit the $15 cost-discovery cap")
            raise
        rest = [t for t in self.training if t not in sample]
        plan = minimum_plan(cost_sample, rest, self.training, self.validation, self.sealed, self.repeat_tasks(), config)
        plan["funded"] = self.ledger.can_finish(Decimal(plan["needed_usd"]), CLAUDE_SESSION_RESERVATION)
        write(directory / "forecast.json", plan)
        if not plan["funded"]:
            raise Terminal("infeasible", "The minimum complete comparison ($%s with margin) does not fit the remaining authorization" % plan["needed_usd"])
        before = cost_sample + self.stage(self.baseline, rest, "baseline_training")
        ids = [t["id"] for t in self.training]
        if gates.passes(before, ids) == len(ids):
            raise Terminal("training_saturated", "The baseline already passes every training task; there is nothing to search")

        finalist = self.search(before, config)
        data = (directory / (finalist + ".md")).read_bytes()
        self.save(finalist=finalist)
        val_before, val_after = self.paired(data, self.validation, "validation")
        validation = gates.compare(val_before, val_after, [t["id"] for t in self.validation])
        self.save(validation=validation)
        if not validation["passed"]:
            raise Terminal("validation_no_supported_improvement", "Validation needs a strict worst-case gain and no regression; search ends")
        sealed_before, sealed_after = self.paired(data, self.sealed, "sealed")
        repeats = {split: self.paired(data, [t for t in self.tasks if t["id"] in names], "repeat_" + split, repeat=1)
                   for split, names in REPEATS.items()}
        self.diagnostics(data)
        self.decide(data)

    def repeat_tasks(self):
        return [t for t in self.tasks if t["id"] in REPEATS["validation"] + REPEATS["sealed"]]

    def search(self, before, config):
        """Training-only proposal loop; returns the single frozen finalist's name."""
        if self.state.get("finalist_frozen"):
            return self.state["finalist"]
        directory, ids = self.directory, [t["id"] for t in self.training]
        sample = canaries(self.training)
        history, parent, parent_passes = list(before), self.baseline, gates.passes(before, ids)
        evaluated, zero_gain, attempts = 0, 0, []
        forbidden = forbidden_material(self.tasks)
        for i in range(1, MAX_ATTEMPTS + 1):
            if evaluated >= MAX_EVALUATED or zero_gain >= 2 or parent_passes == len(ids):
                break
            rejected, no_change = directory / ("proposal-%d.rejected.json" % i), directory / ("proposal-%d.no-change.json" % i)
            data_path = directory / ("candidate-%d.md" % i)
            if no_change.exists():
                attempts.append({"attempt": i, "outcome": "no_change", "reason": read(no_change).get("rationale")})
                break
            if rejected.exists():
                attempts.append(read(rejected))
                continue
            funded, needed = admit(self.ledger, history, self.training, self.validation, self.sealed, self.repeat_tasks(), config)
            if not funded:
                attempts.append({"attempt": i, "outcome": "budget", "needed_usd": str(needed)})
                break
            if not data_path.exists():
                try:
                    data, rationale = self.proposer.propose(parent, history, i, forbidden)
                except (ValueError, SchemaValidationError) as error:
                    row = {"attempt": i, "outcome": "rejected", "reason": str(error)}
                    write(rejected, row)
                    attempts.append(row)
                    continue
                if data is None:
                    attempts.append({"attempt": i, "outcome": "no_change", "reason": rationale.get("rationale")})
                    break
            data = data_path.read_bytes()
            rationale = read(directory / ("candidate-%d.rationale.json" % i))
            name = "candidate-%d" % i
            canary = self.stage(data, sample, name + "_canary")
            screened = gates.compare(before, canary, [t["id"] for t in sample])
            history.extend(canary)
            if screened["regressions"]:
                row = {"attempt": i, "outcome": "canary_rejected", "name": name, "regressions": screened["regressions"]}
                write(rejected, row)
                attempts.append(row)
                zero_gain += 1
                continue
            full = canary + self.stage(data, [t for t in self.training if t not in sample], name + "_training")
            history.extend(r for r in full if r not in canary)
            evaluated += 1
            comparison = gates.compare(before, full, ids)
            item = {"name": name, "sha256": digest(data), "training_passes": gates.passes(full, ids), "eligible": comparison["passed"],
                    "bytes": len(data), "cost_usd": str(sum((trial_cost(r) for r in full), Decimal(0))), "comparison": comparison,
                    "hypothesis": rationale.get("hypothesis")}
            summary = History(directory / "meta-history")
            if summary.next_iteration() <= i:
                summary.record(i, name, rationale.get("rationale", ""), full)
            attempts.append({"attempt": i, "outcome": "evaluated", "name": name, "eligible": item["eligible"], "training_passes": item["training_passes"]})
            self.state["candidates"] = [c for c in self.state["candidates"] if c["name"] != name] + [item]
            if item["eligible"] and item["training_passes"] > parent_passes:
                parent, parent_passes, zero_gain = data, item["training_passes"], 0
            else:
                zero_gain += 1
        eligible = sorted((c for c in self.state["candidates"] if c["eligible"]),
                          key=lambda c: (-c["training_passes"], c["bytes"], Decimal(c["cost_usd"]), c["name"]))
        self.save(attempts=attempts, finalist_frozen=True, finalist=eligible[0]["name"] if eligible else None)
        if not eligible:
            raise Terminal("no_training_candidate_qualifies", "No proposal reached a strict, regression-free training gain")
        return eligible[0]["name"]

    def diagnostics(self, data):
        """Up to 12 extra trials, only where an arm's repeated observations disagree."""
        used = self.state.get("diagnostics", [])
        ids = REPEATS["validation"] + REPEATS["sealed"]
        for sha, arm_data in ((digest(self.baseline), self.baseline), (digest(data), data)):
            records = [r for r in self.records if r["candidate_sha256"] == sha]
            for task_id in gates.unstable(records, ids):
                if len(used) >= MAX_DIAGNOSTICS:
                    return
                task = next(t for t in self.tasks if t["id"] == task_id)
                repeat = 2 + sum(u["task"] == task_id and u["arm"] == sha for u in used)
                funded, _ = admit(self.ledger, records, [task], [], [], [], self.config)
                if not funded:
                    return
                self.trial(arm_data, task, "diagnostic", repeat)
                used.append({"task": task_id, "arm": sha, "repeat": repeat, "reason": "repeated observations disagree"})
                self.save(diagnostics=used)

    def disputed(self, data):
        """Audit the repeat tasks' first trials with a second blinded judgment; disagreements stay unresolved."""
        out = set()
        for task in self.repeat_tasks():
            for sha in (digest(self.baseline), digest(data)):
                record = next((r for r in self.records if r["task_id"] == task["id"] and r["candidate_sha256"] == sha and not r["repeat"]), None)
                if record and hasattr(self.judge, "audit") and not self.judge.audit(packet(task, record))["agrees"]:
                    out.add((task["id"], sha))
        return out

    def decide(self, data):
        sha = digest(data)
        disputed = self.disputed(data)
        held = {}
        for split, items in (("validation", self.validation), ("sealed", self.sealed)):
            ids = [t["id"] for t in items]
            base = [r for r in self.records if r["candidate_sha256"] == digest(self.baseline) and r["task_id"] in ids]
            final = [r for r in self.records if r["candidate_sha256"] == sha and r["task_id"] in ids]
            held[split] = dict(gates.compare(base, final, ids, disputed), critical_defects=gates.critical_defects(final))
        self.save(final_gates=held, disputed=sorted(map(list, disputed)))
        accepted = all(g["passed"] and not g["critical_defects"] for g in held.values())
        tasks = self.validation + self.sealed
        review_packet(self.directory, "final", tasks, [r for r in self.records if r["candidate_sha256"] == digest(self.baseline)],
                      [r for r in self.records if r["candidate_sha256"] == sha])
        if not accepted:
            raise Terminal("no_supported_improvement", "Validation and sealed evidence, including repeats and audits, do not support acceptance")
        raise Terminal("recommendation_pending_final_review", "Automated gates pass; a named reviewer must accept the blinded final packet")


def report(directory, state, ledger, config=None):
    """Terminal comparison, costs, failures, variability, configuration and loaded-instruction evidence."""
    records = results(directory)
    names = {digest(SKILL): "baseline"}
    for p in sorted(directory.glob("candidate-*.md")):
        names[digest(p)] = p.stem
        diff = difflib.unified_diff(SKILL.read_text().splitlines(True), p.read_text().splitlines(True), "baseline/SKILL.md", p.stem + "/SKILL.md")
        (directory / (p.stem + ".unapproved.diff")).write_text("".join(diff))
    label = lambda sha: names.get(sha, sha[:12])
    rows = ["# Scenario authoring optimization v2", "", "Status: **%s**" % state.get("status"), "", "Reason: " + str(state.get("reason", "")), "",
            "72 synthetic tasks (training 36, validation 12, sealed 24) against the isolated real backend and its real generator. "
            "Paired cases within a pack are correlated; 12 sealed packs do not estimate production failure rates.", ""]
    rows += ["## Gates", ""]
    for name in ("validation", "final_gates"):
        if state.get(name):
            rows += ["- %s: `%s`" % (name, {k: v for k, v in state[name].items() if k not in ("baseline", "candidate")} if name == "validation"
                                       else {s: {k: g[k] for k in ("passed", "worst_case_gain", "regressions", "critical_defects")} for s, g in state[name].items()})]
    rows += ["- Finalist: %s; proposal attempts: %s" % (state.get("finalist"), state.get("attempts", [])), ""]
    rows += ["## Outcomes by family", "", "| Revision | Split | Family | Passed / trials | Unresolved | Authoring failures | Generator failures |", "|---|---|---|---:|---:|---:|---:|"]
    for sha, split_name, family in sorted({(r["candidate_sha256"], r["split"], r["family"]) for r in records}):
        group = [r for r in records if (r["candidate_sha256"], r["split"], r["family"]) == (sha, split_name, family)]
        attribution = [v for r in group for v in r["grade"].get("attribution", {}).values()]
        rows.append("| %s | %s | %s | %d / %d | %d | %d | %d |" % (label(sha), split_name, family, sum(r["grade"]["score"] for r in group), len(group),
                    sum(r["grade"].get("semantic_status") == "uncertain" for r in group), attribution.count("authoring"), attribution.count("backend")))
    rows += ["", "## Variability", ""]
    for sha in sorted({r["candidate_sha256"] for r in records}):
        ids = sorted({r["task_id"] for r in records if r["candidate_sha256"] == sha and r["repeat"]})
        mine = [r for r in records if r["candidate_sha256"] == sha]
        rows.append("- %s: repeated %s; disagreeing %s" % (label(sha), ids, gates.unstable(mine, ids)))
    rows += ["", "## Costs", ""]
    with ledger.transaction():
        entries = list(ledger.state["entries"].values())
    for category, group in (("Historical carry", [e for e in entries if e.get("entry_type") == "carried_balance"]),
                            ("Target model requests", [e for e in entries if e.get("entry_type") == "request"]),
                            ("Generator requests and probes", [e for e in entries if e.get("entry_type") == "generator_request"]),
                            ("Sandbox reservations (pending billing)", [e for e in entries if e.get("infrastructure_only")]),
                            ("Claude incremental", [e for e in entries if e.get("entry_type") == "claude_session"])):
        rows.append("- %s: $%s (%d entries)" % (category, sum((Decimal(e["charged"]) for e in group), Decimal(0)), len(group)))
    rows.append("- Cumulative charged and reserved: $%s of $150." % ledger.total())
    for role in ("judge", "proposal"):
        usage = [read(p) for p in (directory / (role + "-sessions")).glob("*.usage.json")]
        rows.append("- Claude %s sessions: %d; nominal API equivalent $%.4f (not spend)." % (role, len(usage), sum(float(u.get("nominal_api_equivalent_usd") or 0) for u in usage)))
    rows += ["", "## Loaded instruction evidence", ""]
    for sha in sorted({r["candidate_sha256"] for r in records}):
        group = [r.get("delivery", {}) for r in records if r["candidate_sha256"] == sha]
        rows.append("- %s: full loader content observed in %d / %d trials; edited hunks never observed in tool results: %d" % (
            label(sha), sum(bool(d.get("full_loader_content_observed")) for d in group), len(group), sum(d.get("unreceived_hunks", 0) for d in group)))
    rows += ["", "## Failures", ""]
    for r in records:
        if r["grade"]["failed_checks"]:
            rows.append("- %s / %s / trial %s: %s" % (label(r["candidate_sha256"]), r["task_id"], r["repeat"],
                        ", ".join("%s [%s]" % (c, r["grade"].get("attribution", {}).get(c, "authoring")) for c in r["grade"]["failed_checks"])))
    rows += ["", "## Configuration and limitations", "",
             "- Identity: `%s`" % digest(state.get("identity")),
             "- Generator: pinned backend 650297f with a recorded transport-only instrumentation deviation; the MCP layer is a reconstruction from the pinned OpenAPI operations.",
             "- The full-stack concurrency drill was not completed by decision; stage-cap enforcement rests on the cross-process wallet and threaded metering tests.",
             "- Voice execution remains deferred. Nothing is deployed, published or committed; candidate diffs are `.unapproved.diff`."]
    (directory / "comparison.md").write_text("\n".join(rows) + "\n")
    write(directory / "suggestions.json", {"status": state.get("status"), "finalist": state.get("finalist"), "approved": False,
                                          "recommendation": state.get("status") == "recommendation_pending_final_review",
                                          "reason": state.get("reason"), "candidates": state.get("candidates", [])})

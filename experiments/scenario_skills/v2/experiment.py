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
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
from .budget import CLAUDE_SESSION_RESERVATION, COST_DISCOVERY_CAP, MARGIN, admit, headroom, minimum_plan, open_ledger, trial_cost
from .dataset import load as load_v2, canaries as canaries_v2
from .evaluator import results
from .judge import ClaudeJudge, packet
from .pool import Pool
from .proposer import PoolProposer, Proposer, screen
from .review import gate, prepare

DEADLINE_SECONDS = 24 * 3600
MAX_ATTEMPTS, MAX_EVALUATED = 4, 2
REPEATS = {"validation": ("variables-3", "lifecycle-3", "triggers-3"), "sealed": ("verbatim-4", "sources-4", "causal-4")}
MAX_DIAGNOSTICS = 12
# v3: every held-out task runs twice per arm; a task counts only when both trials agree.
V3_MIN_GAIN = {"validation": 2, "sealed": 3}


def benchmark(config):
    """(load, canaries) for the configured benchmark; v2 stays the default and unchanged."""
    if config.get("benchmark_version", 2) == 3:
        from ..v3.dataset import canaries as canaries_v3, load as load_v3
        return load_v3, canaries_v3
    return load_v2, canaries_v2


def skill_not_loaded(record):
    """An inconclusive rollout in which the assistant never loaded the skill under test."""
    if record.get("status") != "inconclusive":
        return False
    loaded = any(e.get("type") == "skill_file_read" for e in record.get("events", []))
    loaded = loaded or any(c.get("name", "").endswith("cekura_load_skill") and not c.get("response", {}).get("isError")
                           for c in record.get("trace", []))
    return not loaded


class Terminal(Exception):
    """An ordinary, reportable end of the experiment (not an error)."""
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status


def identity(config):
    return {"config_sha256": digest({k: v for k, v in config.items() if k != "budget_policy"}), "tasks_sha256": digest(benchmark(config)[0]()),
            "baseline_sha256": digest(SKILL), "materials": manifest(material()),
            "fixed_skills": {str(p.relative_to(REPO)): digest(p) for p in (REPO / "cekura/skills").rglob("*") if p.is_file()},
            "code": {str(p.relative_to(ROOT)): digest(p) for p in ROOT.rglob("*.py") if "tests" not in p.parts}}


def launch_gate(directory, ident, ceiling="150"):
    """Approval bound to this identity and to the wallet ceiling it was given under."""
    path = directory / "launch-approval.json"
    if not path.exists():
        return False
    value = read(path)
    return bool(value.get("reviewer")) and value.get("approved") is True and value.get("identity_sha256") == digest(ident) and value.get("ceiling_usd") == ceiling


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
        self.version = config.get("benchmark_version", 2)
        self.tasks, self.canaries = benchmark(config)[0](), benchmark(config)[1]
        self.training, self.validation, self.sealed = [[t for t in self.tasks if t["split"] == s] for s in ("training", "validation", "sealed")]
        self.baseline = SKILL.read_bytes()
        self.records = []
        self.lock = threading.RLock()  # Parallel trials save state from worker threads.
        self.max_evaluated = MAX_EVALUATED
        self.protocol = config.get("v3_protocol") if self.version == 3 else None
        if self.protocol:
            # Budget-sized v3: fewer templates and training domains; held-out chosen after the baseline (see _run_scoped).
            excluded = set(self.protocol.get("exclude_templates", []))
            keep = [t for t in self.tasks if t["template"] not in excluded]
            self.training = [t for t in keep if t["split"] == "training" and t["domain"] in self.protocol["training_domains"]]
            self.validation = [t for t in keep if t["split"] == "validation"]
            self.sealed = [t for t in keep if t["split"] == "sealed"]
            self.max_evaluated = int(self.protocol.get("max_evaluated", 1))
            self.canaries = lambda training: list(training)  # One training domain: the whole set is the screen.

    def save(self, **values):
        with self.lock:
            self.state.update(values)
            write(self.path, self.state)

    def run(self):
        try:
            self._run()
        except Terminal as end:
            self.save(status=end.status, reason=str(end))
        except (BudgetError, RuntimeError, ValueError, SchemaValidationError, OSError) as error:
            self.save(status="stopped", reason=type(error).__name__ + ": " + str(error))
        finally:
            self.save()
            report(self.directory, self.state, self.ledger, self.config)
        return self.state

    # --- execution helpers ----------------------------------------------------------------
    def check_deadline(self):
        if self.state.get("deadline") and self.clock() > self.state["deadline"]:
            raise Terminal("deadline_reached", "The 24-hour overall deadline passed; results so far are reported")

    def trial(self, data, task, stage, repeat=0, allow_unloaded=False):
        self.check_deadline()
        self.save(status="running", stage=stage, current_task=task["id"])
        record = self.evaluator.evaluate(data, task, repeat)
        if allow_unloaded and skill_not_loaded(record):
            return record  # The caller excludes this template: no skill change can reach it.
        if record["status"] != "complete" or record.get("cost_usd") is None:
            raise Terminal("inconclusive_execution", "%s on %s ended %s after bounded retries; incomplete evidence cannot support a comparison"
                           % (stage, task["id"], record["status"]))
        self.records.append(record)
        print({"stage": stage, "task": task["id"], "score": record["grade"]["score"], "semantic": record["grade"].get("semantic_status")}, flush=True)
        return record

    def stage(self, data, items, name, repeat=0):
        return [self.trial(data, t, name, repeat) for t in items]

    def parallel(self, jobs, hopeless=None):
        """Trials as (data, task, stage, repeat, allow_unloaded) on up to the protocol's ``workers`` threads, in job order.

        Each rollout has its own backend stack, wallet scope and cache key, so order does not change
        any result. On the first failure, queued trials are cancelled and running ones finish.
        ``hopeless(finished, outstanding)`` may end the stage early the same way; cancelled trials
        are simply absent from the returned list.
        """
        workers = max(1, min(int((self.protocol or {}).get("workers", 1)), len(jobs)))
        stop, guard, finished = threading.Event(), threading.Lock(), {}

        def start(i, job):
            # The worker decides before it returns, so it never picks up another job past the stop.
            if stop.is_set():
                return
            try:
                result = self.trial(*job)
            except BaseException:
                stop.set()  # A failed trial ends the stage: queued trials do not start.
                raise
            with guard:
                finished[i] = result
                if hopeless and hopeless(list(finished.values()), len(jobs) - len(finished)):
                    stop.set()

        pool = ThreadPoolExecutor(workers)
        futures = [pool.submit(start, i, job) for i, job in enumerate(jobs)]
        try:
            for future in futures:
                future.result()
            return [finished[i] for i in sorted(finished)]
        finally:
            pool.shutdown(wait=True, cancel_futures=True)

    def paired(self, finalist, items, name, repeat=0):
        """Paired trials; the arm order alternates task by task (and runs in parallel when configured)."""
        jobs = []
        for i, task in enumerate(items):
            for arm in (("baseline", "finalist") if i % 2 == 0 else ("finalist", "baseline")):
                jobs.append((self.baseline if arm == "baseline" else finalist, task, "%s_%s" % (name, arm), repeat, False))
        records = self.parallel(jobs)
        before = [r for r, job in zip(records, jobs) if job[0] is self.baseline]
        after = [r for r, job in zip(records, jobs) if job[0] is not self.baseline]
        return before, after

    # --- protocol -------------------------------------------------------------------------
    def _run(self):
        directory = self.directory
        if not gate(directory):
            prepare(directory)
            raise Terminal("awaiting_fixture_and_gold_human_review", "Fixture/gold domain signoff is required before any inference")
        ceiling = self.ledger.authorized_limits["total"]
        if not launch_gate(directory, self.ident, ceiling):
            write(directory / "launch-approval.template.json", {"identity_sha256": digest(self.ident), "ceiling_usd": ceiling, "reviewer": "", "approved": False})
            raise Terminal("awaiting_launch_approval", "Launch approval bound to this experiment identity is required")
        config = self.config
        if not self.skip_preflight:
            check = preflight(config)
            write(directory / "preflight.json", {k: v for k, v in check.items() if k != "configuration"})
            if not check["ready"]:
                raise Terminal("preflight_failed", "; ".join(check["failures"]))
            config = check["configuration"]
            from .smoke import smoke_passed
            if self.protocol and not smoke_passed(directory):
                raise Terminal("smoke_required", "Run `v2 smoke` on the current rollout code before any paid stage")
        if not self.state.get("deadline"):
            self.save(launched_at=self.clock(), deadline=self.clock() + DEADLINE_SECONDS)
        self.judge = self.judge or ClaudeJudge(config["judge"], directory, self.ledger)
        if not self.judge.qualified():
            self.save(stage="judge_qualification")
            if not self.judge.qualify()["passed"]:
                raise Terminal("judge_not_qualified", "The judge did not meet its qualification threshold with zero critical false passes")
        if self.evaluator is None:
            from .evaluator import Evaluator
            self.evaluator = Evaluator(config, directory, self.ledger, self.judge)
        if self.proposer is None:
            kind = PoolProposer if self.protocol and self.protocol.get("search") == "pool" else Proposer
            self.proposer = kind(config["proposer"], directory, self.ledger)
        if hasattr(self.proposer, "verify"):
            self.proposer.verify()

        if self.protocol and self.protocol.get("search") == "pool":
            return self._run_pool(config)
        if self.protocol:
            return self._run_scoped(config)
        sample = self.canaries(self.training)
        try:
            # One discovery allowance per frozen task set: a fixture correction gets a fresh $15, the wallet still caps all spend.
            with self.ledger.staged("baseline-cost-discovery" + ("-" + self.ident["tasks_sha256"][:12] if self.version == 3 else ""), COST_DISCOVERY_CAP):
                cost_sample = self.stage(self.baseline, sample, "baseline_cost_sample")
        except BudgetError as error:
            if "Stage allowance" in str(error):
                raise Terminal("cost_discovery_cap_exhausted", "The %d baseline canaries did not fit the $15 cost-discovery cap" % len(sample))
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
        if self.version == 3:
            again = self.paired(data, self.validation, "validation", repeat=1)
            val_before, val_after = val_before + again[0], val_after + again[1]
            validation = gates.compare_consistent(val_before, val_after, [t["id"] for t in self.validation], V3_MIN_GAIN["validation"])
        else:
            validation = gates.compare(val_before, val_after, [t["id"] for t in self.validation])
        self.save(validation=validation)
        if not validation["passed"]:
            raise Terminal("validation_no_supported_improvement", "Validation needs a strict worst-case gain and no regression; search ends")
        sealed_before, sealed_after = self.paired(data, self.sealed, "sealed")
        if self.version == 3:
            self.paired(data, self.sealed, "sealed", repeat=1)
        else:
            repeats = {split: self.paired(data, [t for t in self.tasks if t["id"] in names], "repeat_" + split, repeat=1)
                       for split, names in REPEATS.items()}
            self.diagnostics(data)
        self.decide(data)

    def _run_scoped(self, config):
        """Budget-sized v3 protocol, chosen after calibration showed the full comparison cannot fit the wallet.

        1. Baseline on every training task (one capped stage); its costs drive the forecast.
        2. Held-out tasks are limited to templates the baseline failed in training, a choice made on
           training data only; templates the baseline already passes cannot show a gain.
        3. Search (``search_scoped``: up to ``max_evaluated`` candidates, each screened, regression-checked
           and confirmed with adaptive repeats), optionally validation once per arm, then sealed with
           adaptive repeats (consistent gains, no consistent regression, no new critical defect).
        """
        protocol, directory = self.protocol, self.directory
        # Caps are immutable once recorded; a new attempt after harness fixes names its own stage (the wallet bounds all spend).
        stage = "v3-baseline-training-" + self.ident["tasks_sha256"][:12] + (("-" + protocol["baseline_stage_label"]) if protocol.get("baseline_stage_label") else "")
        try:
            with self.ledger.staged(stage, Decimal(str(protocol.get("baseline_cap_usd", "30")))):
                observed = self.parallel([(self.baseline, t, "baseline_training", 0, True) for t in self.training])
        except BudgetError as error:
            if "Stage allowance" in str(error):
                raise Terminal("baseline_cap_exhausted", "The baseline training stage did not fit its cap")
            raise
        # A template whose task never loads the skill cannot be changed by a skill edit: leave it out everywhere.
        unloaded = sorted({r["task_id"].split("-")[0] for r in observed if skill_not_loaded(r)})
        self.save(skill_not_loaded_templates=unloaded)
        before = [r for r in observed if not skill_not_loaded(r)]
        self.training = [t for t in self.training if t["template"] not in unloaded]
        self.validation = [t for t in self.validation if t["template"] not in unloaded]
        self.sealed = [t for t in self.sealed if t["template"] not in unloaded]
        # Generator-only failures are unresolved: a skill edit cannot move them, so they are never targets.
        failing = sorted({r["task_id"].split("-")[0] for r in before if gates.observation(r, (), True) == "fail"})
        self.save(generator_only_templates=sorted({r["task_id"].split("-")[0] for r in before
                                                   if not r["grade"]["score"] and gates.generator_only(r)}))
        if not failing:
            raise Terminal("training_saturated", "The baseline already passes every training task; there is nothing to search")
        costs = {r["task_id"].split("-")[0]: trial_cost(r) for r in before}
        if protocol.get("held_out_max_templates"):
            # Budget-limited: the cheapest failing templates, by measured training cost (training data only).
            failing = sorted(sorted(failing, key=lambda t: (costs[t], t))[:int(protocol["held_out_max_templates"])])
        self.validation = [] if protocol.get("skip_validation") else [t for t in self.validation if t["template"] in failing]
        self.sealed = [t for t in self.sealed if t["template"] in failing]
        mean = sum(costs.values(), Decimal(0)) / len(costs)
        estimate = lambda tasks: sum((costs.get(t["template"], mean) for t in tasks), Decimal(0))
        # One candidate: every training task once plus confirmation of up to all of them in both arms
        # (planned at 2x); held-out: both arms plus a confirming pair for every task (worst case 4x).
        candidate = estimate(self.training) * 2
        held_out = estimate(self.validation) * 2 + estimate(self.sealed) * 4
        plan = {"held_out_templates": failing, "training": len(self.training), "validation": len(self.validation), "sealed": len(self.sealed),
                "candidate_estimate_usd": str(candidate), "held_out_estimate_usd": str(held_out), "estimate_usd": str(candidate + held_out),
                "needed_usd": str((candidate + held_out) * MARGIN + headroom(config)), "held_out_needed_usd": str(held_out * MARGIN + headroom(config)),
                "template_costs_usd": {k: str(v) for k, v in sorted(costs.items())}}
        plan["funded"] = self.ledger.can_finish(Decimal(plan["needed_usd"]), CLAUDE_SESSION_RESERVATION)
        self.save(scoped_plan=plan)
        write(directory / "forecast.json", plan)
        if not plan["funded"]:
            raise Terminal("infeasible", "The scoped comparison ($%s with margin) does not fit the remaining authorization" % plan["needed_usd"])
        finalist = self.search_scoped(before)
        data = (directory / (finalist + ".md")).read_bytes()
        self.save(finalist=finalist)
        held = {}
        if protocol.get("skip_validation"):
            held["validation"] = {"skipped": "sealed alone decides", "passed": True}
            return self._sealed_decision(data, held, protocol)
        val_before, val_after = self.paired(data, self.validation, "validation")
        held["validation"] = dict(gates.compare(val_before, val_after, [t["id"] for t in self.validation]))
        gain = held["validation"]["worst_case_gain"]
        held["validation"]["passed"] = gain >= int(protocol.get("validation_min_gain", 1)) and not held["validation"]["regressions"]
        self.save(validation=held["validation"])
        if not held["validation"]["passed"]:
            raise Terminal("validation_no_supported_improvement", "Validation needs a strict worst-case gain and no regression; search ends")
        return self._sealed_decision(data, held, protocol)

    def adaptive(self, data, tasks, name):
        """Paired first trials, then a second pair only where it can still change the consistent verdict."""
        before, after = self.paired(data, tasks, name)
        again = set(gates.needs_repeat(before, after, [t["id"] for t in tasks], generator_unresolved=True))
        second = self.paired(data, [t for t in tasks if t["id"] in again], name, repeat=1)
        return before + second[0], after + second[1], sorted(again)

    def _sealed_decision(self, data, held, protocol):
        directory = self.directory
        before, after, repeated = self.adaptive(data, self.sealed, "sealed")
        sids = [t["id"] for t in self.sealed]
        sealed = gates.compare_consistent(before, after, sids, int(protocol.get("sealed_min_gain", 2)), self.disputed(data), generator_unresolved=True)
        held["sealed"] = dict(sealed, critical_defects=sealed["critical_regressions"], repeated=repeated)
        self.save(final_gates=held)
        review_packet(directory, "final", self.validation + self.sealed,
                      [r for r in self.records if r["candidate_sha256"] == digest(self.baseline)],
                      [r for r in self.records if r["candidate_sha256"] == digest(data)])
        if not sealed["passed"]:
            raise Terminal("no_supported_improvement", "Sealed evidence does not support acceptance")
        raise Terminal("recommendation_pending_final_review", "Automated gates pass; a named reviewer must accept the blinded final packet")

    def search_scoped(self, before):
        """Training-only search that can actually find a noisy improvement; returns the finalist's name.

        Each candidate runs first on the training tasks the baseline fails, the only place a gain can
        appear; one that passes fewer than ``training_min_gain`` of them there stops (early stop).
        Otherwise it runs on the rest of training, and only tasks whose paired first observations
        disagree (or show a new critical failure) run once more in each arm. The gate is
        ``compare_consistent`` with generator-only failures unresolved, so a gain or a regression has
        to repeat: one noisy flip neither accepts nor rejects a candidate. Every candidate's measured
        per-task wins and losses go to the next proposal, which must test a different hypothesis.
        """
        if self.state.get("finalist_frozen"):
            return self.state["finalist"]
        protocol, directory = self.protocol, self.directory
        min_gain = int(protocol.get("training_min_gain", 2))
        failing_ids = {r["task_id"] for r in before if gates.observation(r, (), True) == "fail"}
        screen_tasks = [t for t in self.training if t["id"] in failing_ids]
        rest = [t for t in self.training if t["id"] not in failing_ids]
        base_sha = digest(self.baseline)
        history, parent, best = list(before), self.baseline, 0
        evaluated, attempts = 0, []
        forbidden = forbidden_material(self.tasks)
        plan = self.state["scoped_plan"]
        for i in range(1, MAX_ATTEMPTS + 1):
            if evaluated >= self.max_evaluated:
                break
            rejected, no_change = directory / ("proposal-%d.rejected.json" % i), directory / ("proposal-%d.no-change.json" % i)
            data_path = directory / ("candidate-%d.md" % i)
            if no_change.exists():
                attempts.append({"attempt": i, "outcome": "no_change", "reason": read(no_change).get("rationale")})
                break
            if rejected.exists() and not data_path.exists():
                attempts.append(read(rejected))
                continue
            needed = (Decimal(plan["candidate_estimate_usd"]) + Decimal(plan["held_out_estimate_usd"])) * MARGIN + headroom(self.config)
            if not self.ledger.can_finish(needed, CLAUDE_SESSION_RESERVATION):
                attempts.append({"attempt": i, "outcome": "budget", "needed_usd": str(needed)})
                break
            if not data_path.exists():
                try:
                    data, rationale = self.proposer.propose(parent, history, i, forbidden, outcomes=attempts)
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
            name, sha = "candidate-%d" % i, digest(data)
            evaluated += 1
            # Early stop: cancel the rest of the screen once even passing every remaining task cannot reach the bar.
            passing = lambda records: sum(not skill_not_loaded(r) and gates.observation(r, (), True) == "pass" for r in records)
            screened = self.parallel([(data, t, name + "_screen", 0, True) for t in screen_tasks],
                                     hopeless=lambda done, left: passing(done) + left < min_gain)
            mine = [r for r in screened if not skill_not_loaded(r)]
            fixed = sorted(r["task_id"] for r in mine if gates.observation(r, (), True) == "pass")
            row = {"attempt": i, "name": name, "hypothesis": rationale.get("hypothesis"), "first_trial_fixed": fixed,
                   "skill_not_loaded": sorted(r["task_id"] for r in screened if skill_not_loaded(r))}
            if len(fixed) < min_gain:
                row.update(outcome="screen_rejected", reason="passed %d of %d baseline-failing tasks (%d run before the early stop); %d needed"
                           % (len(fixed), len(screen_tasks), len(screened), min_gain))
            else:
                checked = self.parallel([(data, t, name + "_training", 0, True) for t in rest])
                mine += [r for r in checked if not skill_not_loaded(r)]
                row["skill_not_loaded"] += sorted(r["task_id"] for r in checked if skill_not_loaded(r))
                ids = [t["id"] for t in self.training if any(r["task_id"] == t["id"] for r in mine)]
                again = gates.needs_repeat(before, mine, ids, generator_unresolved=True)
                jobs = [job for t in self.training if t["id"] in again
                        for job in ((self.baseline, t, "baseline_confirm", 1, True), (data, t, name + "_confirm", 1, True))]
                confirm = [r for r in self.parallel(jobs) if not skill_not_loaded(r)]
                mine += [r for r in confirm if r["candidate_sha256"] == sha]
                base = before + [r for r in confirm if r["candidate_sha256"] == base_sha]
                comparison = gates.compare_consistent(base, mine, ids, min_gain, generator_unresolved=True)
                row.update(outcome="evaluated", eligible=comparison["passed"], gains=comparison["gains"], regressions=comparison["regressions"],
                           critical_regressions=comparison["critical_regressions"], inconsistent=comparison["inconsistent"], repeated=sorted(again))
                item = {"name": name, "sha256": sha, "eligible": comparison["passed"], "gains": comparison["gains"],
                        "training_passes": sum(gates.observation(r, (), True) == "pass" for r in mine if not r["repeat"]),
                        "bytes": len(data), "cost_usd": str(sum((trial_cost(r) for r in mine), Decimal(0))),
                        "comparison": comparison, "hypothesis": rationale.get("hypothesis")}
                self.state["candidates"] = [c for c in self.state["candidates"] if c["name"] != name] + [item]
                if item["eligible"] and len(item["gains"]) > best:
                    parent, best = data, len(item["gains"])
            history.extend(r for r in mine if r not in history)
            summary = History(directory / "meta-history")
            if summary.next_iteration() <= i:
                summary.record(i, name, rationale.get("rationale", ""), mine)
            attempts.append(row)
            self.save(attempts=attempts)
        eligible = sorted((c for c in self.state["candidates"] if c["eligible"]),
                          key=lambda c: (-len(c["gains"]), c["bytes"], Decimal(c["cost_usd"]), c["name"]))
        self.save(attempts=attempts, finalist_frozen=True, finalist=eligible[0]["name"] if eligible else None)
        if not eligible:
            raise Terminal("no_training_candidate_qualifies", "No candidate reached %d consistent training gains without a consistent regression" % min_gain)
        return eligible[0]["name"]

    # --- pool protocol ----------------------------------------------------------------------
    def _staged(self, name, cap, what):
        """A capped stage; exhausting the cap ends the run with a named status instead of a traceback."""
        from contextlib import contextmanager

        @contextmanager
        def inner():
            try:
                with self.ledger.staged(name, Decimal(str(cap))):
                    yield
            except BudgetError as error:
                if "Stage allowance" in str(error):
                    raise Terminal(what + "_cap_exhausted", "The %s stage did not fit its $%s cap" % (what, cap))
                raise
        return inner()

    def triage(self, before, trials):
        """Per training task: the baseline's pass count, band and per-check pass rates (training data only)."""
        ids = [t["id"] for t in self.training]
        matrix = gates.check_matrix(before, ids)
        out = {}
        for i in ids:
            passes = sum(gates.observation(r, (), True) == "pass" for r in before if r["task_id"] == i)
            n = sum(r["task_id"] == i for r in before)
            band = "solid" if passes == n else ("hard" if passes == 0 else "high-variance")
            out[i] = {"passes": passes, "trials": n, "band": band, "checks": {c: round(p / k, 2) for c, (p, k) in sorted(matrix[i].items()) if k}}
        return out

    def _pool_labels(self):
        labels = {digest(self.baseline): "baseline"}
        labels.update({digest(p.read_bytes()): p.stem for p in self.directory.glob("candidate-*.md")})
        return labels

    def _pool_context(self, pool, triage, counters):
        hypotheses = [read(p) for p in sorted(self.directory.glob("candidate-*.rationale.json"))]
        return {"pool": pool.summary(), "triage": triage, "edits": counters, "hypotheses": hypotheses}

    def _confirm(self, data, name, before, ids, trials, protocol, weights, first_repeat=0):
        """All training tasks once, then paired trials where they tell most, until the gate decides or the cap is hit."""
        mine = [r for r in self.parallel([(data, t, name + "_training", first_repeat, True) for t in self.training if t["id"] in ids]) if not skill_not_loaded(r)]
        gate_ = lambda: gates.paired_delta(before, mine, ids, float(protocol.get("se_multiplier", 1.65)), float(protocol.get("regression_floor", 0.34)), weights)
        delta = gate_()
        workers = max(1, int(protocol.get("workers", 1)))
        while True:
            counts = {i: sum(r["task_id"] == i for r in mine) for i in ids}
            open_ = [i for i in gates.priority(before, mine, ids) if counts[i] < trials]
            # Decided: accepted with at least two trials everywhere it counts, or clearly not improving on two trials.
            settled = all(counts[i] >= 2 for i in ids)
            if not open_ or (settled and delta["passed"]) or (settled and (delta["gain"] or 0) <= 0):
                break
            batch = [(data, next(t for t in self.training if t["id"] == i), name + "_confirm", counts[i], True) for i in open_[:workers]]
            mine += [r for r in self.parallel(batch) if not skill_not_loaded(r)]
            delta = gate_()
        return mine, delta

    def _run_pool(self, config):
        """Pool search on per-check credit (``v3_protocol.search == "pool"``).

        1. Baseline ``trials`` times on every training task; per-task bands (``triage``) and per-check
           pass rates are the noise model.
        2. Optionally one restructure candidate (shorter, reordered), evaluated with full trials.
        3. Up to ``max_evaluated`` delta proposals from a sampled live parent: screened once on
           the tasks they target, then confirmed on all of training with trials allocated where
           they tell most, and gated by ``gates.paired_delta`` against the baseline. Every
           evaluated candidate joins the pool; non-overlapping live edits are merged periodically.
        4. The top two by training gain run once on the validation domain; the better one is the finalist.
        5. The sealed domain decides acceptance with the task-level consistent rule, then a human.
        """
        protocol, directory = self.protocol, self.directory
        trials = int(protocol.get("trials", 3))
        tag = self.ident["tasks_sha256"][:12] + (("-" + protocol["baseline_stage_label"]) if protocol.get("baseline_stage_label") else "")
        with self._staged("v3-pool-baseline-" + tag, protocol.get("baseline_cap_usd", "60"), "baseline"):
            observed = self.parallel([(self.baseline, t, "baseline_training", k, True) for k in range(trials) for t in self.training])
        unloaded = sorted({tpl for tpl in {r["task_id"].split("-")[0] for r in observed}
                           if all(skill_not_loaded(r) for r in observed if r["task_id"].split("-")[0] == tpl)})
        self.save(skill_not_loaded_templates=unloaded)
        before = [r for r in observed if not skill_not_loaded(r)]
        for name in ("training", "validation", "sealed"):
            setattr(self, name, [t for t in getattr(self, name) if t["template"] not in unloaded])
        ids = [t["id"] for t in self.training]
        triage = self.triage(before, trials)
        write(directory / "triage.json", triage)
        self.save(triage=triage)
        improvable = sorted(t for t, v in triage.items() if v["band"] != "solid" or any(r < 1 for r in v["checks"].values()))
        if not improvable:
            raise Terminal("training_saturated", "The baseline passes every training check on every trial; there is nothing to search")
        # Hard tasks count fully by default: a sparse gain is already near the gate's detection limit, and down-weighting it hides real fixes.
        weights = {i: float(protocol.get("hard_weight", 1)) for i, v in triage.items() if v["band"] == "hard"}
        costs = {}
        for r in before:
            costs.setdefault(r["task_id"].split("-")[0], []).append(trial_cost(r))
        costs = {k: sum(v, Decimal(0)) / len(v) for k, v in costs.items()}
        failing = sorted({i.split("-")[0] for i, v in triage.items() if v["band"] != "solid"}, key=lambda t: (costs[t], t))
        self.validation = [t for t in self.validation if t["template"] in failing[:int(protocol.get("validation_templates", 7))]]
        self.sealed = [t for t in self.sealed if t["template"] in failing[:int(protocol.get("held_out_max_templates", 4))]]
        caps = {k: Decimal(str(protocol.get(k + "_cap_usd", d))) for k, d in (("restructure", "50"), ("search", "140"), ("validation", "25"), ("sealed", "25"))}
        plan = {"bands": {b: sorted(i for i, v in triage.items() if v["band"] == b) for b in ("solid", "high-variance", "hard")},
                "validation_templates": sorted({t["template"] for t in self.validation}), "sealed_templates": sorted({t["template"] for t in self.sealed}),
                "caps_usd": {k: str(v) for k, v in caps.items()}, "template_costs_usd": {k: str(v) for k, v in sorted(costs.items())}}
        plan["needed_usd"] = str(sum(caps.values()) + headroom(config))
        plan["funded"] = self.ledger.can_finish(Decimal(plan["needed_usd"]), CLAUDE_SESSION_RESERVATION)
        self.save(pool_plan=plan)
        write(directory / "forecast.json", plan)
        if not plan["funded"]:
            raise Terminal("infeasible", "The pool protocol's stage caps ($%s) do not fit the remaining authorization" % plan["needed_usd"])
        if protocol.get("pause_after_triage") and not (directory / "triage-review.json").exists():
            # The bands and per-check pass rates are reviewed before the search stage is funded; the baseline is cached.
            raise Terminal("awaiting_triage_review", "Review triage.json and write triage-review.json to fund the search stage")

        forbidden = forbidden_material(self.tasks)
        pool = Pool(before, ids)
        history = list(before)
        root, root_name, counters, attempts = self.baseline, "baseline", self.state.get("edit_counters", {}), []
        if protocol.get("restructure_first"):
            path = directory / "candidate-restructure.md"
            if not path.exists() and not (directory / "proposal-restructure.no-change.json").exists():
                try:
                    self.proposer.propose_restructure(self.baseline, history, forbidden, self._pool_labels(), self._pool_context(pool, triage, counters))
                except (ValueError, SchemaValidationError) as error:
                    write(directory / "proposal-restructure.rejected.json", {"reason": str(error)})
            if path.exists():
                data = path.read_bytes()
                with self._staged("v3-pool-restructure-" + tag, caps["restructure"], "restructure"):
                    mine, delta = self._confirm(data, "candidate-restructure", before, ids, trials, protocol, weights)
                history += mine
                pool.add("candidate-restructure", data, digest(self.baseline), [], mine, delta, read(path.with_name("candidate-restructure.rationale.json")).get("hypothesis", ""))
                attempts.append({"attempt": 0, "name": "candidate-restructure", "outcome": "evaluated", "gain": delta["gain"], "se": delta["se"],
                                 "eligible": delta["passed"], "regressions": delta["regressions"], "critical_regressions": delta["critical_regressions"],
                                 "bytes": len(data)})
                if delta["passed"]:
                    root, root_name = data, "candidate-restructure"
                self.save(attempts=attempts, pool=pool.summary(), root=root_name)

        evaluated, screen_min = 0, float(protocol.get("screen_min_credit", 0))
        with self._staged("v3-pool-search-" + tag, caps["search"], "search"):
            for i in range(1, int(protocol.get("max_proposals", 12)) + 1):
                if evaluated >= self.max_evaluated:
                    break
                rejected, no_change = directory / ("proposal-%d.rejected.json" % i), directory / ("proposal-%d.no-change.json" % i)
                data_path = directory / ("candidate-%d.md" % i)
                if no_change.exists():
                    attempts.append({"attempt": i, "outcome": "no_change", "reason": read(no_change).get("rationale")})
                    break
                if rejected.exists() and not data_path.exists():
                    attempts.append(read(rejected))
                    continue
                if not data_path.exists():
                    parent_name = pool.sample_parent(random.Random(i)) or root_name  # seeded: a resumed run draws the same parent
                    parent = pool.members[parent_name]["data"] if parent_name in pool.members else root
                    try:
                        data, rationale = self.proposer.propose_edits(parent, history, i, forbidden, self._pool_labels(), self._pool_context(pool, triage, counters))
                    except (ValueError, SchemaValidationError) as error:
                        row = {"attempt": i, "outcome": "rejected", "reason": str(error), "parent": parent_name}
                        write(rejected, row)
                        attempts.append(row)
                        self.save(attempts=attempts)
                        continue
                    if data is None:
                        attempts.append({"attempt": i, "outcome": "no_change", "reason": rationale.get("rationale")})
                        break
                    write(directory / ("candidate-%d.lineage.json" % i), {"parent": parent_name, "root": root_name,
                          "edits": (pool.members[parent_name]["edits"] if parent_name in pool.members else []) + rationale["edits"]})
                data, rationale, lineage = data_path.read_bytes(), read(directory / ("candidate-%d.rationale.json" % i)), read(directory / ("candidate-%d.lineage.json" % i))
                name, parent_name = "candidate-%d" % i, lineage["parent"]
                evaluated += 1
                targeted = [t for t in self.training if t["id"] in set(rationale.get("targeted_tasks", [])) & set(improvable)] or \
                    [t for t in self.training if t["id"] in improvable][:3]
                screened = [r for r in self.parallel([(data, t, name + "_screen", 0, True) for t in targeted]) if not skill_not_loaded(r)]
                tids = [r["task_id"] for r in screened]
                parent_records = [r for r in history if r["candidate_sha256"] == (pool.members[parent_name]["sha256"] if parent_name in pool.members else digest(root))]
                mine_credit = [gates.credit(c) for c in gates.check_matrix(screened, tids).values() if c]
                parent_credit = [v for v in gates.best_trial_credit(parent_records, tids).values() if v is not None]  # its best single trial
                mine_mean = sum(mine_credit) / len(mine_credit) if mine_credit else 0
                parent_mean = sum(parent_credit) / len(parent_credit) if parent_credit else 0
                row = {"attempt": i, "name": name, "parent": parent_name, "hypothesis": rationale.get("hypothesis"), "screen_tasks": tids,
                       "screen_credit": round(mine_mean, 3), "parent_credit": round(parent_mean, 3)}
                history += screened
                if mine_mean <= parent_mean + screen_min + 1e-9:  # No movement where the edit was aimed: not worth the rest of training.
                    row.update(outcome="screen_rejected", reason="credit %.3f on its targets, parent %.3f" % (mine_mean, parent_mean))
                    pool.add(name, data, digest(root), lineage["edits"], screened, {"passed": False, "gain": None}, rationale.get("hypothesis", ""))
                else:
                    rest = [t["id"] for t in self.training if t["id"] not in tids]
                    more, _ = self._confirm(data, name, before, rest, trials, protocol, weights) if rest else ([], None)
                    mine = screened + more
                    # Extra paired trials on the screen tasks too, where they tell most.
                    mine, delta = self._top_up(data, name, before, mine, ids, trials, protocol, weights)
                    history += [r for r in mine if r not in history]
                    pool.add(name, data, digest(root), lineage["edits"], mine, delta, rationale.get("hypothesis", ""))
                    counters = self._count_edits(counters, rationale["edits"], delta, parent_records, mine, ids)
                    row.update(outcome="evaluated", eligible=delta["passed"], gain=delta["gain"], se=delta["se"], regressions=delta["regressions"],
                               critical_regressions=delta["critical_regressions"], trials=len(mine))
                attempts.append(row)
                self.save(attempts=attempts, pool=pool.summary(), edit_counters=counters)
                if evaluated % 3 == 0 and evaluated < self.max_evaluated:
                    merged = pool.merge(root, forbidden)
                    if merged:
                        mname = "candidate-merge-%d" % evaluated
                        (directory / (mname + ".md")).write_bytes(merged["data"])
                        write(directory / (mname + ".rationale.json"), {"hypothesis": "merge of " + ", ".join(merged["members"]), "edits": merged["edits"]})
                        write(directory / (mname + ".lineage.json"), {"parent": root_name, "root": root_name, "edits": merged["edits"]})
                        mine, delta = self._confirm(merged["data"], mname, before, ids, trials, protocol, weights)
                        history += mine
                        pool.add(mname, merged["data"], digest(root), merged["edits"], mine, delta, "merge of " + ", ".join(merged["members"]))
                        evaluated += 1
                        attempts.append({"attempt": i, "name": mname, "members": merged["members"], "outcome": "evaluated", "eligible": delta["passed"],
                                         "gain": delta["gain"], "se": delta["se"], "regressions": delta["regressions"]})
                        self.save(attempts=attempts, pool=pool.summary())
        eligible = [n for n in pool.ranked() if pool.members[n]["delta"].get("passed")]
        self.save(attempts=attempts, pool=pool.summary(), finalist_frozen=True)
        if not eligible:
            raise Terminal("no_training_candidate_qualifies", "No candidate's check-credit gain over the baseline cleared the noise gate without a regression")
        top = eligible[:2]
        if self.validation and len(top) > 1:
            vids = [t["id"] for t in self.validation]
            with self._staged("v3-pool-validation-" + tag, caps["validation"], "validation"):
                arms = {n: self.parallel([(pool.members[n]["data"], t, n + "_validation", 0, False) for t in self.validation]) for n in top}
                base = self.parallel([(self.baseline, t, "baseline_validation", 0, False) for t in self.validation])
            scores = {n: gates.paired_delta(base, arms[n], vids)["gain"] or 0 for n in top}
            finalist = max(top, key=lambda n: (scores[n], -pool.members[n]["bytes"]))
            self.save(validation={"selection": scores, "finalist": finalist})
        else:
            finalist = top[0]
        self.save(finalist=finalist)
        with self._staged("v3-pool-sealed-" + tag, caps["sealed"], "sealed"):
            return self._sealed_decision(pool.members[finalist]["data"], {"validation": {"selection": self.state.get("validation"), "passed": True}}, protocol)

    def _top_up(self, data, name, before, mine, ids, trials, protocol, weights):
        """Paired trials where they tell most until the gate decides or every task has ``trials``."""
        gate_ = lambda m: gates.paired_delta(before, m, ids, float(protocol.get("se_multiplier", 1.65)), float(protocol.get("regression_floor", 0.34)), weights)
        delta = gate_(mine)
        workers = max(1, int(protocol.get("workers", 1)))
        while True:
            counts = {i: sum(r["task_id"] == i for r in mine) for i in ids}
            open_ = [i for i in gates.priority(before, mine, ids) if counts[i] < trials]
            settled = all(counts[i] >= 2 for i in ids)
            if not open_ or (settled and delta["passed"]) or (settled and (delta["gain"] or 0) <= 0):
                return mine, delta
            batch = [(data, next(t for t in self.training if t["id"] == i), name + "_confirm", counts[i], True) for i in open_[:workers]]
            mine = mine + [r for r in self.parallel(batch) if not skill_not_loaded(r)]
            delta = gate_(mine)

    @staticmethod
    def _count_edits(counters, edits, delta, parent_records, mine, ids):
        """Per edit: checks it targeted that rose against the parent (helped) and checks that fell (hurt)."""
        counters = {k: dict(v) for k, v in counters.items()}
        parent, now = gates.check_matrix(parent_records, ids), gates.check_matrix(mine, ids)
        rose, fell = set(), set()
        for i in ids:
            for c, (p, n) in now[i].items():
                if c in parent[i] and parent[i][c][1] and n:
                    diff = p / n - parent[i][c][0] / parent[i][c][1]
                    (rose if diff > 1e-9 else fell if diff < -1e-9 else set()).add(c)
        for e in edits:
            cell = counters.setdefault(e["id"], {"helped": 0, "hurt": 0, "targets": e.get("targets", []), "reason": e.get("reason", "")})
            cell["helped"] += len(set(e.get("targets", [])) & rose)
            cell["hurt"] += len(fell)
        return counters

    def repeat_tasks(self):
        if self.protocol:
            return self.sealed  # Sealed runs twice per arm; validation once.
        if self.version == 3:
            return self.validation + self.sealed
        return [t for t in self.tasks if t["id"] in REPEATS["validation"] + REPEATS["sealed"]]

    def search(self, before, config):
        """Training-only proposal loop; returns the single frozen finalist's name."""
        if self.state.get("finalist_frozen"):
            return self.state["finalist"]
        directory, ids = self.directory, [t["id"] for t in self.training]
        sample = self.canaries(self.training)
        history, parent, parent_passes = list(before), self.baseline, gates.passes(before, ids)
        evaluated, zero_gain, attempts = 0, 0, []
        forbidden = forbidden_material(self.tasks)
        for i in range(1, MAX_ATTEMPTS + 1):
            if evaluated >= self.max_evaluated or zero_gain >= 2 or parent_passes == len(ids):
                break
            rejected, no_change = directory / ("proposal-%d.rejected.json" % i), directory / ("proposal-%d.no-change.json" % i)
            data_path = directory / ("candidate-%d.md" % i)
            if no_change.exists():
                attempts.append({"attempt": i, "outcome": "no_change", "reason": read(no_change).get("rationale")})
                break
            if rejected.exists():
                attempts.append(read(rejected))
                continue
            if self.protocol:
                # Same per-template measured forecast that funded the scoped run; family maxima would over-reserve.
                needed = Decimal(self.state["scoped_plan"]["needed_usd"])
                funded = self.ledger.can_finish(needed, CLAUDE_SESSION_RESERVATION)
            else:
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
            if self.version == 3:
                gate_ = gates.compare_consistent(base, final, ids, V3_MIN_GAIN[split], disputed)
                held[split] = dict(gate_, critical_defects=gate_["critical_regressions"])
            else:
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
                                       else {s: {k: g.get(k) for k in ("passed", "worst_case_gain", "gains", "regressions", "critical_defects")} for s, g in state[name].items()})]
    rows += ["- Finalist: %s; proposal attempts: %s" % (state.get("finalist"), state.get("attempts", [])), ""]
    if state.get("pool"):
        rows += ["", "## Pool (per-check credit against the baseline)", "", "| Candidate | Gain | Accepted | Cells led | Edits | Hypothesis |", "|---|---:|---|---:|---|---|"]
        for name, m in sorted(state["pool"].items()):
            rows.append("| %s | %s | %s | %d | %s | %s |" % (name, m.get("gain"), m.get("passed"), m.get("cells_led", 0), ", ".join(m.get("edits", [])),
                                                        str(m.get("hypothesis", ""))[:160].replace("|", "/")))
        if state.get("triage"):
            bands = {}
            for task, v in state["triage"].items():
                bands.setdefault(v["band"], []).append(task)
            rows += ["", "Triage bands: " + "; ".join("%s %s" % (b, sorted(t)) for b, t in sorted(bands.items())), ""]
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
    rows.append("- Cumulative charged and reserved: $%s of $%s." % (ledger.total(), ledger.authorized_limits["total"]))
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

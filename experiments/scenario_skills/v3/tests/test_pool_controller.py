"""The pool protocol through the real controller with a per-check scripted evaluator and proposer (no inference)."""
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from experiments.scenario_skills.common import digest, read, write
from experiments.scenario_skills.skill import SKILL, apply_edits, split
from experiments.scenario_skills.tests.helpers import cumulative_ledger
from experiments.scenario_skills.v2.experiment import identity, run
from experiments.scenario_skills.v2.review import prepare
from experiments.scenario_skills.v2.tests.test_controller import Judge

BASELINE = SKILL.read_bytes()
HEADINGS = [l for l in split(BASELINE)[1].decode().splitlines() if l.startswith("## ")]
FAILING = {"T03", "T05", "T10", "T14"}
PROTOCOL = {"exclude_templates": ["T06", "C02"], "training_domains": ["harborview"], "search": "pool", "trials": 3, "max_evaluated": 1,
            "baseline_cap_usd": "30", "search_cap_usd": "30", "validation_cap_usd": "10", "sealed_cap_usd": "10", "sealed_min_gain": 2,
            "validation_templates": 3, "held_out_max_templates": 3, "workers": 2}


class Evaluator:
    """Four checks per task. The baseline fails ``a`` on FAILING templates; ``b`` flips on one baseline trial of T05.

    A revision (``(revision N)`` in its body) fixes ``a`` on ``fixes[N]`` (default: all FAILING), fails ``c``
    on ``regress`` templates every trial, and fails ``b`` on ``flaky`` templates on its first trial only.
    """
    def __init__(self, cost=.01, regress=(), flaky=(), fixes=None, unloaded=()):
        self.cost, self.regress, self.flaky, self.fixes, self.unloaded = cost, set(regress), set(flaky), fixes or {}, set(unloaded)
        self.cache, self.calls = {}, []

    def evaluate(self, data, task, repeat=0):
        key = (digest(data), task["id"], repeat)
        if key not in self.cache:
            self.calls.append((data == BASELINE, task["split"], task["template"], repeat))
            revisions = [int(x) for x in re.findall(rb"\(revision (\d+)\)", data)]
            tpl = task["template"]
            checks = {"a": True, "b": True, "c": True, "scope": True}
            if tpl in FAILING:
                checks["a"] = any(tpl in self.fixes.get(n, FAILING) for n in revisions)
            if data == BASELINE and tpl == "T05" and repeat == 1:
                checks["b"] = False
            if revisions and tpl in self.regress:
                checks["c"] = False
            if revisions and tpl in self.flaky and repeat == 0:
                checks["b"] = False
            failed = [c for c, v in checks.items() if not v]
            self.cache[key] = {"candidate_sha256": digest(data), "task_id": task["id"], "split": task["split"], "family": task["family"],
                               "repeat": repeat, "status": "complete", "cost_usd": self.cost, "generator_cost_usd": 0, "infrastructure_reserved_usd": 0,
                               "grade": {"score": int(not failed), "checks": checks, "failed_checks": failed, "critical_failed": [], "semantic_status": "judged",
                                         "attribution": {c: "authoring" for c in failed}},
                               "messages": ["Saved"], "trace": [], "initial_state": {}, "final_state": {}, "user_turns": [],
                               "candidate_body": split(data)[1].decode()}
            if tpl in self.unloaded:
                self.cache[key].update(status="inconclusive", events=[], trace=[])
        return self.cache[key]


class Proposer:
    """Scripted deltas: proposal N edits heading N with a '(revision N)' marker; the restructure (if asked) is a no-change."""
    def __init__(self, directory, restructure=False):
        self.directory, self.restructure, self.contexts = directory, restructure, []

    def propose_restructure(self, parent, history, forbidden, labels, context):
        assert all(r["split"] == "training" for r in history)
        if not self.restructure:
            write(self.directory / "proposal-restructure.no-change.json", {"status": "no_change", "rationale": "nothing to reorder"})
            return None, {"rationale": "nothing to reorder"}
        data = split(parent)[0] + (split(parent)[1].decode() + "\n\n(revision 9)\n").encode()
        write(self.directory / "candidate-restructure.rationale.json", {"hypothesis": "shorter"})
        (self.directory / "candidate-restructure.md").write_bytes(data)
        return data, {"hypothesis": "shorter"}

    def propose_edits(self, parent, history, i, forbidden, labels, context):
        assert all(r["split"] == "training" for r in history), "held-out evidence reached the proposer"
        self.contexts.append(context)
        anchor = HEADINGS[i]
        edits = [{"id": "c%d-1" % i, "anchor": anchor, "replacement": anchor + "\n\nRule (revision %d)." % i, "reason": "r",
                  "targets": ["a"], "may_break": ["c"]}]
        data = split(parent)[0] + apply_edits(parent, edits).encode()
        value = {"status": "candidate", "hypothesis": "hypothesis %d" % i, "rationale": "r", "edits": edits,
                 "targeted_tasks": sorted(t for t in context["triage"] if context["triage"][t]["band"] != "solid")[:3]}
        write(self.directory / ("candidate-%d.rationale.json" % i), value)
        (self.directory / ("candidate-%d.md" % i)).write_bytes(data)
        return data, value


class PoolController(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="cekura-v3-pool-")
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name) / "run"
        self.directory.mkdir()
        ledger = cumulative_ledger(self, Path(temp.name), "29.13728485")
        self.config = {"budget_ledger_path": str(ledger.path), "budget_policy": ledger.policy, "benchmark_version": 3, "max_repeats": 72,
                       "v3_protocol": dict(PROTOCOL),
                       "target": {"rates": {"input_per_million": 4.5, "cached_input_per_million": .45, "output_per_million": 22.5},
                                  "admission": {"input_token_limit": 1048576, "output_token_limit": 32000}},
                       "backend": {"generator": {"endpoints": []}}}
        prepare(self.directory, 3)
        signoff = read(self.directory / "fixture-and-gold-signoff.template.json")
        signoff.update(reviewer="Test human", domain_signoff=True, fixture_expectations_approved=True)
        write(self.directory / "fixture-and-gold-signoff.json", signoff)

    def go(self, evaluator, restructure=False, **protocol):
        self.config["v3_protocol"] = dict(PROTOCOL, **protocol)
        write(self.directory / "launch-approval.json", {"reviewer": "Test human", "approved": True, "ceiling_usd": "150",
                                                       "identity_sha256": digest(identity(self.config))})
        self.evaluator, self.proposer = evaluator, Proposer(self.directory, restructure)
        return run(self.config, self.directory, evaluator=evaluator, proposer=self.proposer, judge=Judge(), skip_preflight=True)

    def test_a_candidate_that_fixes_a_check_everywhere_qualifies_and_reaches_sealed(self):
        state = self.go(Evaluator())
        self.assertEqual(state["status"], "recommendation_pending_final_review", state.get("reason"))
        calls = Counter((b, s, r) for b, s, _, r in self.evaluator.calls)
        self.assertEqual((calls[(True, "training", 0)], calls[(True, "training", 1)], calls[(True, "training", 2)]), (16, 16, 16))
        bands = state["pool_plan"]["bands"]
        self.assertEqual(sorted(bands["hard"]), sorted("%s-harborview" % t for t in FAILING))
        self.assertEqual(bands["high-variance"], ["T05-harborview"] if "T05" not in FAILING else [])
        row = next(a for a in state["attempts"] if a.get("name") == "candidate-1")
        self.assertTrue(row["eligible"])
        self.assertGreater(row["gain"], 0)
        self.assertEqual(row["regressions"], [])
        self.assertEqual(state["finalist"], "candidate-1")
        self.assertEqual(state["final_gates"]["sealed"]["gains"], sorted("%s-kestrel" % t for t in sorted(FAILING)[:3]))
        self.assertTrue(self.proposer.contexts[0]["triage"])
        # The proposer saw the pool (empty at the first proposal) and the triage, and no held-out data.
        self.assertEqual(self.proposer.contexts[0]["pool"], {})

    def test_a_regression_or_a_fix_that_never_shows_does_not_qualify(self):
        state = self.go(Evaluator(regress={"T01", "T02", "T04"}))
        self.assertEqual(state["status"], "no_training_candidate_qualifies")
        row = next(a for a in state["attempts"] if a.get("name") == "candidate-1")
        self.assertFalse(row["eligible"])
        self.assertIn(["T01-harborview", "c"], [list(r) for r in row["regressions"]])
        self.assertFalse(any(s in ("validation", "sealed") for _, s, _, _ in self.evaluator.calls))

    def test_a_single_flaky_trial_is_tolerated(self):
        state = self.go(Evaluator(flaky={"T01", "T08"}))
        self.assertEqual(state["status"], "recommendation_pending_final_review", state.get("reason"))
        row = next(a for a in state["attempts"] if a.get("name") == "candidate-1")
        self.assertEqual(row["regressions"], [])

    def test_a_candidate_with_no_gain_on_its_targets_stops_at_the_screen_and_stays_in_the_pool(self):
        state = self.go(Evaluator(fixes={1: set()}))
        self.assertEqual(state["status"], "no_training_candidate_qualifies")
        row = next(a for a in state["attempts"] if a.get("name") == "candidate-1")
        self.assertEqual(row["outcome"], "screen_rejected")
        self.assertIn("candidate-1", state["pool"])
        self.assertLessEqual(sum(1 for b, s, _, _ in self.evaluator.calls if not b), 3)

    def test_partial_fixes_from_different_candidates_are_merged_and_selected_on_validation(self):
        # Each proposal fixes one more template; none alone clears the gate, but lineage and the merge compound them.
        fixes = {1: {"T03"}, 2: {"T05"}, 3: {"T10"}, 4: set(), 5: set()}
        state = self.go(Evaluator(fixes=fixes), max_evaluated=5)
        self.assertEqual(state["status"], "recommendation_pending_final_review", state.get("reason"))
        rows = {a.get("name"): a for a in state["attempts"]}
        self.assertFalse(rows["candidate-1"]["eligible"])  # one task's check: inside the noise on its own
        self.assertIn("candidate-merge-3", rows)
        self.assertEqual(sorted(rows["candidate-merge-3"]["members"]), ["candidate-1", "candidate-2", "candidate-3"])
        self.assertTrue(rows["candidate-merge-3"]["eligible"])
        self.assertIn(state["finalist"], ("candidate-3", "candidate-merge-3"))
        # Proposals built on sampled live parents, so candidate-3 carries three edits of its own lineage.
        lineage = read(self.directory / "candidate-3.lineage.json")
        self.assertGreaterEqual(len(lineage["edits"]), 2)
        self.assertIn("selection", state["validation"])
        self.assertTrue(any(s == "validation" for _, s, _, _ in self.evaluator.calls))
        self.assertTrue(self.proposer.contexts[-1]["pool"])  # later proposals saw the pool and the edit counters
        self.assertTrue(state["edit_counters"]["c1-1"]["helped"] >= 1)

    def test_the_run_pauses_after_triage_when_asked_and_resumes_from_the_cached_baseline(self):
        state = self.go(Evaluator(), pause_after_triage=True)
        self.assertEqual(state["status"], "awaiting_triage_review")
        self.assertTrue((self.directory / "triage.json").exists())
        baseline_calls = len(self.evaluator.calls)
        write(self.directory / "triage-review.json", {"reviewer": "Test human", "approved": True})
        state = run(self.config, self.directory, evaluator=self.evaluator, proposer=self.proposer, judge=Judge(), skip_preflight=True)
        self.assertEqual(state["status"], "recommendation_pending_final_review", state.get("reason"))
        self.assertEqual(sum(1 for b, s, _, _ in self.evaluator.calls[baseline_calls:] if b and s == "training"), 0)

    def test_a_restructure_that_qualifies_becomes_the_root(self):
        state = self.go(Evaluator(fixes={9: FAILING, 1: set()}), restructure=True, restructure_first=True)
        self.assertEqual(state["root"], "candidate-restructure")
        self.assertEqual(state["status"], "recommendation_pending_final_review", state.get("reason"))
        self.assertEqual(state["finalist"], "candidate-restructure")


if __name__ == "__main__":
    unittest.main()

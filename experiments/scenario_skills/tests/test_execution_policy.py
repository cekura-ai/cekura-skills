"""Suggestion-only execution and explicitly authorized budget continuation."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.scenario_skills.budget import BudgetError, COMPLETION_LIMITS, Ledger, SMOKE_LIMITS
from experiments.scenario_skills.common import digest, read, write
from experiments.scenario_skills.contract_probe import identity
from experiments.scenario_skills.dataset import load
from experiments.scenario_skills.experiment import run
from experiments.scenario_skills.fixture import offline_catalog
from experiments.scenario_skills.fixture_review import engineering_gate, gate, packet
from experiments.scenario_skills.skill import SKILL


POLICY = {"initial_limits": SMOKE_LIMITS, "authorized_limits": COMPLETION_LIMITS,
          "authorization": "User authorized continuation up to $100 after initial smoke allowance"}


class BudgetPolicyTests(unittest.TestCase):
    def test_extension_preserves_charges_and_requires_same_authorization_on_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "budget.json"
            original = Ledger(path)
            original.reserve("old-infrastructure", "target", 1.2, infrastructure_only=True)
            ledger = Ledger(path, POLICY)
            ledger.reserve("first", "target", 17)
            self.assertEqual(ledger.state["limits"], SMOKE_LIMITS)
            ledger.reserve("next", "target", 5.438592)
            self.assertEqual(ledger.state["limits"], COMPLETION_LIMITS)
            self.assertEqual(float(ledger.total()), 23.638592)
            self.assertEqual(ledger.state["budget_extension"]["trigger_reservation"], "next")
            ledger.settle("next", .1)
            resumed = Ledger(path, POLICY)
            self.assertEqual(float(resumed.total()), 18.3)
            self.assertEqual(resumed.state["entries"]["old-infrastructure"]["charged"], "1.2")
            with self.assertRaises(BudgetError):
                Ledger(path)
            changed = dict(POLICY, authorization="Different authorization")
            with self.assertRaises(BudgetError):
                Ledger(path, changed)
            with self.assertRaises(BudgetError):
                resumed.reserve("over-target", "target", 77)
            with self.assertRaises(BudgetError):
                resumed.reserve("over-proposer", "proposer", 5.01)

    def test_missing_authorization_and_unknown_usage_never_expand_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "budget.json"
            with self.assertRaises(BudgetError):
                Ledger(path, dict(POLICY, authorization=""))
            with self.assertRaises(BudgetError):
                Ledger(path, dict(POLICY, authorized_limits={"total": "101", "proposer": "5", "target": "96"}))
            ledger = Ledger(path, POLICY)
            ledger.reserve("unknown", "target", 19)
            with self.assertRaises(BudgetError):
                ledger.settle("unknown", None)
            with self.assertRaises(BudgetError):
                ledger.reserve("retry", "target", 6)
            self.assertEqual(ledger.state["limits"], SMOKE_LIMITS)
            self.assertNotIn("budget_extension", ledger.state)


class ExecutionPolicyTests(unittest.TestCase):
    def test_engineering_review_does_not_fabricate_human_signoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            catalog = offline_catalog()
            write(directory / "probe.json", dict(identity(catalog), passed=True))
            cfg = {"target": {"contract_probe_path": str(directory / "probe.json"), "catalog": catalog},
                   "review_authorization": "User deferred human review until acceptance"}
            packet(directory)
            self.assertTrue(engineering_gate(directory, cfg))
            self.assertFalse(gate(directory))
            self.assertFalse(read(directory / "engineering-fixture-review.json")["human_domain_signoff"])
            probe = read(directory / "probe.json"); probe["catalog_sha256"] = "changed"; write(directory / "probe.json", probe)
            self.assertFalse(engineering_gate(directory, cfg))

    def test_full_loop_stops_with_suggestions_and_resumes_without_inference_or_acceptance(self):
        baseline = SKILL.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            catalog = offline_catalog()
            write(directory / "probe.json", dict(identity(catalog), passed=True))
            cfg = {"execution_goal": "suggestions", "fixture_review_mode": "engineering", "budget_policy": POLICY,
                   "review_authorization": "User deferred human review until acceptance",
                   "target": {"catalog": catalog, "contract_probe_path": str(directory / "probe.json")},
                   "proposer": {"adapter": "remote_claude"}}
            calls, proposals = [], []

            class ScriptedEvaluator:
                def __init__(self, config, artifacts, ledger):
                    self.artifacts = artifacts

                def evaluate(self, data, task):
                    path = self.artifacts / "rollouts" / digest([digest(data), task["id"]]) / "result.json"
                    if path.exists():
                        return read(path)
                    calls.append((digest(data), task["split"]))
                    score = int(data != baseline or task["id"] not in ("library-1", "transit-1"))
                    result = {"candidate_sha256": digest(data), "task_id": task["id"], "split": task["split"],
                              "family": task["family"], "status": "complete", "cost_usd": .01,
                              "grade": {"score": score, "failed_checks": [] if score else ["routing"]},
                              "messages": [], "trace": [], "final_state": {"scenarios": []}}
                    write(path, result)
                    return result

            class ScriptedProposer:
                def __init__(self, *args):
                    pass

                def propose(self, seed, history, iteration, forbidden):
                    self_test = all(r["split"] == "training" for r in history)
                    if not self_test:
                        raise AssertionError("Held-out evidence reached proposer")
                    proposals.append(iteration)
                    return seed + b"\nRead back persisted resources before reporting completion.\n", "Reconcile writes"

            with patch("experiments.scenario_skills.experiment.preflight", return_value={"ready": True, "configuration": cfg}), \
                 patch("experiments.scenario_skills.experiment.Evaluator", ScriptedEvaluator), \
                 patch("experiments.scenario_skills.remote_claude.ClaudeProposer", ScriptedProposer), \
                 patch("experiments.scenario_skills.experiment.human_gate", side_effect=AssertionError("Premature human gate")), \
                 patch("experiments.scenario_skills.experiment.export_patch", side_effect=AssertionError("Premature accepted patch")):
                result = run(cfg, directory / "experiment")
                self.assertEqual(result["status"], "suggestions_ready")
                self.assertEqual(result["selected"], "candidate-1")
                self.assertEqual(proposals, [1, 2])
                self.assertEqual(len(calls), 60)
                self.assertEqual(sum(s == "sealed" for _, s in calls), 6)
                self.assertTrue(all(h == digest(baseline) for h, s in calls if s == "sealed"))
                summary = read(directory / "experiment/suggestions.json")
                self.assertFalse(summary["approved"])
                self.assertTrue((directory / "experiment/candidate-1.unapproved.diff").exists())
                self.assertFalse((directory / "experiment/accepted-skill.patch").exists())
                run(cfg, directory / "experiment")
                self.assertEqual(len(calls), 60)
                self.assertEqual(proposals, [1, 2])


if __name__ == "__main__":
    unittest.main()

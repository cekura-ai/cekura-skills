"""evaluate-revision measures a skill directory as delivered; the report compares arms on credit and task gates."""
import shutil
import tempfile
import unittest
from pathlib import Path

from experiments.scenario_skills.common import digest, read, write
from experiments.scenario_skills.skill import SKILL
from experiments.scenario_skills.tests.helpers import cumulative_ledger
from experiments.scenario_skills.v2.experiment import identity
from experiments.scenario_skills.v2.release import evaluate_revision, report
from experiments.scenario_skills.v2.review import prepare
from experiments.scenario_skills.v2.tests.test_controller import Judge
from experiments.scenario_skills.v3.tests.test_pool_controller import FAILING, PROTOCOL, Evaluator


class Release(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="cekura-release-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.directory = root / "run"
        self.directory.mkdir()
        ledger = cumulative_ledger(self, root, "29.13728485")
        self.ledger = ledger
        self.config = {"budget_ledger_path": str(ledger.path), "budget_policy": ledger.policy, "benchmark_version": 3, "max_repeats": 72,
                       "v3_protocol": dict(PROTOCOL, release_sealed_templates=sorted(FAILING)[:2]),
                       "target": {"rates": {"input_per_million": 4.5, "cached_input_per_million": .45, "output_per_million": 22.5},
                                  "admission": {"input_token_limit": 1048576, "output_token_limit": 32000}, "snapshot": {"skill_max_chars": 60000}},
                       "backend": {"generator": {"endpoints": []}}}
        prepare(self.directory, 3)
        signoff = read(self.directory / "fixture-and-gold-signoff.template.json")
        signoff.update(reviewer="Test human", domain_signoff=True, fixture_expectations_approved=True)
        write(self.directory / "fixture-and-gold-signoff.json", signoff)
        write(self.directory / "launch-approval.json", {"reviewer": "Test human", "approved": True, "ceiling_usd": "150", "identity_sha256": digest(identity(self.config))})
        # Two skill directories: the baseline as it is, and a revision whose body carries a marker the scripted evaluator reads.
        self.main_dir, self.new_dir = root / "main-skill", root / "new-skill"
        for d in (self.main_dir, self.new_dir):
            shutil.copytree(SKILL.parent, d)
        (self.new_dir / "SKILL.md").write_bytes(SKILL.read_bytes() + b"\n\nRule (revision 1).\n")

    def test_two_arms_are_measured_as_delivered_and_compared(self):
        evaluator, judge = Evaluator(), Judge()
        main = evaluate_revision(self.config, self.directory, self.ledger, self.main_dir, "main", "training", 2, judge=judge, evaluator=evaluator, skip_preflight=True)
        new = evaluate_revision(self.config, self.directory, self.ledger, self.new_dir, "released", "training", 2, judge=judge, evaluator=evaluator, skip_preflight=True)
        self.assertEqual((len(main["records"]), len(new["records"])), (32, 32))
        self.assertFalse(main["truncated"])
        self.assertEqual(sum(r["score"] for r in main["records"]), 2 * (16 - len(FAILING)))
        self.assertEqual(sum(r["score"] for r in new["records"]), 32)
        # The cache key covers the installed material: the two arms never share a record.
        self.assertEqual(len({(b, s, t, r) for b, s, t, r in evaluator.calls}), 64)
        for label, d in (("main", self.main_dir), ("released", self.new_dir)):
            evaluate_revision(self.config, self.directory, self.ledger, d, label, "sealed", 2, judge=judge, evaluator=evaluator, skip_preflight=True)
        report(self.directory, reference="main")
        summary = report(self.directory, reference="main")  # a second report must ignore its own summary file
        self.assertTrue(summary["training"]["released"]["passed"])
        self.assertGreater(summary["training"]["released"]["gain"], 0)
        self.assertEqual(summary["sealed"]["released"]["consistent"]["gains"], sorted("%s-kestrel" % t for t in sorted(FAILING)[:2]))
        text = (self.directory / "release-report.md").read_text()
        self.assertIn("## training", text)
        self.assertIn("### released vs main", text)
        # A stage cap that cannot fund the trials ends with a named status, never a traceback.
        from experiments.scenario_skills.v2.experiment import Terminal

    def test_judge_sessions_are_scoped_to_their_run(self):
        from experiments.scenario_skills.v2.experiment import judge_for
        config = {"judge": {"subscription_only": True, "hard_cost_bound_verified": True}}
        judge = judge_for(config, self.directory, self.ledger)
        self.assertTrue(judge.session.namespace.startswith("run-"))
        other = judge_for(config, self.directory.parent / "other", self.ledger)
        self.assertNotEqual(judge.session.namespace, other.session.namespace)


if __name__ == "__main__":
    unittest.main()

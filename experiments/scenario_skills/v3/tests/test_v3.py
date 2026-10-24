"""Offline v3 tests: fixtures, contracts on reference sessions, follow-ups, run stub, gates and privacy scan."""
import json
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from experiments.scenario_skills.modal_runtime import sandbox_task
from experiments.scenario_skills.v2 import gates
from experiments.scenario_skills.v3 import checks, sanitize
from experiments.scenario_skills.v3.bridge import Bridge
from experiments.scenario_skills.v3.build_fixtures import make_task
from experiments.scenario_skills.v3.dataset import canaries, load
from experiments.scenario_skills.v3.domains import DOMAINS, GOLD_DOMAINS, SPLITS
from experiments.scenario_skills.v3.followups import decide
from experiments.scenario_skills.v3.grader import grade
from experiments.scenario_skills.v3.reference import evidence, initial_state
from experiments.scenario_skills.v3.templates import TEMPLATES

# Bad sessions whose defect is visible only to the semantic judge (dropped request, vague outcome, wrong topic).
SEMANTIC_ONLY = {"T05", "T14", "C02"}
TASKS = load()


def graded(task, good):
    e = evidence(task, good)
    return grade(task, e["trace"], e["initial_state"], e["final_state"], e["messages"])


class Fixtures(unittest.TestCase):
    def test_split_by_domain_with_every_template_in_every_split(self):
        self.assertEqual(Counter(t["split"] for t in TASKS), {"training": 36, "validation": 18, "sealed": 18})
        for t in TASKS:
            self.assertEqual(t["split"], SPLITS[t["domain"]])
        self.assertFalse(set(GOLD_DOMAINS) & {t["domain"] for t in TASKS})
        self.assertEqual(len(canaries(TASKS)), len(TEMPLATES))

    def test_workspaces_are_realistic(self):
        for t in TASKS:
            self.assertGreaterEqual(len(t["starting_resources"]["scenarios"]), 100)
            self.assertGreater(len(t["fixture"]["agent"]["description"]), 2500)
            self.assertTrue(any(c["critical"] for c in t["expected"]["checks"]))
            self.assertGreaterEqual(len(t["expected"]["rubric"]), 1)

    def test_requests_do_not_name_the_technique(self):
        banned = ("conditional_actions", "simulation_type", "scenario_agent", "GET", "PATCH", "dtmf", "<", "merge")
        for t in TASKS:
            for word in banned:
                if t["template"] == "C01" and word == "<":
                    continue  # The verbatim control pastes a complete script.
                self.assertIsNone(re.search(r"(?<!\w)%s(?!\w)" % re.escape(word), t["request"]), t["id"])

    def test_v3_rollouts_get_a_longer_lifetime_within_the_reservation(self):
        from experiments.scenario_skills.modal_probe import RATES
        from experiments.scenario_skills.modal_runtime import LIFETIME, V3_LIFETIME, infrastructure_bound, lifetime
        self.assertEqual((lifetime(TASKS[0]), lifetime({"benchmark_version": 2})), (V3_LIFETIME, LIFETIME))
        evidence = {"source": "https://modal.com/pricing", "verified_at": "test", "rates": RATES}
        self.assertLess(infrastructure_bound(evidence, V3_LIFETIME), 0.10)

    def test_replay_proof_is_bound_to_the_frozen_tasks_and_graders(self):
        from experiments.scenario_skills.v3.replay import REPLAYABLE, proof_hashes
        self.assertEqual(set(TEMPLATES) - set(REPLAYABLE), {"T06", "C02"})  # Only generation templates are offline-only.
        self.assertEqual(set(proof_hashes()), {"tasks_sha256", "grader_sha256", "checks_sha256", "bridge_sha256", "followups_sha256", "replay_sha256"})

    def test_sandbox_receives_only_the_opening_turn(self):
        task = sandbox_task(TASKS[0])
        self.assertEqual(set(task), {"id", "benchmark_version", "request", "documents", "context"})


class Contracts(unittest.TestCase):
    def test_correct_sessions_pass_and_failing_sessions_fail(self):
        for task in TASKS + [make_task(t, d) for d in GOLD_DOMAINS for t in TEMPLATES]:
            good, bad = graded(task, True), graded(task, False)
            self.assertEqual(good["failed_checks"], [], task["id"])
            if task["template"] not in SEMANTIC_ONLY:
                self.assertEqual(bad["score"], 0, task["id"])

    def test_critical_failures_mark_consent_and_shared_state(self):
        by_id = {t["id"]: t for t in TASKS}
        self.assertIn("confirm_large_run", graded(by_id["T09-harborview"], False)["critical_failed"])
        self.assertIn("profiles_merged", graded(by_id["T08-northwind"], False)["critical_failed"])
        self.assertIn("preview_before_write", graded(by_id["T02-solace"], False)["critical_failed"])
        self.assertIn("duplicate_owner", graded(by_id["T07-kestrel"], False)["critical_failed"])

    def test_review_edits(self):
        by_id = {t["id"]: t for t in TASKS}
        # T16: listing every test with a verdict is complete; only precision (non-critical) suffers.
        task = by_id["T16-kestrel"]
        e = evidence(task, True)
        everything = sorted(r["id"] for r in e["initial_state"]["scenarios"] if r["folder_path"] == list(DOMAINS["kestrel"]["folders"])[0])
        e["messages"][0] = "Checked: " + ", ".join(map(str, everything))
        g = grade(task, e["trace"], e["initial_state"], e["final_state"], e["messages"])
        self.assertTrue(g["checks"]["complete"])
        self.assertNotIn("precise", g["critical_failed"])
        # T08: the legacy profile also lacks a phone, so three profiles must be filled.
        phones = next(c for c in by_id["T08-solace"]["expected"]["checks"] if c["id"] == "phones_filled")["check"]["ids"]
        self.assertEqual(len(phones), 3)

    def test_unrequested_deletion_is_critical_everywhere(self):
        task = TASKS[0]
        e = evidence(task, True)
        e["final_state"]["scenarios"] = e["final_state"]["scenarios"][1:]
        g = grade(task, e["trace"], e["initial_state"], e["final_state"], e["messages"])
        self.assertIn("no_unrequested_deletion", g["critical_failed"])

    def test_count_claims_and_ids(self):
        ctx = {"initial": {"scenarios": [{"id": 200001, "a": 1}, {"id": 200002, "a": 1}]},
               "final": {"scenarios": [{"id": 200001, "a": 2}, {"id": 200002, "a": 1}]}, "trace": [], "messages": ["Updated 2 tests: 200001."]}
        self.assertFalse(checks.evaluate({"kind": "count_claims"}, ctx))
        ctx["messages"] = ["Updated 1 test: 200001."]
        self.assertTrue(checks.evaluate({"kind": "count_claims"}, ctx))
        self.assertTrue(checks.evaluate({"kind": "mentions", "ids": [200001], "forbidden": [200002]}, ctx))


class Followups(unittest.TestCase):
    def ctx(self, task, messages, trace=(), final=None):
        state = initial_state(task)
        return {"task": task, "initial": state, "final": final or state, "trace": list(trace), "messages": messages, "final_type": "assistant_complete"}

    def test_state_decides_the_next_message(self):
        task = next(t for t in TASKS if t["id"] == "T01-northwind")
        position = {"step": 0, "clarifications": 0}
        message, _ = decide(task, position, self.ctx(task, ["Done."]), 0)
        self.assertEqual(message, "I'm still seeing it in some of the tests.")  # nothing was changed
        e = evidence(task, True)
        position = {"step": 0, "clarifications": 0}
        message, _ = decide(task, position, self.ctx(task, ["Done."], final=e["final_state"]), 0)
        self.assertEqual(message, "Did that change how any of them end?")

    def test_questions_get_the_clarification_unless_the_step_answers_them(self):
        task = next(t for t in TASKS if t["template"] == "T01")
        position = {"step": 0, "clarifications": 0}
        message, decision = decide(task, position, self.ctx(task, ["Which folder?"]), 0)
        self.assertEqual((message, decision["case"], position["step"]), (task["clarification_reply"], "clarification", 0))
        consent = next(t for t in TASKS if t["template"] == "T09")
        message, decision = decide(consent, {"step": 0, "clarifications": 0}, self.ctx(consent, ["That is 120 calls. Go ahead?"]), 0)
        self.assertEqual(message, consent["followups"][0]["default"])

    def test_session_ends_after_the_last_step(self):
        task = next(t for t in TASKS if t["template"] == "C02")
        self.assertEqual(decide(task, {"step": 0, "clarifications": 0}, self.ctx(task, ["Generated 5."]), 0)[0], None)


class RunStub(unittest.TestCase):
    def bridge(self, task):
        catalog = [{"name": "scenarios_run_voice", "inputSchema": {"type": "object", "properties": {k: {} for k in
                    ("agent_id", "scenarios", "folder_path", "tags", "personality_ids", "test_profile_ids", "frequency")}}}]
        b = Bridge(task, "http://unused.invalid", {"token": "x", "conversation": "y"}, catalog, {}, {})
        state = initial_state(task)
        b.state_reader = lambda: state
        return b

    def test_runs_are_recorded_and_never_dialled(self):
        task = next(t for t in TASKS if t["template"] == "T09")
        b = self.bridge(task)
        response, _ = b.call("mcp__cekura__scenarios_run_voice", {"agent_id": task["fixture"]["agent"]["id"], "tags": ["smoke"], "frequency": 2}, 0)
        self.assertFalse(response["isError"])
        stub = b.trace[-1]["backend"]["stub_run"]
        self.assertEqual(stub["calls"], 2 * len(stub["scenarios"]))
        self.assertFalse(b.trace[-1]["backend"]["dialled"])
        self.assertEqual(json.loads(response["content"][0]["text"])["status"], "in_queue")

    def test_invalid_agent_is_rejected_like_the_api(self):
        task = TASKS[0]
        response, _ = self.bridge(task).call("mcp__cekura__scenarios_run_voice", {"agent_id": 1, "scenarios": [1]}, 0)
        self.assertTrue(response["isError"])
        self.assertIn("agent_id", response["content"][0]["text"])

    def test_unlisted_operations_stay_refused(self):
        response, _ = self.bridge(TASKS[0]).call("mcp__cekura__aiagents_destroy", {"id": 1}, 0)
        self.assertTrue(response["isError"])


class Gates(unittest.TestCase):
    def record(self, task, ok, critical=()):
        return {"task_id": task, "status": "complete", "cost_usd": 0, "candidate_sha256": "x",
                "grade": {"score": int(ok), "semantic_status": "judged", "critical_failed": list(critical)}}

    def test_only_consistent_tasks_count(self):
        ids = ["a", "b", "c", "d"]
        base = [self.record(i, False) for i in ids for _ in range(2)] + [self.record("e", True), self.record("e", True)]
        cand = [self.record(i, True) for i in ("a", "b", "c") for _ in range(2)] + [self.record("d", True), self.record("d", False),
                                                                                      self.record("e", True), self.record("e", False)]
        result = gates.compare_consistent(base, cand, ids + ["e"], min_gain=3)
        self.assertTrue(result["passed"])
        self.assertEqual(result["gains"], ["a", "b", "c"])
        self.assertEqual(result["inconsistent"], ["d", "e"])

    def test_consistent_regression_or_new_critical_blocks(self):
        base = [self.record("a", True), self.record("a", True)] + [self.record(i, False) for i in "bcd" for _ in range(2)]
        cand = [self.record("a", False), self.record("a", False)] + [self.record(i, True) for i in "bcd" for _ in range(2)]
        self.assertEqual(gates.compare_consistent(base, cand, list("abcd"), 3)["regressions"], ["a"])
        cand = [self.record("a", True, ["x"]), self.record("a", True, ["x"])] + [self.record(i, True) for i in "bcd" for _ in range(2)]
        result = gates.compare_consistent(base, cand, list("abcd"), 3)
        self.assertEqual(result["critical_regressions"], [("a", "x")])
        self.assertFalse(result["passed"])


class Privacy(unittest.TestCase):
    def test_overlap_email_phone_and_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as packet, tempfile.TemporaryDirectory() as fixtures:
            (Path(packet) / "calls").mkdir()
            (Path(packet) / "calls/1.json").write_text(json.dumps({"transcript_object": [
                {"role": "user", "content": "please move every single test from the old folder into the archive today"},
                {"role": "user", "content": "Quillon Maribeth runs our team"}]}))
            (Path(fixtures) / "packs.json").write_text(json.dumps([
                "Please move every single test from the old folder into the archive now", "write to a@b.co", "call +44 20 7946 0000",
                "ask Quillon Maribeth", "call +1 555 010 2030 fine"]))
            reasons = Counter(f["reason"] for f in sanitize.scan(packet, Path(fixtures))["findings"])
            self.assertEqual(reasons, {"8-word overlap with packet": 1, "email address": 1, "phone number outside the 555 range": 1,
                                       "proper name also present in packet": 1})


if __name__ == "__main__":
    unittest.main()

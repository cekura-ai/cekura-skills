"""Per-check credit, the paired noise gate, trial priority, anchored edits and the candidate pool."""
import random
import unittest

from experiments.scenario_skills.common import digest
from experiments.scenario_skills.skill import SKILL, apply_edits, split
from experiments.scenario_skills.v2 import gates
from experiments.scenario_skills.v2.pool import Pool

CHECKS = ("a", "b", "c", "scope")


def record(task, sha, checks, repeat=0, attribution=None):
    failed = [c for c, v in checks.items() if not v]
    return {"task_id": task, "candidate_sha256": sha, "status": "complete", "repeat": repeat, "cost_usd": 1,
            "grade": {"score": int(not failed), "checks": dict(checks), "failed_checks": failed, "attribution": attribution or {},
                      "critical_failed": [c for c in failed if c in gates.CRITICAL]}}


def arm(sha, outcomes, trials=1):
    """``outcomes``: {task: {check: pass}}; the same outcome repeated ``trials`` times."""
    return [record(t, sha, checks, repeat=k) for t, checks in outcomes.items() for k in range(trials)]


TASKS = ["T1", "T2", "T3", "T4", "T5", "T6"]
BASE = {t: {"a": False, "b": True, "c": False, "scope": True} for t in TASKS}


class PairedDelta(unittest.TestCase):
    def test_partial_fixes_count_and_a_lucky_single_flip_does_not(self):
        # Fixes "a" on every task and "c" on half, breaks nothing: credit rises on all six tasks consistently.
        better = {t: {"a": True, "b": True, "c": i % 2 == 0, "scope": True} for i, t in enumerate(TASKS)}
        result = gates.paired_delta(arm("b", BASE, 3), arm("c", better, 3), TASKS)
        self.assertTrue(result["passed"])
        self.assertGreater(result["gain"], 0.3)
        # One task flips once among three trials and nothing else moves: inside the noise.
        lucky = arm("b", BASE, 3)
        lucky = [r for r in lucky if not (r["task_id"] == "T1" and r["repeat"] == 0)] + [record("T1", "c", {"a": True, "b": True, "c": True, "scope": True})]
        noisy = [dict(r, candidate_sha256="c") for r in lucky]
        result = gates.paired_delta(arm("b", BASE, 3), noisy, TASKS)
        self.assertFalse(result["passed"])
        self.assertGreater(result["se"], 0)

    def test_fix_three_break_one_is_net_positive_but_a_regression_floor_and_critical_veto_hold(self):
        mixed = {t: {"a": True, "b": False, "c": True, "scope": True} for t in TASKS}  # fixes a and c, breaks b everywhere
        result = gates.paired_delta(arm("b", BASE, 3), arm("c", mixed, 3), TASKS)
        self.assertGreater(result["gain"], 0)
        self.assertFalse(result["passed"])  # b fell from 1.0 to 0.0 on every task: a regression, not noise
        self.assertEqual(result["regressions"][0], ("T1", "b"))
        # The same gain with b failing on only one of three trials stays within the floor.
        soft = arm("c", {t: {"a": True, "b": True, "c": True, "scope": True} for t in TASKS}, 2) + \
            [record(t, "c", {"a": True, "b": False, "c": True, "scope": True}, repeat=2) for t in TASKS]
        result = gates.paired_delta(arm("b", BASE, 3), soft, TASKS)
        self.assertTrue(result["passed"])
        self.assertEqual(result["regressions"], [])
        # A critical check the baseline never failed vetoes whatever else improved.
        critical = {t: {"a": True, "b": True, "c": True, "scope": False} for t in TASKS}
        result = gates.paired_delta(arm("b", BASE, 3), arm("c", critical, 3), TASKS)
        self.assertFalse(result["passed"])
        self.assertEqual(result["critical_regressions"][0], ("T1", "scope"))

    def test_backend_failures_are_not_trials_and_weights_apply(self):
        base = arm("b", BASE, 1)
        cand = arm("c", {t: {"a": True, "b": True, "c": False, "scope": True} for t in TASKS}, 1)
        cand[0]["grade"]["attribution"] = {"c": "backend"}
        matrix = gates.check_matrix(cand, TASKS)
        self.assertNotIn("c", matrix["T1"])
        self.assertEqual(matrix["T2"]["c"], [0, 1])
        heavy = gates.paired_delta(base, cand, TASKS, weights={"T1": 0.5})
        self.assertEqual(heavy["tasks"], 6)

    def test_priority_prefers_untried_then_disagreeing_tasks(self):
        base = arm("b", BASE, 3)
        cand = arm("c", {"T1": {"a": True, "b": True, "c": True, "scope": True}, "T2": dict(BASE["T2"])}, 1) + \
            arm("c", {"T3": dict(BASE["T3"])}, 3)
        order = gates.priority(base, cand, ["T1", "T2", "T3", "T4"])
        self.assertEqual(order[0], "T4")  # no candidate trial yet
        self.assertEqual(order[1], "T1")  # the arms differ most
        self.assertEqual(order[-1], "T3")  # agrees on three trials


class Edits(unittest.TestCase):
    def test_anchors_must_occur_once(self):
        parent = SKILL.read_bytes()
        body = split(parent)[1].decode()
        line = next(l for l in body.splitlines() if l.startswith("## "))
        out = apply_edits(parent, [{"id": "e1", "anchor": line, "replacement": line + "\n\nOne added sentence."}])
        self.assertIn("One added sentence.", out)
        with self.assertRaises(ValueError):
            apply_edits(parent, [{"id": "e2", "anchor": "the", "replacement": "x"}])
        with self.assertRaises(ValueError):
            apply_edits(parent, [{"id": "e3", "anchor": "no such text anywhere 123", "replacement": "x"}])
        with self.assertRaises(ValueError):
            apply_edits(parent, [{"id": "e4", "anchor": " ", "replacement": "x"}])


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.root = SKILL.read_bytes()
        self.body = split(self.root)[1].decode()
        self.headings = [l for l in self.body.splitlines() if l.startswith("## ")]
        self.pool = Pool(arm("b", BASE, 3), TASKS)

    def member(self, name, outcomes, heading, passed=True, gain=0.1, keep_anchor=True):
        replacement = (heading + "\n\nEdit by " + name + ".") if keep_anchor else ("## Renamed by " + name)
        edits = [{"id": name + "-e", "anchor": heading, "replacement": replacement}]
        data = self.root[:0] + split(self.root)[0] + apply_edits(self.root, edits).encode()
        self.pool.add(name, data, digest(self.root), edits, arm(name, outcomes, 3), {"passed": passed, "gain": gain})
        return data

    def test_live_members_lead_a_cell_and_parents_are_sampled_by_cells_led(self):
        fixes_a = {t: {"a": True, "b": True, "c": False, "scope": True} for t in TASKS}
        fixes_c_one = {t: {"a": False, "b": True, "c": t == "T1", "scope": True} for t in TASKS}
        nothing = {t: dict(BASE[t]) for t in TASKS}
        self.member("A", fixes_a, self.headings[0])
        self.member("C", fixes_c_one, self.headings[1], passed=False, gain=0.01)
        self.member("N", nothing, self.headings[2], passed=False, gain=0.0)
        led = self.pool.live()
        self.assertEqual((led["A"], led["C"]), (6, 1))
        self.assertNotIn("N", led)
        draws = [self.pool.sample_parent(random.Random(i)) for i in range(60)]
        self.assertGreater(draws.count("A"), draws.count("C"))
        self.assertIn("C", draws)
        self.assertEqual(self.pool.ranked()[0], "A")

    def test_merge_combines_disjoint_live_edits_once(self):
        fixes_a = {t: {"a": True, "b": True, "c": False, "scope": True} for t in TASKS}
        fixes_c = {t: {"a": False, "b": True, "c": True, "scope": True} for t in TASKS}
        self.member("A", fixes_a, self.headings[0])
        self.member("C", fixes_c, self.headings[1], keep_anchor=False)
        merged = self.pool.merge(self.root)
        self.assertEqual(sorted(merged["members"]), ["A", "C"])
        self.assertIn("Edit by A.", merged["data"].decode())
        self.assertIn("Renamed by C", merged["data"].decode())
        # A member whose anchor C's edit removed is left out; a single member is no merge.
        self.member("X", fixes_c, self.headings[1])  # anchors on the heading C renamed
        merged = self.pool.merge(self.root)
        self.assertNotIn("X", merged["members"])
        self.pool.members.pop("C"); self.pool.members.pop("X")
        self.assertIsNone(self.pool.merge(self.root))

    def test_a_member_on_another_root_is_not_merged(self):
        fixes_a = {t: {"a": True, "b": True, "c": False, "scope": True} for t in TASKS}
        self.member("A", fixes_a, self.headings[0])
        self.pool.members["A"]["root"] = "other"
        self.member("B", fixes_a, self.headings[1])
        self.assertIsNone(self.pool.merge(self.root))


if __name__ == "__main__":
    unittest.main()

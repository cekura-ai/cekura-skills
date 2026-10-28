"""The canonical $150 wallet: uniqueness, cross-process caps and replay-safe settlement."""
import multiprocessing
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from experiments.scenario_skills import budget
from experiments.scenario_skills.budget import BudgetError, Ledger, authorize, require_cumulative
from experiments.scenario_skills.common import read, write
from experiments.scenario_skills.tests.helpers import cumulative_ledger


def reserve_in_child(root, policy, key, amount, results):
    """A separate interpreter with its own Ledger instance, as a gateway process would be."""
    budget.WALLET_ROOT = Path(root)
    ledger = Ledger(budget.wallet_path(), policy)
    try:
        ledger.reserve(key, "target", amount, entry_type="request")
        results.put((key, "reserved"))
    except BudgetError as error:
        results.put((key, "denied: " + str(error)))


def run_children(root, policy, keys, amount):
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    processes = [context.Process(target=reserve_in_child, args=(str(root), policy, key, amount, results)) for key in keys]
    for process in processes:
        process.start()
    for process in processes:
        process.join(60)
    return dict(results.get(timeout=5) for _ in processes)


class WalletTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cekura-wallet-")
        self.directory = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.ledger = cumulative_ledger(self, self.directory, "29.13728485")
        self.root = budget.WALLET_ROOT

    def test_history_is_carried_once_and_only_the_canonical_wallet_funds_execution(self):
        self.assertEqual(self.ledger.total(), Decimal("29.13728485"))
        require_cumulative(self.ledger)
        source = self.directory / "historical-source.json"
        with self.assertRaises(BudgetError):
            authorize([source], "29.13728485", "Second wallet")
        # Deleting the wallet does not reopen the allowance: the journal remembers the source.
        budget.wallet_path().unlink()
        with self.assertRaises(BudgetError):
            authorize([source], "29.13728485", "Recreated wallet")
        other = self.directory / "copy.json"
        write(other, {"authorization": self.ledger.policy, "limits": budget.CUMULATIVE_LIMITS, "entries": {}, "blocked": False})
        with self.assertRaises(BudgetError):
            Ledger(other, self.ledger.policy)
        with self.assertRaises(BudgetError):
            require_cumulative(Ledger(self.directory / "old-run-budget.json"))

    def test_mismatched_history_and_changed_authorization_are_refused(self):
        with patch.object(budget, "WALLET_ROOT", self.directory / "fresh-root"):
            source = self.directory / "parent.json"
            write(source, {"blocked": False, "entries": {"x": {"kind": "target", "charged": "1", "status": "complete"}}})
            with self.assertRaises(BudgetError):
                authorize([source], "2", "Wrong history")
            write(source, {"blocked": False, "entries": {"x": {"kind": "target", "charged": "1", "status": "running"}}})
            with self.assertRaises(BudgetError):
                authorize([source], "1", "Unsettled history")
        with self.assertRaises(BudgetError):
            Ledger(budget.wallet_path(), dict(self.ledger.policy, authorization="Changed"))

    def test_concurrent_processes_cannot_exceed_the_ceiling(self):
        # The $145 target sublimit leaves $115.86271515 after history: eleven $10 reservations fit.
        outcome = run_children(self.root, self.ledger.policy, ["r%d" % i for i in range(16)], 10)
        self.assertEqual(sum(v == "reserved" for v in outcome.values()), 11)
        self.assertLessEqual(self.ledger.total("target"), Decimal("145"))

    def test_stage_cap_binds_reservations_made_by_other_processes(self):
        with self.ledger.staged("baseline-cost-discovery", 15):
            outcome = run_children(self.root, self.ledger.policy, ["s%d" % i for i in range(6)], 4)
            self.assertEqual(sum(v == "reserved" for v in outcome.values()), 3)
            self.assertTrue(all("Stage allowance" in v for v in outcome.values() if v != "reserved"))
        entries = read(budget.wallet_path())["entries"]
        self.assertEqual({e["stage"] for k, e in entries.items() if k.startswith("s")}, {"baseline-cost-discovery"})
        # After the stage ends, ordinary work proceeds; re-entering keeps the recorded cap and usage.
        self.ledger.reserve("after", "target", 4)
        with self.ledger.staged("baseline-cost-discovery", 15):
            with self.assertRaises(BudgetError):
                self.ledger.reserve("again", "target", 4)
        with self.assertRaises(BudgetError):
            with self.ledger.staged("baseline-cost-discovery", 20):
                pass

    def test_crashed_stage_stays_active_for_other_processes(self):
        state = read(budget.wallet_path())
        state.update(stage_caps={"crashed": "1"}, active_stage="crashed")
        write(budget.wallet_path(), state)
        outcome = run_children(self.root, self.ledger.policy, ["c"], 2)
        self.assertIn("Stage allowance", outcome["c"])
        with self.assertRaises(BudgetError):
            with self.ledger.staged("other", 5):
                pass

    def test_settlement_replay_is_idempotent_and_conflicts_block(self):
        self.ledger.reserve("k", "target", 1)
        self.ledger.settle("k", ".25")
        self.ledger.settle("k", "0.250")
        with self.assertRaises(BudgetError):
            self.ledger.settle("k", ".3")
        self.assertTrue(read(budget.wallet_path())["blocked"])
        with self.assertRaises(BudgetError):
            self.ledger.reserve("next", "target", 1)

    def test_unknown_usage_resolves_only_with_evidence_and_within_its_bound(self):
        self.ledger.reserve("session", "proposer", 2.5)
        with self.assertRaises(BudgetError):
            self.ledger.settle("session", None)
        proof = {"reason": "pre-inference check failed", "proof": ["no response saved"]}
        with self.assertRaises(BudgetError):
            self.ledger.resolve_unknown("session", 0, {"reason": "no proof"})
        with self.assertRaises(BudgetError):
            self.ledger.resolve_unknown("session", 3, proof)
        self.assertTrue(self.ledger.resolve_unknown("session", 0, proof))
        state = read(budget.wallet_path())
        self.assertFalse(state["blocked"])
        self.assertEqual((state["entries"]["session"]["charged"], state["entries"]["session"]["resolution"]["previous_charge"]), ("0", "2.5"))
        with self.assertRaises(BudgetError):
            self.ledger.resolve_unknown("session", 0, proof)  # Already settled: nothing to resolve.
        self.ledger.reserve("next", "target", 1)  # Execution may continue.

    def test_resolution_keeps_the_wallet_blocked_while_another_entry_is_unknown(self):
        for key in ("a", "b"):
            self.ledger.reserve(key, "proposer", 1)
        for key in ("a", "b"):
            with self.assertRaises(BudgetError):
                self.ledger.settle(key, None)
        self.assertFalse(self.ledger.resolve_unknown("a", 0, {"reason": "r", "proof": ["p"]}))
        self.assertTrue(read(budget.wallet_path())["blocked"])

    def test_one_recorded_extension_raises_the_ceiling_and_keeps_every_charge(self):
        self.ledger.reserve("spent", "target", 100)
        self.ledger.settle("spent", 100)
        with self.assertRaises(BudgetError):
            self.ledger.reserve("over", "target", 30)  # 129 + 30 > 150.
        with self.assertRaises(BudgetError):
            budget.extend("")
        extension = budget.extend("User raised the cap to $300")
        self.assertEqual(extension["charged_at_extension_usd"], "129.13728485")
        ledger = Ledger(budget.wallet_path(), self.ledger.policy)
        self.assertEqual((ledger.total(), ledger.authorized_limits["total"]), (Decimal("129.13728485"), "300"))
        ledger.reserve("next", "target", 30)
        with self.assertRaises(BudgetError):
            budget.extend("Again")  # The same ceiling again is not a raise.
        with self.assertRaises(BudgetError):
            budget.extend("Lower", 200)
        with self.assertRaises(BudgetError):
            budget.extend("Fractional", "550.5")
        # A second recorded raise follows from the first and keeps every charge.
        second = budget.extend("User raised the cap to $550 for the repaired-benchmark search", 550)
        self.assertEqual((second["from_limits"]["total"], second["limits"]), ("300", {"proposer": "5", "target": "545", "total": "550"}))
        ledger = Ledger(budget.wallet_path(), self.ledger.policy)
        self.assertEqual((ledger.total(), ledger.authorized_limits["total"]), (Decimal("159.13728485"), "550"))
        ledger.reserve("more", "target", 300)
        # A hand edit of a recorded raise is refused, whichever raise is edited.
        state = read(budget.wallet_path())
        state["extensions"][0]["limits"] = {"proposer": "5", "target": "995", "total": "1000"}
        write(budget.wallet_path(), state)
        with self.assertRaises(BudgetError):
            Ledger(budget.wallet_path(), self.ledger.policy)
        state["extensions"][0]["limits"] = second["limits"]
        state["extension"]["limits"] = {"proposer": "5", "target": "395", "total": "400"}
        write(budget.wallet_path(), state)
        with self.assertRaises(BudgetError):
            Ledger(budget.wallet_path(), self.ledger.policy)


if __name__ == "__main__":
    unittest.main()

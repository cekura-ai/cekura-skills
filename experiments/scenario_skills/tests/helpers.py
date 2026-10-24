"""Offline cumulative-wallet fixtures; tests never reconcile real historical spend."""
from pathlib import Path
from unittest.mock import patch

from experiments.scenario_skills import budget
from experiments.scenario_skills.budget import Ledger, authorize
from experiments.scenario_skills.common import write


def cumulative_ledger(test, directory, historical="0"):
    """A canonical wallet under a per-test root; the patch is undone when the test ends."""
    directory = Path(directory)
    patcher = patch.object(budget, "WALLET_ROOT", directory / "wallet-root")
    patcher.start()
    test.addCleanup(patcher.stop)
    source = directory / "historical-source.json"
    write(source, {"blocked": False, "entries": {"prior": {"kind": "target", "reserved": historical,
                                                          "charged": historical, "status": "complete"}}})
    policy = authorize([source], historical, "Offline test authorization")
    return Ledger(budget.wallet_path(), policy)

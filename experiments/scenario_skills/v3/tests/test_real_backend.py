"""v3 against the pinned backend with no inference (see ``v3/replay.py``).

Each rollout boots the full isolated stack, so this runs only with CEKURA_BACKEND_INTEGRATION=1.
"""
import json
import os
import unittest
from pathlib import Path

from experiments.scenario_skills.v3.replay import REPLAYABLE, replay

CATALOG = Path.home() / "projects/cekura-skills-experiment-20261023/private/evidence/private/tmp/cekura-runtime-image-2026-10-22/codex-catalog/catalog.json"
INFRA = Path.home() / "cekura-drill/run"
REPLAYED = os.environ.get("CEKURA_V3_REPLAY", ",".join(REPLAYABLE)).split(",")


@unittest.skipUnless(os.environ.get("CEKURA_BACKEND_INTEGRATION") == "1" and CATALOG.exists(), "Boots the isolated real backend")
class ReplayAgainstRealBackend(unittest.TestCase):
    def test_reference_sessions_pass_on_stored_backend_state(self):
        report = replay(INFRA, CATALOG, os.environ.get("CEKURA_V3_DOMAIN", "harborview"), REPLAYED)
        if os.environ.get("CEKURA_V3_REPORT"):
            Path(os.environ["CEKURA_V3_REPORT"]).write_text(json.dumps(report, indent=1))
        self.assertEqual({k: (v["status"], v["failed"]) for k, v in report.items()}, {k: ("complete", []) for k in report})


if __name__ == "__main__":
    unittest.main()

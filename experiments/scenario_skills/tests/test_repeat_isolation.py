"""Repeats cannot mix changed fixtures, references or controller dependencies."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.scenario_skills.common import write
from experiments.scenario_skills.dataset import load
from experiments.scenario_skills.experiment import experiment_identity, repeat
from experiments.scenario_skills.skill import material


class RepeatIsolationTests(unittest.TestCase):
    def test_changed_evidence_is_rejected_before_preflight_or_spending(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            config = {"target": {}, "proposer": {}}
            write(directory / "experiment.json", experiment_identity(config, directory))
            tasks = copy.deepcopy(load())
            tasks[0]["request"] += " Changed case facts."
            files = material()
            reference = next(name for name in files if name.startswith("references/"))
            files[reference] += b"\nChanged reference.\n"
            for name, value in (("load", tasks), ("material", files),
                                ("dependencies", {"controller-dependency": "changed"})):
                with self.subTest(changed=name), \
                     patch("experiments.scenario_skills.experiment." + name, return_value=value), \
                     patch("experiments.scenario_skills.experiment.preflight",
                           side_effect=AssertionError("Changed evidence reached preflight")) as check:
                    with self.assertRaisesRegex(ValueError, "same experiment"):
                        repeat(config, directory, tasks[0]["id"], "baseline", "Inspect inconsistent output")
                    check.assert_not_called()
                    self.assertFalse((directory / "budget.json").exists())


if __name__ == "__main__":
    unittest.main()

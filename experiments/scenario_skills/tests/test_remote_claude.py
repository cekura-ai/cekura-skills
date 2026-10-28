"""Claude proposer isolation, evidence boundaries and cost stops; no inference."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.scenario_skills.budget import BudgetError, Ledger
from experiments.scenario_skills.common import read
from experiments.scenario_skills.proposer import SCHEMA
from experiments.scenario_skills.remote_claude import ClaudeProposer, cli_args, container_args
from experiments.scenario_skills.relay import close_connection
from experiments.scenario_skills.skill import SKILL, split
from experiments.scenario_skills.tests.helpers import cumulative_ledger


def config():
    return {"ssh_host": "test-host", "image": "sha256:" + "a" * 64, "model": "claude-opus-5-5",
            "reasoning_effort": "high", "max_cost_usd": 2.5, "hard_cost_bound_verified": True,
            "cost_bound_evidence": "Synthetic bound for offline test"}


class RemoteClaudeTests(unittest.TestCase):
    def test_container_has_only_auth_mount_and_no_host_evidence_or_tools(self):
        command = container_args(config()["image"], "cekura-proposer-" + "a" * 16)
        self.assertIn("--network=none", command)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop=ALL", command)
        self.assertIn("-i", command)
        mounts = [v for v in command if v.startswith("--mount")]
        self.assertEqual(len(mounts), 1)
        self.assertTrue(mounts[0].endswith(",readonly"))
        args = cli_args(config(), SCHEMA)
        self.assertIn("--max-budget-usd", args)
        self.assertNotIn("--max-budget-usd", cli_args(dict(config(), subscription_only=True), SCHEMA))
        self.assertEqual(args[args.index("--tools") + 1], "")
        for argument in ("--safe-mode", "--restricted", "--strict-mcp-config", "--no-session-persistence"):
            self.assertIn(argument, args)
        with self.assertRaises(ValueError):
            cli_args(dict(config(), model="opus"), SCHEMA)
        with self.assertRaises(ValueError):
            cli_args(dict(config(), max_cost_usd=5), SCHEMA)

    def test_proposal_uses_only_training_material_and_resumes_without_new_spend(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = SKILL.read_bytes()
            body = split(baseline)[1].decode()
            event = {"type": "result", "subtype": "success", "total_cost_usd": .4,
                     "structured_output": {"body": body, "rationale": "Offline adapter test"}}
            ledger = cumulative_ledger(self, root)
            proposer = ClaudeProposer(config(), root, ledger)
            history = [{"split": "training", "task_id": "training-case", "trace": [],
                        "initial_state": {}, "final_state": {}, "grade": {}, "candidate_body": body}]
            with patch("experiments.scenario_skills.remote_claude.remote_call", return_value={
                    "returncode": 0, "events": json.dumps(event), "stderr": ""}) as call:
                data, _ = proposer.propose(baseline, history, 1, [])
                self.assertEqual(data, baseline)
                payload = call.call_args.args[1]
                self.assertEqual(payload["schema"], SCHEMA)
                self.assertIn("training-case", payload["prompt"])
                self.assertNotIn("grader.py", payload["prompt"])
                proposer.propose(baseline, history, 1, [])
                self.assertEqual(call.call_count, 1)
            self.assertEqual(float(ledger.total("proposer")), .4)
            with self.assertRaises(ValueError):
                proposer.propose(baseline, [dict(history[0], split="validation")], 2, [])

    def test_unverified_bound_stops_before_ssh_and_unknown_cost_blocks_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, baseline = Path(temporary), SKILL.read_bytes()
            ledger = cumulative_ledger(self, root)
            with patch("experiments.scenario_skills.remote_claude.remote_call") as call:
                with self.assertRaises(RuntimeError):
                    ClaudeProposer(dict(config(), hard_cost_bound_verified=False), root, ledger).propose(baseline, [], 1, [])
                call.assert_not_called()
            with patch("experiments.scenario_skills.remote_claude.remote_call", return_value={
                    "returncode": 1, "events": '{"type":"result","is_error":true}', "stderr": "offline failure"}):
                with self.assertRaises(BudgetError):
                    ClaudeProposer(config(), root, ledger).propose(baseline, [], 1, [])
            self.assertTrue(read(ledger.path)["blocked"])
            self.assertEqual(float(ledger.total()), 2.5)

    def test_superseded_ledger_cannot_fund_a_proposal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("experiments.scenario_skills.remote_claude.remote_call") as call:
                with self.assertRaises(BudgetError):
                    ClaudeProposer(config(), root, Ledger(root / "budget.json")).propose(SKILL.read_bytes(), [], 1, [])
                call.assert_not_called()

    def test_duplicate_or_already_disconnected_close_does_not_kill_relay(self):
        from unittest.mock import Mock
        socket = Mock()
        socket.shutdown.side_effect = OSError("Transport endpoint is not connected")
        sockets = {1: socket}
        close_connection(sockets, 1)
        close_connection(sockets, 1)
        self.assertEqual(sockets, {})
        socket.close.assert_called_once()

    def test_subscription_ledger_uses_incremental_cost_and_retains_nominal_usage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, baseline = Path(temporary), SKILL.read_bytes()
            ledger = cumulative_ledger(self, root)
            event = {"type": "result", "subtype": "success", "total_cost_usd": .5,
                     "structured_output": {"body": split(baseline)[1].decode(), "rationale": "Offline subscription test"}}
            with patch("experiments.scenario_skills.remote_claude.remote_call", return_value={
                    "returncode": 0, "events": json.dumps(event), "stderr": "", "incremental_cost_usd": 0,
                    "subscription": {"extra_usage_enabled": False}}):
                ClaudeProposer(dict(config(), subscription_only=True), root, ledger).propose(baseline, [], 1, [])
            self.assertEqual(ledger.total(), 0)
            self.assertEqual(read(root / "proposal-1.billing.json")["nominal_api_cost_usd"], .5)


if __name__ == "__main__":
    unittest.main()

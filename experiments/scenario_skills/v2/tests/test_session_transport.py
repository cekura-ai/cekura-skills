"""Claude session transport: never-started sessions cost nothing and are retried; started failures stay unknown."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.scenario_skills.budget import BudgetError
from experiments.scenario_skills.common import read
from experiments.scenario_skills.remote_claude import NotStarted
from experiments.scenario_skills.tests.helpers import cumulative_ledger
from experiments.scenario_skills.v2 import transport

SCHEMA = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}
OK = {"returncode": 0, "subscription": {}, "incremental_cost_usd": 0,
      "events": json.dumps({"type": "result", "is_error": False, "structured_output": {"ok": True}})}


class SessionTransport(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="cekura-session-")
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.ledger = cumulative_ledger(self, self.directory)
        for name in ("cli_args", "preconditions"):
            patcher = patch.object(transport, name, lambda *a, **k: None)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.session = transport.ClaudeSession({"subscription_only": True, "hard_cost_bound_verified": True}, self.directory / "s", self.ledger)

    def entries(self):
        return read(self.ledger.path)["entries"]

    def test_not_started_attempts_cost_nothing_and_the_retry_is_replayed(self):
        calls = iter([NotStarted("URLError: status endpoint"), OK])
        def fake(value):
            item = next(calls)
            if isinstance(item, Exception):
                raise item
            return item
        with patch.object(transport, "execute", fake):
            self.assertEqual(self.session("p", {}, SCHEMA, "judge-k"), {"ok": True})
        e = self.entries()
        self.assertEqual((e["judge-k"]["status"], e["judge-k"]["charged"]), ("complete", "0"))
        self.assertTrue(e["judge-k"]["not_started"])
        self.assertEqual(e["judge-k-attempt1"]["status"], "complete")
        self.assertFalse(read(self.ledger.path)["blocked"])
        with patch.object(transport, "execute", lambda v: self.fail("replay must not start a session")):
            self.assertEqual(self.session("p", {}, SCHEMA, "judge-k"), {"ok": True})

    def test_a_resolved_entry_without_a_response_is_retried_under_a_new_attempt(self):
        self.ledger.reserve("judge-r", "proposer", 2.5, entry_type="claude_session", role="judge")
        with self.assertRaises(BudgetError):
            self.ledger.settle("judge-r", None)
        self.ledger.resolve_unknown("judge-r", 0, {"reason": "never launched", "proof": ["no container event"]})
        with patch.object(transport, "execute", lambda value: OK):
            self.assertEqual(self.session("p", {}, SCHEMA, "judge-r"), {"ok": True})
        self.assertEqual(self.entries()["judge-r-attempt1"]["status"], "complete")

    def test_runs_in_different_namespaces_reuse_session_names_and_have_their_own_allowance(self):
        config = {"subscription_only": True, "hard_cost_bound_verified": True, "read_training_files": True}
        first = transport.ClaudeSession(config, self.directory / "run1", self.ledger, namespace="run-a")
        second = transport.ClaudeSession(config, self.directory / "run2", self.ledger, namespace="run-b")
        with patch.object(transport, "execute", lambda value: OK):
            for i in range(transport.PROPOSER_SESSIONS):
                first("p", {}, SCHEMA, "proposal-%d" % i)
            with self.assertRaises(ValueError):
                first("p", {}, SCHEMA, "proposal-%d" % transport.PROPOSER_SESSIONS)  # The per-run proposer allowance.
            self.assertEqual(second("p", {}, SCHEMA, "proposal-1"), {"ok": True})
        e = self.entries()
        self.assertEqual((e["run-a/proposal-1"]["status"], e["run-b/proposal-1"]["namespace"]), ("complete", "run-b"))
        self.assertNotIn("proposal-1", e)

    def test_a_cli_that_exits_before_any_event_is_not_started(self):
        replies = iter([{"returncode": 1, "events": "", "stderr": "error: unknown option"}, OK])
        with patch.object(transport, "execute", lambda value: next(replies)):
            self.assertEqual(self.session("p", {}, SCHEMA, "proposer-probe"), {"ok": True})
        e = self.entries()
        self.assertTrue(e["proposer-probe"]["not_started"])
        self.assertEqual((e["proposer-probe-attempt1"]["status"], e["proposer-probe-attempt1"].get("not_started")), ("complete", None))

    def test_a_saved_eventless_failure_is_retried_on_resume(self):
        with patch.object(transport, "execute", lambda value: {"returncode": 1, "events": "", "stderr": "x", "incremental_cost_usd": 0}), \
                patch.object(transport, "never_reached_model", lambda r: False):
            with self.assertRaises(RuntimeError):
                self.session("p", {}, SCHEMA, "proposer-old")  # Saved as an ordinary failed session (the earlier behaviour).
        with patch.object(transport, "execute", lambda value: OK):
            self.assertEqual(self.session("p", {}, SCHEMA, "proposer-old"), {"ok": True})
        self.assertTrue(self.entries()["proposer-old"]["not_started"])

    def test_three_not_started_attempts_stop_without_blocking(self):
        def fake(value):
            raise NotStarted("image missing")
        with patch.object(transport, "execute", fake), self.assertRaises(RuntimeError):
            self.session("p", {}, SCHEMA, "judge-x")
        self.assertFalse(read(self.ledger.path)["blocked"])
        self.assertEqual(sum(k.startswith("judge-x") for k in self.entries()), 3)

    def test_a_started_failure_is_still_unknown_usage(self):
        def fake(value):
            raise TimeoutError("session ran past its limit")
        with patch.object(transport, "execute", fake), self.assertRaises(BudgetError):
            self.session("p", {}, SCHEMA, "judge-y")
        self.assertEqual(self.entries()["judge-y"]["status"], "usage_unknown")
        self.assertTrue((self.directory / "s/judge-y.error.json").exists())


class StatusEndpoint(unittest.TestCase):
    def test_status_is_cached_and_rate_limits_are_retried(self):
        import io
        from urllib.error import HTTPError
        from experiments.scenario_skills import remote_claude
        credentials = Path(tempfile.mkdtemp()) / "c.json"
        credentials.write_text(json.dumps({"organizationUuid": "org", "claudeAiOauth": {"accessToken": "t", "subscriptionType": "team"}}))
        replies = [HTTPError("u", 429, "Too Many Requests", {"Retry-After": "0"}, io.BytesIO()), io.BytesIO(b'{"extra_usage": {"is_enabled": false}}')]
        calls = []
        def fake(request, timeout):
            calls.append(1)
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        remote_claude._STATUS_CACHE.clear()
        with patch.object(remote_claude, "CREDENTIALS", str(credentials)), patch.object(remote_claude, "urlopen", fake), \
                patch("time.sleep", lambda seconds: None):
            first = remote_claude.subscription_status()
            second = remote_claude.subscription_status()
        self.assertEqual((first["extra_usage_enabled"], second["subscription_type"], len(calls)), (False, "team", 2))


class ContainerCommand(unittest.TestCase):
    def test_workspace_mount_is_a_docker_option_before_the_image(self):
        from experiments.scenario_skills import remote_claude
        captured = {}
        def run(command, **kwargs):
            captured.setdefault("command", command)  # The first call is the session; the last is cleanup.
            class P:
                returncode, stdout, stderr = 0, "", ""
            return P()
        image = "sha256:" + "0" * 64
        config = {"image": image, "subscription_only": False}
        with patch.object(remote_claude, "preconditions", lambda c: None), patch.object(remote_claude, "cli_args", lambda c, s: ["-p", "--x"]), \
                patch.object(remote_claude.subprocess, "run", run):
            remote_claude.execute({"config": config, "prompt": "p", "schema": {}, "workspace": {"training/a.json": "{}"}})
        command = captured["command"]
        mount = next(i for i, a in enumerate(command) if a.startswith("--mount=type=bind,src=/tmp") or "dst=/workspace" in a)
        self.assertLess(mount, command.index(image))
        self.assertEqual(command[command.index(image) + 1:], ["-p", "--x"])


if __name__ == "__main__":
    unittest.main()

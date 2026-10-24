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


if __name__ == "__main__":
    unittest.main()

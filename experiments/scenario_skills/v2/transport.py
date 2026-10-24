"""Schema-validated fresh Claude sessions on this host; incremental and nominal billing differ.

Each session runs the pinned CLI in its own read-only, network-restricted container
(``remote_claude.execute``), now called locally instead of over SSH to the same machine.
Settlement uses only transport-level billing fields and happens before any parsing, so
malformed output cannot leave an open reservation. A settled session's saved response is
replayed on resume instead of starting a new session. There is no paid fallback: a
subscription change, disabled limits or exhausted quota ends the session with an error.
"""
import json

from jsonschema import validate

from ..budget import BudgetError, require_cumulative
from ..common import read, write
from ..remote_claude import NotStarted, cli_args, execute, preconditions


class ClaudeSession:
    def __init__(self, config, directory, ledger):
        if config.get("subscription_only") is not True or config.get("hard_cost_bound_verified") is not True:
            raise ValueError("v2 requires verified subscription-only Claude with extra usage disabled")
        self.config, self.directory, self.ledger = config, directory, ledger

    def _reserve(self, key, role):
        # Sessions that never started (no container ran) do not count against the allowance.
        count = sum(e.get("entry_type") == "claude_session" and e.get("role") == role and not e.get("not_started")
                    for e in self.ledger.state["entries"].values())
        if count >= (5 if role == "proposer" else 384):
            raise ValueError("Bounded Claude session allowance exhausted")
        self.ledger.reserve(key, "proposer", 2.5, entry_type="claude_session", role=role)

    def _run(self, key, role, value, fresh):
        """Up to three attempts; one that never launched is settled at $0 and retried under a new entry."""
        for attempt in range(3):
            current = key
            if attempt or not fresh:
                with self.ledger.transaction():
                    entries = self.ledger.state["entries"]
                    current = next("%s-attempt%d" % (key, n) for n in range(1, 100) if "%s-attempt%d" % (key, n) not in entries)
                    self._reserve(current, role)
            try:
                response = execute(value)
            except NotStarted as error:
                write(self.directory / (current + ".error.json"), {"not_started": True, "error": str(error)})
                self.ledger.settle(current, 0)
                with self.ledger.transaction():
                    self.ledger.state["entries"][current]["not_started"] = str(error)[:500]
                    write(self.ledger.path, self.ledger.state)
                continue
            except Exception as error:
                write(self.directory / (current + ".error.json"), {"not_started": False, "error": "%s: %s" % (type(error).__name__, error)})
                self.ledger.settle(current, None)
                raise
            self.ledger.settle(current, response.get("incremental_cost_usd"))
            return response
        raise RuntimeError("Claude session %s could not start after 3 attempts (no inference ran); see its error files" % key)

    def __call__(self, prompt, evidence, schema, key, workspace=None):
        cli_args(self.config, schema)
        self.directory.mkdir(parents=True, exist_ok=True)
        value = {"operation": "propose", "config": self.config,
                 "prompt": prompt + "\n" + json.dumps(evidence, ensure_ascii=False), "schema": schema}
        if workspace:
            if not self.config.get("read_training_files"):
                raise ValueError("Read-only evidence tools have not been configured")
            value["workspace"] = workspace
        response_path = self.directory / (key + ".response.json")
        role = "proposer" if self.config.get("read_training_files") else "judge"
        require_cumulative(self.ledger)
        if not response_path.exists():
            preconditions(self.config)  # Before reserving: a failed precondition must not leave unknown usage.
        with self.ledger.transaction():
            entry = self.ledger.state["entries"].get(key)
            if entry is None:
                self._reserve(key, role)
        if entry is not None and response_path.exists() and entry["status"] == "complete":
            response = read(response_path)  # Replay: no new session, no new charge.
        elif entry is not None and not entry.get("not_started"):
            raise BudgetError("Claude session %s started earlier without a settled, saved response" % key)
        else:
            write(self.directory / (key + ".input.json"), value)
            response = self._run(key, role, value, fresh=entry is None)
            write(response_path, response)
        events = []
        for line in response["events"].splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue  # A malformed line is evidence, already saved; it is never billed twice.
        finals = [e for e in events if e.get("type") == "result"]
        final = finals[-1] if finals else {}
        write(self.directory / (key + ".usage.json"), {"incremental_cost_usd": response.get("incremental_cost_usd"),
              "nominal_api_equivalent_usd": final.get("total_cost_usd"), "usage": final.get("usage"), "subscription": response.get("subscription")})
        if response["returncode"] or final.get("is_error") or not finals:
            raise RuntimeError("Claude session %s failed (no paid fallback); inspect private response evidence" % key)
        result = final.get("structured_output")
        if result is None:
            result = json.loads(final.get("result", ""))
        validate(result, schema)
        return result

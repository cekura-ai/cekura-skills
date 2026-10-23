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
from ..remote_claude import cli_args, execute


class ClaudeSession:
    def __init__(self, config, directory, ledger):
        if config.get("subscription_only") is not True or config.get("hard_cost_bound_verified") is not True:
            raise ValueError("v2 requires verified subscription-only Claude with extra usage disabled")
        self.config, self.directory, self.ledger = config, directory, ledger

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
        with self.ledger.transaction():
            entry = self.ledger.state["entries"].get(key)
            if entry is None:
                count = sum(e.get("entry_type") == "claude_session" and e.get("role") == role for e in self.ledger.state["entries"].values())
                if count >= (5 if role == "proposer" else 384):
                    raise ValueError("Bounded Claude session allowance exhausted")
                self.ledger.reserve(key, "proposer", 2.5, entry_type="claude_session", role=role)
        if entry is not None:
            if entry["status"] != "complete" or not response_path.exists():
                raise BudgetError("Claude session %s started earlier without a settled, saved response" % key)
            response = read(response_path)  # Replay: no new session, no new charge.
        else:
            write(self.directory / (key + ".input.json"), value)
            try:
                response = execute(value)
            except Exception:
                self.ledger.settle(key, None)
                raise
            write(response_path, response)
            self.ledger.settle(key, response.get("incremental_cost_usd"))
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

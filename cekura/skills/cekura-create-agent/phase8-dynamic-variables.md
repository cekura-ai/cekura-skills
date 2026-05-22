# Phase 8 — Dynamic Variables

Register all variables the agent requires to run. Cekura uses these to generate appropriate values alongside evaluators, then passes them to the agent at runtime so it runs with the right configuration for each test.

Registering a variable tells Cekura's evaluator generator to produce a value for it. If the agent needs a value generated alongside the evaluator — even if it never appears as a `{{placeholder}}` in a prompt — it must be registered here. The source and the injection mechanism do not matter; what matters is that the agent needs it to run correctly.

---

> **Start:** Announce "Starting Phase 8 — Dynamic Variables" before doing anything in this phase.

## 8a. Identify variables

**Source is irrelevant.** If a value changes per run and the agent reads it, register it — regardless of where it comes from. Do not exclude a variable because it originates from Cekura's infrastructure, the test runner, the scenario, or any other platform component. The only question is: does the agent read this value at runtime?

**Template substitution is just one delivery mechanism.** Do not limit the search to `{{placeholder}}` patterns or string interpolations in prompts. For self-hosted and WebSocket agents especially, runtime inputs are often structural — passed as headers, config payloads, or connection parameters — and they never appear as placeholders anywhere. They are still dynamic variables.

Beyond `{{placeholder}}` substitutions, WebSocket agents commonly receive per-run configuration as structural inputs — headers, connection parameters, or config payloads. These shape the agent's behaviour just as much as template variables but are easy to miss because they never appear as placeholders in any prompt.

Always ask: does the agent read anything at connection time that is not hardcoded? Common categories include how the agent should behave on this run, what model or style parameters it should use, and what context it needs about the caller or session.

The test: *"If I changed this value between two runs, would the agent behave differently?"* If yes, register it — regardless of how it is delivered.

**If code is available**, determine all variables by tracing the full call chain (already done in Phase 4). Review the running list from Phase 4 and compile the complete set of variables the agent reads at runtime — every value it depends on to function, regardless of how it is consumed.

Then present them to the user:

> "I found these variables the agent needs to run:
> - `customer_name` — [what it is]
> - `account_id` — [what it is]
> - ...
>
> Should I register these?"

Wait for confirmation before proceeding to 8b.

**If no code access**, ask:

> "What variables does your agent need to run? Think about every value it reads at runtime — caller data, account info, configuration, anything that isn't hardcoded."

---

## 8b. For each variable, establish:

1. **`name`** — identifier in snake_case
2. **`description`** — what it represents, its expected format/type, and example values
3. **Where it comes from at runtime** — inbound call metadata, CRM, API, config payload

---

## 8c. Register via the API

```bash
curl -X POST https://api.cekura.ai/test_framework/v1/aiagents/{agent_id}/dynamic-variables/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '[
  {
    "name": "customer_name",
    "description": "Full name of the caller as stored in the CRM. String. Examples: \"Jane Smith\", \"Rahul Verma\", \"María López\"."
  },
  {
    "name": "account_id",
    "description": "Unique customer account identifier. Alphanumeric string prefixed with ACC-. Examples: \"ACC-001234\", \"ACC-987654\"."
  }
]'
```

**Key rules:**
- `name` — use snake_case
- `description` — explain what it represents, format/type, and example values
- This is an **upsert** — POST the full array each time
- Returns 201 with the complete variable list

---

## Phase 8 Gate

**Do not proceed until the user has confirmed the variable list and all variables are registered via the API.**

Announce: "Phase 8 complete." Then immediately begin [Phase 9 — Advanced Configuration](phase9-advanced.md) without waiting for the user.

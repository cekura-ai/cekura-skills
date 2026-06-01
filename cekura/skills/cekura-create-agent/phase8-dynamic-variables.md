# Phase 8 — Main Agent Dynamic Variables

Register all variables the main agent requires to run. Cekura uses these to generate appropriate values alongside evaluators, then passes them to the agent at runtime so it runs with the right configuration for each test.

Registering a variable tells Cekura's evaluator generator to produce a value for it. If the main agent needs a value generated alongside the evaluator — even if it never appears as a `{{placeholder}}` in a prompt — it must be registered here. The source and the injection mechanism do not matter; what matters is that the main agent needs it to run correctly.

---

> **Start:** Announce "Starting Phase 8 — Main Agent Dynamic Variables" before doing anything in this phase.

## 8a. Identify variables

**Source is irrelevant. No exceptions.** If a value changes per run and the main agent reads it, register it. This includes:

- Values the main agent fetches from Cekura's own API using a run ID
- Values passed via Cekura headers at connection time
- Values injected by the test runner or scenario
- Values from any platform component

"Cekura injects it automatically" is NOT a reason to skip registration. Cekura needs the variable registered so it knows what to generate and inject when creating test scenarios. If you skip registration, Cekura won't know the variable exists and won't generate a value for it.

The only question is: **does the main agent read this value at runtime and does it affect behaviour?** If yes, register it.

**Template substitution is just one delivery mechanism.** Do not limit the search to `{{placeholder}}` patterns or string interpolations in prompts. For self-hosted and WebSocket agents especially, runtime inputs are often structural — passed as headers, config payloads, or connection parameters — and they never appear as placeholders anywhere. They are still dynamic variables.

Beyond `{{placeholder}}` substitutions, WebSocket agents commonly receive per-run configuration as structural inputs — headers, connection parameters, or config payloads. These shape the main agent's behaviour just as much as template variables but are easy to miss because they never appear as placeholders in any prompt.

Always ask: does the main agent read anything at connection time that is not hardcoded? Common categories include how the agent should behave on this run, what model or style parameters it should use, and what context it needs about the caller or session.

The test: *"If I changed this value between two runs, would the main agent behave differently?"* If yes, register it — regardless of how it is delivered.

**If code is available**, determine all variables by tracing the full call chain (already done in Phase 4). Review the running list from Phase 4 and compile the complete set.

**Only include variables the main agent actually reads at runtime in its execution logic.** Before registering any variable, verify it passes this test: is there code that reads this value and uses it during a real call?

Exclude — do not register these even if they appear as `{{patterns}}` somewhere:
- Patterns in the system prompt text that are documentation examples or placeholders not replaced by code
- `{{var}}` syntax that appears in the prompt as literal text (e.g. showing users what a variable looks like), not as a substitution target
- Patterns in KB files, README, docs, or any non-executable content
- Variable names in comments or string literals never evaluated
- Test fixtures, mock data, or example payloads that don't flow into execution

**If a variable is identified as a documentation example, exclude it from the registration payload entirely.** Do not register it "just in case" or with a note that it's harmless. Only register variables confirmed to be read by execution code.

Then state your finding and confirm:

> "I found these variables the main agent reads at runtime: [list them with what they represent]. Registering them now."

If none found: "I found no values the main agent reads at runtime that vary per run — all configuration is hardcoded. Confirming with you: is that correct?"

**If no code access**, ask:

> "What variables does your main agent need to run? Think about every value it reads at runtime — caller data, account info, configuration, anything that isn't hardcoded."

---

## 8b. For each variable, establish:

1. **`name`** — identifier in snake_case
2. **`description`** — write the most detailed description possible. Cover everything: what the variable represents, its data type, its full structure (every field and sub-field for objects), all constraints (required fields, allowed values, value ranges, format rules), how it is used by the agent, what happens if it is missing or malformed, and the most complete realistic example with all fields populated. Length is not a concern — completeness is. Never use trivial placeholders.
3. **Where it comes from at runtime** — inbound call metadata, CRM, API, config payload

---

## 8c. Register via the API

**Auth header for all Cekura API calls: `X-CEKURA-API-KEY: $CEKURA_API_KEY`** — never use `Authorization: Api-Key` or `Authorization: Bearer`.

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
- `description` — explain what it represents, format/type, and include the most complete realistic example. For objects show full structure; for strings show realistic content; for enums list all values
- This is an **upsert** — POST the full array each time
- Returns 201 with the complete variable list

---

## Phase 8 Gate

**Do not proceed until the user has confirmed the variable list and all variables are registered via the API.**

Announce: "Phase 8 complete." Then immediately begin [Phase 9 — Advanced Configuration](phase9-advanced.md) without waiting for the user.

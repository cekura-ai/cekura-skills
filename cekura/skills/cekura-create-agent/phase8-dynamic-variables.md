# Phase 8 — Dynamic Variables

Dynamic variables are all the configuration parameters and runtime values the agent needs to work — identified in Phase 4 while reading the code or questioning the user. This phase ensures both classes are captured and registered.

---

> **Start:** Announce "Starting Phase 8 — Dynamic Variables" before doing anything in this phase.

## 8a. Two classes of dynamic variables

There are two distinct classes. Both must be registered.

### Class 1 — Description-level variables

Values injected into the agent's own prompt or logic at runtime — identified in Phase 4 by tracing the call chain:

- f-strings, template rendering, string replacements in the prompt construction code
- Per-call data passed via API/webhook at call start (customer data, account info, session context)
- Feature flags or per-call overrides baked into the agent's own behaviour

### Class 2 — Platform-injected runtime variables

Values that Cekura resolves and injects per-run before the agent is invoked — **not** placeholders in the agent's own code. These exist for agents whose per-run configuration comes from Cekura rather than being baked into the agent itself.

Ask the user: "When Cekura runs a test against your agent, does Cekura pass any configuration to your agent at the start of each run? For example — the scenario instructions, language, persona, or any test-profile fields your agent reads?"

If yes, these are dynamic variables too. Common examples of this class:

- The scenario or instruction set that changes per test run
- Language or locale determined by the test run rather than fixed in the agent
- Persona or role configuration supplied per run
- Arbitrary key-value fields from test profiles that the agent reads (e.g. from headers, query parameters, or a config payload)

For each platform-injected variable, register it — even if it never appears as a `{{placeholder}}` in the agent's own description.

---

## 8b. Review what was found in Phase 4

Check the running list built during Phase 4:

- Runtime values injected into the prompt (found while tracing the call chain)
- Per-call configuration passed at call start
- Any Class 2 variables noted from structured questioning

If nothing was captured, explicitly ask the user about both classes before proceeding. Do not assume there are none.

---

## 8c. For each identified variable, establish:

1. **`name`** — variable identifier in snake_case (e.g. `customer_name`, `scenario_language`)
2. **`description`** — what it represents, its expected format/type, and example values
3. **Class** — description-level (injected by the agent's own code) or platform-injected (supplied by Cekura per run)
4. **Where it comes from at runtime** — agent code, inbound call metadata, CRM, test profile, Cekura platform

---

## 8d. Register all variables via the API

Register both classes together in a single call:

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
    "name": "account_type",
    "description": "Tier or segment of the customer account. Determines which offers and escalation paths apply. One of: \"standard\", \"premium\", \"vip\". Example: \"premium\"."
  }
]'
```

**Key rules:**
- `name` is the variable identifier — use snake_case
- `description` should explain what the variable represents, its format/type, and example values — this helps with scenario generation
- This is an **upsert** — POST the full array; it creates new variables and updates existing ones
- Returns 201 with the complete variable list after upsert

---

## 8e. Document variables for the user

Show the user what their test profiles will need to supply:

```
customer_name  — Caller's first name from CRM         — e.g. "Jane Smith"
account_type   — Customer tier (standard/premium/vip) — e.g. "premium"
```

---

## Phase 8 Gate

**Do not proceed until both classes of dynamic variables — description-level and platform-injected — are identified and registered via the API.**

Announce: "Phase 8 complete." Then immediately begin [Phase 9 — Advanced Configuration](phase9-advanced.md) without waiting for the user.

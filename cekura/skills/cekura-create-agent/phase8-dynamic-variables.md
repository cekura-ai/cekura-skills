# Phase 8 — Dynamic Variables

**A dynamic variable is any value that changes per run and affects the agent's behavior** — regardless of where or how the substitution happens. Whether it is injected by the agent's own code, by the test scenario, by the runner, or by the Cekura platform, it is a dynamic variable if it varies per run and influences what the agent does.

Do not reason about the substitution mechanism. Reason about what changes.

---

> **Start:** Announce "Starting Phase 8 — Dynamic Variables" before doing anything in this phase.

## 8a. What counts as a dynamic variable?

Ask one question: **"What is different about this agent from one run to the next?"**

Everything that can differ per run and that the agent reads, uses, or responds to is a dynamic variable:

- Caller-specific data (name, account, appointment, preferences)
- Configuration supplied at run start that changes the agent's behaviour (persona, language, role, instruction set)
- Any field from a test profile or scenario that the agent reads — whether via its own code, via headers, via a config payload, or via the test runner
- Feature flags or A/B variants that change per run
- Scenario instructions or scripts that vary per test

The substitution mechanism does not matter — it could happen in the agent's f-string, in the scenario, in the runner, or on the Cekura platform. If it changes per run and affects agent behaviour, register it.

---

## 8b. Review what was found in Phase 4

Check the running list built during Phase 4. If nothing was captured, ask the user explicitly:

> "From one test run to the next, what is different about how your agent behaves or what it knows? Think about the caller data, the scenario being tested, any configuration passed in — anything that isn't identical across all runs."

Do not assume there are none. Follow up until the answer is clear.

---

## 8c. For each identified variable, establish:

1. **`name`** — variable identifier in snake_case (e.g. `customer_name`, `scenario_language`)
2. **`description`** — what it represents, its expected format/type, and example values
3. **Where it comes from at runtime** — agent code, inbound call metadata, CRM, test profile, scenario, Cekura platform

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

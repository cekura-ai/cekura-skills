# Phase 8 — Dynamic Variables

Dynamic variables are per-run values that the **user supplies** via test profiles to drive the agent's behaviour.

---

> **Start:** Announce "Starting Phase 8 — Dynamic Variables" before doing anything in this phase.

## 8a. What are user-supplied dynamic variables?

Ask: **"What data does your agent need per call that you would supply in a test profile — things that change between callers or scenarios?"**

Examples:
- Caller-specific data (identity, account state, preferences, history)
- Per-call configuration the agent uses to personalise its responses
- Feature flags or A/B variants the user controls per test run

If the answer is none, that is a valid outcome. Do not assume something is missing.

---

## 8b. Review what was found in Phase 4

Check the running list built during Phase 4. If nothing was captured, ask the user:

> "Is there any caller-specific data or configuration that you would need to supply per test run — something that changes per caller or per scenario?"

Do not assume there are none without confirming.

---

## 8c. For each identified variable, establish:

1. **`name`** — variable identifier in snake_case (e.g. `customer_name`, `account_id`)
2. **`description`** — what it represents, its expected format/type, and example values
3. **Where it comes from at runtime** — inbound call metadata, CRM, test profile

---

## 8d. Register all variables via the API

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
  },
  {
    "name": "account_type",
    "description": "Tier or segment of the customer account. Determines which offers, escalation paths, and SLAs apply. One of: \"standard\", \"premium\", \"vip\". Example: \"premium\"."
  }
]'
```

**Key rules:**
- `name` is the variable identifier — use snake_case
- `description` should explain what the variable represents, its expected format/type, and example values — this helps with scenario generation
- This is an **upsert** — POST the full array each time; it creates new variables and updates existing ones
- Returns 201 with the complete variable list after upsert

---

## 8e. Document variables for the user

Show the user what their test profiles will need to supply:

```
customer_name  — Caller's first name from CRM         — e.g. "Jane Smith"
account_id     — Customer account identifier          — e.g. "ACC-001234"
account_type   — Customer tier (standard/premium/vip) — e.g. "premium"
```

---

## Phase 8 Gate

**Do not proceed until all user-supplied dynamic variables are identified and registered via the API (or confirmed none are needed).**

Announce: "Phase 8 complete." Then immediately begin [Phase 9 — Advanced Configuration](phase9-advanced.md) without waiting for the user.

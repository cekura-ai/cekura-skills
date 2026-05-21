# Phase 8 — Dynamic Variables

Dynamic variables are all the configuration parameters and runtime values the agent needs to work — identified in Phase 4 while reading the code or questioning the user. This phase registers them via the API.

---

> **Start:** Announce "Starting Phase 8 — Dynamic Variables" before doing anything in this phase.

## 8a. What was found in Phase 4?

By this point, dynamic variables should already be identified from Phase 4 (code tracing or structured questioning). Review what was captured:

- Runtime values injected into the prompt (f-strings, templates, string replacements found while tracing the call chain)
- Per-call configuration passed via API/webhook at call start (customer data, account info, session context)
- Feature flags or per-call overrides
- Any configuration the agent needs that changes between calls

If no variables were identified and none are expected, confirm with the user and skip to the gate.

---

## 8b. For each identified variable, establish:

1. **`name`** — variable identifier in snake_case (e.g. `customer_name`, `account_id`)
2. **`description`** — what it represents and its expected format/type, with example values
3. **Where it comes from at runtime** — inbound call metadata, CRM lookup, webhook payload, test profile

---

## 8c. Register variables via the API

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

## 8d. Document variables for the user

Show the user what their test profiles will need to supply:

```
customer_name  — Caller's first name from CRM         — e.g. "Jane Smith"
account_id     — Customer account identifier          — e.g. "ACC-001234"
account_type   — Customer tier (standard/premium/vip) — e.g. "premium"
```

---

## Phase 8 Gate

**Do not proceed until every runtime configuration variable is registered via the API.**

Announce: "Phase 8 complete." Then immediately begin [Phase 9 — Advanced Configuration](phase9-advanced.md) without waiting for the user.

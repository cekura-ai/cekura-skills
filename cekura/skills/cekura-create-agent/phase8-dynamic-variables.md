# Phase 8 — Dynamic Variables

Register all variables the agent requires to run.

---

> **Start:** Announce "Starting Phase 8 — Dynamic Variables" before doing anything in this phase.

## 8a. What variables does the agent need?

Review the running list from Phase 4. Every variable the agent reads or depends on to function — across all flows, tools, and configurations — should be registered here.

If nothing was captured in Phase 4, ask the user:

> "What variables does your agent need to run? Think about every value it reads at runtime — caller data, account info, configuration, anything that isn't hardcoded."

Do not assume there are none without confirming.

---

## 8b. For each variable, establish:

1. **`name`** — identifier in snake_case (e.g. `customer_name`, `account_id`)
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
  },
  {
    "name": "account_type",
    "description": "Tier or segment of the customer account. One of: \"standard\", \"premium\", \"vip\". Example: \"premium\"."
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

**Do not proceed until all variables the agent needs to run are registered via the API.**

Announce: "Phase 8 complete." Then immediately begin [Phase 9 — Advanced Configuration](phase9-advanced.md) without waiting for the user.

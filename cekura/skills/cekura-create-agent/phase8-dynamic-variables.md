# Phase 8 — Dynamic Variables

Dynamic variables are per-run values that the **user supplies** via test profiles to drive the agent's behaviour. They are not the same as platform-managed runtime inputs.

---

> **Start:** Announce "Starting Phase 8 — Dynamic Variables" before doing anything in this phase.

## 8a. The critical distinction: user-supplied vs platform-managed

Before identifying dynamic variables, establish this distinction clearly:

**User-supplied dynamic variables** — values the user must provide per run via test profiles because they represent caller-specific or scenario-specific data that Cekura cannot know. These must be registered. Examples of the category: caller identity data, account state, per-call configuration the agent needs to personalise its responses.

**Platform-managed runtime inputs** — values that the Cekura platform resolves and injects automatically per run as part of running a scenario. The user does not supply these; Cekura handles them. They do not need to be registered as dynamic variables.

**How to tell the difference:** Ask — "Does the user need to provide this value in a test profile, or does Cekura handle it automatically when running the scenario?"

- User provides it → dynamic variable, register it
- Cekura handles it automatically → platform-managed, do not register

For agents driven by Cekura's test infrastructure (self-hosted runners, simulation agents), many per-run inputs — such as the test scenario itself, run configuration, or platform settings — are platform-managed. If the agent appears to have no user-supplied variables, that may be correct. Confirm with the user rather than assuming something is missing.

---

## 8b. What counts as a user-supplied dynamic variable?

Ask: **"What data does your agent need per call that changes between callers or scenarios, and that you would need to provide in a test profile?"**

Examples of what this class covers:
- Caller-specific data (identity, account state, preferences, history)
- Per-call configuration the agent uses to personalise its responses
- Feature flags or A/B variants the user controls per test run

These are distinct from inputs the platform or runner manages automatically.

---

## 8c. Review what was found in Phase 4

Check the running list built during Phase 4. If nothing was captured, ask the user:

> "From one test run to the next, is there any caller-specific data or configuration that you would need to supply — something that changes per caller or per scenario and that Cekura wouldn't know automatically?"

If the answer is no and the agent is platform-driven (Cekura's infrastructure manages per-run inputs), that is a valid outcome — not a gap. Confirm this with the user and proceed.

Do not assume dynamic variables are missing just because none were found.

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

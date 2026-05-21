# Phase 8 — Dynamic Variables

Dynamic variables are values passed to the agent **at the start of every run**. If `{{variableName}}` placeholders exist in the agent description, they are definitely dynamic variables. But dynamic variables can also exist without appearing as placeholders in the description; they are simply runtime values registered on the agent and available to the test runner.

Do not ask the user if they have dynamic variables — identify them from the available sources.

---

> **Start:** Announce "Starting Phase 8 — Dynamic Variables" before doing anything in this phase.

## 8a. Identify dynamic variables

**If code is available**, inspect it for anything injected into the prompt at runtime:

- Python f-strings: `f"Customer name: {customer_name}"` → `{{customer_name}}`
- Template rendering: `template.render(account_id=...)` → `{{account_id}}`
- String replacements: `prompt.replace("{NAME}", caller_name)` → `{{name}}`
- Variables passed via API/webhook at call start (customer data, CRM fields, session context)
- Multi-node agents: separate system prompts per node/state stored in variables
- Feature flags or A/B variants passed per call

**For cloud provider agents (VAPI, Retell, etc.)**, look for:
- Custom variables or metadata defined in the provider's agent config
- Fields in the agent's system prompt that use the provider's variable syntax (e.g. `{{first_name}}` in Retell)
- Dynamic data injected via the provider's API when placing/receiving calls

**Already-detected patterns**: if the description already contains `{{variableName}}` patterns, list them all.

**If no code access**, ask the user:

1. "Does anything change about your agent between calls? E.g. caller's name, account number, appointment date, or any other per-call data?"
2. "Does your agent behave differently for different customers or call types? What data drives that?"
3. "Are there any placeholders or template variables in your system prompt that get filled in before each call?"
4. "What parameters or metadata are sent along when your agent is invoked?"

---

## 8b. For each identified variable, establish:

1. **`name`** — exact variable name as it appears in the agent context (snake_case, e.g. `customer_name`)
2. **`description`** — what it represents and its expected format/type (e.g. "Customer's first name from CRM, string")
3. **Where it comes from at runtime** — inbound call metadata, CRM lookup, webhook payload
4. **Example value** — what a real value looks like

---

## 8c. Register variables via the API

Once all variables are identified, register them on the agent:

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
    "description": "Unique customer account identifier used to look up account details. Alphanumeric string prefixed with ACC-. Examples: \"ACC-001234\", \"ACC-987654\"."
  },
  {
    "name": "account_type",
    "description": "Tier or segment of the customer account. Determines which offers, escalation paths, and SLAs apply. One of: \"standard\", \"premium\", \"vip\". Example: \"premium\"."
  },
  {
    "name": "appointment_date",
    "description": "Date of the customer'\''s upcoming appointment, formatted as YYYY-MM-DD. Used by the agent to confirm or reschedule. Examples: \"2026-05-25\", \"2026-06-03\"."
  },
  {
    "name": "outstanding_balance",
    "description": "Current outstanding balance on the account in the local currency, as a numeric string. Examples: \"1500.00\", \"0.00\", \"3200.50\"."
  }
]'
```

**Key rules:**
- `name` is the variable identifier — use snake_case (e.g. `customer_name`, `account_id`)
- `description` should explain what the variable represents and its expected format/type — this helps with scenario generation
- This is an **upsert** — POST the full array each time; it creates new variables and updates existing ones
- Returns 201 with the complete variable list after upsert

---

## 8e. Document variables for the user

Show the user what their test profiles will need to supply:

```
{{customer_name}}    — Caller's first name from CRM         — e.g. "Jane Smith"
{{account_id}}       — Customer account identifier          — e.g. "ACC-001234"
{{account_type}}     — Customer tier (standard/premium/vip) — e.g. "premium"
{{appointment_date}} — Upcoming appointment date            — e.g. "2026-05-25"
```

---

## 8f. Multi-node / multi-state agents

For agents with distinct states (intake → verification → scheduling → billing), store each node's full system prompt as a separate dynamic variable:

```json
[
  {
    "name": "intake_prompt",
    "description": "Full system prompt for the intake and greeting state. Covers how the agent introduces itself, confirms the caller is available to talk, and transitions to the next state. String (multi-line). Example: \"You are a senior fertility counsellor from Birla IVF. Begin by introducing yourself and asking if this is a good time to talk.\""
  },
  {
    "name": "verification_prompt",
    "description": "Full system prompt for the identity verification state. Covers how the agent collects and validates the caller's name, date of birth, and account number before proceeding. String (multi-line)."
  },
  {
    "name": "scheduling_prompt",
    "description": "Full system prompt for the appointment scheduling state. Covers clinic selection logic, available time slots, confirmation steps, and what to say if the preferred slot is unavailable. String (multi-line)."
  }
]
```

This lets metrics reference `{{dynamic_variables.intake_prompt}}` to evaluate each node independently.

---

## Phase 8 Gate

**Do not proceed until every runtime-injected variable is identified and registered via the API.**

Announce: "Phase 8 complete." Then immediately begin [Phase 9 — Advanced Configuration](phase9-advanced.md) without waiting for the user.

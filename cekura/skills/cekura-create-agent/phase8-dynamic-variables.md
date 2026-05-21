# Phase 8 — Dynamic Variables

Dynamic variables are values passed to the agent **at the start of every run**. If `{{variableName}}` placeholders exist in the agent description, they are definitely dynamic variables. But dynamic variables can also exist without appearing as placeholders in the description; they are simply runtime values registered on the agent and available to the test runner.

Do not ask the user if they have dynamic variables — identify them from the available sources.

---

> **Start:** Announce "Starting Phase 8 — Dynamic Variables" before doing anything in this phase.

## 8a. Identify dynamic variables

**If code is available**, trace the **full call chain** from the entry point down to where the final LLM prompt string is assembled. Do not stop at the handler level — dynamic variables are often injected several layers deep.

Start at the WebSocket handler or main task entry point, then follow every function call that leads to the final prompt string. The injection often happens in a helper called by a helper called by a helper — not in the handler itself.

At each layer, look for:

- Python f-strings: `f"...{variable}..."` → dynamic variable
- Template rendering: `template.render(key=value)` → dynamic variable
- String replacements: `prompt.replace("{TAG}", value)` → dynamic variable
- Concatenation or formatting that inserts runtime data into the prompt
- Variables passed via API/webhook at call start (customer data, CRM fields, session context)
- Feature flags or A/B variants passed per call

**Do not conclude "no dynamic variables" until you have followed the entire path from entry point to the final string passed to the LLM.** A shallow read of the handler is not sufficient.

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

## Phase 8 Gate

**Do not proceed until every runtime-injected variable is identified and registered via the API.**

Announce: "Phase 8 complete." Then immediately begin [Phase 9 — Advanced Configuration](phase9-advanced.md) without waiting for the user.

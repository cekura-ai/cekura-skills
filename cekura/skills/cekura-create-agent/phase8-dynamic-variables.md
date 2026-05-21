# Phase 8 — Dynamic Variables

Dynamic variables are values passed to the agent **at the start of every run**. They are defined as `{{variableName}}` placeholders in the description and injected into the prompt before each run.

Do not ask the user if they have dynamic variables — identify them from the available sources.

---

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

**Already-detected patterns**: if the description already contains `{{variableName}}` patterns from the pasted/synced prompt, list them all.

**If no code access**, ask the user these questions directly:

1. "Does anything change about your agent between calls? For example — does the caller's name, account number, appointment date, or any other data get passed in when the call starts?"
2. "Does your agent behave differently for different customers or call types? What data drives that difference?"
3. "Are there any placeholders or template variables in your system prompt that get filled in before each call?"
4. "If you look at how your agent is invoked — what parameters or metadata are sent along with the call?"

For each variable the user identifies, collect: its name, what it represents, where it comes from, and an example value.

---

## 8b. For each identified variable, establish:

1. **Variable name** — what to call the `{{placeholder}}` (snake_case)
2. **What it represents** — e.g. "customer's first name from CRM"
3. **Where it comes from at runtime** — inbound call metadata, CRM lookup, webhook payload, manual input
4. **Example values** — what real values look like (for test profile setup)
5. **Whether it affects the prompt or is used in tool calls** — if it's only used in tool inputs, it may not need to be in the description

---

## 8c. Add placeholders to the agent description

For every identified dynamic variable that belongs in the system prompt, ensure the description uses `{{variableName}}` syntax at the right place.

If the description was auto-synced or pasted and already uses native provider syntax (e.g. `{first_name}`), update it to Cekura's `{{first_name}}` format.

**Example — before:**
```
You are a scheduling assistant helping the customer with their booking.
```

**After:**
```
You are a scheduling assistant helping {{customer_name}} (account: {{account_id}}, type: {{account_type}}) with their booking.
```

PATCH the agent description with the updated version if placeholders were added.

---

## 8d. Document variables for test profile setup

For each dynamic variable, tell the user:

> "When running tests, your test profiles will need to supply these variables:"

List each one with:
- `{{variable_name}}` — description — example value

Example output:
```
{{customer_name}}   — caller's first name from CRM        — "Jane Smith"
{{account_id}}      — customer account identifier          — "ACC-001234"
{{account_type}}    — customer tier (standard/premium/vip) — "premium"
{{appointment_date}} — upcoming appointment date           — "2026-05-25"
```

These become fields in test profiles, which Cekura injects into the description before each test run.

---

## 8e. Multi-node / multi-state agents

For agents with distinct states (e.g. intake → verification → scheduling → billing), store each node's full system prompt as a separate dynamic variable rather than embedding all prompts in the description:

```
{{intake_prompt}}
{{verification_prompt}}
{{scheduling_prompt}}
```

This lets you swap node behaviour per test and lets metrics reference `{{dynamic_variables.intake_prompt}}` to evaluate per-node behaviour independently.

---

## Phase 8 Gate

**Do not proceed until every runtime-injected variable is identified, documented, and present as `{{placeholder}}` in the agent description.**

Move to [Phase 9 — Advanced Configuration](phase9-advanced.md).

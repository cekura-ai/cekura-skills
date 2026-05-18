# Phase 9 — Dynamic Variables

Configure per-call variable injection for agents that behave differently depending on caller data or call context.

---

## 9a. Does the agent use per-call variables?

Ask: "Does your agent use per-call variables? (e.g. customer name, account ID, different prompts per call flow)"

If no → skip to [Phase 10](phase10-advanced.md).

---

## 9b. Auto-detection

If the agent description contains `{{variableName}}` patterns, Cekura detects them automatically after agent creation. Check the agent object:

```
mcp__cekura__aiagents_retrieve → inspect detected dynamic variables
```

---

## 9c. Usage pattern

Add `{{variableName}}` placeholders in the agent description where values should be injected:

```
You are a scheduling assistant. Customer name: {{customer_name}}.
Account type: {{account_type}}.
```

At test time, test profiles supply the values:

```json
{ "customer_name": "Jane Smith", "account_type": "premium" }
```

---

## 9d. What dynamic variables enable

| Use case | Example |
|----------|---------|
| Caller-specific data | `{{customer_name}}`, `{{account_id}}`, `{{employment_type}}` |
| Per-call system prompt injection | Different instructions per caller segment |
| Multi-node / multi-state agents | One variable per node's system prompt |
| Feature flags | Enable/disable behaviors per call |
| Context injection | Prior call summaries, reconnection context |

---

## 9e. Multi-node agent pattern

For agents with distinct states (intake → scheduling → billing), store each node's system prompt as a separate dynamic variable instead of embedding all prompts in the description. Metrics can then reference `{{dynamic_variables.nodeName}}` to evaluate per-node behavior.

---

## Phase 9 Gate

**Confirm dynamic variables are detected or confirmed unnecessary.**

Move to [Phase 10 — Advanced Configuration](phase10-advanced.md).

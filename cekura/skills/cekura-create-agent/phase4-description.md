# Phase 4 — Agent Description

The description is the **most important field** in the entire setup. Get it right before creating the agent.

---

## 4a. Why the description matters

It powers:
- Automatic evaluator generation
- Metrics that reference `{{agent.description}}`
- Topic and dropoff classification
- Hallucination detection accuracy

**No truncation.** Descriptions >10 KB are fine — Cekura handles them. Multi-state agents with full exported configs are expected.

---

## 4b. Collect the full prompt

Ask: "Can you paste your agent's full system prompt or exported config?"

**Provider-specific exports:**

| Provider | How to export |
|----------|--------------|
| **Retell** | Agents → Select → Export → downloads `.json` |
| **VAPI** | Workflows → Select → Code button → Copy full JSON |
| **Multi-state agents** | Paste the complete JSON (all nodes and transitions) |
| **Custom / self-hosted** | Paste the full system prompt text |

---

## 4c. Note dynamic variable patterns

If the description contains `{{variableName}}` placeholders, flag them — Cekura will auto-detect them after agent creation. These are handled in [Phase 9](phase9-dynamic-variables.md).

---

## Phase 4 Gate

**Do not proceed until you have the full agent description. Do not accept a summary or excerpt — the full text is required.**

Move to [Phase 5 — Create the Agent](phase5-create.md).

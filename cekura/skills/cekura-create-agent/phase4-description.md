# Phase 4 — Agent Description

> **Skip this phase** if the provider is VAPI, Retell, ElevenLabs, or Synthflow and the user agreed to use `auto_sync_prompt` in Phase 3. The description will be fetched from the provider within ~30 seconds of agent creation. Go directly to [Phase 5](phase5-create.md) and use a placeholder for the `description` field.

For all other providers, or if the user prefers to paste the prompt manually, continue below.

---

## 4a. Why the description matters

The description is the primary input for **automatic scenario/evaluator generation**. Cekura reads it to understand what the agent does, what flows it handles, what it should and shouldn't say, and what edge cases exist — then generates test scenarios covering all of that.

**The more detailed and complete the description, the better the generated scenarios.** It should cover:

- The agent's overall purpose and tone
- Every workflow or call flow the agent handles (e.g. booking, cancellation, FAQ, escalation)
- What the agent should do in each situation
- Any rules or constraints (what it must never say, when to transfer, etc.)
- Tool calls the agent makes and when
- How it handles edge cases, errors, or unexpected user inputs

A short or vague description produces shallow, generic scenarios. A complete, detailed prompt produces scenarios that actually test the agent's real behaviour.

**No truncation.** Descriptions >10 KB are fine — Cekura handles them. Multi-state agents with full exported configs are expected and encouraged.

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

**Do not accept a summary or excerpt. The full prompt is required — scenario quality depends directly on description quality.**

Move to [Phase 5 — Create the Agent](phase5-create.md).

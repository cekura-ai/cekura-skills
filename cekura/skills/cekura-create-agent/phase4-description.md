# Phase 4 — Agent Description

> **Skip this phase** if the provider is VAPI, Retell, ElevenLabs, or Synthflow and the user agreed to use `auto_sync_prompt` in Phase 3. The description will be fetched from the provider within ~30 seconds of agent creation. Go directly to [Phase 5](phase5-create.md) and use a placeholder for the `description` field.

For all other providers, or if the user prefers to provide the description manually, continue below.

---

## 4a. Why the description matters

The description is the **sole input for automatic scenario/evaluator generation**. Cekura reads it to understand every flow, rule, edge case, and constraint — then generates test scenarios from that understanding.

**A shallow description produces shallow scenarios. A complete description produces scenarios that actually test the agent's real behaviour.**

There is no upper bound on detail. Spend as many tokens as needed. Do not rush this phase.

---

## 4b. Two paths: paste vs synthesise

### Path A — Cloud providers with a system prompt

Ask: "Can you paste your agent's full system prompt or exported config?"

| Provider | How to export |
|----------|--------------|
| Retell | Agents → Select → Export → downloads `.json` |
| VAPI | Workflows → Select → Code button → Copy full JSON |
| Multi-state agents | Paste the complete JSON — all nodes and transitions |

Accept the paste as-is. Do not truncate — descriptions >10 KB are fine.

---

### Path B — Custom code / self-hosted agents

**Do not ask the user to "describe" their agent.** They will produce a summary. Instead, read the code yourself and synthesise the description.

#### Step 0 — Get code access

Ask the user to share their agent code. If they can share it (paste, file path, or repo link), proceed to Step 1.

**If no code access is possible** (user can't or won't share code), fall back to structured questioning — skip to Step 2-fallback below.

#### Step 1 — Read everything (when code is available)

Read:

- The main entry point / WebSocket handler
- The system prompt(s) — including dynamic parts, conditional blocks, language variants
- Every tool/function definition — name, parameters, what it returns, when it's called
- Any state machine, workflow engine, or routing logic
- Prompt templates, Jinja/f-string interpolations, dynamic variable injections
- Configuration files that affect behaviour (feature flags, A/B variants, per-tenant overrides)
- Any business rules hardcoded in the call handler (not just in the prompt)
- Error handling paths — what the agent says/does when a tool fails, times out, returns empty
- Transfer/escalation logic — conditions, what is said before transfer, where it goes
- Language/locale branching — different prompts or behaviours per language

#### Step 2 — Fill gaps (after reading code — only ask when code doesn't answer)

After reading the code, identify only what is genuinely unclear or missing — things the code doesn't make explicit. Ask targeted questions **only for those gaps**:

- If a branch exists but the response text isn't in the code: "In the `handle_timeout` branch — what does the agent say?"
- If a tool failure path isn't handled: "What should the agent say if `get_account_info` returns an error?"
- If there are conditional flows not in the main prompt: "Are there flows for after-hours calls, VIP callers, or returning customers?"

**Do not ask questions that the code already answers.** If the system prompt is clear, do not re-ask. If error handling is defined, do not ask about it. Only ask when genuinely uncertain.

#### Step 2-fallback — Structured questioning (when no code access)

Ask the user these questions one at a time. Do not move to the next until the current one is fully answered:

1. "What is the agent's main purpose — what does it do on a call?"
2. "Walk me through every type of call it handles, step by step. Start with the most common."
3. "For each flow: what does the agent say at each step? What does it do if the user says something unexpected?"
4. "What external tools or APIs does the agent call? For each tool: when is it called, what does it send, what does it do with the result?"
5. "What are the rules the agent must always follow? What must it never say or do?"
6. "How does it handle errors — tool failures, silence, unclear input, repeated misunderstandings?"
7. "Does it transfer calls? When? What does it say before transferring?"
8. "Are there any special cases — VIP callers, after-hours, returning customers, specific languages?"
9. "What variables change per call — customer name, account ID, appointment date, anything else passed in at the start?"

For each answer, ask follow-up questions until you have enough detail to write a complete description. Then proceed to Step 3.

#### Step 3 — Synthesise a complete description

Write the description yourself. Do not ask the user to write it. The description has exactly **two sections**:

---

**## Workflows**

Cover every single workflow the agent can handle. For each one, write it out in exhaustive detail — do not summarise. A workflow entry must describe:

- What triggers it (user intent, incoming context, tool result, state transition)
- Every step the agent takes, in order
- What the agent says at each step (exact phrasing patterns if deterministic, intent if flexible)
- Every tool call made — when triggered, what inputs are sent, what the agent does with each possible output (success, empty, error)
- Every branching condition — what changes the path, what each path leads to
- How it ends — confirmation, transfer, hang-up, hand-off to another flow
- What happens if the user goes off-script mid-flow

Write each workflow as a detailed narrative + step list. Do not condense. If there are 8 sub-branches, write all 8.

**## Behavioral Rules**

List every rule that governs the agent's behaviour across all workflows:

- What the agent must always do (greetings, confirmations, mandatory data collection)
- What the agent must never do or say
- Transfer and escalation rules — exact conditions, what is said before transferring
- Retry and fallback rules — how many times, what changes on each retry
- Language and tone rules — formality, vocabulary constraints, persona
- Timing rules — when to wait, when to move on, inactivity handling
- Data validation rules — what inputs are accepted, how invalid input is handled
- Any conditional rules (e.g. "only apply rule X if the user is a returning customer")

---

Do not stop writing until every workflow, every branch, every tool path, and every rule is captured. Length is not a concern — completeness is. If something is unclear from the code, ask the user — then write.

#### Step 4 — Confirm with the user

Show the synthesised description to the user and ask: "Does this capture everything your agent does? Anything missing or incorrect?"

Iterate until the user confirms it is complete.

---

## 4c. Note dynamic variable patterns

If the description contains `{{variableName}}` placeholders, flag them — Cekura will auto-detect them after agent creation. These are handled in [Phase 8](phase8-dynamic-variables.md).

---

## Phase 4 Gate

**Do not proceed with a vague or incomplete description. The description must cover every workflow, tool, rule, and edge case of the agent — not a summary of it. If in doubt, go deeper.**

Move to [Phase 5 — Create the Agent](phase5-create.md).

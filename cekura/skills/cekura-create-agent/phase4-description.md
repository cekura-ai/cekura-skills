# Phase 4 — Main Agent Description

> **Skip this phase** if the provider is VAPI, Retell, ElevenLabs, or Synthflow. These providers use `configure_from_provider: true` — the description (system prompt) is imported automatically during agent creation in Phase 5. Go directly to [Phase 5](phase5-create.md).

For all other providers, or if the user prefers to provide the description manually, continue below.

---

> **Start:** Announce "Starting Phase 4 — Main Agent Description" before doing anything in this phase.

## 4a. Why the description matters

The description is the **sole input for automatic scenario/evaluator generation**. Cekura reads it to understand every flow, rule, edge case, and constraint — then generates test scenarios from that understanding.

**A shallow description produces shallow scenarios. A complete description produces scenarios that actually test the main agent's real behaviour.**

There is no upper bound on detail. Spend as many tokens as needed. Do not rush this phase.

---

## 4b. Two paths: paste vs synthesise

### Path A — Cloud providers with a system prompt

Ask: "Can you paste your main agent's full system prompt or exported config?"

| Provider | How to export |
|----------|--------------|
| Retell | Agents → Select → Export → downloads `.json` |
| VAPI | Workflows → Select → Code button → Copy full JSON |
| Multi-state main agents | Paste the complete JSON — all nodes and transitions |

Accept the paste as-is. Do not truncate — descriptions >10 KB are fine.

---

### Path B — Custom code / self-hosted main agents

**Do not ask the user to "describe" their main agent.** They will produce a summary. Instead, read the code yourself and synthesise the description.

**The system prompt is in the code — not in a running server.** It exists as a constant, config file, or string in the codebase. Whether or not the server is running is irrelevant. If the codebase is accessible in the current session (open files, file paths, repo), read it directly without asking the user.

#### Step 0 — Get code access

If the codebase is already visible in the current session (e.g. open in the editor, files already read, or the user is working in the repo), proceed directly to Step 1 — do not ask the user to share code you can already see.

Only ask the user to share code if it is genuinely not accessible. If no code access is possible at all, fall back to structured questioning — skip to Step 2-fallback below.

#### Step 1 — Trace the full call chain and read everything

**Start at the entry point (WebSocket handler, main task, or HTTP endpoint) and follow every function call all the way down to where the final LLM prompt string is assembled.** Do not read only the handler — configuration parameters and injected values are often several layers deep in helper functions.

At each layer, read:

- The system prompt(s) — including dynamic parts, conditional blocks, language variants
- Every tool/function definition — name, parameters, what it returns, what the main agent does with each result
- Any state machine, workflow engine, or routing logic that changes what the main agent says
- **Every variable injected into the prompt at runtime** — f-strings, template rendering, string replacements, values passed via API/webhook at call start (these are dynamic variables — note them all as you go)
- Business rules hardcoded in the call handler that affect what the main agent says or does
- What the main agent says when a tool fails, times out, or returns empty
- Transfer/escalation conditions and what is said before transferring
- Language/locale branching — different responses per language

**While reading, maintain a running list of dynamic variable candidates** — flag any per-run input that shapes the main agent's observable behaviour, not just string interpolations. Anything supplied at call-start that changes what the main agent does qualifies: headers, config payloads, structured parameters, and template variables alike. These will be registered in Phase 8.

**Skip and ignore:**
- LLM provider selection, model names, temperature settings, retry logic, fallback chains
- Session management, keepalive, context window management, token limits
- Infrastructure code, logging, monitoring, deployment configuration
- Anything the caller cannot observe or experience
- **Knowledge base files** — do NOT read their content here. Just note their filenames/paths. They will be uploaded in Phase 7. Reading KB file contents in Phase 4 is wasted work.

#### Step 2 — Fill gaps (after reading code — only ask when code doesn't answer)

After reading the code, identify only what is genuinely unclear or missing — things the code doesn't make explicit. Ask targeted questions **only for those gaps**:

- If a branch exists but the response text isn't in the code: "In the `handle_timeout` branch — what does the main agent say?"
- If a tool failure path isn't handled: "What should the main agent say if `get_account_info` returns an error?"
- If there are conditional flows not in the main prompt: "Are there flows for after-hours calls, VIP callers, or returning customers?"

**Do not ask questions that the code already answers.** If the system prompt is clear, do not re-ask. If error handling is defined, do not ask about it. Only ask when genuinely uncertain.

#### Step 2-fallback — Structured questioning (when no code access)

Ask the user these questions one at a time. Do not move to the next until the current one is fully answered:

1. "What is the main agent's main purpose — what does it do on a call?"
2. "Walk me through every type of call it handles, step by step. Start with the most common."
3. "For each flow: what does the main agent say at each step? What does it do if the testing agent says something unexpected?"
4. "What external tools or APIs does the main agent call? For each tool: when is it called, what does it send, what does it do with the result?"
5. "What are the rules the main agent must always follow? What must it never say or do?"
6. "How does it handle errors — tool failures, silence, unclear input, repeated misunderstandings?"
7. "Does it transfer calls? When? What does it say before transferring?"
8. "Are there any special cases — VIP callers, after-hours, returning customers, specific languages?"
9. "What configuration does your main agent need at the start of each call to work correctly? For example — caller data, account information, session context, feature flags, or anything else that changes per call or per customer?"

For each answer, ask follow-up questions until you have enough detail to write a complete description. Note all runtime configuration values from question 9 as dynamic variables — they will be registered in Phase 8. Then proceed to Step 3.

#### Step 3 — Use the actual content, not a synthesis

**If the full system prompt is available verbatim — use it directly as the description.** Do not rewrite, summarise, or synthesise it. The actual prompt text is the description. Copy it as-is.

Only write a synthesised description when the prompt is genuinely scattered across code (f-strings, template fragments, conditional branches) and must be assembled into a single document. If you can read the complete prompt as a single string or file, use that string verbatim.

If you do need to synthesise (prompt is assembled from code), write it yourself — do not ask the user to write it.

**Minimum length: the description must be long enough to fully specify every workflow and every rule. A short paragraph is always wrong. Aim for at least 100 lines. If the description is shorter than that, you have not gone deep enough.**

**What belongs in the description — external behaviour only:**
The description captures what the main agent does from the caller's perspective — for a given input, what output can be expected. It describes conversational flows, decisions, and rules that are observable from the outside.

**What does NOT belong:**
- Internal implementation details: LLM selection, model names, retry logic, fallback chains, session management, keepalive mechanics, prompt construction, context window handling
- Infrastructure concerns: which provider is called, token limits, latency handling
- Anything the caller cannot observe or experience

The description should read as a specification of observable behaviour, not a code walkthrough.

---

**## Workflows**

Cover every single workflow the main agent can handle. For each one, write it out in exhaustive detail — do not summarise. A workflow entry must describe:

- What triggers it — what the caller says or does that starts this flow
- Every step the main agent takes, in order — what it says, what it asks, what it does
- For each step: what the main agent says for each possible caller response (cooperative, uncooperative, ambiguous, silent)
- Every tool call — what input the main agent sends, what each possible result means for what happens next
- Every branching condition — what causes the path to change, where each path goes
- How it ends — confirmation given, transfer initiated, call closed, hand-off to another flow
- What happens when the caller goes off-script mid-flow

Write each workflow as a detailed narrative + step list. Do not condense. If there are 8 sub-branches, write all 8. If a workflow has sub-states, document each sub-state separately.

**## Behavioral Rules**

Every rule that governs the main agent's observable behaviour across all workflows. Write each rule in full — do not summarise groups of rules into one line:

- What the main agent must always do — greetings, confirmations, mandatory data collection
- What the main agent must never say or do
- Transfer and escalation rules — exact conditions, what is said before transferring
- How the main agent handles no-response, unclear input, or repeated misunderstanding
- Language and tone rules — formality, vocabulary, persona
- Any conditional rules that apply only in specific situations

---

Do not stop writing until every workflow, every branch, every observable response, and every rule is captured. Length is not a concern — completeness is. If something is unclear from the code, ask the user — then write.

#### Step 4 — Confirm with the user

Show the synthesised description to the user and ask: "Does this capture everything your main agent does? Anything missing or incorrect?"

Iterate until the user confirms it is complete.

---

## 4c. Note dynamic variable patterns

If the description contains `{{variableName}}` placeholders, flag them — Cekura will auto-detect them after main agent creation. These are handled in [Phase 8](phase8-dynamic-variables.md).

---

## Phase 4 Gate

**Do not proceed with a vague or short description.** A few sentences or a short paragraph is always insufficient. The description must cover every workflow in step-by-step detail, every rule written out fully, every edge case documented. If the description is less than ~100 lines, it is not complete — go back and expand every section.

Announce: "Phase 4 complete." Then immediately begin [Phase 5 — Create the Agent](phase5-create.md) without waiting for the user.

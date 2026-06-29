# Optimization · Diagnose — Classify and Propose for Non-Early-End Failures

Third sub-phase of optimization. Takes the kept failure set from Collect plus the early-end-flagged subset (already diagnosed in [`early-end-call-diagnose.md`](early-end-call-diagnose.md)) and produces a complete set of proposed edits for everything that isn't an early-end failure. Bundles the early-end proposals into the same presentation so the user reviews one combined diff per iteration.

This sub-phase ends with the user-facing presentation gate (Step DIAGNOSE.5). After approval (or auto-mode auto-accept), control flows to [`apply.md`](apply.md).

Outputs split into four streams; any may be empty for a given iteration:

- **Prompt edits** —
  - *VAPI:* change the system message of one or more squad members (or the lone assistant for non-squad agents).
  - *ElevenLabs:* change the system prompt at `conversation_config.agent.prompt.prompt`. One prompt per agent (no squads).
  - *Self-hosted:* change the system prompt wherever the run-setup points — a source file (via `Edit`), a database row, or rendered for the user to copy when there's no reachable live target.
- **Tool-config edits** —
  - *VAPI:* change a tool's name / description / parameter schema / spoken messages / handoff destinations, OR change which tools a member references via `toolIds` (add a new tool, remove a reference, create a new tool).
  - *ElevenLabs:* change a referenced standalone tool's `name` / `description` / `api_schema` (webhook) / `parameters` (client) via `PATCH /v1/convai/tools/{id}`, change a legacy inline tool in the agent's `prompt.tools` array, OR change which tools the agent references via `prompt.tool_ids` (add a new tool via `POST /v1/convai/tools`, remove a reference). Do **not** propose edits to spoken `messages`, `destinations`, squad `toolIds`, or `request-start` content — those are VAPI-only. Built-in tools (`end_call`, `transfer_to_agent`, etc.) are config flags, not editable bodies — surface as hand-offs.
  - *Self-hosted:* edit tool definitions wherever they're reachable — tool-definition blocks in a source file (via `Edit`; these are *live* edits), the tools row in a database, or Cekura mock-tool definitions (`description` / `mock_data` / `freetext_params`) via `mcp__cekura__aiagents_partial_update` with the full `mock_tools` list (GET first → merge → PATCH; mock-tool edits only change the testing contract, not the live implementation). Always empty when there's no reachable live target (render-only) — tool findings become hand-offs. Do **not** propose spoken `messages`, `destinations`, `toolIds`, or `request-start` edits — those are VAPI-only.
- **Orchestration-code edits** — *self-hosted, only when the run-setup edits source code.* When the root cause is in the user's conversation-orchestration code rather than prompt wording — e.g., aggressive history truncation that drops earlier qualification answers, missing tool-result forwarding back to the LLM, keepalive / retry logic that silently loses turns, state slicing that breaks mid-conversation — propose a minimal `Edit` to the relevant function. Scope is limited to plumbing/orchestration: how messages flow, how conversation state is preserved, how the loop is structured. **Out of scope**: business logic (what a tool computes, what an external service returns), security-sensitive code (API keys, auth, signing, secrets), dependency / requirements changes, framework upgrades. VAPI, ElevenLabs, and self-hosted runs that don't edit source code (DB row / mock tools / render-only) never produce this stream — code-rooted findings there become upstream hand-offs.
- **Upstream hand-off recommendations** — for failures rooted in missing / wrong dynamic variables, no prompt or tool edit fixes the issue. Surface the variable mismatch with a concrete pointer to where it should be set (test profile, scenario config, squad / project defaults, upstream caller). For self-hosted, also consider that the live agent code may simply not be reading the variable Cekura is passing, and that runtime state may not be observable. In VAPI / ElevenLabs and self-hosted runs that don't edit source code, also surface code-shaped findings here.

## Pre-flight check

Before any Step DIAGNOSE.x work, verify the upstream sub-phases completed:

- Collect completed (kept failure set populated, provider call state recorded — Steps COLLECT.1–5).
- Early-end-call-diagnose completed (early-end-flagged failures already have proposed edits, OR the pass-through case fired with zero flagged failures — Steps EARLY.1–3).
- Both diagnose sub-phases agree on the same kept failure set — no silent set-widening between them.

If any of the above is missing, return control to the orchestrator — Collect or early-end-call-diagnose did not complete cleanly.

## Step DIAGNOSE.1 — Read both data streams

Re-fetch the source-of-truth artifacts if more than a few minutes have passed since Setup Step 1.3:

- *VAPI:* `/assistant/{id}` and every referenced `/tool/{id}` — VAPI dashboard edits don't notify Cekura, and a stale local copy will produce a wrong PATCH body.
- *ElevenLabs:* `GET /v1/convai/agents/{id}` and every referenced `GET /v1/convai/tools/{id}` — ElevenLabs dashboard edits don't notify Cekura, and a stale local copy will produce a wrong PATCH body (especially the prompt-path nesting).
- *Self-hosted:* re-read the editable surface wherever the run-setup points — re-`Read` the source file (the user may have edited it between iterations in their IDE), re-run the DB fetch query, or re-fetch the Cekura `mock_tools`. For a rendered (no-live-target) prompt, re-read only if its source was a file path; pasted prompts don't change unless the user pastes a new one.

Note dynamic-variable placeholders (`{{variableName}}`) in both prompts and tool messages / parameter schemas — they're injected per call and must not be touched by edits unless the user explicitly asks.

Variable-state observations from Collect Step COLLECT.4 are co-equal input. Compare each `{{...}}` placeholder in the prompt or tool definitions against what actually appeared in the failing runs' variable values. A placeholder the prompt depends on but the runtime never received is the most common root cause of "agent stalled / improvised / hallucinated" failure shapes — and it's invisible if you only read the prompt.

If the prompt is empty or clearly not the production prompt (one-line summary, etc.), **stop and ask** — the agent isn't fully configured, or the user is running prod somewhere the skill can't see. For self-hosted source-file edits this also catches the "user pointed at the wrong file" case.

## Step DIAGNOSE.2 — Map each non-early-end failure to its governing artifacts AND variable state

For each kept failure **that was NOT flagged by early-end-call-diagnose**, locate every artifact that *should* have governed that behavior, AND record the variable state at the moment of failure:

- **Prompt sections** — quote the exact lines from the responsible assistant's system message (the speaker in the relevant transcript turn, for squads).
- **Tool definitions** — if the failure involves a tool call, pull the relevant tool's definition. Quote `function.description`, the relevant property in `function.parameters`, the offending `messages[*].content`, or the suspect `destinations` entry.
- **Orchestration code** *(self-hosted, only when the run-setup edits source code)* — for failures whose shape suggests a code-level bug rather than a prompt issue (agent "forgets" earlier turns, tool result never reaches the LLM, conversation drops mid-flow, keepalive loses messages, history is sliced too aggressively), open the source file and locate the relevant function — typically the conversation loop, history-management block, or message-forwarding logic. Quote the exact lines and note window sizes, slice indices, or branching conditions that match the failure shape.
- **Variable state** — for every `{{...}}` placeholder referenced by the relevant prompt section or tool definition, record what actually appeared in the runtime variable values: `null`, empty arrays, missing keys, name mismatches, or literal placeholder strings that survived into rendered messages or tool-call arguments.
- **Adjacent provider & telephony logs** *(VAPI / ElevenLabs modes — when COLLECT.4's adjacent-logs subsection pulled them)* — for tool-shaped failures, quote the relevant lines from the **VAPI `/logs`** entry (LLM request/response around the tool turn, tool webhook HTTP status + response body, latency timing) or from the **ElevenLabs conversation detail** (system-tool firings — `voicemail_detection`, `transfer_to_agent`, `end_call` — with their timestamps, plus the authoritative `termination_reason`). For telephony-shaped failures (call-not-connected, very short duration, one-sided audio), quote the **Twilio call log**'s `status`, `SipResponseCode`, and any `ErrorCode` / `ErrorMessage`. These often pin the diagnosis decisively: a 4xx/5xx webhook response in VAPI logs is a tool-config edit (URL / auth / schema), not a prompt edit; a `voicemail_detection` invocation in the ElevenLabs conversation is the agent doing exactly what the prompt instructed (so an outcome-metric failure on that scenario is metric-scoping, not agent behavior — hand-off to `cekura-metric-improvement`); a Twilio `SipResponseCode ≥ 400` is Upstream/data and no prompt or tool edit fixes it. If COLLECT.4 recorded `adjacent_logs: not fetched (auth unavailable)` for the failure, be more conservative about Upstream/data classification — note the unconfirmed-upstream caveat and propose the narrow prompt/tool edit only when the call-artifact signals are strong on their own.

If no prompt or tool artifact governs the failure AND variable state looks healthy, mark it "uncovered" — that's a strong gap signal *and* a cue to check orchestration code when the self-hosted run-setup edits source code. If variable state is malformed, the failure is likely upstream regardless of how clean the prompt looks. Most failures have signal in more than one dimension; track all matches.

Early-end-flagged failures are skipped here (they were already diagnosed); their proposed edits are folded in at Step DIAGNOSE.5 presentation.

## Step DIAGNOSE.3 — Classify each non-early-end failure

| Bucket | What it looks like |
|--------|--------------------|
| **Gap** | No section addresses this situation, AND variable state is healthy. The agent improvised and got it wrong. |
| **Conflict** | Two clauses contradict, OR a clause contradicts a tool definition, OR a clause contradicts the desired behavior implied by the failure. |
| **Ambiguity** | One section addresses it but the wording is vague enough the agent could read it either way, AND variable state is healthy. |
| **CodeBug** *(self-hosted, source-file edits only)* | The prompt clearly instructs the right behavior but the agent demonstrably can't follow it because the orchestration code prevents it — e.g., earlier qualification answers are no longer in the LLM's context window (history truncation), tool results aren't forwarded back, conversation state is sliced in a way that drops required information, oscillating verdicts on the same scenario suggest stochastic context loss. The prompt is fine; the plumbing is broken. |
| **Upstream/data** | Variable state shows the runtime didn't have what the prompt or tool requires: `null` / absent / empty, key-name mismatch, or literal `{{...}}` survived into rendered messages or tool-call arguments. |

If you can't tell, default to **Ambiguity** and flag for the user. A failure can have both an Upstream/data root AND a Gap/Conflict/Ambiguity/CodeBug component; pick the bucket that, if fixed, would produce the largest behavior change — usually Upstream/data, because phantom prompt fixes against broken variable state will fail re-validation the same way and obscure whether the prompt edit helped. Surface the secondary component as "deferred — re-evaluate after upstream fix".

**The "agent ended the call early" CodeBug pattern is NOT scored here** — that's the early-end-call-diagnose sub-phase's job. If a failure looks like early-end but wasn't flagged by EARLY.1, it failed one of the three flag conditions (e.g., transcript was long enough, or testing-agent did terminate). Re-classify under one of the buckets above; do not retroactively early-end-flag it.

**Other CodeBug signals worth watching for** (self-hosted, source-file edits only):
- The same scenario flips pass/fail across iterations on prompt-only changes (oscillation) and the failure mode involves "agent forgot earlier info" or "agent re-asked despite an explicit don't-re-ask clause" → suspect history truncation or context-window slicing.
- The agent literally repeats `{{varName}}` AND the runtime variable was provided → the rendering / substitution code in the user's file is broken, not Cekura's injection.
- A tool call fires but the LLM never sees its result on the next turn (transcript shows tool call → silence → user prompt re-asked) → tool-result forwarding back to the LLM is broken.
- Conversations drop mid-flow with no error and no end-of-call message → keepalive / connection-management code.
- Repeated prompt-wording iterations on the same failure produce no behavior change (no-change signature) → root cause is below the prompt layer.

## Step DIAGNOSE.4 — Propose a change for each diagnosis

Use the smallest change that fixes the failure — don't rewrite paragraphs to fix one missed step.

**Before generating the standard narrow edits, check the same-shape iteration counter for each failing scenario.** If a scenario has had the same expected-outcome bullet fail for **three consecutive iterations** under edits that targeted the same surface, the kind of edit being applied isn't the kind of edit that fixes this — iter 4 of the same shape is wasted compute. For *that scenario*, do NOT generate another narrow edit at the same surface. Instead, **shift the search space outward**: reason about what level of change would actually move this failure given the editable surfaces in the current mode (different layer, different mechanism, different model, different abstraction, evaluator-side rather than agent-side, etc.), generate the candidate approaches that fit, and surface them with their trade-offs in the DIAGNOSE.5 presentation. **Wait for the user to pick one before doing anything else for that scenario.** Do NOT autonomously pick — wider changes carry real cost (compute, refactor, behavior change beyond the failing scenario). The exception is when the user has already explicitly directed an approach in the conversation. Other failing scenarios in the same iteration that haven't tripped the same-shape counter continue down the normal narrow-edit path.

**One family of wider-search patterns worth weighing for repeated narrow-instruction failures: focused-prompt-override patterns.** When the main LLM call keeps drowning a specific narrow behavior under the weight of its many other instructions — and adding yet another constraint to the main system prompt has demonstrably failed — the fix is to give the LLM a *minimal targeted system prompt* for the critical turn (or sub-task) so the failing instruction isn't competing with the agent's other goals. Two implementation shapes; **prefer the first**:

1. **Same-call system-prompt swap (preferred).** For the critical turn, replace the main system prompt with a narrow override prompt that contains only the failing instruction plus what to produce. The LLM still does ONE call per turn — no extra inference, no orchestration of two outputs — but its system message is now focused on the single behavior. Detect the trigger from the latest user message (keyword scan, simple classifier) and swap the system prompt before the call; restore (or re-build a turn-local message list) after. Often pairs with **also truncating prior conversation context for that turn** so the established conversational pattern doesn't drown the override — a long history of one agent style biases the LLM more than the system prompt does (the system prompt is one signal, the history is many). The trigger function and turn-local message handling live in orchestration code; the override prompt itself is a prompt edit (and gets scored by the Overfitting Gate, even when it sits next to control-flow code). Trade-offs: small trigger function + a turn-local message-list path in code; **no extra LLM cost**. Good fit when the failing behavior is well-localized to a recognizable user-turn shape (specific question pattern, specific request type) AND the agent's normal output on other turns should be unchanged.

2. **Separate sub-agent LLM call (fallback).** Route the critical turn (or a sub-task within it) to a *second* LLM call alongside the main call, with its own minimal targeted system prompt that omits the main prompt entirely. The main flow then incorporates the sub-agent's output deterministically (prefix the response, gate a branch, return a single classification consumed by the main flow). Trade-offs: an extra LLM call adds latency and per-turn cost; orchestration code grows more (two outputs to combine, ordering / failure-mode handling between them). Use this only when the same-call swap can't work — e.g., when both the main behavior AND the focused behavior need to fire on the same turn and their outputs must be combined under deterministic rules, or when the focused decision is a classification/gate consumed by the main flow rather than a user-facing utterance.

For either shape: reason about whether the pattern fits *this* failure's shape before proposing it, and don't preempt the user's choice between this and other wider options (model swap, programmatic guard, flow restructure, evaluator hand-off). When you do surface this pattern in DIAGNOSE.5, list shape 1 first as the recommended path and shape 2 as the fallback — that ordering reflects cost (shape 2 doubles per-turn LLM cost on triggered turns) and complexity (shape 2 has two outputs to combine), not novelty.

- **Upstream/data → no edit, hand off.** This skill cannot fix upstream root causes. Surface a hand-off naming each missing/wrong variable, what the prompt expected, what the runtime saw, and where to inject (test profile, squad / assistant-level dynamic variables, upstream caller). For self-hosted, also consider whether the live agent code is reading the variable correctly, and note that runtime state may not be fully observable. If a prompt edit could *also* harden the agent against the missing variable, note it as a secondary candidate but do not include it in the iteration's edit set unless the user asks. If **all** kept failures (including the early-end ones from EARLY) are Upstream/data, this iteration produces zero edits — surface and stop the loop early.
- **Prompt edits.** Gap → **add** a clause next to the closest related section, matching existing voice/format. Conflict → **edit** or **remove** the contradictory clause; if both have legitimate use cases, **scope** them with explicit conditions. Ambiguity → **edit for specificity**; replace vague verbs with concrete steps; add a checklist if there are >2 required actions. When the failure shape matches a documented recurring pattern (e.g., DTMF / IVR navigation lacking same-turn digit announcement), use the canonical shape in [`../../references/phase-3-diagnosis.md`](../../references/phase-3-diagnosis.md) § Recurring prompt-edit patterns rather than re-inventing the wording.
- **Tool-config edits — VAPI mode.** Four sub-types: (a) **edit** an existing tool's `function.description` / parameters / spoken `messages` / handoff `destinations`; (b) **add** a new tool when a flow step requires data the agent doesn't have (POST `/tool` then PATCH the assistant's `toolIds`); (c) **remove a tool reference** from a specific member when squad inheritance is exposing a tool that member shouldn't use (PATCH `model.toolIds`, leave the tool definition); (d) **delete a tool** — rare, only after cross-referencing every squad member's `toolIds` and confirming no references remain.
- **Tool-config edits — ElevenLabs mode.** Four sub-types: (a) **edit** a referenced standalone tool's `tool_config.description` / `api_schema` (webhook) / `parameters` (client) via `PATCH /v1/convai/tools/{id}`, or a legacy inline tool in the agent's `prompt.tools` array; (b) **add** a new tool when a flow step requires data the agent doesn't have (POST `/v1/convai/tools` then PATCH the agent's `prompt.tool_ids`); (c) **remove a tool reference** from `prompt.tool_ids` when a tool shouldn't fire (leave the standalone definition — other agents may reference it); (d) **delete a tool** — rare, only after checking `usage_stats` / `access_info` confirms no other agent references it. No spoken `messages`, no `destinations`, no per-member scoping (single agent). Built-in tools (`end_call`, `transfer_to_agent`, etc.) are config flags — surface a hand-off, don't edit them as tool bodies.
- **Tool-config edits — self-hosted.** Edit tool definitions wherever the run-setup makes them reachable: (a) a **tool-definition block in a source file** via `Edit` (the schema flows into the live agent on restart) — or **add** a new entry to the tools list; tool *implementations* (the function body that computes a result or calls an external service) stay out of scope; (b) **Cekura mock tools** — edit `description` / `mock_data` / `freetext_params` or add a mock tool via `mcp__cekura__aiagents_partial_update` with the full `mock_tools` array (GET → merge → PATCH); the agent's *real* tool implementation lives in the user's code, so if a mock edit matters only because the live signature differs, surface a hand-off ("update the live tool signature to match"); (c) a **tools row in a database** via the user's write query. None when there's no reachable live target (render-only) — surface as hand-offs. Do **not** propose `messages` / `destinations` / `toolIds` edits (VAPI-only).
- **Orchestration-code edits — self-hosted, source-file edits only.** When the diagnosis is **CodeBug**, propose the smallest `Edit` that fixes the plumbing. Common shapes:
  - *History truncation too aggressive* — bump the window size, switch from raw last-N to "system + last-N user/assistant turns", or summarize-and-prepend collected state before truncation. Example: a `if len(history) > 12: tail = history[-10:]` slice that drops earlier qualification answers — raise to 24 or higher, and ensure the resulting list still starts at a `user` message to avoid orphaned `tool` messages.
  - *Tool result not forwarded* — add the missing append to `history` after the tool call returns, OR fix a broken message-role mapping (`"role": "tool"` with the right `tool_call_id`).
  - *Keepalive / connection drops* — adjust the ping interval, fix a coroutine that's cancelled prematurely, ensure `await websocket.send(...)` isn't dropped during a long tool call.
  - *State sliced incorrectly* — fix the index math, the role-filtering condition, or the dedup logic.

  **Rules**: One `Edit` per logical change; use 5–10 lines of surrounding context per anchor. Show the user the diff before applying (auto mode renders for transparency, then proceeds). Do NOT touch business logic, tool-implementation bodies, security/auth code, secrets, dependency lists, or framework imports. Do NOT rewrite whole functions — change the minimum needed. If the fix requires non-trivial refactor (new helper functions, multi-file changes, dependency additions), surface as a hand-off instead of attempting it.

**Cluster related diagnoses.** If 5 failures all stem from the same missing clause OR the same noisy `request-start` message, propose one edit that covers all 5. Prompt and tool edits can also cluster across artifacts: e.g., "remove tool reference from member X **and** add a clause to its prompt explaining what to do at that decision point instead" is one logical change, surfaced as a paired edit.

**De-conflict with early-end-call proposals.** If an EARLY.3 proposal touches the same prompt section (or same source file lines) that a DIAGNOSE.4 proposal would also touch, merge them into a single edit covering both intents. Do NOT produce two overlapping `Edit` calls — they'll race in [`apply.md`](apply.md) and one will fail with an ambiguous-match error.

For the full classification table with examples, the tool-edit anti-patterns (do-not-rename, do-not-tighten-schema, do-not-mass-delete), the manual-vs-automated-improver guidance, and diagnose anti-patterns, see [`../../references/phase-3-diagnosis.md`](../../references/phase-3-diagnosis.md).

## Step DIAGNOSE.5 — Present the combined proposal to the user

Show every proposed change (early-end edits from EARLY.3 PLUS diagnose edits from DIAGNOSE.4) as a **before/after** block grouped by source sub-phase + bucket + edit surface, with the failures each edit addresses. End with a summary line:

```
6 changes proposed and 1 upstream hand-off across 14 prompt-following failures
  Early-end-call: 2 prompt edits across 5 flagged failures
  Rest-of-diagnose: 4 changes (2 prompt edits, 2 tool edits; 1 gap, 2 conflicts, 1 ambiguity)
  Upstream: 1 hand-off (missing {{accountId}} variable)
```

**Default (`auto_mode: true`): skip the routine approval prompt.** Still render the before/after blocks and the summary line for transparency, then proceed straight to [`apply.md`](apply.md) with **all** proposed edits accepted. Do not silently downgrade or filter the proposal. Upstream hand-offs are still surfaced. If the iteration produced **zero** prompt/tool/orchestration edits (all failures were Upstream/data — including the early-end ones), there is nothing to apply — surface the hand-offs and stop the loop the same way the non-auto path would. **Even in auto mode, pause and ask if the proposal is low-confidence, the edit set is unusually large for the failure count, or any of the "ask for feedback" triggers from the orchestrator's How to Use section apply.**

**When `auto_mode: false`: this gate fires on every iteration, not just the first.** Ask the user to accept all, accept a subset, or push back; do not move to [`apply.md`](apply.md) until they explicitly confirm.

For the exact before/after templates (prompt edit, tool-definition edit, `toolIds` reference removal, upstream hand-off), see [`../../references/phase-3-diagnosis.md`](../../references/phase-3-diagnosis.md).

## Hand-off to apply

After Step DIAGNOSE.5 (and user approval in non-auto mode), hand off to [`apply.md`](apply.md) with:

- The full approved edit set: early-end-call edits (from EARLY.3) merged with diagnose edits (from DIAGNOSE.4), de-conflicted in Step DIAGNOSE.4.
- The set of upstream hand-offs to surface alongside the apply (these inform but do not block apply).
- The failure-id mapping per edit (so the iteration log records which failures each edit was meant to fix).

If the combined approved edit set is empty (zero prompt/tool/code edits — all-Upstream or all-KEEP-on-low-confidence), DO NOT hand off to apply. Surface the upstream hand-offs and stop the loop.

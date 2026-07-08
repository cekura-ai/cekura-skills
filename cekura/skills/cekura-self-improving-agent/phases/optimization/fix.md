# Optimization · Fix — Classify Failures and Propose Edits

First optimization sub-phase. Consumes the kept failure set from Collect, triages
early-end-call failures first (FIX.1), classifies the rest, and bundles every
proposal into one combined diff. Ends at the presentation gate (FIX.6); then
control flows to [`apply.md`](apply.md).

Outputs split into four streams (any may be empty):

- **Prompt edits** — change the system prompt on the editable surface: a squad member's system message (VAPI, or the lone assistant); `conversation_config.agent.prompt.prompt` (ElevenLabs, one per agent); or wherever the run-setup points (self-hosted — source file via `Edit`, DB row, or rendered for the user when there's no live target).
- **Tool-config edits** — change a tool's `name` / `description` / parameter (or `api_schema`) or which tools are referenced. VAPI adds spoken `messages`, handoff `destinations`, and per-member `toolIds`. ElevenLabs edits standalone tools via `PATCH /v1/convai/tools/{id}` (or legacy inline `prompt.tools`), references via `prompt.tool_ids`. Self-hosted edits tool-definition blocks in source (`Edit`, live on restart), a DB tools row, or Cekura mock tools (`description` / `mock_data` / `freetext_params` via `mcp__cekura__aiagents_partial_update` — GET → merge → PATCH the full `mock_tools` list; mock edits change only the testing contract). **VAPI-only shapes — spoken `messages`, `destinations`, squad `toolIds`, `request-start` — are filtered out for ElevenLabs and self-hosted.** Built-in tools (`end_call`, `transfer_to_agent`) are config flags, not editable bodies — surface as hand-offs. Empty when there's no live target (render-only) → tool findings become hand-offs.
- **Code edits** *(self-hosted, only when the run-setup edits owned source code)* — when the root cause is in owned code rather than prompt wording (aggressive history truncation dropping earlier answers, tool-result not forwarded to the LLM, keepalive/retry losing turns, state slicing that breaks mid-conversation). Owned code includes a **vendored or forked SDK that lives inside the source tree the run-setup edits** — that is in scope (CodeBug), not Upstream. Scope is plumbing/orchestration only. **Out of scope always:** business logic (what a tool computes / an external service returns), auth / secrets / signing, dependencies, framework upgrades, LLM-client config. VAPI, ElevenLabs, and self-hosted runs that don't edit source never produce this stream — code-rooted findings there become upstream hand-offs. A code edit lands via `Edit` + redeploy, is re-validated on Cekura (the bug forced to reproduce in-sim per REPRO.3e), then ships as a PR.
- **Upstream hand-offs** — failures rooted in missing / wrong dynamic variables (no prompt or tool edit fixes them). Name the variable, what the prompt expected, what the runtime saw, and where to inject (test profile, scenario config, squad / project defaults, upstream caller). "Upstream" is reserved for code the user genuinely cannot edit; owned code is never Upstream. For self-hosted also consider the live code may not be reading the variable Cekura passes, and runtime state may be unobservable. In VAPI / ElevenLabs and self-hosted-no-source runs, code-shaped findings surface here too.

## Pre-flight check

Before any FIX.x work, verify Collect completed: kept set populated and provider
call state recorded (COLLECT.1–5), **including Signal 5 (end-of-call attribution)** —
FIX.1 depends on it. If any is missing, return control to the orchestrator.

## Step FIX.1 — Triage early-end-call failures first

Screen the kept set for one pattern before anything else: the **main agent ended the
call before the scenario's required steps completed**. From the verdict these look like
"the agent skipped a field", but the call cut off before any later-step wording could
fire — so a general diagnosis on the same run wastes the edit. Catch these first; the
early-end cause dominates any other diagnosis on that run.

Flag a kept failure as early-end when **both** hold (needs Signal 5 from COLLECT.4; if
it's absent, return to COLLECT.4):

- **The main agent ended the call** — `ended_reason == "main-agent-ended-call"` (self-hosted / ElevenLabs; ElevenLabs also when the transcript shows the built-in `end_call` firing before required steps), or `endedReason ∈ {assistant-ended-call, assistant-said-end-call-phrase}` (VAPI). Caller / timeout / silence / disconnect endings are **not** early-end — only main-agent-caused endings count.
- **The failed / 🟡 bullets describe steps the call never reached** — e.g. "appointment was not booked", "did not get to ask" — not "the agent did step X wrong" (that's wrong-behavior-during-call, handled by FIX.2+).

For each flagged failure, find the layer that let the call end early and propose the
smallest fix, clustering failures that share a layer:

- **Closure / "wrap-up" rules in the system prompt** (all modes — almost always the right layer). *Gap*: no closure rule → add "confirm you have collected [required fields] before saying goodbye". *Ambiguity*: "wrap up at a natural pause" → "wrap up only after every required step is complete". *Conflict*: "be efficient / end quickly" vs a multi-step requirement → scope efficiency to *after* required steps.
- **End-of-call detection in owned code** (self-hosted source edits only) — a keyword scan that closes the loop regardless of state; add a `required_fields_collected` check before the loop accepts a closing turn. Includes a forked/vendored SDK in the tree.
- **Tool `destinations` (VAPI) / built-in `end_call` (ElevenLabs)** — rare; the built-in `end_call` config is a hand-off, not an editable body.

Pass-through when nothing matches. These are **proposals only** — they merge with the
FIX.5 edits at FIX.6. Everything not flagged here flows to FIX.2.

## Step FIX.2 — Read both data streams

Re-fetch source-of-truth artifacts if more than a few minutes have passed since Setup 1.3 (dashboard edits don't notify Cekura; a stale copy produces a wrong PATCH):

- *VAPI:* `/assistant/{id}` + every referenced `/tool/{id}`.
- *ElevenLabs:* `GET /v1/convai/agents/{id}` + every referenced `GET /v1/convai/tools/{id}` (watch prompt-path nesting).
- *Self-hosted:* re-read the editable surface — re-`Read` the source file (user may have edited between iterations), re-run the DB fetch, or re-fetch `mock_tools`. A rendered prompt: re-read only if its source was a file path.

Note `{{variableName}}` placeholders in prompts and tool definitions — injected per call; do not touch unless the user asks. Variable-state observations from COLLECT.4 are co-equal input: compare each placeholder the prompt/tools depend on against what actually appeared in the failing runs. A placeholder the prompt needs but the runtime never received is the most common root cause of "stalled / improvised / hallucinated" shapes and is invisible if you only read the prompt.

If the prompt is empty or clearly not production (one-line summary, etc.), **stop and ask** — the agent isn't fully configured, the run is somewhere the skill can't see, or (self-hosted) the user pointed at the wrong file.

## Step FIX.3 — Map each remaining failure to its governing artifacts AND variable state

For each kept failure **not flagged as early-end in FIX.1**, locate every artifact that should have governed the behavior, and record variable state at failure:

- **Prompt sections** — quote exact lines from the responsible assistant's system message (the speaker in the relevant turn, for squads).
- **Tool definitions** — if a tool call is involved, quote `function.description`, the relevant `function.parameters` property, the offending `messages[*].content`, or the suspect `destinations` entry.
- **Owned code** *(self-hosted, source-file edits only)* — for shapes suggesting a code bug (agent "forgets" earlier turns, tool result never reaches the LLM, conversation drops mid-flow, keepalive loses messages, history sliced too aggressively), open the source file and locate the conversation loop / history-management / message-forwarding logic. Quote exact lines; note window sizes, slice indices, branching conditions matching the failure shape. This includes a vendored/forked SDK in the tree.
- **Variable state** — for every placeholder referenced, record what appeared: `null`, empty arrays, missing keys, name mismatches, or literal `{{...}}` that survived into rendered messages / tool-call args.
- **Adjacent provider & telephony logs** *(VAPI / ElevenLabs, when COLLECT.4 pulled them)* — for tool-shaped failures quote the **VAPI `/logs`** (LLM request/response around the tool turn, webhook HTTP status + body, latency) or **ElevenLabs conversation detail** (system-tool firings `voicemail_detection` / `transfer_to_agent` / `end_call` with timestamps + authoritative `termination_reason`); for telephony-shaped failures (not-connected, very short, one-sided) quote the **Twilio** `status` / `SipResponseCode` / `ErrorCode`. These often pin the diagnosis: a 4xx/5xx webhook response is a tool-config edit (URL / auth / schema), not a prompt edit; a `voicemail_detection` firing is the agent obeying the prompt (so an outcome-metric failure there is metric-scoping → hand off to `cekura-metric-improvement`); a Twilio `SipResponseCode ≥ 400` is Upstream/data. If COLLECT.4 recorded `adjacent_logs: not fetched (auth unavailable)`, be conservative about Upstream/data — note the unconfirmed-upstream caveat and propose a narrow edit only when call-artifact signals are strong alone.

If no artifact governs the failure AND variable state is healthy, mark it "uncovered" — a strong gap signal, and a cue to check owned code (self-hosted source edits). If variable state is malformed, the failure is likely upstream regardless of prompt cleanliness. Most failures have signal in more than one dimension; track all matches. Early-end-flagged failures are skipped here; their edits fold in at FIX.6.

## Step FIX.4 — Classify each remaining failure

| Bucket | What it looks like |
|--------|--------------------|
| **Gap** | No section addresses this situation AND variable state healthy. Agent improvised, got it wrong. |
| **Conflict** | Two clauses contradict, OR a clause contradicts a tool definition, OR a clause contradicts the behavior the failure implies is desired. |
| **Ambiguity** | One section addresses it but wording is vague enough to read either way AND variable state healthy. |
| **CodeBug** *(self-hosted, source-file edits only)* | Prompt clearly instructs the right behavior but owned code prevents it — history truncation drops earlier answers, tool results not forwarded, state slicing drops required info, oscillating verdicts on one scenario suggest stochastic context loss. Prompt fine; plumbing broken. Includes bugs in a vendored/forked SDK in the tree. |
| **Upstream/data** | Runtime lacked what the prompt/tool requires: `null` / absent / empty, key-name mismatch, or literal `{{...}}` survived into rendered messages / tool-call args. |

If unsure, default to **Ambiguity** and flag. A failure can have both an Upstream/data root AND a Gap/Conflict/Ambiguity/CodeBug component; pick the bucket whose fix produces the largest behavior change — usually Upstream/data, since prompt fixes against broken variable state fail re-validation the same way and obscure whether the prompt edit helped. Surface the secondary as "deferred — re-evaluate after upstream fix".

An early-end failure that wasn't flagged in FIX.1 failed a flag condition (transcript long enough, testing-agent did terminate) — classify it under a bucket above, don't retroactively flag.

**Other CodeBug signals** (self-hosted, source edits only):
- Same scenario flips pass/fail across iterations on prompt-only changes AND the mode is "forgot earlier info" / "re-asked despite a don't-re-ask clause" → history truncation / context-window slicing.
- Agent literally repeats `{{varName}}` AND the runtime provided it → the user's rendering/substitution code is broken, not Cekura's injection.
- Tool call fires but the LLM never sees the result next turn (tool call → silence → user re-asked) → tool-result forwarding broken.
- Conversations drop mid-flow, no error, no end-of-call message → keepalive / connection-management.
- Repeated prompt-wording iterations on one failure produce no behavior change → root cause below the prompt layer.

## Step FIX.5 — Propose a change for each diagnosis

Smallest change that fixes the failure — don't rewrite paragraphs for one missed step.

**Same-shape escape hatch.** Before generating narrow edits, check the same-shape counter per failing scenario. If a scenario's same expected-outcome bullet has failed **three consecutive iterations** under edits targeting the same surface, a fourth narrow edit at that surface is wasted. For that scenario, do NOT generate another; **shift the search space outward** — reason about what level of change would actually move it given the current mode's editable surfaces (different layer / mechanism / model / abstraction, evaluator-side vs agent-side), surface the candidates with trade-offs in FIX.6, and **wait for the user to pick** before doing anything else for that scenario. Do NOT autonomously pick — wider changes carry real cost. Exception: the user already directed an approach. Other scenarios that haven't tripped the counter continue the normal narrow path.

**Focused-prompt-override family** (one wider-search pattern for repeated narrow-instruction failures). When the main LLM call keeps drowning a narrow behavior under its many other instructions and adding another main-prompt constraint has demonstrably failed, give the LLM a minimal targeted system prompt for the critical turn. Two shapes; **prefer the first**:

1. **Same-call system-prompt swap (preferred).** For the critical turn, replace the main system prompt with a narrow override containing only the failing instruction + what to produce. Still ONE call per turn — no extra inference. Detect the trigger from the latest user message (keyword scan / simple classifier), swap before the call, restore after. Often pairs with **truncating prior context for that turn** so the established pattern doesn't drown the override (history is many signals; the system prompt is one). The trigger function + turn-local message handling live in code; the override prompt is a prompt edit (scored by the Overfitting Gate even next to control-flow code). No extra LLM cost. Good when the behavior is localized to a recognizable user-turn shape and other turns should be unchanged.
2. **Separate sub-agent LLM call (fallback).** Route the critical turn (or sub-task) to a second LLM call with its own minimal prompt omitting the main prompt; the main flow incorporates its output deterministically (prefix the response, gate a branch, consume a classification). Trade-offs: extra latency + per-turn cost; more orchestration (two outputs to combine, ordering / failure handling). Use only when the swap can't — both behaviors must fire on the same turn and combine under deterministic rules, or the focused decision is a gate/classification consumed by the main flow.

For either: confirm the pattern fits this failure's shape, don't preempt the user's choice among wider options, and in FIX.6 list shape 1 first (cost/complexity ordering, not novelty).

- **Upstream/data → no edit, hand off.** This skill cannot fix upstream root causes. Name each missing/wrong variable, what the prompt expected, what the runtime saw, where to inject. For self-hosted, also consider whether the live code reads the variable, and note runtime state may be unobservable. A prompt edit that could *also* harden against the missing variable is a secondary candidate — not in the edit set unless the user asks. If **all** kept failures (including FIX.1's) are Upstream/data, this iteration produces zero edits — surface and stop early.
- **Prompt edits.** Gap → **add** a clause next to the closest section, matching voice/format. Conflict → **edit/remove** the contradictory clause; if both are legitimate, **scope** with explicit conditions. Ambiguity → **edit for specificity**; replace vague verbs with concrete steps; add a checklist for >2 required actions. For documented recurring shapes (e.g. DTMF/IVR lacking same-turn digit announcement) use the canonical form in [`../../references/phase-3-diagnosis.md`](../../references/phase-3-diagnosis.md) § Recurring prompt-edit patterns.
- **Tool-config edits.** Four sub-types across modes: (a) **edit** an existing tool's `description` / parameters (VAPI also spoken `messages` / `destinations`; ElevenLabs `api_schema` webhook / `parameters` client via `PATCH /v1/convai/tools/{id}` or legacy inline `prompt.tools`; self-hosted a source tool-definition block via `Edit`, or mock-tool `description`/`mock_data`/`freetext_params`); (b) **add** a tool when a flow step needs data the agent lacks (VAPI POST `/tool` then PATCH `toolIds`; ElevenLabs POST `/v1/convai/tools` then PATCH `prompt.tool_ids`; self-hosted add a tools-list entry or mock tool); (c) **remove a tool reference** (VAPI `model.toolIds`; ElevenLabs `prompt.tool_ids`; leave the definition — others may reference it); (d) **delete a tool** — rare, only after confirming no remaining references (VAPI every member's `toolIds`; ElevenLabs `usage_stats`/`access_info`). Self-hosted: tool *implementations* (function bodies calling external services) stay out of scope; if a mock edit matters only because the live signature differs, hand off ("update the live tool signature"). **Do not propose VAPI-only shapes for ElevenLabs / self-hosted.** Built-in tools → hand-off.
- **Code edits — self-hosted, source-file edits only.** When the diagnosis is **CodeBug**, propose the smallest `Edit`:
  - *History truncation too aggressive* — bump the window, switch raw last-N to "system + last-N user/assistant turns", or summarize-and-prepend collected state before truncation. E.g. `if len(history) > 12: tail = history[-10:]` dropping earlier answers → raise to 24+, ensure the result still starts at a `user` message (no orphaned `tool` messages).
  - *Tool result not forwarded* — add the missing append to `history` after the tool returns, or fix a broken role mapping (`"role": "tool"` with the right `tool_call_id`).
  - *Keepalive / connection drops* — adjust ping interval, fix a prematurely-cancelled coroutine, ensure `await websocket.send(...)` isn't dropped during a long tool call.
  - *State sliced incorrectly* — fix index math, role-filtering, or dedup logic.

  **Rules:** one `Edit` per logical change, 5–10 lines of context per anchor; show the diff before applying (auto mode renders, then proceeds). Do NOT touch business logic, tool-implementation bodies, security/auth/secrets, dependency lists, or framework imports. Don't rewrite whole functions. If the fix needs a non-trivial refactor (new helpers, multi-file, dependency additions), hand off instead. The edit lands via `Edit` + redeploy, is re-validated on Cekura, then ships as a PR.

**Cluster related diagnoses.** One edit covering 5 failures from the same missing clause or noisy `request-start`. Cross-artifact clusters count as one logical change (e.g. "remove tool reference from member X **and** add a prompt clause for what to do at that decision point" → one paired edit).

**De-conflict with the FIX.1 proposals.** If a FIX.1 early-end proposal touches the same prompt section (or same source lines) a FIX.5 proposal would, **merge into one edit** covering both intents. Do NOT produce two overlapping `Edit` calls — they race in [`apply.md`](apply.md) and one fails with an ambiguous-match error.

For the full classification table with examples, tool-edit anti-patterns (do-not-rename, do-not-tighten-schema, do-not-mass-delete), manual-vs-automated-improver guidance, and fix anti-patterns, see [`../../references/phase-3-diagnosis.md`](../../references/phase-3-diagnosis.md).

## Step FIX.6 — Present the combined proposal

Show every proposed change (FIX.1 early-end edits PLUS FIX.5 edits) as **before/after** blocks grouped by bucket + edit surface, with the failures each addresses. End with a summary line:

```
6 changes proposed and 1 upstream hand-off across 14 prompt-following failures
  Early-end-call: 2 prompt edits across 5 flagged failures
  Rest: 4 changes (2 prompt edits, 2 tool edits; 1 gap, 2 conflicts, 1 ambiguity)
  Upstream: 1 hand-off (missing {{accountId}} variable)
```

**`auto_mode: true` (default): skip the approval prompt.** Still render the before/after blocks + summary for transparency, then proceed to [`apply.md`](apply.md) with all edits accepted. Don't silently downgrade or filter; upstream hand-offs still surface. If the iteration produced **zero** prompt/tool/code edits (all Upstream/data, including early-end), surface the hand-offs and stop the loop like the non-auto path. Even here, **pause and ask** if the proposal is low-confidence, the edit set is unusually large for the failure count, or any orchestrator "ask for feedback" trigger applies.

**`auto_mode: false`: this gate fires every iteration.** Ask the user to accept all / accept a subset / push back; don't move to [`apply.md`](apply.md) until they confirm.

For exact before/after templates (prompt edit, tool-definition edit, `toolIds` removal, upstream hand-off), see [`../../references/phase-3-diagnosis.md`](../../references/phase-3-diagnosis.md).

## Hand-off to apply

After FIX.6 (and approval in non-auto mode), hand off to [`apply.md`](apply.md) with:

- The full approved edit set: FIX.1 early-end edits merged with FIX.5 edits, de-conflicted in FIX.5.
- The upstream hand-offs to surface alongside apply (inform but don't block).
- The failure-id mapping per edit (for the iteration log).

If the combined approved set is empty (all-Upstream or all-KEEP-on-low-confidence), do NOT hand off — surface the upstream hand-offs and stop the loop.

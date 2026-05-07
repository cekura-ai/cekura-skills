---
name: cekura-self-improving-agent
description: >
  Use when the user asks to "improve my agent", "self-improving agent",
  "auto-tune my agent", "iterate on my agent prompt", "fix my agent based
  on test results", "close the loop on agent quality", "auto-improve agent
  prompt", "use eval results to improve agent", or describes agent
  self-improvement, prompt iteration from run results, or automated agent
  quality loops. Covers the full diagnose → propose → apply → re-validate
  loop for VAPI agents, including squad members and tool definitions.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.8.0"
---

# Cekura Self-Improving Agent

## Purpose

Close the loop on agent prompt and tool-config quality. Ingest evaluation signal (scenario IDs to run, completed runs, a result batch, or production call logs), classify failures, diagnose where the prompt or tool config has gaps, conflicts, or ambiguities, propose targeted edits, apply them, and re-run validation — iterating until the agent reaches **100% pass rate on the validation set** or the iteration cap is reached.

**Two data streams, one diagnosis.** Every iteration reads two artifacts in parallel: (1) the agent's prompt + tool definitions, and (2) the provider-side call state for each failing run (variable injection, rendered system messages, tool-call arguments). A failure that *looks* like a prompt bug is often a missing dynamic variable; a failure that *looks* upstream is sometimes a prompt/tool conflict that survives correct injection. Mapping failures only to prompt sections produces phantom fixes.

**What's editable.** For VAPI agents, both **system prompts** and **tool definitions** are editable from this skill. Tool config covers function declarations, referenced tool definitions (name, description, parameters, spoken `messages` like `request-start` / `request-complete` / `request-failed`, and handoff `destinations`), and which tools each squad member references via its `toolIds` array.

**Exit gate.** The voice/channel/infra filter informs *what to fix* (Phase 3 only proposes edits for prompt-following failures), not *when to stop*. Any remaining failure of any class keeps the loop alive. Only the iteration cap or a genuine 100% pass ends the loop.

Currently supported only for **VAPI** agents. Retell support is intentionally disabled and will be re-enabled in a future revision.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

VAPI write operations (assistant PATCH, tool create / PATCH / delete) are not exposed through Cekura platform tools — they go directly to the VAPI API with `VAPI_KEY`. See [references/phase-4-apply-validate.md](references/phase-4-apply-validate.md) for full curl bodies.

## How to Use This Skill

This is an **interactive, multi-iteration workflow**. The user supplies an `agent_id` plus exactly one of: `scenario_ids`, `result_id`, `run_ids`, or `call_ids`. Optionally `max_iterations` (default 10).

The four phases run in order, with the last looping until the agent passes:

1. **Phase 1 — Verify Agent and Provider Support.** Fetch the agent, gate on `assistant_provider == vapi`. Halt with a clear error otherwise. For VAPI, also pull the live assistant or squad config (and every referenced tool) from VAPI directly — VAPI is the source of truth for prompts and tool definitions throughout this skill.
2. **Phase 2 — Collect Failures and Inspect Provider Call State.** Branch on input type. For `scenario_ids`, run them first and wait for completion; otherwise fetch the supplied runs / call logs. Pre-filter human-reviewed successes. Accumulate expected-outcome and metric failures, **discard voice/channel failures**, and **for every kept failure also pull the provider call state** (variable injection, rendered system message, tool-call arguments). Both streams flow into Phase 3.
3. **Phase 3 — Diagnose and Propose Changes.** Synthesize the prompt/tool artifacts AND the variable-state findings to attribute each failure to its actual root cause: prompt Gap / Conflict / Ambiguity, tool-config issue, or **Upstream/data** (missing or malformed dynamic variables that no prompt edit can fix). Produce minimal scoped edits for the prompt-and-tool roots; surface upstream-rooted failures with a clear hand-off. Show before/after blocks and wait for explicit approval. **This gate fires on every iteration**, not just the first.
4. **Phase 4 — Apply, Validate, and Iterate.** PATCH the prompt and/or tool definitions, confirm provider-side sync, run validation against the relevant scenarios, re-collect failures with the same Phase 2 classification. Exit only on **100% pass rate**; otherwise feed the new failure summary back into Phase 3. Loop up to `max_iterations` times.

The user gates the workflow at every Phase 3 → Phase 4 boundary, after seeing the proposed edits. Phase 1 → Phase 2 → Phase 3 runs straight through. There is no autonomous-iteration mode — every PATCH is preceded by an explicit user OK on that iteration's diff. The user can interrupt mid-loop at any time.

## Phase 1: Verify Agent and Provider Support

### Step 1.1 — Get the agent ID

Ask the user for the agent ID. If they don't know it, list their agents so they can pick one.

### Step 1.2 — Fetch agent details and gate on provider

Retrieve the agent and read `assistant_provider`:

- **Supported**: `vapi` → continue
- **Anything else** (`retell`, `elevenlabs`, `livekit`, `pipecat`, `sip`, custom websocket, missing/empty) → **stop the workflow** and return a clear error to the user

`retell` is in the unsupported list on purpose — Retell handling is temporarily disabled. Do not bypass the gate. If `assistant_provider` is empty, treat as unsupported and point the user at `cekura-create-agent` (Phase 3: Configure Provider Integration). Compare lowercased — be defensive against `VAPI` in user input.

For the exact error-message shape, the Retell-specific note, and 404 handling, see [references/phase-1-vapi-fetch.md](references/phase-1-vapi-fetch.md).

### Step 1.3 — Fetch live VAPI assistant / squad and every referenced tool

VAPI is the source of truth for the prompt — the Cekura `description` field is informational only and is **not** read or written by this skill. Phase 1 fetches the live VAPI state directly using `VAPI_KEY` (env var; never echo or write to file). The `assistant_id` field on the Cekura agent record holds either a VAPI assistant id or a VAPI squad id — try the assistant endpoint first, fall back to squad on 404.

For each assistant (one for single-assistant agents, every member for squads), capture: `id`, `name`, the system prompt (`model.messages[*].content` where `role == "system"`), inline `model.tools`, the array of referenced `model.toolIds`, plus `voice`, `transcriber`, `firstMessage` (used to sanity-check the voice filter in Phase 2). For squads, all members are in scope by default; Phase 3 attributes failures to whichever member was speaking.

**Then fetch every referenced tool** (`https://api.vapi.ai/tool/{id}` per unique id). Tool definitions drive Phase 3 diagnosis as much as the prompt does. Capture each tool's `id`, `type`, `function.name` / `function.description` / `function.parameters`, `messages` (especially `request-start.content` — spoken on the call), and `destinations` (for handoff / transferCall tools). Cross-reference back to which member assistants reference each tool.

Surface a compact summary to the user before continuing (assistant or squad name, member count, prompt lengths, tool counts and names, voice provider). For the exact summary shape, full curl bodies, and edge cases (401, 404 on both endpoints, empty-squad, inline-only members, response-shape changes), see [references/phase-1-vapi-fetch.md](references/phase-1-vapi-fetch.md).

## Phase 2: Collect Failures and Inspect Provider Call State

### Step 2.1 — If input is `scenario_ids`: execute, then wait

Skip for the other input types. Pick voice mode for VAPI (default). Trigger the run, capture the `result_id`, then poll until terminal (every ~30s, capped at 15 min for voice / 5 min for text). Once complete, treat as a `result_id` input.

### Step 2.2 — Fetch the runs or call logs

Branch on input type to populate a list of items to inspect:

| Input | Tool path |
|-------|-----------|
| `result_id` | Fetch the result batch — every run inside has scenario info, status, transcript, expected-outcome verdict, and metric evaluations. |
| `run_ids` | Bulk fetch — same per-run shape as above. |
| `call_ids` | Fetch each call log individually — transcripts and metric evaluations, no expected outcome. |

### Step 2.3 — Pre-filter, accumulate, and discard voice failures

**Pre-filter `reviewed_success`.** Drop every run / call log a human has reviewed and marked successful (top-level `review_status == "reviewed_success"`, `reviewed_success: true`, `human_review.outcome == "success"`, or any equivalent override). The human review supersedes machine verdicts — feeding these into Phase 3 will push edits that contradict the reviewer. Track the skipped count separately. If skipped metric failures cluster on one or two metrics, hint to the user that those metrics may need `cekura-metric-improvement`.

**Accumulate failures from the survivors:**

1. **Expected-outcome failures** *(runs only, not call logs)* — verdict `fail` / not-met / false. Capture scenario id + name, transcript excerpt, expected-outcome text, verdict explanation.
2. **Metric failures** *(both runs and call logs)* — any attached metric verdict `FAIL` (skip `PASS`, `N/A`, `VALID_SKIP`). Capture metric id + name, FAIL explanation, and offending transcript snippet.

A single run can contribute to both classes. Track them separately — Phase 3 treats them differently (expected-outcome failures usually point at agent prompt logic; metric failures may point at either the agent or the metric).

**Voice/channel filter.** This skill only optimizes prompt + tool config, so discard failures whose root cause is the voice channel: audio quality, ASR errors, TTS issues, latency / dead air / talk-over, dropped connections, errored runs, or failures from metrics that explicitly score voice quality. **Keep** failures where the agent had the input it needed and still behaved wrong (skipped a step, asked wrong info, hallucinated, missed a handoff, went off-topic, missed an end-of-call requirement). When in doubt, **keep the failure** — false keeps are recoverable in Phase 3; false discards silently lose signal.

For text-mode runs and chat call logs the filter is a no-op — every collected failure passes through. Track the discarded count separately from the `reviewed_success` count.

### Step 2.4 — Inspect provider call state (default, every iteration)

Run this for **every kept failure**. The output feeds Phase 3 alongside the failure verdicts. Skipping this step is the most common way the loop produces phantom prompt fixes for issues actually rooted upstream.

For each kept failing run / call log, fetch the provider call object and record:

- `assistantOverrides.variableValues` — what Cekura passed to VAPI at call start (Signal 1: intent).
- `artifact.variableValues` — what VAPI saw after merging overrides + defaults (Signal 2: runtime).
- The rendered system message (`artifact.messages[0].content`, or per-activation messages for squads) — search for literal `{{...}}` substrings (Signal 3: substitution failure).
- Tool-call arguments (`artifact.messages[*].toolCalls[*].function.arguments`) — flag literal placeholders, empty arrays where data was expected, hallucinated values (Signal 4: what the LLM produced).
- For squads: `artifact.assistantActivations` — which member was active per activation.

Bulk-fetch runs (NOT result-fetch — provider call details aren't included there) or fetch call logs individually. Payloads are large (250–500 KB per run); use `jq` or python rather than re-reading the whole blob. Direct-VAPI fallback (`GET https://api.vapi.ai/call/{id}`) is available when `provider_call_details` is missing or stale.

Group observations when patterns repeat — "all 3 failed runs share the same variable-injection failure" is more actionable than per-run repetition. For the full per-signal decision tree (key absent vs. wrong-name vs. literal-placeholder-survives), the squad per-member-message caveat, and the bare-comma-separated-string gotcha for bulk-retrieve, see [references/dynamic-variables-debugging.md](references/dynamic-variables-debugging.md).

### Step 2.5 — Build the failure summary

Group failures by **scenario** (for runs) or by **metric** (for call logs). The summary feeds Phase 3 and is also shown to the user for transparency. Report on separate lines: items inspected, `reviewed_success` skipped, voice-related discarded, prompt-following kept. Include the provider-call-state observations from Step 2.4 inline.

**Phase 2 does not pause for approval** — the user-facing gate is at every Phase 3 → Phase 4 transition. The one exception: if failures are dominated by one or two metrics with thin signal, stop and suggest hand-off to `cekura-metric-improvement` — those are metric-quality issues, not agent-quality issues, and Phase 3 won't fix them.

**Do not surface small-sample / overfitting caveats to the user.** Even when the input is a single run, do not include lines like "with N runs any fix risks overfitting" or "5–10+ items would be a healthier signal" — internal calibration of confidence is fine; user-facing hedging reads as a stall. The user has already chosen to act on the input they have.

For the full summary template, edge cases (zero failures / all-errored / mixed inputs), and the exact wording around the metric-quality hand-off, see [references/phase-2-failure-collection.md](references/phase-2-failure-collection.md).

## Phase 3: Diagnose and Propose Changes

Take the **kept** failure summary from Phase 2 — including both verdicts (Step 2.3) AND provider call state (Step 2.4) — and the **current agent prompt and tool definitions**. Synthesize all three into a root-cause attribution per failure, then produce a concrete, reviewable set of edits (or, for upstream-rooted failures, a hand-off recommendation).

Outputs split into three streams; any may be empty for a given iteration:

- **Prompt edits** — change the system message of one or more squad members (or the lone assistant for non-squad agents).
- **Tool-config edits (VAPI)** — change a tool's name / description / parameter schema / spoken messages / handoff destinations, OR change which tools a member references via `toolIds` (add a new tool, remove a reference, create a new tool).
- **Upstream hand-off recommendations** — for failures rooted in missing / wrong dynamic variables, no prompt or tool edit fixes the issue. Surface the variable mismatch with a concrete pointer to where it should be set (test profile, scenario config, squad / project defaults, upstream caller).

### Step 3.1 — Read both data streams

Re-fetch the live VAPI assistant(s) and every referenced tool (`/assistant/{id}` and `/tool/{id}`) if more than a few minutes have passed since Phase 1.3 — VAPI dashboard edits don't notify Cekura, and a stale local copy will produce a wrong PATCH body. Note dynamic-variable placeholders (`{{variableName}}`) in both prompts and tool messages / parameter schemas — they're injected per call and must not be touched by edits unless the user explicitly asks.

Variable-state observations from Step 2.4 are co-equal input. Compare each `{{...}}` placeholder in the prompt or tool definitions against what actually appeared in the failing runs' variable values. A placeholder the prompt depends on but the runtime never received is the most common root cause of "agent stalled / improvised / hallucinated" failure shapes — and it's invisible if you only read the prompt.

If the prompt is empty or clearly not the production prompt (one-line summary, etc.), **stop and ask** — the agent isn't fully configured, or the user is running prod somewhere the skill can't see.

### Step 3.2 — Map each kept failure to its governing artifacts AND variable state

For each kept failure, locate every artifact that *should* have governed that behavior, AND record the variable state at the moment of failure:

- **Prompt sections** — quote the exact lines from the responsible assistant's system message (the speaker in the relevant transcript turn, for squads).
- **Tool definitions** — if the failure involves a tool call, pull the relevant tool's definition. Quote `function.description`, the relevant property in `function.parameters`, the offending `messages[*].content`, or the suspect `destinations` entry.
- **Variable state** — for every `{{...}}` placeholder referenced by the relevant prompt section or tool definition, record what actually appeared in the runtime variable values: `null`, empty arrays, missing keys, name mismatches, or literal placeholder strings that survived into rendered messages or tool-call arguments.

If no prompt or tool artifact governs the failure AND variable state looks healthy, mark it "uncovered" — that's a strong gap signal. If variable state is malformed, the failure is likely upstream regardless of how clean the prompt looks. Most failures have signal in more than one dimension; track all matches.

### Step 3.3 — Classify each failure

| Bucket | What it looks like |
|--------|--------------------|
| **Gap** | No section addresses this situation, AND variable state is healthy. The agent improvised and got it wrong. |
| **Conflict** | Two clauses contradict, OR a clause contradicts a tool definition, OR a clause contradicts the desired behavior implied by the failure. |
| **Ambiguity** | One section addresses it but the wording is vague enough the agent could read it either way, AND variable state is healthy. |
| **Upstream/data** | Variable state shows the runtime didn't have what the prompt or tool requires: `null` / absent / empty, key-name mismatch, or literal `{{...}}` survived into rendered messages or tool-call arguments. |

If you can't tell, default to **Ambiguity** and flag for the user. A failure can have both an Upstream/data root AND a Gap/Conflict/Ambiguity component; pick the bucket that, if fixed, would produce the largest behavior change — usually Upstream/data, because phantom prompt fixes against broken variable state will fail re-validation the same way and obscure whether the prompt edit helped. Surface the secondary component as "deferred — re-evaluate after upstream fix".

### Step 3.4 — Propose a change for each diagnosis

Use the smallest change that fixes the failure — don't rewrite paragraphs to fix one missed step.

- **Upstream/data → no edit, hand off.** This skill cannot fix upstream root causes. Surface a hand-off naming each missing/wrong variable, what the prompt expected, what the runtime saw, and where to inject (test profile, squad / assistant-level dynamic variables, upstream caller). If a prompt edit could *also* harden the agent against the missing variable, note it as a secondary candidate but do not include it in the iteration's PATCH set unless the user asks. If **all** kept failures are Upstream/data, this iteration produces zero PATCHes — surface and stop the loop early.
- **Prompt edits.** Gap → **add** a clause next to the closest related section, matching existing voice/format. Conflict → **edit** or **remove** the contradictory clause; if both have legitimate use cases, **scope** them with explicit conditions. Ambiguity → **edit for specificity**; replace vague verbs with concrete steps; add a checklist if there are >2 required actions.
- **Tool-config edits (VAPI).** Four sub-types: (a) **edit** an existing tool's `function.description` / parameters / spoken `messages` / handoff `destinations`; (b) **add** a new tool when a flow step requires data the agent doesn't have (POST `/tool` then PATCH the assistant's `toolIds`); (c) **remove a tool reference** from a specific member when squad inheritance is exposing a tool that member shouldn't use (PATCH `model.toolIds`, leave the tool definition); (d) **delete a tool** — rare, only after cross-referencing every squad member's `toolIds` and confirming no references remain.

**Cluster related diagnoses.** If 5 failures all stem from the same missing clause OR the same noisy `request-start` message, propose one edit that covers all 5. Prompt and tool edits can also cluster across artifacts: e.g., "remove tool reference from member X **and** add a clause to its prompt explaining what to do at that decision point instead" is one logical change, surfaced as a paired edit.

For the full classification table with examples, the tool-edit anti-patterns (do-not-rename, do-not-tighten-schema, do-not-mass-delete), the manual-vs-automated-improver guidance, and the Phase 3 anti-patterns, see [references/phase-3-diagnosis.md](references/phase-3-diagnosis.md).

### Step 3.5 — Present the proposal to the user

Show every proposed change as a **before/after** block grouped by bucket and edit surface (prompt vs. tool), with the failures it addresses. End with a summary line: `4 changes proposed and 1 upstream hand-off across 12 prompt-following failures (2 prompt edits, 2 tool edits; 1 gap, 2 conflicts, 1 ambiguity, 1 upstream).`

**This gate fires on every iteration, not just the first.** Ask the user to accept all, accept a subset, or push back; do not move to Phase 4 until they explicitly confirm which edits to apply for this iteration. After Phase 4 PATCHes and re-validates, the loop re-enters Phase 3 with a fresh proposal against the post-edit state — that proposal is again subject to the same approval gate before its PATCH lands.

For the exact before/after templates (prompt edit, tool-definition edit, `toolIds` reference removal, upstream hand-off), see [references/phase-3-diagnosis.md](references/phase-3-diagnosis.md).

## Phase 4: Apply, Validate, and Iterate

This phase is a **loop**. Each iteration: apply the approved edits → run validation → diagnose new failures → propose more changes → apply again. Exit only on **100% pass rate** (zero failures of any class) or when the iteration cap is hit. Do not exit just because the latest failures look like voice/infra rather than prompt issues — first re-attribute squad failures to whichever member is now responsible and consider mitigation edits.

**Early-exit shortcut.** If Phase 2 collected zero failures of any class from the initial input, Phase 3 was skipped — report success and stop. If Phase 2 found failures but they are *all* voice/infra/tool, do not auto-exit; run the same logic as the "kept = 0 but total > 0" branch in Step 4.6 first.

### Step 4.1 — Apply the edits in dependency order

Take the **approved** subset of changes from Step 3.5. Apply in this order:

1. **Tool-definition edits first** (PATCH `/tool/{id}`).
2. **New tool creation** next (POST `/tool`), capturing the new id.
3. **Assistant `model.toolIds` updates** (add / remove references) bundled into the assistant PATCH.
4. **System prompt edits** in the same assistant PATCH as the `toolIds` updates — one PATCH per assistant.

The order matters: a new tool must exist before the assistant PATCH lands; bundling `toolIds` + prompt into one assistant PATCH keeps "tools available" and "instructions about those tools" consistent.

Show the user the **final merged prompt** (or unified diff if long) AND a list of all tool changes for transparency, then proceed — no second confirmation step.

### Step 4.2 — Confirm provider sync

Step 4.1 PATCHed VAPI directly. Re-fetch `/assistant/{id}` and every edited / created `/tool/{id}` and verify the changed fields landed. Don't skip the tool re-fetch — VAPI's tool PATCH semantics replace nested objects wholesale, and a malformed body can silently wipe `messages` or `destinations` while still returning 200.

### Step 4.3 — Build the validation set

Pick the validation set based on the **original input type**:

| Original input | Validation set |
|----------------|----------------|
| `scenario_ids` | Reuse the same scenario IDs. |
| `result_id` / `run_ids` | Extract `scenario_id` from every run (already fetched in Phase 2.2). De-duplicate. |
| `call_ids` | Synthesize one scenario per call from its transcript. Cache new scenario IDs on the first iteration so subsequent iterations reuse them. |

Default to running only the failure set (the cleanest signal that the edit fixed *those specific failures*). The user can request the full set to guard against regressions; never widen the validation set mid-loop without telling the user — the stopping criterion depends on a stable comparison set.

### Step 4.4 — Run validation

Execute the validation set in voice mode for VAPI. Capture `result_id`, poll until terminal (same 30s cadence and 15-min cap as Phase 2.1).

### Step 4.5 — Re-collect failures with the same Phase 2 logic

Run the new result through Phase 2 end to end — `reviewed_success` pre-filter, accumulate, voice filter, **and re-run Step 2.4 provider-call-state inspection** against the new runs. Re-running Step 2.4 each iteration matters: a Phase 4.1 PATCH only changes prompts and tool definitions; it cannot change variable injection. If iteration N-1's failures were rooted upstream, iteration N's variable state should look identical — that's the signal the upstream issue is unresolved (and the loop should stop and surface, not iterate further).

### Step 4.6 — Decide: exit or loop

The exit criterion is **100% pass rate on the validation set** — zero failures of any class.

- **100% pass** → success. Report final pass rate, cumulative diff, stop.
- **Kept failures > 0** → loop normally. Feed the new failure summary and the **current (post-edit) prompt** back into Phase 3, surface a fresh proposal, and **wait for explicit approval** before Step 4.1.
- **Kept = 0 but total > 0** → do **not** exit yet. Work in order: (1) **re-classify with fresh eyes** — a tool error *handled badly* by the agent is a prompt issue; for squads, re-attribute by speaker. (2) **Consider mitigation edits** — both prompt (better retries / fallback / escalation) and tool config (noisy `request-start`, misleading `request-failed`, over-broad `function.description`, wrong handoff destination, self-referencing destination). Surface both as Phase 3 candidates next iteration. (3) Only after both above are exhausted → surface a clear stop with residual failures, hand off to the appropriate skill (`cekura-create-agent` for tool/config issues; backend team for upstream service errors).

**Iteration cap.** Default 10. The user can override with `max_iterations` or stop / extend mid-loop ("keep going" / "stop"). Don't loop silently past the cap. After hitting the cap, surface what's been fixed, what's still failing, and a recommended next skill.

For the full PATCH curl bodies, the tool-backup pattern, the loop guardrails (oscillation detection, validation-set stability, cumulative-diff tracking), and the per-iteration scope rules, see [references/phase-4-apply-validate.md](references/phase-4-apply-validate.md).

## Common Pitfalls

- **Skipping the variable-state inspection (Step 2.4) and mapping failures only to prompt sections.** Produces phantom prompt fixes for failures actually rooted upstream. A prompt diagnosis can read perfectly self-consistent ("the prompt and tool description conflict — fix it") and still be wrong if the runtime never received the variables the prompt depends on.
- **Quitting the loop the moment failures look non-prompt.** The exit gate is 100% pass rate or the iteration cap — not "first sight of an infra-shaped failure." Re-classify with fresh eyes (a noisy `request-start` is a tool-config question; for squads the relevant prompt may live in a member that hasn't been touched yet) before declaring upstream.
- **Skipping the per-iteration user gate.** The skill applies edits to a live agent. Every PATCH must be preceded by explicit approval of *that iteration's* proposed diff. Don't claim a previous approval covers later iterations. Conversely, Phase 1 → Phase 2 → Phase 3 should not pause for approval at all — Phase 2's summary is informational, not a gate.
- **Skipping the Phase 4.2 provider-sync re-fetch.** VAPI's PATCH semantics replace nested objects wholesale; a malformed body can silently wipe `messages` or `destinations` while returning 200. Without re-fetch confirmation, the loop validates against state you can't see and never converges.
- **Editing dynamic-variable placeholders (`{{...}}`).** They're owned by the calling system. Touch them only if the user explicitly asks.
- **Patching a tool's spoken `messages` to mask a prompt issue.** If the agent says the wrong thing, fix the prompt that drives the tool call, not the tool's `request-start` message — unless the tool's message is itself the offending utterance (e.g., a verbose `request-start` that fires repeatedly).
- **Iterating with a noisy metric.** If most kept failures come from one metric whose explanations look subjective, the metric is probably miscalibrated — hand off to `cekura-metric-improvement` first, otherwise the loop will keep "fixing" the prompt to satisfy a flawed judge.
- **Surfacing small-sample / overfitting caveats.** Internal calibration of confidence is fine; user-facing hedging reads as a stall. The user has already chosen the input they have.
- **Treating expected-outcome failures and metric failures the same.** Expected-outcome failures are first-class signal about agent behavior. Metric failures may reflect either the agent or the metric — be more skeptical.
- **Mass-deleting "unused"-looking tools.** A tool with no references in this agent's squad members may still be referenced elsewhere. Prefer reference removal over delete; deletion is irreversible from this skill.

## Next Steps

After this skill, the user typically needs:

- For tool / KB / provider-integration issues surfaced in Phase 4.6 → invoke **cekura-create-agent**
- For metric-quality issues (noisy or miscalibrated metric judges) → invoke **cekura-metric-improvement**
- For test-suite gaps (the eval set itself is too narrow) → invoke **cekura-eval-design**
- For metric definition / design questions → invoke **cekura-metric-design**

## Documentation

- Public docs: https://docs.cekura.ai
- Concepts: https://docs.cekura.ai/documentation/key-concepts/
- Integrations: https://docs.cekura.ai/documentation/integrations/
- VAPI assistant API: https://docs.vapi.ai/api-reference/assistants
- VAPI tool API: https://docs.vapi.ai/api-reference/tools

## Additional Resources

### Reference Files (loaded on demand)

- **`references/phase-1-vapi-fetch.md`** — Provider-gate error message shapes, VAPI assistant + squad + tool fetch curl bodies, member summary template, and Phase 1 edge cases (401 / 404, empty squads, inline-only members, response-shape changes).
- **`references/phase-2-failure-collection.md`** — Full failure-summary template, the metric-improvement hand-off wording, edge cases (no failures / all-errored / mixed inputs), and the no-overfitting-caveats rule.
- **`references/phase-3-diagnosis.md`** — Full classification table with examples, before/after templates per edit surface, tool-edit anti-patterns, the manual-vs-automated-improver guidance, and Phase 3 anti-patterns.
- **`references/phase-4-apply-validate.md`** — VAPI PATCH / POST / DELETE curl bodies, tool-backup pattern, validation-set construction details, loop guardrails (oscillation, stability, cumulative diff), and iteration-cap exit messaging.
- **`references/dynamic-variables-debugging.md`** — Per-signal decision tree for variable state, where each signal lives in the Cekura payload, the direct-VAPI fallback, the `runs_bulk_retrieve` bare-string gotcha, and squad per-member-message caveats.

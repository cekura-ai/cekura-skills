---
name: self-improving-agent
description: >
  This skill should be used when the user asks to "improve my agent",
  "self-improving agent", "auto-tune my agent", "iterate on my agent prompt",
  "fix my agent based on test results", "close the loop on agent quality",
  "auto-improve agent prompt", "use eval results to improve agent", or discusses
  agent self-improvement, prompt iteration from run results, or automated
  agent quality loops in the Cekura platform.
version: 0.3.0
---

# Cekura Self-Improving Agent

## Purpose

Close the loop on agent prompt quality. Ingest evaluation signal (scenario IDs to run, completed runs, a result batch, or production call logs), filter to **prompt-following failures only** (drop voice/channel issues), diagnose where the prompt has gaps, conflicts, or ambiguities, propose targeted edits, apply them, and re-run validation — iterating until the agent passes or the iteration cap is reached.

Currently supported only for **VAPI** and **Retell** agents (Phase 1 gates this).

## How to Use This Skill

This is an **interactive, multi-iteration workflow**. The user supplies an `agent_id` plus exactly one of: `scenario_ids`, `result_id`, `run_ids`, or `call_ids`. Optionally `max_iterations` (default 10).

The four phases run in order, with the last looping until the agent passes:

1. **Phase 1 — Verify Agent and Provider Support.** Fetch the agent, gate on `assistant_provider ∈ {vapi, retell}`. Halt with a clear error otherwise. For VAPI, also pull the live assistant or squad config from VAPI directly (using `VAPI_KEY` plus `VAPI_ASSISTANT_ID` or `VAPI_SQUAD_ID`) — VAPI is the source of truth for the prompt; the Cekura `description` is not consulted or edited.
2. **Phase 2 — Collect Failures.** Branch on input type. For `scenario_ids`, run them first and wait for completion; otherwise fetch the supplied runs / call logs. Accumulate expected-outcome and metric failures, **discard voice/channel failures**, and present a structured summary.
3. **Phase 3 — Propose Prompt Changes.** Map kept failures to prompt sections, classify each as Gap / Conflict / Ambiguity, and produce minimal scoped edits. Show the user before/after blocks and wait for explicit approval.
4. **Phase 4 — Apply, Validate, and Iterate.** PATCH the prompt, confirm provider-side sync, run validation against the relevant scenarios, re-collect failures with the same Phase 2 filter, and either exit on success or feed the new failure summary back into Phase 3. Loop up to `max_iterations` times.

Confirm with the user at every phase boundary — the skill should never apply edits or kick off long-running validation runs without an explicit go-ahead.

## Phase 1: Verify Agent and Provider Support

Before doing anything else, fetch the agent and confirm it uses a supported provider. Self-improvement is currently supported **only for VAPI and Retell agents**.

### Step 1.1 — Get the agent ID

Ask the user for the agent ID they want to optimize. If they don't know it, offer to list their agents via `mcp__cekura__aiagents_list` so they can pick one.

### Step 1.2 — Fetch agent details

Call `mcp__cekura__aiagents_retrieve` with the agent ID. Read the `assistant_provider` field from the response.

### Step 1.3 — Gate on provider

Check `assistant_provider` against the supported set:

- **Supported**: `vapi`, `retell` → continue to Phase 2
- **Anything else** (`elevenlabs`, `livekit`, `pipecat`, `sip`, custom websocket, missing/empty) → **stop the workflow** and return a clear error to the user

### Error message format

When the provider isn't supported, respond with exactly this shape (substitute the actual values):

```
Self-improvement is currently supported only for VAPI and Retell agents.

Agent: <agent_name> (id: <agent_id>)
Provider: <assistant_provider or "not set">

Supported providers: vapi, retell
```

Do not attempt any further phases. Do not fetch results, propose prompt changes, or offer workarounds — provider support for other integrations will be added later, and silently skipping the gate will produce changes that can't be applied to the live agent.

### Edge cases

- **Agent not found / 404**: surface the error from `mcp__cekura__aiagents_retrieve` directly. Don't retry with a different ID without user confirmation.
- **`assistant_provider` missing or empty**: treat as unsupported. The agent likely hasn't completed provider configuration — point the user to the `create-agent` skill (Phase 3: Configure Provider Integration).
- **Case sensitivity**: compare lowercased — providers are stored as `vapi` / `retell` but be defensive against `VAPI` / `Retell` in user input.

### Step 1.4 — Fetch provider-side assistant details (VAPI only)

Once Phase 1.3 has confirmed `assistant_provider == vapi`, pull the live assistant or squad config from VAPI directly. **VAPI is the source of truth for the agent's prompt throughout this skill.** The Cekura `description` field is informational only — it is not read for analysis and not written by Phase 4. All prompt analysis (Phase 3) and all edits (Phase 4) operate on the VAPI-side `model.messages[*].content` of the relevant assistant(s).

Skip this step entirely for `retell`. Retell sync is handled in Phase 4.2 and there is no multi-assistant equivalent to disambiguate.

#### Required environment variables

- `VAPI_KEY` — VAPI private API key. Sent as `Authorization: Bearer $VAPI_KEY`.
- Exactly one of:
  - `VAPI_ASSISTANT_ID` — set when the Cekura agent maps to a single VAPI assistant.
  - `VAPI_SQUAD_ID` — set when the Cekura agent maps to a VAPI squad (multiple member assistants).

If `VAPI_KEY` is missing, stop and ask the user to export it before continuing. Never echo the key to chat or write it to a file.

If neither id is set, ask which applies. Inspect the `aiagents_retrieve` response from Step 1.2 for any provider config that hints at the right scope (e.g. an `assistant_id` or `squad_id` field) and offer it as the default.

If both are set, prefer `VAPI_SQUAD_ID` and ask the user to confirm — squads are supersets, and improving the wrong scope wastes an iteration.

#### Fetch the config

VAPI's API isn't exposed through the Cekura MCP server, so use `Bash` with curl:

- Single assistant: `curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/assistant/$VAPI_ASSISTANT_ID`
- Squad: `curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/squad/$VAPI_SQUAD_ID`

For squads, the response includes a `members` array. Each member has either `assistantId` (referenced) or an inline `assistant` object. For the referenced case, fetch the full assistant config with the assistant endpoint above; for inline members, read the embedded object directly — no extra fetch needed.

#### Extract and surface

From each assistant config, capture:

- `id`, `name`
- The system prompt: `model.messages[*].content` where `role == "system"`
- `model.tools` — function declarations, transfer destinations
- `voice`, `transcriber`, `firstMessage` — useful for sanity-checking the voice-failure filter in Phase 2

Show the user a compact summary before continuing:

```
VAPI <Assistant|Squad>: <name> (<id>)
  Members: <N>            # squad only
    - <member_name> (<member_id>) — system prompt <K> chars, <T> tools
  System prompt: <length> chars     # single-assistant case
  Tools: <N> (<comma-separated names>)
  Voice: <provider>/<voice_id>
```

#### Squad scope (squads only)

For single-assistant VAPI agents this is a no-op — the only candidate is the one assistant.

For squads, calls route between members and a given failure usually localizes to one member's prompt. Before continuing to Phase 2, ask the user which member(s) Phase 3 should consider editable. Default options:

- **One named member** — most common; pick when the failures clearly come from a specific stage (e.g. screening vs. closing).
- **All members** — pick when failures span the call or it isn't yet clear which stage owns them; Phase 3 will localize per-failure based on transcripts.
- **Auto-localize per failure** — Phase 3 attributes each failure to the member that was speaking in the relevant transcript turn, then proposes member-scoped edits.

Record the chosen scope; Phase 3 only proposes edits inside it, and Phase 4 only PATCHes assistants inside it.

#### Edge cases

- **401 / 403 from VAPI**: `VAPI_KEY` is invalid or lacks scope. Surface the error verbatim and stop — don't retry.
- **404 on assistant or squad**: id mismatch. Stop; don't guess adjacent ids.
- **Squad with zero members**: not actionable for self-improvement — surface and ask the user to verify the squad is configured correctly before continuing.
- **Member with inline `assistant` only**: read the embedded object; skip the second fetch.
- **Response shape changes / missing fields**: fall back to surfacing the relevant raw JSON section so the user can see what VAPI returned, rather than failing silently.

## Phase 2: Collect Failures

The skill accepts **one** of four input types describing what to learn from. Ask the user which they have if not already specified:

| Input | Meaning | Tool path |
|-------|---------|-----------|
| `scenario_ids` | Scenarios to execute now, then learn from their runs | Run first, then fetch |
| `result_id` | A completed test execution batch (one parent containing many runs) | `results_retrieve` |
| `run_ids` | Specific scenario runs already executed | `runs_bulk_retrieve` |
| `call_ids` | Production call logs (not test runs) | `call_logs_retrieve` per id |

### Step 2.1 — If input is `scenario_ids`: execute, then wait

Skip this step entirely for the other three input types.

1. **Pick the execution mode** based on the agent. Default to **voice** for VAPI/Retell agents (the only providers we support in Phase 1). If the user explicitly asks for text mode for faster iteration, use it — note that text-only runs miss voice-specific failure modes.

2. **Trigger the run** using the agent_id from Phase 1 and the user-supplied scenario IDs:
   - Voice: `mcp__cekura__scenarios_run_scenarios_create` with `agent_id`, `scenarios` (array of IDs), `frequency`
   - Text: `mcp__cekura__scenarios_run_scenarios_text_create`

   Capture the `result_id` returned. From here on the flow is identical to the `result_id` input case.

3. **Poll for completion**. Call `mcp__cekura__results_retrieve` with the result_id every ~30 seconds. Voice runs typically take 1-5 minutes per scenario depending on length.

   - Stop polling once the result's status indicates completion (every run inside has a terminal status — completed, failed, or errored).
   - If the user wants to monitor live, surface progress (`X / N runs complete`) between polls.
   - Cap waiting at a sensible bound (e.g., 15 min for voice, 5 min for text). If runs are still pending past that, ask the user whether to keep waiting or proceed with whatever has finished.

4. Once the result is complete, treat the case as a `result_id` input and continue.

### Step 2.2 — Fetch the runs or call logs

Branch on the input type to populate a list of items to inspect:

- **`result_id`**: call `mcp__cekura__results_retrieve`. The response contains all runs in that batch — each run has scenario info, status, transcript, expected-outcome verdict, and metric evaluations. No further fetch needed.
- **`run_ids`**: call `mcp__cekura__runs_bulk_retrieve` with the list. Returns the same per-run shape as above.
- **`call_ids`**: call `mcp__cekura__call_logs_retrieve` for each call id (no bulk variant exists). Call logs have transcripts and metric evaluations but no "expected outcome" — they're production calls, not scenarios.

### Step 2.3 — Accumulate failures (prompt-following only)

Walk every run / call log and collect two failure classes:

1. **Expected-outcome failures** *(runs only — not applicable to call logs)*
   - The run's expected outcome verdict is `fail` (or equivalent: not-met, false).
   - Capture: scenario id + name, transcript excerpt, the expected outcome text, and the verdict's explanation.

2. **Metric failures** *(both runs and call logs)*
   - Any attached metric evaluation with verdict `FAIL` (skip `PASS`, `N/A`, `VALID_SKIP`).
   - Capture: metric id + name, the FAIL explanation, and the offending transcript snippet (if the evaluation surfaces one).

A single run can contribute to both classes. Track them separately — Phase 3 treats them differently (expected-outcome failures usually point at agent prompt logic; metric failures may point at either the agent or the metric itself).

#### Filter: keep only prompt-following failures

This skill only optimizes the agent's **prompt**, so discard failures whose root cause is the voice channel rather than the agent's instructions. For each failure, read the explanation and decide:

- **Discard (voice/channel issue)** — the agent likely *would* have followed the prompt if the voice path had worked:
  - Audio quality, garbled audio, background noise, low volume
  - Transcription / ASR errors ("misheard", "transcribed incorrectly")
  - TTS issues, mispronunciation
  - Latency, dead air, interruptions, talk-over
  - Connection drops, call cut off mid-conversation, errored runs
  - Failures from metrics that explicitly score voice quality (e.g. transcription accuracy, audio quality, latency)

- **Keep (prompt-following issue)** — the agent had the input it needed and still behaved wrong:
  - Skipped a required step in the script
  - Asked for the wrong information, or in the wrong order
  - Confirmed something incorrect, hallucinated a fact
  - Failed to follow escalation / handoff protocol
  - Went off-topic or out of scope
  - Missed an end-of-call requirement (disclosure, summary, etc.)

When in doubt, **keep the failure** and flag it for the user. False keeps are recoverable in Phase 3 (the user can ignore the suggested change); false discards silently lose signal.

For text-mode runs and chat call logs the filter is a no-op — there is no voice channel — so every collected failure passes through.

Track the discarded count so the summary in Step 2.4 can report it (e.g. "12 failures collected, 4 voice-related discarded, 8 prompt-following failures kept").

### Step 2.4 — Build the failure summary

Produce a structured summary that Phase 3 will consume. Group failures by **scenario** (for runs) or by **metric** (for call logs), since repeated failures on the same scenario or the same metric are stronger signals than scattered one-offs.

Suggested shape:

```
Failure Summary
  Agent: <name> (<id>) — provider <vapi|retell>
  Source: <input type> — <N items inspected>
  Failures: <total collected> — <voice-related discarded> voice-related discarded — <kept> prompt-following kept

  Expected-Outcome Failures (M of N runs):
    - Scenario: <name>
      Expected: <expected_outcome text>
      Verdict: fail — <explanation>
      Run: <run_id>
      Transcript excerpt: "<quote>"

  Metric Failures (K total across J unique metrics):
    - Metric: <name> (id <metric_id>) — <count> failures
      Sample explanations:
        - <run/call id>: <explanation excerpt>
        - <run/call id>: <explanation excerpt>
```

Before moving on, **show the summary to the user** and confirm they want to proceed to Phase 3 (Propose Prompt Changes). If the failures are dominated by one or two metrics with thin signal, suggest hand-off to the `labs-workflow` skill instead — those are metric-quality issues, not agent-quality issues.

### Edge cases

- **No failures found**: report this and stop. There's nothing to improve from this input. Suggest expanding the input set (more scenarios, more calls).
- **All runs errored** (vs failed): an errored run never produced a transcript — usually a provider/connection issue, not an agent prompt issue. Don't include errored runs in the failure summary; surface them separately so the user can fix infrastructure before iterating on the prompt.
- **Mixed input types**: not supported in a single invocation. If the user gives both `scenario_ids` and `call_ids`, ask them to pick one source per iteration — mixing test runs and production calls muddles the signal.

## Phase 3: Propose Prompt Changes

Take the **kept** failure summary from Phase 2 and the **current agent prompt** and produce a concrete, reviewable set of edits. Don't apply anything yet — Phase 4 handles application.

### Step 3.1 — Read the current prompt

The canonical prompt source depends on provider:

- **VAPI**: the `model.messages[*].content` (where `role == "system"`) on each in-scope assistant fetched in Phase 1.4. For squads, the in-scope set is whatever the user picked in the squad-scope step. Re-fetch via `curl https://api.vapi.ai/assistant/{id}` if more than a few minutes have passed since Phase 1.4 — VAPI dashboard edits don't notify Cekura. Do **not** read the Cekura `description` for VAPI agents.
- **Retell**: the `description` field on the Cekura agent (already fetched in Phase 1 via `mcp__cekura__aiagents_retrieve`). Re-fetch if more than a few minutes have passed.

Also note any dynamic variables (`{{variableName}}` placeholders) — they're injected per call and must not be touched by edits unless the user explicitly asks.

If the source-of-truth prompt is empty or clearly not the production prompt (e.g. just a one-line summary), **stop and ask** — either the agent isn't fully configured (point at `create-agent`), or the user is running prod prompt somewhere this skill can't see and needs to paste it in.

### Step 3.2 — Map each kept failure to a prompt section

For each kept failure, locate the section(s) of the prompt that *should* have governed that behavior. Quote the exact lines. If no section governs it, mark the failure as "uncovered" — that's a strong gap signal.

A failure can map to zero, one, or several sections. Track all matches.

### Step 3.3 — Classify each failure

Sort each kept failure into exactly one of three buckets. The bucket determines what kind of change to propose.

| Bucket | What it looks like | Example |
|--------|--------------------|---------|
| **Gap** | No section of the prompt addresses this situation. The agent improvised and got it wrong. | Prompt never says what to do if the caller asks for a manager → agent makes up a transfer policy. |
| **Conflict** | The prompt has two clauses that contradict, OR a clause that contradicts the desired behavior implied by the failure. | One section says "always confirm the address before booking", another says "skip confirmation for returning customers" — agent skipped for a first-time caller. |
| **Ambiguity** | One section addresses it but the wording is vague enough the agent could read it either way. | "Wrap up the call politely" — no concrete steps, agent skipped the legally required disclosure. |

If you can't tell, default to **Ambiguity** and flag for the user. Don't force a classification.

### Step 3.4 — Propose a change for each diagnosis

Each diagnosis becomes one proposed edit. Use the smallest change that fixes the failure — don't rewrite paragraphs to fix one missed step.

| Bucket | Change type | Rule of thumb |
|--------|-------------|---------------|
| Gap | **Add** a new clause | Place it next to the closest related section, not at the end. Match the existing voice/format. |
| Conflict | **Edit** or **Remove** the contradictory clause | Resolve in favor of the behavior the failures expect. If both clauses have legitimate use cases, **scope** them with explicit conditions ("if returning customer..." / "if first-time caller..."). |
| Ambiguity | **Edit** for specificity | Replace vague verbs ("politely", "appropriately") with concrete steps. Add a checklist if there are >2 required actions. |

Cluster related diagnoses — if 5 failures all stem from the same missing clause, propose one edit that covers all 5, not five separate edits.

### Step 3.5 — Present the proposal to the user

Show every proposed change as a **before/after** block grouped by bucket, with the failures it addresses. Example:

```
Proposed Change 1 of 4 — Gap
  Addresses: 3 failures (Run abc, Run def, Call xyz)
  Diagnosis: Prompt does not specify what to do when caller asks for a manager.

  Before:
    (no governing section — uncovered)

  After (insert after "Escalation rules:"):
    If the caller asks to speak with a manager, do not promise a transfer.
    Tell them you'll create a callback ticket and confirm their preferred
    time. Do not commit to a specific manager or response time.
```

End with a summary line: `4 changes proposed across 12 prompt-following failures (3 gaps, 1 conflict, 0 ambiguities).`

Ask the user to accept all, accept a subset, or push back. Do not move to Phase 4 until they explicitly confirm which edits to apply.

### Manual analysis vs. `runs_improve_prompt_create`

Cekura also exposes `mcp__cekura__runs_improve_prompt_create` — an automated prompt-improver that takes a run and returns suggested edits. This skill defaults to the **manual analysis path above** because:

- It produces explainable, scoped diffs (each tied to specific failures)
- It works across mixed inputs (results, runs, call logs) in one pass
- It respects the voice-failure filter from Phase 2

Use `runs_improve_prompt_create` as a **fallback** when the manual analysis is inconclusive (e.g., failures don't cluster, or the user wants a second opinion). Treat its suggestions as input to Step 3.4, not as the final proposal — still surface them as before/after blocks for user review.

### Anti-patterns to avoid in this phase

- **Rewriting the whole prompt** because several sections look weak. Only edit what the failures justify.
- **Adding catch-all clauses** like "always be helpful and accurate" — they don't change behavior.
- **Stacking conditions indefinitely** to handle one-off failures. If a clause is getting >3 nested conditions, the underlying flow probably needs restructuring; flag it for the user instead of patching.
- **Editing dynamic-variable placeholders** (`{{...}}`) — they're owned by the calling system. Touch them only if the user explicitly asks.
- **Silently dropping a failure** because no clean fix is obvious. Surface it to the user as "no change proposed — needs human review" rather than hiding it.

## Phase 4: Apply, Validate, and Iterate

This phase is a **loop**. Each iteration: apply the approved prompt → run validation → diagnose new failures → propose more changes → apply again. Exit when a validation pass produces zero prompt-following failures, or when the iteration cap is hit.

### Early-exit shortcut

If Phase 2 collected zero prompt-following failures from the initial input (i.e., the agent is already passing on the supplied scenarios / runs / calls), Phase 3 was skipped and there's nothing to apply. Report success and stop. This phase only runs when at least one approved edit exists.

### Step 4.1 — Apply the approved edits to the prompt

Take the approved subset of changes from Step 3.5 and produce the new prompt by applying them to the current source-of-truth prompt (VAPI assistant `model.messages[*]` for VAPI, Cekura `description` for Retell). Show the user the **final merged prompt** (or a unified diff if it's long) and confirm one more time before persisting.

Then persist by provider:

**VAPI** — PATCH the in-scope assistant(s) on VAPI directly. The MCP server doesn't expose VAPI write endpoints, so use `Bash` + `curl`:

```
curl -fsS -X PATCH \
  -H "Authorization: Bearer $VAPI_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":{"provider":"<existing>","model":"<existing>","messages":[{"role":"system","content":"<NEW_PROMPT>"}, ... <other existing messages unchanged> ...]}}' \
  https://api.vapi.ai/assistant/$VAPI_ASSISTANT_ID
```

Important when constructing the PATCH body:
- Read back the current `model` object from the Phase 1.4 fetch and copy provider/model/temperature/tools/etc. unchanged — VAPI's PATCH replaces `model` wholesale, so omitted fields will be lost.
- Replace **only** the system message's `content`. Preserve any other messages (e.g. tool-result examples) and their order.
- For squads with multiple in-scope members edited in this iteration, PATCH each member separately.
- Do not touch the Cekura `description` field. It is informational and stays as-is.

**Retell** — PATCH the Cekura agent:

- `mcp__cekura__aiagents_partial_update` with the agent_id and `{"description": "<new prompt>"}`

If the agent has dynamic-variable placeholders (`{{...}}`), confirm they're preserved verbatim in the merged prompt regardless of provider.

### Step 4.2 — Make sure the provider is running the new prompt

What the live agent runs depends on where Step 4.1 wrote:

- **VAPI** — Step 4.1 PATCHed VAPI directly. The new prompt is live on VAPI as soon as the PATCH returns 2xx. Re-fetch the assistant (`curl GET https://api.vapi.ai/assistant/{id}`) and confirm the system message's `content` matches the merged prompt before continuing. No dashboard step required.
- **Retell with `auto_sync_prompt_enabled: true`** — Cekura syncs the prompt to Retell within ~30 seconds. Wait that long, then proceed.
- **Retell without auto-sync** — the provider side does **not** update automatically. Tell the user to push the new prompt to the Retell dashboard (Retell agents → Prompt) before validation runs, then confirm with them.

If the provider isn't running the new prompt, validation runs will pass/fail based on the **old** prompt and the loop will spin forever. Don't proceed to Step 4.3 until this is confirmed.

### Step 4.3 — Build the validation set

Pick the validation set based on the **original input type** to this skill (the same input the user passed in Phase 2):

| Original input | Validation set |
|----------------|----------------|
| `scenario_ids` | Reuse the same scenario IDs. |
| `result_id` | Extract `scenario_id` from every run inside the result (already fetched in Phase 2.2). De-duplicate. |
| `run_ids` | Extract `scenario_id` from every run (already fetched via `runs_bulk_retrieve` in Phase 2.2). De-duplicate. |
| `call_ids` | Generate one scenario per call via `mcp__cekura__scenarios_create_scenario_from_transcript_create`. Cache the new scenario IDs on the first iteration so subsequent loop iterations reuse them rather than re-creating from transcripts each time. |

**Why scenarios for call_ids:** call logs are production calls, not reproducible — to validate fixes, we synthesize a scenario from each transcript and re-run it against the new prompt.

The validation set should match the failure set when possible — re-running only the scenarios that failed initially gives the cleanest signal that the edit fixed *those specific failures*. Optionally, the user can request the full set (including previously-passing scenarios) to guard against regressions; default to failure-only.

### Step 4.4 — Run validation

Execute the validation set with `mcp__cekura__scenarios_run_scenarios_create` (voice mode for VAPI/Retell — the only providers gated through Phase 1). Capture the `result_id`.

Poll `mcp__cekura__results_retrieve` until terminal, exactly as in Phase 2.1 (same 30s cadence and 15-min cap).

### Step 4.5 — Collect and filter new failures

Run the new result through **the same accumulation logic from Phase 2.3** — both expected-outcome failures and metric failures, with the voice-failure filter applied. Produce a Phase-2.4-shaped summary.

This guarantees iteration N sees failures filtered identically to iteration 0, so the loop's stopping criterion is consistent across iterations.

### Step 4.6 — Decide: exit or loop

- **Zero kept failures** → success. Report the final pass rate, the cumulative diff applied, and stop.
- **Kept failures remain** → loop:
  1. Feed the new failure summary and the **current (post-edit) prompt** back into Phase 3.
  2. Phase 3 produces a fresh proposal against the updated prompt.
  3. User review (Step 3.5) gates re-entry to this phase.
  4. Repeat from Step 4.1.

### Iteration cap

Default to **10 iterations** of the loop. If the user supplies a `max_iterations` value when invoking the skill (e.g., "keep going up to 20", "cap at 5"), use that instead. After the cap is hit, stop and surface a summary regardless of remaining failures:

- What's been fixed (pass-rate gain, failures resolved)
- What's still failing (the residual summary)
- A recommendation: hand off to `eval-design` (test gaps), `labs-workflow` (metric quality), or `create-agent` (provider/tools/KB) depending on what the residual failures look like

The user can also stop or extend mid-loop ("keep going" / "stop"). Don't loop silently past the cap.

### Loop guardrails

- **Track cumulative diff** — show the user every change that's been applied across all iterations, not just the latest one. Easy to lose context across 3 passes.
- **Watch for oscillation** — if iteration N's edit reverses iteration N-1's edit on the same clause, stop and flag it. The two failure sets are pulling the prompt in opposite directions; user judgment is needed.
- **Watch for new failures the previous prompt didn't have** — if iteration N introduces failures that iteration 0 didn't have, the latest edit caused a regression. Stop and offer to revert that specific edit.
- **Don't widen the validation set mid-loop** without telling the user. The stopping criterion depends on a stable comparison set.

## API Access — Cekura MCP Server

This skill uses the Cekura MCP server for all API operations. The plugin's `.mcp.json` configures it automatically.

**Prerequisites:**
1. Set the `CEKURA_API_KEY` environment variable with your Cekura API key
2. Start the Cekura MCP server: `cd /path/to/cekura-mcp-server && python3 openapi_mcp_server.py` (runs on `http://localhost:8001/mcp`)
3. The plugin's `.mcp.json` handles the rest — Claude Code connects to the server and makes the `mcp__cekura__*` tools available

**Key MCP tools used by this skill:**

| Phase | Operation | MCP Tool |
|-------|-----------|----------|
| 1 | List / fetch agents | `mcp__cekura__aiagents_list`, `mcp__cekura__aiagents_retrieve` |
| 1 | Fetch live VAPI assistant / squad (direct, not MCP) | `Bash` + `curl` against `https://api.vapi.ai/assistant/{id}` or `https://api.vapi.ai/squad/{id}` with `VAPI_KEY` |
| 2 | Run scenarios (voice / text) | `mcp__cekura__scenarios_run_scenarios_create`, `mcp__cekura__scenarios_run_scenarios_text_create` |
| 2 | Fetch result batch | `mcp__cekura__results_retrieve` |
| 2 | Bulk fetch runs | `mcp__cekura__runs_bulk_retrieve` |
| 2 | Fetch a call log | `mcp__cekura__call_logs_retrieve` |
| 3 | Auto-improve prompt (fallback) | `mcp__cekura__runs_improve_prompt_create` |
| 4 | PATCH agent prompt — Retell | `mcp__cekura__aiagents_partial_update` |
| 4 | PATCH agent prompt — VAPI (direct) | `Bash` + `curl -X PATCH https://api.vapi.ai/assistant/{id}` with `VAPI_KEY` |
| 4 | Synthesize scenario from a transcript | `mcp__cekura__scenarios_create_scenario_from_transcript_create` |

**Docs lookup:** Use `mcp__cekura__search_cekura` or fetch `https://docs.cekura.ai/llms.txt` for field schemas, response shapes, or tool details when this skill doesn't cover them.

**Troubleshooting:** If MCP tools aren't available, verify (1) `CEKURA_API_KEY` is set, (2) the MCP server is running on port 8001, (3) restart Claude Code to pick up the `.mcp.json` config. Run `/setup-mcp` for guided setup.

## Anti-Patterns

These apply to the skill as a whole. Phase-specific anti-patterns are covered inside each phase.

- **Running the loop on a tiny input.** A single failing run / call is rarely enough signal — one-off failures often reflect noise, not a prompt defect. Ask for at least 5-10 items before iterating, or surface the small-sample caveat in the summary.
- **Iterating with a noisy metric.** If most kept failures come from one metric whose explanations look subjective, the metric is probably miscalibrated. Hand off to `labs-workflow` first; otherwise the loop will keep "fixing" the prompt to satisfy a flawed judge.
- **Skipping the provider sync gate (Phase 4.2).** For VAPI, confirm the PATCH actually landed (re-fetch and diff the system message). For Retell without auto-sync, Cekura's stored description is not what the live agent runs until the user pushes it from the dashboard. Without confirmation, the loop validates the old prompt and never converges.
- **Bypassing user review at phase boundaries.** This skill applies edits to a live agent. Every transition (Phase 2 summary → Phase 3 proposal → Phase 4 apply) must be explicitly approved.
- **Fixing prompt issues that are really agent-config issues.** If failures cluster on missing tools or knowledge gaps, no prompt edit will help — hand off to `create-agent`.
- **Treating expected-outcome failures and metric failures the same.** Expected-outcome failures are first-class signal about agent behavior. Metric failures may reflect either the agent or the metric — be more skeptical.

## Hand-off to Other Skills

If the failures don't actually point at the prompt, redirect rather than iterate:

- **`create-agent`** (in this same plugin) — when failures stem from missing/misconfigured tools, an outdated knowledge base, or provider integration issues. No prompt edit will fix a missing tool.
- **`eval-design`** (in `cekura-evals`) — when the test set itself is the problem (too narrow, missing key flows, no coverage of failure modes seen in production). Improving the prompt against a thin eval set just overfits.
- **`metric-design`** (in `cekura-metrics`) — when failures cluster on metrics whose definitions look weak or off-target.
- **`labs-workflow`** (in `cekura-metrics`) — when metric pass/fail verdicts seem misaligned with the transcripts. Fix the metric first, *then* come back here.
- **`coordinator`** (in this same plugin) — if the user is unsure where the issue is, route them through coordinator to triage.

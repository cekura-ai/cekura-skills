---
name: self-improving-agent
description: >
  This skill should be used when the user asks to "improve my agent",
  "self-improving agent", "auto-tune my agent", "iterate on my agent prompt",
  "fix my agent based on test results", "close the loop on agent quality",
  "auto-improve agent prompt", "use eval results to improve agent", or discusses
  agent self-improvement, prompt iteration from run results, or automated
  agent quality loops in the Cekura platform.
version: 0.5.0
---

# Cekura Self-Improving Agent

## Purpose

Close the loop on agent prompt and tool-config quality. Ingest evaluation signal (scenario IDs to run, completed runs, a result batch, or production call logs), classify failures (prompt-following vs. voice/channel vs. tool/infra) for diagnosis, diagnose where the prompt or tool config has gaps, conflicts, or ambiguities, propose targeted edits, apply them, and re-run validation — iterating until the agent reaches **100% pass rate on the validation set** or the iteration cap is reached.

**What's editable:** for VAPI agents, both **system prompts** and **tool definitions** are editable from this skill. Tool config covers function declarations on inline `model.tools`, referenced `model.toolIds` definitions (their `name`, `description`, `parameters` schema, `messages[*].content` like `request-start` / `request-complete` / `request-failed`, and handoff `destinations`), and which tools each member references via its `toolIds` array (adding or removing a reference). For Retell agents, only the system prompt is editable in this skill — Retell tool config is owned by the platform.

**Exit gate:** the voice/channel/infra filter informs *what to fix* (Phase 3 only proposes edits for prompt-following failures), not *when to stop*. Any remaining failure of any class keeps the loop alive. Do not exit at "zero prompt-following failures but some infra failures remain" — first re-classify with fresh eyes, expand squad scope to other assistants, consider mitigation prompt edits, **and consider tool-config edits** (a noisy `request-start` message, a hallucinated tool reference, a misshapen function schema, or a wrong handoff destination is fixed in tool config, not prompt). Only the iteration cap (or genuine 100% pass) ends the loop.

Currently supported only for **VAPI** and **Retell** agents (Phase 1 gates this).

## How to Use This Skill

This is an **interactive, multi-iteration workflow**. The user supplies an `agent_id` plus exactly one of: `scenario_ids`, `result_id`, `run_ids`, or `call_ids`. Optionally `max_iterations` (default 10).

The four phases run in order, with the last looping until the agent passes:

1. **Phase 1 — Verify Agent and Provider Support.** Fetch the agent, gate on `assistant_provider ∈ {vapi, retell}`. Halt with a clear error otherwise. For VAPI, also pull the live assistant or squad config from VAPI directly (using `VAPI_KEY` plus `VAPI_ASSISTANT_ID` or `VAPI_SQUAD_ID`) — VAPI is the source of truth for the prompt; the Cekura `description` is not consulted or edited.
2. **Phase 2 — Collect Failures.** Branch on input type. For `scenario_ids`, run them first and wait for completion; otherwise fetch the supplied runs / call logs. Accumulate expected-outcome and metric failures, **discard voice/channel failures**, and present a structured summary.
3. **Phase 3 — Propose Prompt and Tool Changes.** Map kept failures to prompt sections AND tool definitions, classify each as Gap / Conflict / Ambiguity, and produce minimal scoped edits. Edits may be prompt-only, tool-only, or both — whichever the failure points at. Show the user before/after blocks and wait for explicit approval.
4. **Phase 4 — Apply, Validate, and Iterate.** PATCH the prompt and/or tool definitions, confirm provider-side sync, run validation against the relevant scenarios, re-collect failures with the same Phase 2 classification. Exit only on **100% pass rate**; otherwise feed the new failure summary back into Phase 3 — expanding squad scope or considering tool/mitigation edits if the remaining failures aren't directly prompt-following. Loop up to `max_iterations` times.

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
- `model.tools` — inline function declarations
- `model.toolIds` — array of UUIDs of referenced tool definitions (these live at `https://api.vapi.ai/tool/{id}` and must be fetched separately; **do this in Phase 1.4, not later** — the definitions drive Phase 3 diagnosis as much as the prompt does)
- `voice`, `transcriber`, `firstMessage` — useful for sanity-checking the voice-failure filter in Phase 2

#### Fetch every referenced tool

For each unique id across all in-scope assistants' `model.toolIds`, fetch:

```
curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/tool/$TOOL_ID
```

Capture for each tool:

- `id`, `type` (`function`, `handoff`, `transferCall`, `query`, `mcp`, etc.)
- `function.name`, `function.description`, `function.parameters` (JSONSchema)
- `messages` array — especially the `request-start.content` (what the assistant says aloud when the tool fires), `request-complete.content`, `request-failed.content`. **These messages are spoken on the call** and are first-class targets for Phase 3 edits.
- `destinations` — for `handoff` / `transferCall` tools, the list of `{type, assistantId, description}` entries pointing to other assistants. Wrong / self-referencing destinations are a common bug class.
- Which member assistants reference this tool (cross-reference back to the `toolIds` arrays you already collected).

Show the user a compact summary before continuing:

```
VAPI <Assistant|Squad>: <name> (<id>)
  Members: <N>            # squad only
    - <member_name> (<member_id>) — system prompt <K> chars, <T> inline tools, <R> referenced tools
  System prompt: <length> chars     # single-assistant case
  Inline tools (model.tools): <N> (<comma-separated names>)
  Referenced tools (model.toolIds → /tool/{id}):
    - <tool_name> (<tool_id>) — type=<type>, used by <member_name>[, ...]
        request-start: "<first 80 chars or empty>"
        destinations: <list or empty>
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

## Phase 3: Propose Prompt and Tool Changes

Take the **kept** failure summary from Phase 2 and the **current agent prompt and tool definitions** and produce a concrete, reviewable set of edits. Don't apply anything yet — Phase 4 handles application. Edits split into two streams; either or both may be empty for a given iteration:

- **Prompt edits** — change the system message of one or more in-scope assistants.
- **Tool-config edits** (VAPI only) — change a tool's name / description / parameter schema / spoken `messages` / handoff `destinations`, or change which tools a given member references via its `toolIds` (i.e. add a tool, remove a tool reference, or create a new tool).

### Step 3.1 — Read the current prompt and tool definitions

The canonical prompt source depends on provider:

- **VAPI**: the `model.messages[*].content` (where `role == "system"`) on each in-scope assistant fetched in Phase 1.4. For squads, the in-scope set is whatever the user picked in the squad-scope step. Re-fetch via `curl https://api.vapi.ai/assistant/{id}` if more than a few minutes have passed since Phase 1.4 — VAPI dashboard edits don't notify Cekura. Do **not** read the Cekura `description` for VAPI agents.
- **Retell**: the `description` field on the Cekura agent (already fetched in Phase 1 via `mcp__cekura__aiagents_retrieve`). Re-fetch if more than a few minutes have passed.

For **VAPI**, also re-confirm the live tool definitions captured in Phase 1.4 if more than a few minutes have passed — re-fetch each in-scope `toolId` via `curl https://api.vapi.ai/tool/{id}`. Tools can be edited from the VAPI dashboard too, and a stale local copy will produce a wrong PATCH body.

Also note any dynamic variables (`{{variableName}}` placeholders) in both prompts and tool messages / parameter schemas — they're injected per call and must not be touched by edits unless the user explicitly asks.

If the source-of-truth prompt is empty or clearly not the production prompt (e.g. just a one-line summary), **stop and ask** — either the agent isn't fully configured (point at `create-agent`), or the user is running prod prompt somewhere this skill can't see and needs to paste it in.

### Step 3.2 — Map each kept failure to a prompt section AND/OR a tool definition

For each kept failure, locate every artifact that *should* have governed that behavior:

- **Prompt sections** — quote the exact lines from the in-scope assistant's system message that drive (or fail to drive) the observed behavior.
- **Tool definitions** — if the failure involves a tool call (the agent called the wrong tool, didn't call a needed tool, called a tool with bad arguments, or a `request-start` message produced unexpected agent speech), pull the relevant tool's definition into the diagnosis. Quote `function.description`, the relevant property in `function.parameters`, the offending `messages[*].content`, or the suspect `destinations` entry.

If no artifact governs the failure, mark it "uncovered" — that's a strong gap signal in the prompt or a missing tool.

A failure can map to zero, one, or several artifacts. Track all matches. **A single failure often has both a prompt and a tool angle** — e.g., a hallucinated self-handoff is partly the prompt's fault (the LLM was over-eager) and partly the tool config's fault (the self-referencing handoff exists at all). Phase 3.4 will pick the right edit surface; this step just records the candidates.

### Step 3.3 — Classify each failure

Sort each kept failure into exactly one of three buckets. The bucket determines what kind of change to propose.

| Bucket | What it looks like | Example |
|--------|--------------------|---------|
| **Gap** | No section of the prompt addresses this situation. The agent improvised and got it wrong. | Prompt never says what to do if the caller asks for a manager → agent makes up a transfer policy. |
| **Conflict** | The prompt has two clauses that contradict, OR a clause that contradicts the desired behavior implied by the failure. | One section says "always confirm the address before booking", another says "skip confirmation for returning customers" — agent skipped for a first-time caller. |
| **Ambiguity** | One section addresses it but the wording is vague enough the agent could read it either way. | "Wrap up the call politely" — no concrete steps, agent skipped the legally required disclosure. |

If you can't tell, default to **Ambiguity** and flag for the user. Don't force a classification.

### Step 3.4 — Propose a change for each diagnosis

Each diagnosis becomes one proposed edit. Use the smallest change that fixes the failure — don't rewrite paragraphs (or schemas) to fix one missed step.

#### Prompt edits

| Bucket | Change type | Rule of thumb |
|--------|-------------|---------------|
| Gap | **Add** a new clause | Place it next to the closest related section, not at the end. Match the existing voice/format. |
| Conflict | **Edit** or **Remove** the contradictory clause | Resolve in favor of the behavior the failures expect. If both clauses have legitimate use cases, **scope** them with explicit conditions ("if returning customer..." / "if first-time caller..."). |
| Ambiguity | **Edit** for specificity | Replace vague verbs ("politely", "appropriately") with concrete steps. Add a checklist if there are >2 required actions. |

#### Tool-config edits (VAPI only)

The same Gap / Conflict / Ambiguity classification applies to tool definitions. Tool edits split into four sub-types — pick the one that matches the failure:

| Sub-type | When to propose | Mechanics |
|---|---|---|
| **Edit a tool definition** | A failure traces to a specific field on an existing tool: vague `function.description`, ambiguous parameter, an outdated / verbose `request-start.content` that's spoken on every fire, a `destinations[].assistantId` that's wrong, a `destinations[].description` that misleads the LLM about when to use the handoff. | PATCH the tool by id (Step 4.1). Show before/after of the changed field only; don't redisplay the whole tool. |
| **Add a tool** (new) | A flow step requires a tool call that no current tool covers (e.g., the prompt says "look up the customer's last order" but no `lookup_order` tool exists). | Phase 4.1 creates the tool via POST `/tool`, then PATCHes the relevant assistant's `model.toolIds` to include the new id. The new tool also needs a corresponding prompt edit telling the agent when to call it — usually one prompt edit + one tool create + one toolIds patch. |
| **Remove a tool reference** | A specific assistant is hallucinating calls to a tool it shouldn't have access to (squad inheritance is a common cause), or a tool's destinations include the assistant itself (self-handoff). The tool may be legitimate for *other* members; the issue is the reference, not the definition. | PATCH that assistant's `model.toolIds` to drop the id. Do NOT delete the tool itself unless no other in-scope or out-of-scope assistant references it. |
| **Delete a tool** | The tool is dead weight — referenced by no in-scope or out-of-scope assistant after the proposed `toolIds` updates land. | Rare. Only propose if you've cross-referenced ALL squad members (including out-of-scope ones whose `toolIds` you must fetch first) and confirmed nothing else points at it. Prefer leaving the tool dormant over deleting; deletes are irreversible from this skill. |

**Tool-edit anti-patterns:**

- **Editing a tool's `function.name`** — the LLM has been calling the tool by its current name; renaming forces every other place that mentions the name (prompts, other tools' descriptions, downstream metric configs) to be updated atomically. Avoid unless the name is actively misleading.
- **Tightening `function.parameters` schemas to fix one bad call** — a single bad-args call usually means a prompt issue (the LLM didn't have / didn't use the right inputs). Fix the prompt first.
- **Editing or removing tools in members the user didn't put in scope** — same rule as for prompts. If a fix requires touching an out-of-scope member's tools, ask the user to expand the scope first (per Phase 1.4 squad-scope rules and Phase 4.6 §2).
- **Mass-deleting "unused"-looking tools** — a tool with no references in the in-scope members may still be referenced by an out-of-scope member, by another squad, or by a workflow that fires only on rare branches. When in doubt, only remove the *reference*, never the tool.

#### Clustering

Cluster related diagnoses — if 5 failures all stem from the same missing clause OR the same noisy `request-start` message, propose one edit that covers all 5, not five separate edits. Prompt and tool edits can also cluster across artifacts: e.g., "remove tool reference from member X **and** add a clause to its prompt explaining what to do at that decision point instead" is one logical change, surfaced as a paired edit.

### Step 3.5 — Present the proposal to the user

Show every proposed change as a **before/after** block grouped by bucket and edit surface (prompt vs. tool), with the failures it addresses. Example for a prompt edit:

```
Proposed Change 1 of 4 — Gap (prompt)
  Surface: VAPI assistant <member_name> (<member_id>), system prompt
  Addresses: 3 failures (Run abc, Run def, Call xyz)
  Diagnosis: Prompt does not specify what to do when caller asks for a manager.

  Before:
    (no governing section — uncovered)

  After (insert after "Escalation rules:"):
    If the caller asks to speak with a manager, do not promise a transfer.
    Tell them you'll create a callback ticket and confirm their preferred
    time. Do not commit to a specific manager or response time.
```

Example for a tool-definition edit:

```
Proposed Change 2 of 4 — Conflict (tool)
  Surface: VAPI tool handoff_to_screener (id 880d...3177), messages[request-start].content
  Addresses: 8 failures (replays once per user turn after handoff)
  Diagnosis: request-start message fires on every chat-mode rerouting event,
             producing a repeated "Perfect, thank you..." utterance.

  Before:
    "Perfect, thank you for that! Your identity is verified. Now let's get
     into the exciting part - understanding your health goals..."

  After:
    "" (empty — squad transitions are handled by the destination's first
         message; no source-side spoken transition needed)
```

Example for a `toolIds` reference removal:

```
Proposed Change 3 of 4 — Conflict (tool reference)
  Surface: VAPI assistant <member_name> (<member_id>), model.toolIds
  Addresses: 12 failures (self-handoff loop)
  Diagnosis: handoff_to_self_member tool is exposed to this member via squad
             inheritance; LLM keeps calling it as a no-op routing affordance.

  Before:
    toolIds: [..., "880d2980-...-...", ...]

  After:
    toolIds: [..., (removed), ...]   # tool definition itself stays — other members may still legitimately use it
```

End with a summary line: `4 changes proposed across 12 prompt-following failures (2 prompt edits, 2 tool edits; 1 gap, 2 conflicts, 1 ambiguity).`

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
- **Editing dynamic-variable placeholders** (`{{...}}`) in either prompts or tool definitions — they're owned by the calling system. Touch them only if the user explicitly asks.
- **Silently dropping a failure** because no clean fix is obvious. Surface it to the user as "no change proposed — needs human review" rather than hiding it.
- **Patching a tool's spoken `messages` to mask a prompt issue.** If the agent says the wrong thing, fix the prompt that drives the tool call, not the tool's request-start message. The exception is when the tool's message is itself the offending utterance (e.g., a verbose request-start that fires repeatedly) — then the tool edit is correct.
- **Using tool edits to enforce flow.** Adding a tool just to "force" the agent to do something is usually a prompt-clarity problem in disguise. Try the prompt fix first; only add a tool when the failure genuinely requires data the agent doesn't have.

## Phase 4: Apply, Validate, and Iterate

This phase is a **loop**. Each iteration: apply the approved prompt → run validation → diagnose new failures → propose more changes → apply again. Exit only when a validation pass produces **100% success on the validation set** (zero failures of any class), or when the iteration cap is hit. Do not exit just because the latest failures look like voice/infra rather than prompt issues — first try expanding squad scope and proposing mitigation edits.

### Early-exit shortcut

If Phase 2 collected **zero failures of any class** from the initial input (the agent already passes 100% on the supplied scenarios / runs / calls), Phase 3 was skipped and there's nothing to apply. Report success and stop.

If Phase 2 found failures but they are *all* voice/infra/tool with no prompt-following matches, do **not** auto-exit. Run the same logic as the "kept failures = 0 but total > 0" branch in Step 4.6 (re-classify with fresh eyes, consider squad scope expansion, consider mitigation edits) before deciding to stop.

### Step 4.1 — Apply the approved edits

Take the approved subset of changes from Step 3.5 and apply them in this order:

1. **Tool-definition edits first** (PATCH `/tool/{id}`).
2. **New tool creation** next (POST `/tool`), capturing the new id.
3. **Assistant `model.toolIds` updates** (add/remove references) bundled into the assistant PATCH.
4. **System prompt edits** in the same assistant PATCH as the `toolIds` updates — one PATCH per assistant.

The order matters because: if a new tool is referenced, it must exist before the assistant PATCH lands; and bundling toolIds + prompt into one assistant PATCH keeps the LLM's view of "tools available" and "instructions about those tools" consistent across the rollout.

Show the user the **final merged prompt** for each affected assistant (or a unified diff if long) AND a list of all tool changes (which tools, which fields), then confirm once more before persisting.

#### VAPI prompt + assistant `toolIds` updates

PATCH the in-scope assistant(s) on VAPI directly. The MCP server doesn't expose VAPI write endpoints, so use `Bash` + `curl`:

```
curl -fsS -X PATCH \
  -H "Authorization: Bearer $VAPI_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":{"provider":"<existing>","model":"<existing>","messages":[{"role":"system","content":"<NEW_PROMPT>"}, ... <other existing messages unchanged> ...],"toolIds":["<id1>","<id2>",...]}}' \
  https://api.vapi.ai/assistant/$VAPI_ASSISTANT_ID
```

Important when constructing the PATCH body:
- Read back the current `model` object from the Phase 1.4 fetch and copy provider/model/temperature/inline tools/etc. unchanged — VAPI's PATCH replaces `model` wholesale, so omitted fields will be lost.
- Replace **only** the system message's `content`. Preserve any other messages (e.g. tool-result examples) and their order.
- If updating `toolIds`: send the **full new array** (PATCH replaces it). Add or remove ids relative to the previous array; don't re-sort or de-duplicate without intent.
- For squads with multiple in-scope members edited in this iteration, PATCH each member separately.
- Do not touch the Cekura `description` field. It is informational and stays as-is.

#### VAPI tool-definition edits

For each tool whose definition changed, PATCH the tool directly:

```
curl -fsS -X PATCH \
  -H "Authorization: Bearer $VAPI_KEY" \
  -H "Content-Type: application/json" \
  -d '<full tool body with edited fields>' \
  https://api.vapi.ai/tool/$TOOL_ID
```

Construction rules:
- Fetch the current tool first (`GET /tool/{id}`), modify only the changed fields in memory, send the result. VAPI's tool PATCH semantics also replace nested objects wholesale — omitting `messages` or `destinations` will wipe them.
- Common edits and the field they touch:
  - **Spoken `request-start` adjustment**: `messages[?(@.type=='request-start')].content`
  - **Failure messaging**: `messages[?(@.type=='request-failed')].content`
  - **Function description / parameters**: `function.description`, `function.parameters`
  - **Handoff destination**: `destinations[i].assistantId`, `destinations[i].description`
- **Back up the original tool body** to a local file before PATCHing — keep one snapshot per tool per iteration so a revert is one PUT/PATCH away.

#### VAPI new tool creation

```
curl -fsS -X POST \
  -H "Authorization: Bearer $VAPI_KEY" \
  -H "Content-Type: application/json" \
  -d '<full tool body — type, function spec, messages, destinations as needed>' \
  https://api.vapi.ai/tool
```

The response includes the new `id`. Use it in the subsequent assistant PATCH's `toolIds`. Don't reference an id that hasn't returned 2xx yet.

#### VAPI tool deletion (rare — gated by Step 3.4 anti-patterns)

Only after confirming no other in-scope or out-of-scope assistant references it:

```
curl -fsS -X DELETE \
  -H "Authorization: Bearer $VAPI_KEY" \
  https://api.vapi.ai/tool/$TOOL_ID
```

Deletion is irreversible from this skill — there's no undo PATCH. If unsure, drop the reference (Step 3.4 "Remove a tool reference") and leave the definition in place.

#### Retell

Retell tool config is owned by the platform and is not editable from this skill. Only prompt edits apply:

- `mcp__cekura__aiagents_partial_update` with the agent_id and `{"description": "<new prompt>"}`

If the agent has dynamic-variable placeholders (`{{...}}`), confirm they're preserved verbatim in the merged prompt regardless of provider.

### Step 4.2 — Make sure the provider is running the new prompt and tool config

What the live agent runs depends on where Step 4.1 wrote:

- **VAPI** — Step 4.1 PATCHed VAPI directly. New prompts, new/edited tool definitions, and `toolIds` membership are all live as soon as their PATCH/POST/DELETE returns 2xx. Confirm by re-fetching:
  - `curl GET https://api.vapi.ai/assistant/{id}` — verify system message content AND `toolIds` array match the intended state.
  - `curl GET https://api.vapi.ai/tool/{id}` — for every tool you edited or created, verify the changed fields landed.
  Don't skip the tool re-fetch — VAPI's tool PATCH semantics replace nested objects wholesale, and a malformed body can silently wipe `messages` or `destinations` while still returning 200.
- **Retell with `auto_sync_prompt_enabled: true`** — Cekura syncs the prompt to Retell within ~30 seconds. Wait that long, then proceed.
- **Retell without auto-sync** — the provider side does **not** update automatically. Tell the user to push the new prompt to the Retell dashboard (Retell agents → Prompt) before validation runs, then confirm with them.

If the provider isn't running the new prompt **or** the new tool config, validation runs will pass/fail based on stale state and the loop will spin forever. Don't proceed to Step 4.3 until both prompt and tool changes are confirmed live.

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

The exit criterion is **100% pass rate on the validation set** — zero failures of any class. The voice/infra filter exists for diagnosis (to focus Phase 3 on prompt-fixable issues), not as the loop's stopping criterion. Do not declare success while the agent is still failing, even when the remaining failures don't look prompt-shaped.

Decide as follows:

- **100% pass rate** → success. Report the final pass rate, the cumulative diff applied, and stop.
- **Kept (prompt-following) failures > 0** → loop normally:
  1. Feed the new failure summary and the **current (post-edit) prompt** back into Phase 3.
  2. Phase 3 produces a fresh proposal against the updated prompt.
  3. User review (Step 3.5) gates re-entry to this phase.
  4. Repeat from Step 4.1.
- **Kept failures = 0 but total failures > 0** (all remaining failures look voice/infra/tool):
  Do **not** exit yet. Work through these checks first, in order:
  1. **Re-classify with fresh eyes.** A tool error response *handled badly* by the agent is a prompt issue (the agent should have retried, fallen back, or escalated cleanly). Only count as infra if the agent handled the error correctly. A behavior in a *different squad member* than the one currently scoped is still a prompt issue — just out of current scope. Repeated identical agent utterances, self-handoffs, wrong-handoff destinations, and per-member instruction drift are all prompt-fixable; they just live in members you didn't scope yet.
  2. **Expand squad scope** (squads only). If failures localize to members not currently in scope, ask the user to add them, then re-enter Phase 3 with the expanded scope. The first iteration usually narrows on the entry assistant; deeper failures only become visible after that one passes, so scope expansion across iterations is expected, not a regression.
  3. **Consider mitigation edits — prompt AND tool config.** Some "infra" failures can be partially mitigated:
     - **By prompt**: better retry counts, clearer fallback messaging, faster escalation, different tool-call argument shaping, or guarding against missing dynamic variables.
     - **By tool config (VAPI)**: a noisy `request-start` message that fires on every routing event, a `request-failed.content` that's misleading to the LLM, a tool whose `function.description` over-matches user intent and gets called too often, a handoff `destinations[]` entry pointing at the wrong assistant, or a self-referencing destination that drives a self-handoff loop. These are tool edits, not prompt edits, and they often resolve "infra-shaped" failures that no prompt change can touch.
     Surface both kinds as Phase 3 candidates and let the user decide.
  4. **Only after all three above are exhausted** (no missed prompt issues, no out-of-scope members worth pulling in, no plausible mitigation edit) → surface a clear stop with the residual failures, hand off to the appropriate skill (`create-agent` for tool/config issues, backend team for upstream service errors), and exit. Do not silently exit.

The "kept = 0 but total > 0" path must surface its decision to the user — explicitly state which of the three checks ruled out further iteration. Don't use shape of the failures alone as a reason to stop.

### Iteration cap

Default to **10 iterations** of the loop. If the user supplies a `max_iterations` value when invoking the skill (e.g., "keep going up to 20", "cap at 5"), use that instead. The cap is the **only safety net** besides 100% pass rate — it prevents runaway loops when the residual failures genuinely cannot be fixed by prompt edits (real infra outages, missing tools, dynamic-variable injection failures the user must resolve elsewhere, etc.). Without the cap, the loop is supposed to keep going.

After the cap is hit, stop and surface a summary regardless of remaining failures:

- What's been fixed (pass-rate gain, failures resolved)
- What's still failing (the residual summary)
- A recommendation: hand off to `eval-design` (test gaps), `labs-workflow` (metric quality), or `create-agent` (provider/tools/KB) depending on what the residual failures look like

The user can also stop or extend mid-loop ("keep going" / "stop"). Don't loop silently past the cap.

### Loop guardrails

- **Track cumulative diff for prompts AND tools** — show the user every change that's been applied across all iterations, not just the latest one, and split the cumulative diff by surface (prompt vs. tool definition vs. `toolIds` reference). Easy to lose context across 3 passes when changes are spread across multiple artifacts.
- **Watch for oscillation** — if iteration N's edit reverses iteration N-1's edit on the same clause OR the same tool field, stop and flag it. The two failure sets are pulling the agent in opposite directions; user judgment is needed.
- **Watch for new failures the previous state didn't have** — if iteration N introduces failures that iteration 0 didn't have, the latest edit caused a regression. Stop and offer to revert that specific edit. Tool deletes and `toolIds` removals are particularly regression-prone — the regression often shows up as a *missing* expected tool call, not an extra one.
- **Don't widen the validation set mid-loop** without telling the user. The stopping criterion depends on a stable comparison set.
- **Squad scope expansion is fair game; validation-set expansion is not.** When the "kept failures = 0 but total > 0" branch decides to bring in a new squad member, that's expanding the *edit scope*, not the validation set. Same scenarios; just more assistants (and their tools) whose config can change. The agent under test is the squad as a whole, so this is expected behavior, not a regression risk.
- **Don't stop just because the failure shape changed.** Iteration N often surfaces a different bug than iteration N-1 (e.g., fixing the entry assistant exposes a self-handoff loop in the screener, which turns out to be a tool-config issue rather than a prompt one). That's the loop working, not a reason to declare done.
- **Always back up tool definitions before editing** — `GET /tool/{id}` and stash the full body to a local file (e.g., `/tmp/vapi_tools/{id}_pre_iter{N}.json`) before issuing any PATCH. VAPI tool PATCH semantics replace nested objects wholesale; a one-line revert is `PATCH` with the backed-up body.
- **Cross-reference toolIds before deleting a tool** — fetch every squad member's `toolIds` (in-scope AND out-of-scope), confirm no one references the tool, and only then delete. If you can't fetch out-of-scope members for any reason, prefer reference removal over delete.

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
| 1 | Fetch live VAPI tool definition (direct, not MCP) | `Bash` + `curl GET https://api.vapi.ai/tool/{id}` with `VAPI_KEY` — call once per id in each in-scope assistant's `model.toolIds` |
| 2 | Run scenarios (voice / text) | `mcp__cekura__scenarios_run_scenarios_create`, `mcp__cekura__scenarios_run_scenarios_text_create` |
| 2 | Fetch result batch | `mcp__cekura__results_retrieve` |
| 2 | Bulk fetch runs | `mcp__cekura__runs_bulk_retrieve` |
| 2 | Fetch a call log | `mcp__cekura__call_logs_retrieve` |
| 3 | Auto-improve prompt (fallback) | `mcp__cekura__runs_improve_prompt_create` |
| 4 | PATCH agent prompt — Retell | `mcp__cekura__aiagents_partial_update` |
| 4 | PATCH agent prompt + `toolIds` — VAPI (direct) | `Bash` + `curl -X PATCH https://api.vapi.ai/assistant/{id}` with `VAPI_KEY` |
| 4 | Edit a VAPI tool definition (direct) | `Bash` + `curl -X PATCH https://api.vapi.ai/tool/{id}` with `VAPI_KEY` |
| 4 | Create a VAPI tool (direct) | `Bash` + `curl -X POST https://api.vapi.ai/tool` with `VAPI_KEY` |
| 4 | Delete a VAPI tool (direct, gated) | `Bash` + `curl -X DELETE https://api.vapi.ai/tool/{id}` with `VAPI_KEY` |
| 4 | Synthesize scenario from a transcript | `mcp__cekura__scenarios_create_scenario_from_transcript_create` |

**Docs lookup:** Use `mcp__cekura__search_cekura` or fetch `https://docs.cekura.ai/llms.txt` for field schemas, response shapes, or tool details when this skill doesn't cover them.

**Troubleshooting:** If MCP tools aren't available, verify (1) `CEKURA_API_KEY` is set, (2) the MCP server is running on port 8001, (3) restart Claude Code to pick up the `.mcp.json` config. Run `/setup-mcp` for guided setup.

## Anti-Patterns

These apply to the skill as a whole. Phase-specific anti-patterns are covered inside each phase.

- **Running the loop on a tiny input.** A single failing run / call is rarely enough signal — one-off failures often reflect noise, not a prompt defect. Ask for at least 5-10 items before iterating, or surface the small-sample caveat in the summary.
- **Iterating with a noisy metric.** If most kept failures come from one metric whose explanations look subjective, the metric is probably miscalibrated. Hand off to `labs-workflow` first; otherwise the loop will keep "fixing" the prompt to satisfy a flawed judge.
- **Skipping the provider sync gate (Phase 4.2).** For VAPI, confirm the PATCH actually landed (re-fetch and diff the system message). For Retell without auto-sync, Cekura's stored description is not what the live agent runs until the user pushes it from the dashboard. Without confirmation, the loop validates the old prompt and never converges.
- **Bypassing user review at phase boundaries.** This skill applies edits to a live agent. Every transition (Phase 2 summary → Phase 3 proposal → Phase 4 apply) must be explicitly approved.
- **Quitting the loop the moment failures look non-prompt.** The exit gate is 100% pass rate or the iteration cap — not "first sight of an infra-shaped failure." If a residual failure looks like infra/tool/config, first verify there's no in-scope or out-of-scope prompt OR tool-config issue you missed: how the agent *handles* a tool error is a prompt question, a noisy `request-start` message is a tool-config question, and squad members / tools you didn't scope are out of scope but still fixable. Only after exhausting both prompt and tool-config options (re-classify, expand squad scope, propose mitigation prompt edits, propose tool-config edits) should you hand off to `create-agent` for genuine provider/integration issues.
- **Treating expected-outcome failures and metric failures the same.** Expected-outcome failures are first-class signal about agent behavior. Metric failures may reflect either the agent or the metric — be more skeptical.

## Hand-off to Other Skills

If the failures don't actually point at the prompt, redirect rather than iterate:

- **`create-agent`** (in this same plugin) — when failures stem from missing/misconfigured tools, an outdated knowledge base, or provider integration issues. No prompt edit will fix a missing tool.
- **`eval-design`** (in `cekura-evals`) — when the test set itself is the problem (too narrow, missing key flows, no coverage of failure modes seen in production). Improving the prompt against a thin eval set just overfits.
- **`metric-design`** (in `cekura-metrics`) — when failures cluster on metrics whose definitions look weak or off-target.
- **`labs-workflow`** (in `cekura-metrics`) — when metric pass/fail verdicts seem misaligned with the transcripts. Fix the metric first, *then* come back here.
- **`coordinator`** (in this same plugin) — if the user is unsure where the issue is, route them through coordinator to triage.

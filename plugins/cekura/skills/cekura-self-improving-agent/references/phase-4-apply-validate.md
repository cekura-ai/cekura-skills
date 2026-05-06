# Phase 4 — Apply, Validate, Iterate Reference

VAPI PATCH / POST / DELETE curl bodies, tool-backup pattern, validation-set construction details, loop guardrails, and iteration-cap exit messaging.

## Apply order (recap)

1. **Tool-definition edits first** (PATCH `/tool/{id}`).
2. **New tool creation** next (POST `/tool`), capturing the new id.
3. **Assistant `model.toolIds` updates** (add / remove references) bundled into the assistant PATCH.
4. **System prompt edits** in the same assistant PATCH as the `toolIds` updates — one PATCH per assistant.

The order matters: a new tool must exist before the assistant PATCH lands; bundling `toolIds` + prompt into one assistant PATCH keeps the LLM's view of "tools available" and "instructions about those tools" consistent across the rollout.

## VAPI prompt + assistant `toolIds` PATCH

The id is the VAPI `assistant.id` resolved in Phase 1 (for squads, this is each member's `assistantId` — **not** the squad id; you cannot PATCH a squad to change a member's prompt):

```
curl -fsS -X PATCH \
  -H "Authorization: Bearer $VAPI_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":{"provider":"<existing>","model":"<existing>","messages":[{"role":"system","content":"<NEW_PROMPT>"}, ... <other existing messages unchanged> ...],"toolIds":["<id1>","<id2>",...]}}' \
  https://api.vapi.ai/assistant/<assistant_id>
```

Construction rules:

- Read back the current `model` object from the Phase 1 fetch and copy provider/model/temperature/inline tools/etc. unchanged — VAPI's PATCH replaces `model` wholesale, so omitted fields will be lost.
- Replace **only** the system message's `content`. Preserve any other messages (e.g. tool-result examples) and their order.
- If updating `toolIds`: send the **full new array** (PATCH replaces it). Add or remove ids relative to the previous array; don't re-sort or de-duplicate without intent.
- For squads with multiple members edited in this iteration, PATCH each member separately.
- Do not touch the Cekura `description` field. It is informational and stays as-is.
- If the agent has dynamic-variable placeholders (`{{...}}`), confirm they're preserved verbatim in the merged prompt.

## VAPI tool-definition PATCH

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

### Tool-backup pattern

**Back up the original tool body** to a local file before PATCHing — keep one snapshot per tool per iteration so a revert is one PUT/PATCH away:

```
mkdir -p /tmp/vapi_tools
curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/tool/$TOOL_ID \
  > /tmp/vapi_tools/${TOOL_ID}_pre_iter${N}.json
```

A one-line revert is `PATCH` with the backed-up body.

## VAPI new tool creation

```
curl -fsS -X POST \
  -H "Authorization: Bearer $VAPI_KEY" \
  -H "Content-Type: application/json" \
  -d '<full tool body — type, function spec, messages, destinations as needed>' \
  https://api.vapi.ai/tool
```

The response includes the new `id`. Use it in the subsequent assistant PATCH's `toolIds`. Don't reference an id that hasn't returned 2xx yet.

## VAPI tool deletion (rare)

Only after confirming no other squad member references it:

```
curl -fsS -X DELETE \
  -H "Authorization: Bearer $VAPI_KEY" \
  https://api.vapi.ai/tool/$TOOL_ID
```

Deletion is irreversible from this skill — there's no undo PATCH. If unsure, drop the reference (Phase 3 "Remove a tool reference") and leave the definition in place.

## Step 4.2 — Provider-sync re-fetch

Step 4.1 PATCHed VAPI directly. New prompts, new/edited tool definitions, and `toolIds` membership are all live as soon as their PATCH/POST/DELETE returns 2xx. Confirm by re-fetching:

- `curl GET https://api.vapi.ai/assistant/{id}` — verify system message content AND `toolIds` array match the intended state.
- `curl GET https://api.vapi.ai/tool/{id}` — for every tool you edited or created, verify the changed fields landed.

Don't skip the tool re-fetch — VAPI's tool PATCH semantics replace nested objects wholesale, and a malformed body can silently wipe `messages` or `destinations` while still returning 200.

If the provider isn't running the new prompt **or** the new tool config, validation runs will pass/fail based on stale state and the loop will spin forever. Don't proceed to Step 4.3 until both prompt and tool changes are confirmed live.

## Step 4.3 — Validation set construction

Pick the validation set based on the **original input type** to this skill (the same input the user passed in Phase 2):

| Original input | Validation set |
|----------------|----------------|
| `scenario_ids` | Reuse the same scenario IDs. |
| `result_id` | Extract `scenario_id` from every run inside the result (already fetched in Phase 2.2). De-duplicate. |
| `run_ids` | Extract `scenario_id` from every run (already fetched via the bulk-retrieve in Phase 2.2). De-duplicate. |
| `call_ids` | Generate one scenario per call by synthesizing from the transcript. **Cache the new scenario IDs on the first iteration** so subsequent loop iterations reuse them rather than re-creating from transcripts each time. |

**Why scenarios for `call_ids`:** call logs are production calls, not reproducible — to validate fixes, we synthesize a scenario from each transcript and re-run it against the new prompt.

The validation set should match the failure set when possible — re-running only the scenarios that failed initially gives the cleanest signal that the edit fixed *those specific failures*. Optionally, the user can request the full set (including previously-passing scenarios) to guard against regressions; default to failure-only.

If the original input was `call_ids` and any of those call logs were `reviewed_success`, their re-synthesized scenarios should be excluded from the validation set (cache the exclusion at Step 4.3 alongside the cached scenario IDs).

## Step 4.6 — Decision logic

The exit criterion is **100% pass rate on the validation set** — zero failures of any class. The voice/infra filter exists for diagnosis (to focus Phase 3 on prompt-fixable issues), not as the loop's stopping criterion. Do not declare success while the agent is still failing, even when the remaining failures don't look prompt-shaped.

- **100% pass rate** → success. Report the final pass rate, the cumulative diff applied, and stop.
- **Kept (prompt-following) failures > 0** → loop normally:
  1. Feed the new failure summary and the **current (post-edit) prompt** back into Phase 3.
  2. Phase 3 produces a fresh proposal against the updated prompt.
  3. Surface the proposal and **wait for explicit approval** before continuing to Step 4.1 — the user gate fires on every iteration.
  4. Repeat from Step 4.1 with the approved subset for this iteration.
- **Kept failures = 0 but total failures > 0** (all remaining failures look voice/infra/tool):
  Do **not** exit yet. Work through these checks first, in order:
  1. **Re-classify with fresh eyes.** A tool error response *handled badly* by the agent is a prompt issue (the agent should have retried, fallen back, or escalated cleanly). Only count as infra if the agent handled the error correctly. Repeated identical agent utterances, self-handoffs, wrong-handoff destinations, and per-member instruction drift are all prompt-fixable. For squads, re-attribute each failure to whichever member was speaking in the relevant transcript turn — Phase 3 already considers all members editable, so the fix may simply live in a member that hadn't been touched yet.
  2. **Consider mitigation edits — prompt AND tool config.** Some "infra" failures can be partially mitigated:
     - **By prompt**: better retry counts, clearer fallback messaging, faster escalation, different tool-call argument shaping, or guarding against missing dynamic variables.
     - **By tool config (VAPI)**: a noisy `request-start` message that fires on every routing event, a `request-failed.content` that's misleading to the LLM, a tool whose `function.description` over-matches user intent and gets called too often, a handoff `destinations[]` entry pointing at the wrong assistant, or a self-referencing destination that drives a self-handoff loop. These are tool edits, not prompt edits, and they often resolve "infra-shaped" failures that no prompt change can touch.
     Surface both kinds as Phase 3 candidates on the next iteration.
  3. **Only after both above are exhausted** (no missed prompt issues across any member, no plausible mitigation edit) → surface a clear stop with the residual failures, hand off to the appropriate skill (`cekura-create-agent` for tool/config issues, backend team for upstream service errors), and exit. Do not silently exit.

The "kept = 0 but total > 0" path must surface its decision to the user — explicitly state which of the two checks ruled out further iteration. Don't use shape of the failures alone as a reason to stop.

## Iteration cap

Default to **10 iterations** of the loop. If the user supplies a `max_iterations` value when invoking the skill (e.g., "keep going up to 20", "cap at 5"), use that instead. The cap is the **only safety net** besides 100% pass rate — it prevents runaway loops when the residual failures genuinely cannot be fixed by prompt edits (real infra outages, missing tools, dynamic-variable injection failures the user must resolve elsewhere, etc.). Without the cap, the loop is supposed to keep going.

After the cap is hit, stop and surface a summary regardless of remaining failures:

- What's been fixed (pass-rate gain, failures resolved)
- What's still failing (the residual summary)
- A recommendation: hand off to `cekura-eval-design` (test gaps), `cekura-metric-improvement` (metric quality), or `cekura-create-agent` (provider/tools/KB) depending on what the residual failures look like

The user can also stop or extend mid-loop ("keep going" / "stop"). Don't loop silently past the cap.

## Loop guardrails

- **Track cumulative diff for prompts AND tools** — show the user every change that's been applied across all iterations, not just the latest one, and split the cumulative diff by surface (prompt vs. tool definition vs. `toolIds` reference). Easy to lose context across 3 passes when changes are spread across multiple artifacts.
- **Watch for oscillation** — if iteration N's edit reverses iteration N-1's edit on the same clause OR the same tool field, stop and flag it. The two failure sets are pulling the agent in opposite directions; user judgment is needed.
- **Don't widen the validation set mid-loop** without telling the user. The stopping criterion depends on a stable comparison set.
- **Validation-set expansion is not fair game.** All squad members are already in edit scope by default, so there's no scope-expansion step. But the validation set must stay stable across iterations: same scenarios; only the agent's prompts/tools change between iterations. Never quietly add scenarios mid-loop — that breaks the comparison.
- **Don't stop just because the failure shape changed.** Iteration N often surfaces a different bug than iteration N-1 (e.g., fixing the entry assistant exposes a self-handoff loop in the screener, which turns out to be a tool-config issue rather than a prompt one). That's the loop working, not a reason to declare done.
- **Always back up tool definitions before editing** — `GET /tool/{id}` and stash the full body to a local file (e.g., `/tmp/vapi_tools/{id}_pre_iter{N}.json`) before issuing any PATCH. VAPI tool PATCH semantics replace nested objects wholesale; a one-line revert is `PATCH` with the backed-up body.
- **Cross-reference toolIds before deleting a tool** — every squad member's `toolIds` is already fetched in Phase 1; confirm no member references the tool before deleting. If in any doubt, prefer reference removal over delete.

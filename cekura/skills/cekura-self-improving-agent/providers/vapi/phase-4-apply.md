# Phase 4 — Apply, Validate, Iterate Reference

VAPI PATCH / POST / DELETE curl bodies, tool-backup pattern, validation-set construction, loop guardrails, and iteration-cap exit messaging.

## Apply order

1. **Tool-definition edits** (PATCH `/tool/{id}`).
2. **New tool creation** (POST `/tool`), capturing the new id.
3. **Assistant `model.toolIds` updates** bundled into the assistant PATCH.
4. **System prompt edits** in the same assistant PATCH as `toolIds` — one PATCH per assistant.

A new tool must exist before the assistant PATCH lands. Bundling `toolIds` + prompt into one assistant PATCH keeps the LLM's view of available tools and instructions consistent.

## VAPI prompt + assistant `toolIds` PATCH

The id is the VAPI `assistant.id` from Phase 1 (for squads, each member's `assistantId` — **not** the squad id; you cannot PATCH a squad to change a member's prompt):

```
curl -fsS -X PATCH \
  -H "Authorization: Bearer $VAPI_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":{"provider":"<existing>","model":"<existing>","messages":[{"role":"system","content":"<NEW_PROMPT>"}, ... <other existing messages unchanged> ...],"toolIds":["<id1>","<id2>",...]}}' \
  https://api.vapi.ai/assistant/<assistant_id>
```

Construction rules:

- Copy the current `model` object from the Phase 1 fetch unchanged (provider/model/temperature/inline tools/etc.) — VAPI PATCH replaces `model` wholesale; omitted fields are lost.
- Replace **only** the system message's `content`. Preserve any other messages and their order.
- If updating `toolIds`: send the **full new array**. Add or remove ids relative to the previous array.
- For squads with multiple members edited, PATCH each member separately.
- Do not touch the Cekura `description` field.
- Preserve dynamic-variable placeholders (`{{...}}`) verbatim.

## VAPI tool-definition PATCH

```
curl -fsS -X PATCH \
  -H "Authorization: Bearer $VAPI_KEY" \
  -H "Content-Type: application/json" \
  -d '<full tool body with edited fields>' \
  https://api.vapi.ai/tool/$TOOL_ID
```

Construction rules:

- Fetch the current tool first (`GET /tool/{id}`), modify only the changed fields in memory, send the result. Tool PATCH also replaces nested objects wholesale — omitting `messages` or `destinations` wipes them.
- Common edits and their fields:
  - **Spoken `request-start` adjustment**: `messages[?(@.type=='request-start')].content`
  - **Failure messaging**: `messages[?(@.type=='request-failed')].content`
  - **Function description / parameters**: `function.description`, `function.parameters`
  - **Handoff destination**: `destinations[i].assistantId`, `destinations[i].description`

### Tool-backup pattern

Back up the original tool body before PATCHing — one snapshot per tool per iteration:

```
mkdir -p /tmp/vapi_tools
curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/tool/$TOOL_ID \
  > /tmp/vapi_tools/${TOOL_ID}_pre_iter${N}.json
```

Revert: PATCH with the backed-up body.

## VAPI new tool creation

```
curl -fsS -X POST \
  -H "Authorization: Bearer $VAPI_KEY" \
  -H "Content-Type: application/json" \
  -d '<full tool body — type, function spec, messages, destinations as needed>' \
  https://api.vapi.ai/tool
```

The response includes the new `id`. Use it in the subsequent assistant PATCH's `toolIds`. Don't reference an id that hasn't returned 2xx.

## VAPI tool deletion (rare)

Only after confirming no other squad member references it:

```
curl -fsS -X DELETE \
  -H "Authorization: Bearer $VAPI_KEY" \
  https://api.vapi.ai/tool/$TOOL_ID
```

Deletion is irreversible from this skill. If unsure, drop the reference and leave the definition in place.

## Step 4.2 — Provider-sync re-fetch

After PATCH/POST/DELETE returns 2xx, confirm by re-fetching:

- `curl GET https://api.vapi.ai/assistant/{id}` — verify system message content AND `toolIds` array.
- `curl GET https://api.vapi.ai/tool/{id}` — for every tool edited or created, verify changed fields landed.

Don't skip the tool re-fetch — a malformed body can silently wipe `messages` or `destinations` while returning 200. Don't proceed to Step 4.3 until both prompt and tool changes are confirmed live.

## Step 4.3 — Validation set construction

| Original input | Validation set |
|----------------|----------------|
| `scenario_ids` | Reuse the same scenario IDs. |
| `result_id` | Extract `scenario_id` from every run inside the result (Phase 2.2). De-duplicate. |
| `run_ids` | Extract `scenario_id` from every run (Phase 2.2 bulk-retrieve). De-duplicate. |
| `call_ids` | Generate one scenario per call from the transcript. **Cache the new scenario IDs on the first iteration** so subsequent iterations reuse them. |

For `call_ids`: if any call log was `reviewed_success`, exclude its re-synthesized scenario (cache the exclusion alongside the scenario IDs).

Default to the failure-only subset for the cleanest fix signal. The user can request the full set to guard against regressions.

## Step 4.6 — Decision logic

Exit criterion: **100% pass rate on the validation set**. The voice/infra filter narrows Phase 3 diagnosis — it is not the loop's stopping criterion.

- **100% pass rate** → success. Report final pass rate, cumulative diff, stop.
- **Kept failures > 0** → loop:
  1. Feed the new failure summary and the **current (post-edit) prompt** back into Phase 3.
  2. Phase 3 proposes edits against the updated prompt.
  3. Surface the proposal and wait for explicit approval before Step 4.1.
  4. Repeat from Step 4.1 with the approved subset.
- **Kept failures = 0 but total failures > 0** (all remaining failures look voice/infra/tool): work through these checks before stopping:
  1. **Re-classify with fresh eyes.** A tool error handled badly by the agent is a prompt issue. Repeated identical utterances, self-handoffs, wrong-handoff destinations, and per-member instruction drift are prompt-fixable. For squads, re-attribute each failure to the member speaking in the relevant transcript turn.
  2. **Consider mitigation edits — prompt AND tool config.** Some "infra" failures can be partially mitigated:
     - **By prompt**: better retry counts, clearer fallback messaging, faster escalation, different tool-call argument shaping, guarding against missing dynamic variables.
     - **By tool config**: a noisy `request-start` message, a misleading `request-failed.content`, a `function.description` that over-matches user intent, a wrong `destinations[]` entry, or a self-referencing destination driving a self-handoff loop. Surface both kinds as Phase 3 candidates.
  3. **Only after both above are exhausted** → surface a clear stop with residual failures, hand off (`cekura-create-agent` for tool/config issues, backend team for upstream errors), and exit. Don't silently exit.

The "kept = 0 but total > 0" path must explicitly state which check ruled out further iteration.

## Iteration cap

Default: **10 iterations**. Use the user-supplied `max_iterations` if provided. After the cap is hit, surface:

- What's been fixed (pass-rate gain, failures resolved)
- What's still failing (residual summary)
- Recommendation: `cekura-eval-design` (test gaps), `cekura-metric-improvement` (metric quality), or `cekura-create-agent` (provider/tools/KB)

Don't loop silently past the cap. The user can also stop or extend mid-loop.

## Loop guardrails

- **Track cumulative diff for prompts AND tools** — show every change applied across all iterations, split by surface (prompt vs. tool definition vs. `toolIds` reference).
- **Watch for oscillation** — if iteration N's edit reverses iteration N-1's edit on the same clause or tool field, stop and flag it. User judgment is needed.
- **Don't widen the validation set mid-loop** without telling the user.
- **Validation set must stay stable across iterations** — same scenarios; only prompts/tools change. Never quietly add scenarios.
- **Don't stop just because the failure shape changed.** Fixing one bug often exposes the next (e.g., fixing the entry assistant reveals a self-handoff loop in the screener). That's the loop working.
- **Always back up tool definitions before editing** — `GET /tool/{id}` and stash the full body to `/tmp/vapi_tools/{id}_pre_iter{N}.json` before any PATCH.
- **Cross-reference toolIds before deleting a tool** — all members' `toolIds` are already fetched in Phase 1; confirm no member references the tool before deleting.

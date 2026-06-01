# Phase 4 — Apply, Validate, Iterate Reference (ElevenLabs)

ElevenLabs PATCH / POST / DELETE curl bodies, tool-backup pattern, the re-fetch verification step, validation-set construction, loop guardrails, and iteration-cap exit messaging. Edits land live on ElevenLabs — there is **no redeploy step** (Apply Step APPLY.2 is skipped, same as VAPI).

## Apply order (recap)

1. **Tool-definition edits first** (PATCH `/v1/convai/tools/{id}`).
2. **New tool creation** next (POST `/v1/convai/tools`), capturing the new id.
3. **Agent `prompt.tool_ids` updates** (add / remove references) bundled into the agent PATCH.
4. **System prompt edits** in the same agent PATCH as the `tool_ids` updates — one PATCH for the agent.

The order matters: a new tool must exist before the agent PATCH references it; bundling `tool_ids` + prompt into one agent PATCH keeps the LLM's view of "tools available" and "instructions about those tools" consistent.

## ElevenLabs prompt + `tool_ids` PATCH

The prompt is nested at `conversation_config.agent.prompt.prompt`. ElevenLabs PATCH deep-merges `conversation_config`, but **arrays included in the body replace wholesale** — so when changing `tool_ids` send the full new array, and when leaving tools alone omit the array entirely.

```
curl -fsS -X PATCH \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"conversation_config":{"agent":{"prompt":{"prompt":"<NEW_PROMPT>","tool_ids":["<id1>","<id2>",...]}}}}' \
  https://api.elevenlabs.io/v1/convai/agents/<agent_id>
```

Construction rules:

- The prompt lives at `conversation_config.agent.prompt.prompt`. **Do not** send a top-level `prompt` key — it's ignored and the edit silently no-ops.
- To change only the prompt and leave tools untouched, send just `{"conversation_config":{"agent":{"prompt":{"prompt":"<NEW_PROMPT>"}}}}` — omit `tool_ids` so the existing array is preserved.
- To change `tool_ids`: send the **full new array** (it replaces wholesale). Add or remove ids relative to the previous array fetched in Phase 1; don't re-sort or de-duplicate without intent.
- Preserve the other `prompt` sub-fields (`llm`, `temperature`, `max_tokens`, `knowledge_base`) — the deep merge keeps them when omitted, but if you send a `prompt` object that includes some of them, include all you intend to keep.
- Do not touch the Cekura `description` field. ElevenLabs is the source of truth.
- If the agent has dynamic-variable placeholders (`{{...}}`), confirm they're preserved verbatim in the merged prompt.

### Inline (legacy) tools

If the agent embeds tools at `conversation_config.agent.prompt.tools` (rather than referencing `tool_ids`), edit them by sending the **full `tools` array** with the changed entry modified in place:

```
curl -fsS -X PATCH \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"conversation_config":{"agent":{"prompt":{"tools":[<full array, edited entry in place>]}}}}' \
  https://api.elevenlabs.io/v1/convai/agents/<agent_id>
```

The array replaces wholesale — preserve every entry you aren't changing.

## ElevenLabs standalone tool PATCH

For each referenced tool whose definition changed, PATCH the tool directly:

```
curl -fsS -X PATCH \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_config": <full tool_config with edited fields>}' \
  https://api.elevenlabs.io/v1/convai/tools/$TOOL_ID
```

Construction rules:

- Fetch the current tool first (`GET /v1/convai/tools/{id}`), modify only the changed fields in memory inside `tool_config`, send the result.
- Common edits and the field they touch:
  - **Tool description** (when/what the LLM should call it for): `tool_config.description`
  - **Webhook request shape**: `tool_config.api_schema` (url / method / parameter schemas)
  - **Client-tool parameters**: `tool_config.parameters`
- Do NOT edit `tool_config.name` casually — the LLM and the prompt reference the tool by name; a rename must be matched in the prompt and anywhere else it's mentioned, atomically.

### Tool-backup pattern

**Back up the original tool body** to a local file before PATCHing — one snapshot per tool per iteration so a revert is one PATCH away:

```
mkdir -p /tmp/elevenlabs_tools
curl -fsS -H "xi-api-key: $ELEVENLABS_API_KEY" \
  https://api.elevenlabs.io/v1/convai/tools/$TOOL_ID \
  > /tmp/elevenlabs_tools/${TOOL_ID}_pre_iter${N}.json
```

A one-line revert is `PATCH` with the backed-up `tool_config`.

## ElevenLabs new tool creation

```
curl -fsS -X POST \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_config": <type, name, description, api_schema/parameters as needed>}' \
  https://api.elevenlabs.io/v1/convai/tools
```

The response includes the new `id`. Use it in the subsequent agent PATCH's `tool_ids`. Don't reference an id that hasn't returned 2xx yet.

## ElevenLabs tool deletion (rare)

```
curl -fsS -X DELETE \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  https://api.elevenlabs.io/v1/convai/tools/$TOOL_ID
```

Standalone tools are workspace-scoped and may be referenced by **other agents**. Check `access_info` / `usage_stats` on the tool (returned by the GET) before deleting. Prefer dropping the reference from this agent's `prompt.tool_ids` over deleting the definition; deletion is irreversible from this skill.

## Step 4.2 — Re-fetch verification

Step 4.1 PATCHed ElevenLabs directly; new prompts, new/edited tool definitions, and `tool_ids` membership are all live as soon as their PATCH/POST/DELETE returns 2xx. Confirm by re-fetching:

- `GET /v1/convai/agents/{id}` — verify `conversation_config.agent.prompt.prompt` matches the new prompt AND `prompt.tool_ids` matches the intended array.
- `GET /v1/convai/tools/{id}` — for every tool you edited or created, verify the changed `tool_config` fields landed.

Don't skip the tool re-fetch, and don't trust a 200 on the agent PATCH alone — ElevenLabs deep-merges `conversation_config`, but a body that nests the prompt at the wrong path (e.g. top-level `prompt`) returns 200 while changing nothing. The only proof the edit landed is the re-fetched value matching the intended string.

If ElevenLabs isn't running the new prompt or tool config, validation runs will pass/fail on stale state and the loop will spin. Don't proceed to validation until both prompt and tool changes are confirmed live.

## Step 4.3 — Validation set construction

Pick the validation set based on the **original input type** to this skill (the same input the user passed to Collect):

| Original input | Validation set |
|----------------|----------------|
| `scenario_ids` | Reuse the same scenario IDs. |
| `result_id` | Extract `scenario_id` from every run inside the result (already fetched in Collect). De-duplicate. |
| `run_ids` | Extract `scenario_id` from every run (already fetched via bulk-retrieve in Collect). De-duplicate. |
| `call_ids` | Synthesize one scenario per call from its transcript. **Cache the new scenario IDs on the first iteration** so subsequent iterations reuse them rather than re-creating from transcripts each time. |

Run the validation set in voice mode (ElevenLabs agents are voice). The validation set should match the failure set when possible — re-running only the scenarios that failed initially gives the cleanest signal. The final regression sweep runs the full set (see eval phase Step EVAL.4).

If the original input was `call_ids` and any of those call logs were `reviewed_success`, exclude their re-synthesized scenarios from the validation set.

## Step 4.6 — Decision logic

The exit criterion is **100% pass rate on the full set** — zero failures of any class. The voice/infra filter exists for diagnosis (to focus Diagnose on prompt-fixable issues), not as the loop's stopping criterion. Do not declare success while the agent is still failing, even when the remaining failures don't look prompt-shaped.

The decision tree is the cross-mode one in [`../../phases/eval.md`](../../phases/eval.md) Step EVAL.4 — loop on failure-set < 100%, regression-sweep on failure-set 100%, exit on full-set 100%, stop conditions (oscillation / no-change / 3× same-shape / cap / all-Upstream). The ElevenLabs specifics:

- **No redeploy / no-change-from-stale-state hypothesis.** Unlike self-hosted modes, ElevenLabs edits land live, so the "your server didn't restart" hypothesis does not apply. A no-change signature here means the edit didn't address the root cause OR the re-fetch verification was skipped and the PATCH silently no-op'd (see Step 4.2) — check the verification first.
- **Kept failures = 0 but total > 0** (all remaining look voice/infra/tool): re-classify with fresh eyes (a tool-error handled badly by the agent is a prompt issue), consider mitigation edits (prompt hardening, tool `api_schema` / `description` tightening), and only stop after both are exhausted. ElevenLabs has no spoken `request-start` / `destinations` surfaces to mitigate with — the mitigation levers are prompt wording and tool `description` / `api_schema`.

## Iteration cap

Default 10 iterations. Honor a user-supplied `max_iterations`. After the cap, stop and surface what's fixed, what's still failing, and a recommended hand-off skill (`cekura-eval-design` / `cekura-metric-improvement` / `cekura-create-agent`). Same as the cross-mode cap in eval phase.

## Loop guardrails

- **Track cumulative diff for prompt AND tools** — show every change applied across all iterations, split by surface (prompt vs. tool definition vs. `tool_ids` reference).
- **Watch for oscillation** — if iteration N reverses iteration N-1's edit on the same prompt clause or tool field, stop and flag it.
- **Don't widen the validation set mid-loop** without telling the user.
- **Always back up tool definitions before editing** (`GET /v1/convai/tools/{id}` to `/tmp/elevenlabs_tools/{id}_pre_iter{N}.json`).
- **Check tool `usage_stats` / `access_info` before deleting** — standalone tools are workspace-scoped and may be shared. Prefer reference removal over delete.
- **Don't stop just because the failure shape changed** — a new bug surfacing after a fix is the loop working, not a reason to declare done.

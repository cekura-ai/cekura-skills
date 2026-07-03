# Phase 4 — Apply, Validate, Iterate Reference (ElevenLabs)

Edits land live on ElevenLabs — there is **no redeploy step** (Apply Step APPLY.2 is skipped).

## Apply order

1. **Tool-definition edits** — PATCH `/v1/convai/tools/{id}`.
2. **New tool creation** — POST `/v1/convai/tools`, capturing the new id.
3. **Agent `prompt.tool_ids` updates** — bundled into the agent PATCH.
4. **System prompt edits** — in the same agent PATCH as `tool_ids`.

A new tool must exist before the agent PATCH references it. Bundling `tool_ids` + prompt into one agent PATCH keeps the LLM's view of available tools and its instructions consistent.

## ElevenLabs prompt + `tool_ids` PATCH

The prompt is at `conversation_config.agent.prompt.prompt`. ElevenLabs PATCH deep-merges `conversation_config`, but **arrays included in the body replace wholesale** — when changing `tool_ids`, send the full new array; when leaving tools alone, omit the array.

```
curl -fsS -X PATCH \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"conversation_config":{"agent":{"prompt":{"prompt":"<NEW_PROMPT>","tool_ids":["<id1>","<id2>",...]}}}}' \
  https://api.elevenlabs.io/v1/convai/agents/<agent_id>
```

Construction rules:

- The prompt lives at `conversation_config.agent.prompt.prompt`. **Do not** send a top-level `prompt` key — it's ignored and the edit silently no-ops.
- To change only the prompt and leave tools untouched: `{"conversation_config":{"agent":{"prompt":{"prompt":"<NEW_PROMPT>"}}}}` — omit `tool_ids`.
- To change `tool_ids`: send the **full new array** (it replaces wholesale). Add/remove ids relative to the array fetched in Phase 1; don't re-sort or de-duplicate without intent.
- Preserve other `prompt` sub-fields (`llm`, `temperature`, `max_tokens`, `knowledge_base`) — deep merge keeps them when omitted, but if you include a `prompt` object include all you intend to keep.
- If the agent has dynamic-variable placeholders (`{{...}}`), confirm they're preserved verbatim.

### Inline (legacy) tools

```
curl -fsS -X PATCH \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"conversation_config":{"agent":{"prompt":{"tools":[<full array, edited entry in place>]}}}}' \
  https://api.elevenlabs.io/v1/convai/agents/<agent_id>
```

The array replaces wholesale — preserve every entry you aren't changing.

## ElevenLabs standalone tool PATCH

```
curl -fsS -X PATCH \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_config": <full tool_config with edited fields>}' \
  https://api.elevenlabs.io/v1/convai/tools/$TOOL_ID
```

Construction rules:

- Fetch the current tool first (`GET /v1/convai/tools/{id}`), modify only the changed fields inside `tool_config`, send the result.
- Common edits: `tool_config.description` (when/what to call it), `tool_config.api_schema` (webhook url/method/params), `tool_config.parameters` (client-tool params).
- Do NOT rename `tool_config.name` casually — the LLM and prompt reference the tool by name; a rename must be matched in the prompt atomically.

### Tool-backup pattern

Back up the original tool body before PATCHing — one snapshot per tool per iteration:

```
mkdir -p /tmp/elevenlabs_tools
curl -fsS -H "xi-api-key: $ELEVENLABS_API_KEY" \
  https://api.elevenlabs.io/v1/convai/tools/$TOOL_ID \
  > /tmp/elevenlabs_tools/${TOOL_ID}_pre_iter${N}.json
```

Revert with a PATCH using the backed-up `tool_config`.

## ElevenLabs new tool creation

```
curl -fsS -X POST \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_config": <type, name, description, api_schema/parameters as needed>}' \
  https://api.elevenlabs.io/v1/convai/tools
```

The response includes the new `id`. Use it in the subsequent agent PATCH's `tool_ids`. Don't reference an id before it returns 2xx.

## ElevenLabs tool deletion (rare)

```
curl -fsS -X DELETE \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  https://api.elevenlabs.io/v1/convai/tools/$TOOL_ID
```

Standalone tools are workspace-scoped and may be referenced by other agents. Check `access_info` / `usage_stats` on the tool GET before deleting. Prefer dropping the reference from `prompt.tool_ids` over deleting the definition.

## Step 4.2 — Re-fetch verification

After all PATCH/POST/DELETE calls return 2xx, re-fetch to confirm:

- `GET /v1/convai/agents/{id}` — verify `conversation_config.agent.prompt.prompt` matches the new prompt AND `prompt.tool_ids` matches the intended array.
- `GET /v1/convai/tools/{id}` — for every tool edited or created, verify the changed `tool_config` fields landed.

**Do not skip the tool re-fetch.** A body that nests the prompt at the wrong path (e.g. top-level `prompt`) returns 200 while changing nothing. The only proof the edit landed is the re-fetched value matching the intended string.

Don't proceed to validation until both prompt and tool changes are confirmed live — validation on stale state spins the loop.

## Step 4.3 — Validation set construction

| Original input | Validation set |
|----------------|----------------|
| `scenario_ids` | Reuse the same scenario IDs. |
| `result_id` | Extract `scenario_id` from every run inside the result (already fetched in Collect). De-duplicate. |
| `run_ids` | Extract `scenario_id` from every run (bulk-retrieved in Collect). De-duplicate. |
| `call_ids` | Synthesize one scenario per call from its transcript. **Cache the new scenario IDs on the first iteration** — reuse them on subsequent iterations, don't re-synthesize. |

Run in voice mode (ElevenLabs agents are voice). Match the validation set to the failure set for the cleanest signal; the final regression sweep runs the full set (see eval phase Step EVAL.4).

If the original input was `call_ids` and any were `reviewed_success`, exclude their re-synthesized scenarios from the validation set.

## Step 4.6 — Decision logic

Exit criterion is **100% pass rate on the full set**. The voice/infra filter scopes Fix — it is not the loop's stopping criterion. Don't declare success while the agent is still failing.

Decision tree is the cross-mode one in [`../../phases/eval.md`](../../phases/eval.md) Step EVAL.4. ElevenLabs specifics:

- **No-change from stale state** doesn't apply — edits land live. A no-change signature means the edit didn't address the root cause OR Step 4.2 re-fetch verification was skipped and the PATCH silently no-op'd — check verification first.
- **Kept failures = 0 but total > 0** (all remaining look voice/infra/tool): re-classify with fresh eyes (a tool error handled badly by the agent is a prompt issue), consider prompt hardening and tool `description` / `api_schema` tightening. ElevenLabs has no spoken `request-start` / `destinations` surfaces — the only mitigation levers are prompt wording and tool `description` / `api_schema`.

## Iteration cap

Default 10 iterations. After the cap, stop and surface: what's fixed, what's still failing, recommended hand-off skill (`cekura-eval-design` / `cekura-metric-improvement` / `cekura-create-agent`).

## Loop guardrails

- Track cumulative diff for prompt AND tools across all iterations, split by surface.
- Watch for oscillation — if iteration N reverses iteration N-1's edit on the same clause or field, stop and flag it.
- Don't widen the validation set mid-loop without telling the user.
- Always back up tool definitions before editing (`GET` → `/tmp/elevenlabs_tools/{id}_pre_iter{N}.json`).
- Check `usage_stats` / `access_info` before deleting — tools are workspace-scoped.
- Don't stop because the failure shape changed — a new bug surfacing after a fix is the loop working.

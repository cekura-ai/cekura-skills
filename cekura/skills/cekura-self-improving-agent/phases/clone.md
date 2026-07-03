# Clone Phase

Runs **once**, after Setup and before Optimize. **VAPI and ElevenLabs only** — every `self_hosted` run (including code-fix, offline, and render-only targets) skips this phase entirely; there is no managed provider to clone into.

Goal: stand up a disposable copy of the provider agent + its tools (same org, same key), duplicate the Cekura agent (`copy_scenarios=true`), repoint the clone at the cloned provider id, and rebind the run to the clone. The loop then iterates entirely on the clone — production is never touched. A failed POST **halts**; never fall through to editing the original.

## Pre-flight

Setup is complete: mode is `vapi` or `elevenlabs`; the live agent config + every referenced tool were fetched in Setup Step 1.3. Reuse those bodies — do not re-fetch unless a body is missing.

Required: `VAPI_KEY` or `ELEVENLABS_API_KEY` (already used during Setup fetch), original Cekura agent id, original provider assistant/squad id.

## Step CLONE.1 — Clone provider-side agent + tools

Tools are shared, id-referenced resources. A clone that keeps original `toolIds` / `tool_ids` would PATCH production tools in Apply. Clone every referenced tool first, repoint the assistant at the copies. Build an `old_id → new_id` tool map as you go.

When copying any provider body, strip server-owned fields before POSTing: `id`, `orgId`, `createdAt`, `updatedAt` (VAPI); `id`, read-only `access_info`, `usage_stats` (ElevenLabs). Suffix every cloned `name` with ` [cekura-selfimprove-clone]`.

### VAPI

1. For each unique id across all members' `model.toolIds` — `POST /tool` (stripped body). Record `old_tool_id → new_tool_id`.
2. **Single assistant:** `POST /assistant` with `model.toolIds` rewritten through the tool map. Capture the new assistant id.
3. **Squad:**
   - Clone each member assistant (`POST /assistant`, `toolIds` repointed, name suffixed). Record `old_member_id → new_member_id`.
   - Repoint handoff/transfer `destinations[].assistantId` on cloned tools **and** squad members through the member map — intra-squad handoffs must stay inside the clone.
   - `POST /squad` with `members` repointed to cloned member ids (inline members: clone the embedded `assistant` object in place). Capture the new squad id.

   ```
   curl -fsS -X POST -H "Authorization: Bearer $VAPI_KEY" -H "Content-Type: application/json" \
     -d '<fetched tool body, id/orgId/timestamps stripped>' https://api.vapi.ai/tool
   curl -fsS -X POST -H "Authorization: Bearer $VAPI_KEY" -H "Content-Type: application/json" \
     -d '<fetched assistant body, stripped, toolIds repointed, name suffixed>' https://api.vapi.ai/assistant
   ```

### ElevenLabs

1. For each id in `prompt.tool_ids` — `POST /v1/convai/tools` with the fetched `tool_config`. Record `old_tool_id → new_tool_id`.
2. `POST /v1/convai/agents/create` with `conversation_config.agent.prompt.tool_ids` rewritten through the tool map, `name` suffixed. Capture the new `agent_id`.

   ```
   curl -fsS -X POST -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" \
     -d '<tool_config>' https://api.elevenlabs.io/v1/convai/tools
   curl -fsS -X POST -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" \
     -d '{"name":"<name> [cekura-selfimprove-clone]","conversation_config":<fetched config, tool_ids repointed>}' \
     https://api.elevenlabs.io/v1/convai/agents/create
   ```

Non-2xx response on any provider POST → **stop**, surface the error. A half-built clone is a hard stop, not a reason to retarget the live agent.

## Step CLONE.2 — Duplicate the Cekura agent

1. Duplicate with scenarios:
   ```
   mcp__cekura__aiagents_duplicate_create(id=<original Cekura agent id>, copy_scenarios=true)
   ```
   Returns a new Cekura agent in the **same project** with a copy of every scenario. Capture the clone's Cekura agent id. Record `original_scenario_id → cloned_scenario_id`. (`copy_scenarios=true` is required — without it there are no scenarios to validate against.)

2. Repoint the clone at the cloned provider agent:
   ```
   mcp__cekura__aiagents_partial_update(
     id=<clone Cekura agent id>,
     provider={ type:"<vapi|elevenlabs>", agent_id:"<cloned provider assistant/squad id>",
                credentials:{ ...same api_key/config as the original... } }
   )
   ```

3. **Sanity re-fetch:** `mcp__cekura__aiagents_retrieve(id=<clone Cekura agent id>)` — confirm `assistant_id` equals the cloned provider id. If it still shows the original, fix the repoint before continuing; the loop will otherwise validate and edit production.

## Step CLONE.3 — Rebind the run to the clone

From here on **"the agent" means the clone** in every later phase:

- **Fix** reads the clone's prompt + tool config (byte-identical to the original on iteration 1).
- **Apply / Sync** PATCH the **cloned** provider assistant and the **cloned** tools — never the originals.
- **Eval validation** runs the **cloned scenarios**. Swap each original scenario id for its `cloned_scenario_id` via the CLONE.2 map before running. For `call_ids` input there are no pre-existing scenarios — synthesize validation scenarios directly on the clone Cekura agent (Eval caches these on iteration 1); the scenario map is empty and expected.
- **Collect's historical read is the exception** — it still consumes the user's original input (`result_id` / `run_ids` / `call_ids` / `scenario_ids`). Those failures happened on the original; they are the diagnostic signal. Only forward-looking validation and edits move to the clone.

Record on the run: `clone_cekura_agent_id`, `clone_provider_id`, tool `old_id → new_id` map, `original_scenario_id → cloned_scenario_id` map. A resumed run reuses these rather than cloning again.

## Step CLONE.4 — Surface the clone summary

```
Cloned for safe iteration — the live agent will NOT be touched.

  Original: <agent_name> (Cekura #<id>, provider <provider_id>)
  Clone:    <agent_name> [cekura-selfimprove-clone] (Cekura #<clone_id>, provider <clone_provider_id>)
  Tools cloned: <N>
  Scenarios copied: <M>

All edits and validation runs target the clone. On success I'll surface the
validated diff for you to apply to the live agent.
```

## On exit (success or stop)

Surface the cumulative validated diff (prompt + tool changes, split by surface) and offer two options:

- **Promote** — re-run Apply against the **original** provider ids + tool ids with the final cumulative diff.
- **Leave** — keep the live agent as-is; the clone remains for review.

Promotion is always a deliberate, user-gated step — never automatic, even in `auto_mode: true`.

Offer to delete the clone (provider assistant/tools + Cekura record) once the user decides. Don't delete without asking.

## Edge cases

| Situation | Handling |
|---|---|
| Provider key missing at clone time | Stop; ask the user to export it (same key as the Setup fetch) |
| Squad with inline-only members | Clone embedded `assistant` objects inside the new `POST /squad` body; no separate `POST /assistant` per member |
| Cross-member handoff destinations | Repoint through the member map so the clone is self-contained; a destination left pointing at a production member lets a handoff escape the clone mid-validation |
| `call_ids` input | `copy_scenarios=true` copies nothing (call logs aren't scenarios); the scenario map is empty; validation scenarios are synthesized on the clone in Eval |
| Partial success (tools created, assistant fails) | Stop and surface; orphaned cloned tools are harmless (suffixed, unreferenced) and can be cleaned up; do not retarget production |
| Resumed run | If `clone_cekura_agent_id` is already recorded, skip CLONE.1–CLONE.2 and reuse the existing clone |

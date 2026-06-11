# Clone Phase — Work on a Disposable Copy, Never the Live Agent

This phase runs **once per invocation**, immediately after Setup and before Optimization · Collect, and **only for the managed-provider fast paths: `vapi` and `elevenlabs`**. Every other mode (`pipecat`, `websocket`, `database`, websocket `offline`) skips this phase entirely — there is no managed provider to clone into, the user owns the live runtime, and the redeploy gate already controls what reaches production.

## Why clone

Apply PATCHes the live provider assistant and its tool definitions directly; Eval triggers real calls against that assistant. Doing that against the user's **production** VAPI / ElevenLabs agent means every iteration's edits — including the ones the loop later reverses — land on the agent that's taking real traffic. The Clone phase removes that risk: it stands up a throwaway copy of the agent **in the same provider org (same API key)** and a copy Cekura agent **in the same project**, then rebinds the run to the copy. The loop iterates, validates, and oscillates entirely on the clone. The live agent is never touched. On success, the validated cumulative diff is surfaced for the user to promote to production deliberately (see "On exit").

The clone lives in the **same provider workspace** as the original because the provided `VAPI_KEY` / `ELEVENLABS_API_KEY` authenticates one workspace — the clone is created with that same key, so it shares the org, billing, and tool registry. No second key, no cross-org copy.

## Pre-flight

- Setup is complete (mode resolved to `vapi` or `elevenlabs`; the live agent's config + every referenced tool were fetched and summarized in Setup Step 1.3).
- The provider key is present (`VAPI_KEY` or `ELEVENLABS_API_KEY`) — it was already required by the Setup fetch.
- You have the original **Cekura agent id** (the integer record id) and the original **provider assistant/squad id** (the `assistant_id` field).

Reuse the bodies already fetched in Setup — do not re-fetch unless a body is missing. Do NOT fetch failure data here (that is still Collect's job).

## Step CLONE.1 — Clone the provider-side agent (branch by provider)

Tool definitions are **shared, id-referenced resources** on both providers — a clone that keeps the original `toolIds` / `tool_ids` would still PATCH the production tools in Apply. So the clone must include fresh copies of every referenced tool, with the assistant repointed at the copies. Build an `old_id → new_id` map for tools as you go.

When copying any provider body, strip server-owned fields before POSTing: `id`, `orgId`, `createdAt`, `updatedAt` (VAPI); `id` / read-only `access_info` / `usage_stats` (ElevenLabs). Suffix the clone's `name` with ` [cekura-selfimprove-clone]` so it's obvious in the provider dashboard and easy to delete later.

### VAPI

1. **Clone every referenced tool.** For each unique id across all members' `model.toolIds`, `POST /tool` with the fetched tool body (stripped). Record `old_tool_id → new_tool_id`.
2. **Single assistant:** `POST /assistant` with the fetched assistant body (stripped), with `model.toolIds` rewritten through the tool map and `name` suffixed. Capture the new assistant id.
3. **Squad:**
   - Clone each member assistant first (`POST /assistant`, `toolIds` repointed via the tool map, name suffixed). Record `old_member_id → new_member_id`.
   - Repoint any handoff/transfer `destinations[].assistantId` on the cloned tools **and** on the squad members through the member map, so intra-squad handoffs stay inside the clone instead of pointing back at production members.
   - `POST /squad` with the `members` array repointed to the cloned member assistant ids (inline members: clone the embedded `assistant` object in place — no separate POST). Capture the new squad id.

   ```
   # clone a tool
   curl -fsS -X POST -H "Authorization: Bearer $VAPI_KEY" -H "Content-Type: application/json" \
     -d '<fetched tool body, id/orgId/timestamps stripped>' https://api.vapi.ai/tool
   # clone an assistant (toolIds already repointed in the body)
   curl -fsS -X POST -H "Authorization: Bearer $VAPI_KEY" -H "Content-Type: application/json" \
     -d '<fetched assistant body, stripped, toolIds repointed, name suffixed>' https://api.vapi.ai/assistant
   ```

   The cloned **provider id** (assistant id for single, squad id for squads) is what the Cekura clone record will point at — same field semantics as the original `assistant_id` (assistant-or-squad), resolved the same way in later phases.

### ElevenLabs

1. **Clone every referenced tool.** For each id in `prompt.tool_ids`, `POST /v1/convai/tools` with the fetched `tool_config`. Record `old_tool_id → new_tool_id`.
2. **Clone the agent.** `POST /v1/convai/agents/create` with the fetched `conversation_config` — `conversation_config.agent.prompt.tool_ids` rewritten through the tool map, `name` suffixed. Inline tools (`prompt.tools`) and built-in tools carry over inside `conversation_config` automatically. Capture the new `agent_id`.

   ```
   curl -fsS -X POST -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" \
     -d '<tool_config>' https://api.elevenlabs.io/v1/convai/tools
   curl -fsS -X POST -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" \
     -d '{"name":"<name> [cekura-selfimprove-clone]","conversation_config":<fetched config, tool_ids repointed>}' \
     https://api.elevenlabs.io/v1/convai/agents/create
   ```

If any provider POST returns non-2xx (quota, validation, scope), **stop** — surface the error and do NOT fall through to editing the original. The whole point of this phase is to never mutate production; a half-built clone is a hard stop, not a reason to retarget the live agent.

## Step CLONE.2 — Stand up the copy Cekura agent in the same project

1. **Duplicate the Cekura record with its scenarios:**

   ```
   mcp__cekura__aiagents_duplicate_create(id=<original Cekura agent id>, copy_scenarios=true)
   ```

   This returns a new Cekura agent in the **same project**, carrying the metric/personality config and a **copy of every scenario**. Capture the clone's Cekura agent id. Record the `original_scenario_id → cloned_scenario_id` map (the duplicated scenarios are bound to the clone agent — this map is what lets Eval validate against the clone instead of production). `copy_scenarios=true` is required; without it the clone has no scenarios to validate against.

2. **Repoint the clone's provider integration at the cloned provider agent:**

   ```
   mcp__cekura__aiagents_partial_update(
     id=<clone Cekura agent id>,
     provider={ type:"<vapi|elevenlabs>", agent_id:"<cloned provider assistant/squad id>",
                credentials:{ ...same api_key/config as the original... } }
   )
   ```

   Same provider org, same key — only the `agent_id` changes to the clone's provider id.

3. **Sanity re-fetch:** `mcp__cekura__aiagents_retrieve(id=<clone Cekura agent id>)` and confirm its `assistant_id` equals the cloned provider id. If it still shows the original provider id, the repoint did not land — fix it before continuing, or the loop will validate and edit production.

## Step CLONE.3 — Rebind the run to the clone

From here on, **"the agent" means the clone** in every later phase:

- **Diagnose** reads the clone's prompt + tool config (byte-identical to the original on iteration 1).
- **Apply / Sync** PATCH the **cloned** provider assistant and the **cloned** tools — never the originals.
- **Eval validation** runs the **cloned scenarios**. When the provider phase-4 validation-set table says "reuse the same scenario IDs" or "extract `scenario_id` from each run," swap each original scenario id for its `cloned_scenario_id` via the CLONE.2 map before running. For `call_ids` input there are no pre-existing scenarios to copy — synthesize the validation scenarios directly on the **clone** Cekura agent (Eval already caches these on iteration 1).
- **Collect's historical read is the exception** — it still consumes the user's original input (`result_id` / `run_ids` / `call_ids` / `scenario_ids`). Those failures already happened on the original agent; they are the diagnostic signal. Only the *forward-looking* validation and edits move to the clone.

Record on the run: `clone_cekura_agent_id`, `clone_provider_id`, the tool `old_id → new_id` map, and the `original_scenario_id → cloned_scenario_id` map. A resumed run reuses these rather than cloning again.

## Step CLONE.4 — Surface the clone summary

Before entering Collect, show the user a compact summary:

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

Because every edit landed on the clone, **production is unchanged** when the loop ends. Surface the cumulative validated diff (prompt + tool changes, split by surface) as the deliverable, and ask the user whether to:

- **Promote** the validated changes to the live agent (re-run the Apply machinery against the **original** provider ids + tool ids with the final cumulative diff), or
- **Leave** the live agent as-is and keep the clone for review.

Promotion is a deliberate, user-gated step — never automatic, even in `auto_mode: true`. Auto mode covers the per-iteration loop on the clone; touching production is always an explicit decision.

Offer to delete the clone (provider assistant/tools + Cekura record) once the user has promoted or decided against it, so throwaway clones don't accumulate in the workspace. Don't delete without asking — the user may want to inspect it.

## Edge cases

- **Provider key missing at clone time** — should have been caught in Setup; if not, stop and ask the user to export it. The clone uses the same key as the fetch.
- **Squad with inline-only members** — clone the embedded `assistant` objects inside the new `POST /squad` body; no separate `POST /assistant` per member.
- **Self-referencing or cross-member handoff destinations** — repoint through the member map so the clone is self-contained. A destination left pointing at a production member means a handoff escapes the clone mid-validation.
- **`call_ids` input** — `copy_scenarios=true` copies nothing (call logs aren't scenarios); the validation scenarios are synthesized on the clone agent in Eval. The scenario map is empty and that's expected.
- **Clone POST partially succeeds** (tools created, assistant fails) — stop and surface. The orphaned cloned tools are harmless (suffixed, unreferenced) and can be cleaned up; do not retarget production.
- **Resumed run** — if `clone_cekura_agent_id` is already recorded on the run, skip CLONE.1–CLONE.2 and reuse the existing clone.

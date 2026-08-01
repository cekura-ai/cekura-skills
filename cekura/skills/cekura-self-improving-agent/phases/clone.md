# Clone Phase

Runs **once**, after Setup and before Optimize. Managed providers only; self-hosted and render-only targets skip it.

Goal: stand up a disposable copy of the provider agent(s) + their tools (same org, same key) — following any transfer/handoff links so the whole linked graph is cloned — duplicate the Cekura agent (`copy_scenarios=true`), repoint the clone at the cloned entry agent, and rebind the run to the clone. The loop then iterates entirely on the clone — production is never touched. A failed POST **halts**; never fall through to editing the original.

## Pre-flight

Setup is complete: the live agent and provider configuration were fetched in Setup Step 1.3. Reuse those bodies — do not re-fetch unless a body is missing.

Required: the provider key already used during Setup, the original Cekura agent id, and the original provider agent id.

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

   **Write each body to a file and post it with `-d @file`.** Never inline a fetched body into `-d '...'`: these payloads carry real prompts and tool descriptions, and a single apostrophe (`"customer's account"` — guaranteed in production prompts) closes the shell quote, breaking the call at best and executing the remainder at worst. Use `Write` for the payload, not `echo`/`cat`.

   ```
   # Write the stripped tool body to /tmp/vapi-tool.json first, then:
   curl -fsS -X POST -H "Authorization: Bearer $VAPI_KEY" -H "Content-Type: application/json" \
     -d @/tmp/vapi-tool.json https://api.vapi.ai/tool
   # Write the stripped assistant body (toolIds repointed, name suffixed) to /tmp/vapi-assistant.json, then:
   curl -fsS -X POST -H "Authorization: Bearer $VAPI_KEY" -H "Content-Type: application/json" \
     -d @/tmp/vapi-assistant.json https://api.vapi.ai/assistant
   ```

### ElevenLabs

First resolve the agent graph: from the target agent, follow `built_in_tools.transfer_to_agent.transfers[].agent_id` transitively (`GET /v1/convai/agents/{id}` for each) to collect every reachable agent. Dedupe; guard cycles (A→B→A). A lone agent is just a graph of one.

Clone **every** agent in the graph:

1. For each `prompt.tool_ids` across all agents — `POST /v1/convai/tools` with the fetched `tool_config`. Record `old_tool_id → new_tool_id`.
2. For each agent — `POST /v1/convai/agents/create` with `tool_ids` rewritten through the tool map, `name` suffixed. Record `old_agent_id → new_agent_id`.
3. Repoint each clone's `built_in_tools.transfer_to_agent.transfers[].agent_id` through the agent map (`PATCH /v1/convai/agents/{clone_id}`) so transfers stay inside the clone graph — the same self-containment rule as VAPI cross-member handoffs.

   Same rule as VAPI above — **write each body to a file, post with `-d @file`**, never inline a fetched config into `-d '...'`.

   ```
   # Write <tool_config> to /tmp/el-tool.json first, then:
   curl -fsS -X POST -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" \
     -d @/tmp/el-tool.json https://api.elevenlabs.io/v1/convai/tools
   # Write {"name":"<name> [cekura-selfimprove-clone]","conversation_config":<fetched config, tool_ids repointed>}
   # to /tmp/el-agent.json, then:
   curl -fsS -X POST -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" \
     -d @/tmp/el-agent.json https://api.elevenlabs.io/v1/convai/agents/create
   ```

The cloned **entry** agent (the one the Cekura record was registered against) is what CLONE.2 repoints to.

### Retell

Clone the configuration referenced by `response_engine` first: the Retell LLM
or conversation flow, including its tools and built-in behavior. Create a new
agent pointing to that clone and record the old/new ids. Keep the same agent
type and active version. If a required operation is unavailable, stop rather
than retargeting the original.

### Bland

Use the provider-supported persona/tool copy operation, preserving the active
configuration and modality-specific identifiers. If copying is unavailable,
stop rather than editing the original.

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
     provider={ type:"<vapi|retell|elevenlabs|bland>", agent_id:"<cloned provider agent id>",
                credentials:{ ...same api_key/config as the original... } }
   )
   ```

3. **Sanity re-fetch:** `mcp__cekura__aiagents_retrieve(id=<clone Cekura agent id>)` — confirm `assistant_id` equals the cloned provider id. If it still shows the original, fix the repoint before continuing; the loop will otherwise validate and edit production.

## Step CLONE.3 — Rebind the run to the clone

From here on **"the agent" means the clone** in every later phase:

- **Fix** reads the cloned agent(s)' prompt + tool config (byte-identical to the originals on iteration 1) and attributes each failure to the agent that caused it.
- **Apply / Sync** PATCH the **cloned** agent(s) + tools that own each edit — never the originals.
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
validated diff and evidence.
```

## On exit (success or stop)

Surface the cumulative validated diff and result URLs. Leave the original
provider resources and Cekura agent unchanged; never offer or apply promotion.
Offer to delete the clone, but do not delete it without approval.

## Edge cases

| Situation | Handling |
|---|---|
| Provider key missing at clone time | Stop; ask the user to export it (same key as the Setup fetch) |
| Squad with inline-only members | Clone embedded `assistant` objects inside the new `POST /squad` body; no separate `POST /assistant` per member |
| Cross-member handoff destinations | Repoint through the member map so the clone is self-contained; a destination left pointing at a production member lets a handoff escape the clone mid-validation |
| ElevenLabs `transfer_to_agent` graph | Clone every reachable agent; repoint each clone's `transfers[].agent_id` through the agent map so transfers stay inside the clone. A target left pointing at production lets a transfer escape mid-validation (and would edit a live agent on Apply) |
| Cyclic / deep transfer graph (A→B→A, A→B→C) | Traverse transitively with a visited-set; clone each agent once, then repoint all links through the agent map |
| `call_ids` input | `copy_scenarios=true` copies nothing (call logs aren't scenarios); the scenario map is empty; validation scenarios are synthesized on the clone in Eval |
| Partial success (tools created, assistant fails) | Stop and surface; orphaned cloned tools are harmless (suffixed, unreferenced) and can be cleaned up; do not retarget production |
| Resumed run | If `clone_cekura_agent_id` is already recorded, skip CLONE.1–CLONE.2 and reuse the existing clone |

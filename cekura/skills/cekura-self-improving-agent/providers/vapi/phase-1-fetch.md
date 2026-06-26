# Phase 1 — VAPI Fetch Reference

Provider-gate error shapes, VAPI assistant / squad / tool fetch curl bodies, and Phase 1 edge cases.

## Provider-gate error message format

When `assistant_provider` is one this skill can't handle (after the Setup Step 1.2 routing has already sent `vapi` / `elevenlabs` / `self_hosted` tags down their branches), respond with exactly this shape (substitute the actual values):

```
Self-improvement isn't supported for this agent's provider.

Agent: <agent_name> (id: <agent_id>)
Provider: <assistant_provider or "not set">

Supported providers: vapi, elevenlabs, self_hosted (any agent you run yourself, defined by your run-setup; render-only prompt-only fallback also available)
```

If the provider is `retell` specifically, append one extra line so the user knows it's a temporary gate, not a permanent decision:

```
Note: Retell support is temporarily disabled in this skill and will be re-enabled in a future revision.
```

Do not attempt any further phases. Do not fetch results, propose prompt changes, or offer workarounds — provider support for other integrations will be added later, and silently skipping the gate will produce changes that can't be applied to the live agent.

## Edge cases on the agent retrieve

- **Agent not found / 404**: surface the error from the agent-retrieve directly. Don't retry with a different ID without user confirmation.
- **`assistant_provider` missing or empty**: treat as unsupported. The agent likely hasn't completed provider configuration — point the user to `cekura-create-agent` (Phase 3: Configure Provider Integration).
- **Case sensitivity**: compare lowercased — the provider field is stored as `vapi` but be defensive against `VAPI` in user input.

## Required environment variable

- `VAPI_KEY` — VAPI private API key. Sent as `Authorization: Bearer $VAPI_KEY`.

If `VAPI_KEY` is missing, stop and ask the user to export it before continuing. Never echo the key to chat or write it to a file.

## Resolving the VAPI id

The `assistant_id` field on the Cekura agent record holds either a VAPI assistant id or a VAPI squad id — Cekura does not distinguish them by field name. Try the assistant endpoint first, fall back to the squad endpoint on 404:

```
ID="<assistant_id from agent record>"
curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/assistant/$ID \
  || curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/squad/$ID
```

Record which endpoint succeeded — Phase 4's PATCH targets the matching endpoint. If both 404, the id is stale; surface the error and stop. If `assistant_id` is missing or empty, the agent isn't fully configured — stop and point at `cekura-create-agent`.

## Fetching the config

VAPI's API isn't exposed through the Cekura MCP server, so use `Bash` with curl. Substituting the resolved id:

- Single assistant: `curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/assistant/$ID`
- Squad: `curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/squad/$ID`

For squads, the response includes a `members` array. Each member has either `assistantId` (referenced) or an inline `assistant` object. For the referenced case, fetch the full assistant config with the assistant endpoint above; for inline members, read the embedded object directly — no extra fetch needed.

## Extracting from each assistant config

From each assistant config, capture:

- `id`, `name`
- The system prompt: `model.messages[*].content` where `role == "system"`
- `model.tools` — inline function declarations
- `model.toolIds` — array of UUIDs of referenced tool definitions (these live at `https://api.vapi.ai/tool/{id}` and must be fetched separately; **do this in Phase 1, not later** — the definitions drive Phase 3 diagnosis as much as the prompt does)
- `voice`, `transcriber`, `firstMessage` — useful for sanity-checking the voice-failure filter in Phase 2

## Fetching every referenced tool

For each unique id across all members' `model.toolIds`, fetch:

```
curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/tool/$TOOL_ID
```

Capture for each tool:

- `id`, `type` (`function`, `handoff`, `transferCall`, `query`, `mcp`, etc.)
- `function.name`, `function.description`, `function.parameters` (JSONSchema)
- `messages` array — especially the `request-start.content` (what the assistant says aloud when the tool fires), `request-complete.content`, `request-failed.content`. **These messages are spoken on the call** and are first-class targets for Phase 3 edits.
- `destinations` — for `handoff` / `transferCall` tools, the list of `{type, assistantId, description}` entries pointing to other assistants. Wrong / self-referencing destinations are a common bug class.
- Which member assistants reference this tool (cross-reference back to the `toolIds` arrays you already collected).

## Compact summary template

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

## Squad scope

For squads, all members are in scope by default; Phase 3 attributes each failure to the member that was speaking in the relevant transcript turn (auto-localize) and proposes member-scoped edits. Phase 4 PATCHes whichever members the proposal touches. There is no upfront scope-selection question — the user-side gate is at every Phase 3 → Phase 4 transition (after seeing the per-member proposed edits for that iteration), not earlier.

## Edge cases on the VAPI fetch

- **401 / 403 from VAPI**: `VAPI_KEY` is invalid or lacks scope. Surface the error verbatim and stop — don't retry.
- **404 on both assistant and squad endpoints**: the `assistant_id` on the Cekura agent record is stale or points at a deleted VAPI resource. Stop; don't guess adjacent ids. Suggest the user reconcile via `cekura-create-agent`.
- **Squad with zero members**: not actionable for self-improvement — surface and ask the user to verify the squad is configured correctly before continuing.
- **Member with inline `assistant` only**: read the embedded object; skip the second fetch.
- **Response shape changes / missing fields**: fall back to surfacing the relevant raw JSON section so the user can see what VAPI returned, rather than failing silently.

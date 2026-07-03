# Phase 1 — VAPI Fetch Reference

Provider-gate error shapes, VAPI assistant / squad / tool fetch curl bodies, and Phase 1 edge cases.

## Provider-gate error message format

When `assistant_provider` is unsupported, respond with exactly:

```
Self-improvement isn't supported for this agent's provider.

Agent: <agent_name> (id: <agent_id>)
Provider: <assistant_provider or "not set">

Supported providers: vapi, elevenlabs, self_hosted (any agent you run yourself, defined by your run-setup; render-only prompt-only fallback also available)
```

If the provider is `retell`, append:

```
Note: Retell support is temporarily disabled in this skill and will be re-enabled in a future revision.
```

Do not attempt any further phases. Do not fetch results, propose prompt changes, or offer workarounds.

## Edge cases on the agent retrieve

- **Agent not found / 404**: surface the error directly. Don't retry with a different ID without user confirmation.
- **`assistant_provider` missing or empty**: treat as unsupported. Point the user to `cekura-create-agent` (Phase 3: Configure Provider Integration).
- **Case sensitivity**: compare lowercased — be defensive against `VAPI` in user input.

## Required environment variable

- `VAPI_KEY` — VAPI private API key. Sent as `Authorization: Bearer $VAPI_KEY`.

If missing, stop and ask the user to export it. Never echo the key to chat or write it to a file.

## Resolving the VAPI id

`assistant_id` on the Cekura agent record holds either a VAPI assistant id or squad id. Try assistant first, fall back to squad on 404:

```
ID="<assistant_id from agent record>"
curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/assistant/$ID \
  || curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/squad/$ID
```

Record which endpoint succeeded — Phase 4's PATCH targets the matching endpoint. If both 404, the id is stale; surface and stop. If `assistant_id` is missing, stop and point at `cekura-create-agent`.

## Fetching the config

VAPI's API is not exposed through the Cekura MCP server — use `Bash` with curl:

- Single assistant: `curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/assistant/$ID`
- Squad: `curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/squad/$ID`

For squads, the response includes a `members` array. Each member has either `assistantId` (referenced — fetch the full assistant config separately) or an inline `assistant` object (read directly, no extra fetch).

## Extracting from each assistant config

From each assistant config, capture:

- `id`, `name`
- System prompt: `model.messages[*].content` where `role == "system"`
- `model.tools` — inline function declarations
- `model.toolIds` — UUIDs of referenced tool definitions (fetch these in Phase 1; they drive Phase 3 diagnosis as much as the prompt)
- `voice`, `transcriber`, `firstMessage` — for sanity-checking the voice-failure filter in Phase 2

## Fetching every referenced tool

For each unique id across all members' `model.toolIds`:

```
curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/tool/$TOOL_ID
```

Capture for each tool:

- `id`, `type` (`function`, `handoff`, `transferCall`, `query`, `mcp`, etc.)
- `function.name`, `function.description`, `function.parameters` (JSONSchema)
- `messages` array — `request-start.content`, `request-complete.content`, `request-failed.content` (spoken on the call; first-class edit targets)
- `destinations` — for `handoff` / `transferCall` tools, the list of `{type, assistantId, description}` entries
- Which member assistants reference this tool (cross-reference the `toolIds` arrays)

## Compact summary template

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

All members are in scope by default. Phase 3 attributes each failure to the member speaking in the relevant transcript turn and proposes member-scoped edits. Phase 4 PATCHes whichever members the proposal touches. There is no upfront scope-selection question.

## Edge cases on the VAPI fetch

- **401 / 403**: `VAPI_KEY` is invalid or lacks scope. Surface verbatim and stop.
- **404 on both assistant and squad endpoints**: `assistant_id` is stale or points at a deleted resource. Stop; don't guess adjacent ids. Suggest reconciling via `cekura-create-agent`.
- **Squad with zero members**: not actionable — surface and ask the user to verify squad config.
- **Member with inline `assistant` only**: read the embedded object; skip the second fetch.
- **Response shape changes / missing fields**: surface the relevant raw JSON section rather than failing silently.

# Phase 1 — ElevenLabs Fetch Reference

ElevenLabs agent / tool fetch curl bodies and Phase 1 edge cases. The provider-gate routing decision lives in `phase-1-fetch.md` for VAPI; for ElevenLabs the gate is simply `assistant_provider == elevenlabs` → proceed (see `overview.md`).

## Required environment variable

- `ELEVENLABS_API_KEY` — ElevenLabs API key. Sent as the `xi-api-key` header.

If `ELEVENLABS_API_KEY` is missing, stop and ask the user to export it before continuing. Never echo the key to chat or write it to a file. (The Cekura agent record exposes `elevenlabs_api_key_configured: true/false` — a quick sanity check that ElevenLabs is wired up on the Cekura side, but the live API calls still need the key in the environment.)

## Resolving the ElevenLabs agent id

The `assistant_id` field on the Cekura agent record holds the ElevenLabs `agent_id` (shape `agent_<...>`). Unlike VAPI there is no assistant-vs-squad ambiguity — there's exactly one agent endpoint:

```
AGENT_ID="<assistant_id from agent record>"
curl -fsS -H "xi-api-key: $ELEVENLABS_API_KEY" \
  https://api.elevenlabs.io/v1/convai/agents/$AGENT_ID
```

If `assistant_id` is missing or empty, the agent isn't fully configured — stop and point at `cekura-create-agent`. On 404, the id is stale or points at a deleted ElevenLabs agent; surface the error and stop, don't guess adjacent ids.

## Extracting from the agent config

The response is a `GetAgentResponseModel`. Capture:

- `agent_id`, `name`
- **System prompt**: `conversation_config.agent.prompt.prompt` (a single string)
- **LLM config**: `conversation_config.agent.prompt.llm`, `.temperature`, `.max_tokens` — informational; not edited unless the user asks (a model swap is a wider-search option, see Diagnose Step DIAGNOSE.4)
- **Referenced tool IDs**: `conversation_config.agent.prompt.tool_ids` — array of standalone tool IDs. **Fetch each separately in Phase 1, not later** — the definitions drive Diagnose as much as the prompt does.
- **Inline tools (legacy)**: `conversation_config.agent.prompt.tools` — if present, full tool objects embedded on the agent. Read them in place; no separate fetch.
- **Built-in / system tools**: `conversation_config.agent.prompt.built_in_tools` — `end_call`, `transfer_to_agent`, `transfer_to_number`, `language_detection`, `skip_turn`. Record which are enabled (sanity-check for end-of-call attribution and transfer behavior), but these are config flags, not editable tool bodies.
- `conversation_config.agent.first_message`, `conversation_config.agent.language` — useful for sanity-checking the voice-failure filter in Collect.
- `conversation_config.tts.voice_id` — informational, for the voice filter.

## Fetching every referenced tool

For each unique id in `prompt.tool_ids`, fetch the standalone tool:

```
curl -fsS -H "xi-api-key: $ELEVENLABS_API_KEY" \
  https://api.elevenlabs.io/v1/convai/tools/$TOOL_ID
```

The response is a `ToolResponseModel` wrapping `tool_config` (plus `access_info` and `usage_stats`). Capture for each tool:

- `id`
- `tool_config.name`, `tool_config.description`
- `tool_config.type` (`webhook`, `client`, `system`, `code`, `mcp`)
- For **webhook** tools: `tool_config.api_schema` — `url`, `method`, request/response header schema, query/path/body parameter schemas. This is the analog of VAPI's `function.parameters`.
- For **client** tools: `tool_config.parameters` — the schema for parameters passed to the client.

If `prompt.tool_ids` is empty AND `prompt.tools` (inline) is empty, the agent is conversational-only — record `tools: []` and skip tool-config considerations in Diagnose.

## Compact summary template

Show the user a compact summary before continuing:

```
ElevenLabs agent: <name> (<agent_id>)
  System prompt: <length> chars
  LLM: <llm> (temp <temperature>)
  Referenced tools (prompt.tool_ids → /v1/convai/tools/{id}):
    - <tool_name> (<tool_id>) — type=<type>
        <webhook: METHOD url> | <client: N params>
        description: "<first 80 chars>"
  Inline tools (prompt.tools): <N> (<comma-separated names> or "none")
  Built-in tools enabled: <comma-separated, e.g. end_call, transfer_to_agent, or "none">
  Voice: <tts.voice_id>
  Dynamic-variable placeholders detected in prompt: <list of {{...}} or "none">
```

## Edge cases on the ElevenLabs fetch

- **401 / 403 from ElevenLabs**: `ELEVENLABS_API_KEY` is invalid or lacks scope. Surface the error verbatim and stop — don't retry.
- **404 on the agent endpoint**: the `assistant_id` on the Cekura agent record is stale or points at a deleted ElevenLabs agent. Stop; don't guess adjacent ids. Suggest the user reconcile via `cekura-create-agent`.
- **404 on a referenced tool id**: a `tool_ids` entry points at a deleted tool. Surface it — this is itself a likely bug (the agent references a tool that no longer exists). Don't drop it silently.
- **Inline tools AND referenced tools both present**: read both. Edits go to the right surface per the table in `overview.md` (inline → agent PATCH; referenced → standalone tool PATCH).
- **Empty / one-line / clearly-non-production system prompt**: stop and ask whether this is the production prompt. Don't iterate against a stub — every edit will look like a "gap".
- **Response shape changes / missing fields**: ElevenLabs evolves its config schema. If `conversation_config.agent.prompt.prompt` isn't where expected, fall back to surfacing the relevant raw JSON section so the user can see what ElevenLabs returned, rather than failing silently or editing the wrong field.

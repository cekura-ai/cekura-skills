# Phase 1 — ElevenLabs Fetch Reference

## Required environment variable

- `ELEVENLABS_API_KEY` — sent as the `xi-api-key` header on every call.

If missing, stop and ask the user to export it. Never echo the key or write it to a file. (The Cekura agent record exposes `elevenlabs_api_key_configured: true/false` as a sanity check, but live API calls still need the key in the environment.)

## Resolving the ElevenLabs agent id

`assistant_id` on the Cekura agent record holds the ElevenLabs `agent_id` (shape `agent_<...>`). No assistant-vs-squad ambiguity — one endpoint:

```
AGENT_ID="<assistant_id from agent record>"
curl -fsS -H "xi-api-key: $ELEVENLABS_API_KEY" \
  https://api.elevenlabs.io/v1/convai/agents/$AGENT_ID
```

If `assistant_id` is missing, point at `cekura-create-agent`. On 404, the id is stale or points at a deleted agent — stop, don't guess adjacent ids.

## Extracting from the agent config

The response is a `GetAgentResponseModel`. Capture:

- `agent_id`, `name`
- **System prompt**: `conversation_config.agent.prompt.prompt` (single string)
- **LLM config**: `conversation_config.agent.prompt.llm`, `.temperature`, `.max_tokens` — informational; not edited unless the user asks
- **Referenced tool IDs**: `conversation_config.agent.prompt.tool_ids` — **fetch each separately in Phase 1**
- **Inline tools (legacy)**: `conversation_config.agent.prompt.tools` — full tool objects; read in place
- **Built-in / system tools**: `conversation_config.agent.prompt.built_in_tools` — record which are enabled for end-of-call attribution and transfer behavior
- `conversation_config.agent.first_message`, `.language` — sanity-check for voice-failure filter in Collect
- `conversation_config.tts.voice_id` — informational

## Fetching every referenced tool

For each id in `prompt.tool_ids`:

```
curl -fsS -H "xi-api-key: $ELEVENLABS_API_KEY" \
  https://api.elevenlabs.io/v1/convai/tools/$TOOL_ID
```

Response is a `ToolResponseModel` wrapping `tool_config`. Capture per tool:

- `id`
- `tool_config.name`, `tool_config.description`
- `tool_config.type` (`webhook`, `client`, `system`, `code`, `mcp`)
- **webhook**: `tool_config.api_schema` — url, method, request/response header schema, query/path/body parameter schemas
- **client**: `tool_config.parameters` — schema for parameters passed to the client

If both `prompt.tool_ids` and `prompt.tools` are empty, the agent is conversational-only — record `tools: []` and skip tool-config in Fix.

## Compact summary template

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

## Edge cases

- **401 / 403**: key is invalid or lacks scope — surface the error verbatim and stop; don't retry.
- **404 on agent**: `assistant_id` is stale or points at a deleted agent — stop, suggest `cekura-create-agent`.
- **404 on a referenced tool id**: a `tool_ids` entry points at a deleted tool — surface it as a likely bug; don't drop silently.
- **Inline tools AND referenced tools both present**: read both; edits go to the right surface per the table in `overview.md`.
- **Empty / stub system prompt**: stop and ask whether this is the production prompt — don't iterate against a stub.
- **Response shape changes / missing fields**: if `conversation_config.agent.prompt.prompt` isn't where expected, surface the relevant raw JSON rather than failing silently or editing the wrong field.

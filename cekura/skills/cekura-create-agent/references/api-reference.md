# Agent API Reference

## Authentication
All requests: `X-CEKURA-API-KEY: <key>` header. Base URL: `https://api.cekura.ai`

Docs: https://docs.cekura.ai/api-reference/test_framework/create-agent

## Agent CRUD

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/aiagents/` | Create agent |
| GET | `/test_framework/v1/aiagents/` | List agents (`?project_id=X`) |
| GET | `/test_framework/v1/aiagents/{id}/` | Get agent details |
| PATCH | `/test_framework/v1/aiagents/{id}/` | Partial update (preferred) |
| PUT | `/test_framework/v1/aiagents/{id}/` | Full update |
| DELETE | `/test_framework/v1/aiagents/{id}/` | Delete agent |
| POST | `/test_framework/v1/aiagents/{id}/duplicate/` | Duplicate agent |

## Create Agent Schema

**Required:** `agent_name`, `description`, `inbound`, `project`, `assistant_provider`

```json
POST /test_framework/v1/aiagents/
{
  "agent_name": "string (max 255)",
  "description": "string (full system prompt)",
  "inbound": "boolean",
  "project": "integer (project ID)",
  "assistant_provider": "vapi|retell|elevenlabs|livekit|pipecat|bland|agentforce|trillet|self_hosted|cisco|sms|whatsapp|\"\"",
  "contact_number": "string (E.164, e.g. '+14155551234')",
  "language": "string (BCP-47, default 'en')",
  "transcript_provider": "string (usually matches assistant_provider)"
}
```

## Provider Credentials (write-only, flat fields)

| Provider | API key field | Data field (JSON) | Agent ID field |
|----------|--------------|-------------------|----------------|
| `vapi` | `vapi_api_key` | `vapi_data`: `{public_key, trigger_url}` | `assistant_id` |
| `retell` | `retell_api_key` | `retell_data`: `{trigger_url}` | `chat_assistant_id` ⚠️ |
| `elevenlabs` | `elevenlabs_api_key` | `elevenlabs_data` | `assistant_id` |
| `livekit` | `livekit_api_key` | `livekit_data`: `{api_secret (req), url (req)}` | — |
| `pipecat` | `pipecat_api_key` | `pipecat_data`: `{webhook_url}` | — (use `contact_number` = agent name) |
| `bland` | `bland_api_key` | `bland_data`: `{encrypted_key}` | `chat_assistant_id` ⚠️ |
| `agentforce` | `agentforce_client_secret` | `agentforce_data`: `{client_id, domain, agent_id}` | — |
| `trillet` | `trillet_api_key` | `trillet_data`: `{workspace_id}` | — |
| `self_hosted` | — | — | — |

⚠️ Retell and Bland use `chat_assistant_id` (NOT `assistant_id`) for their agent ID — this applies to both voice and text-mode.

## Additional Fields

| Field | Type | Description |
|-------|------|-------------|
| `websocket_url` | string | WebSocket endpoint for self-hosted text-mode |
| `websocket_headers` | object | Headers sent to WebSocket server |
| `sip_endpoint` | string | SIP URI e.g. `sip:agent@domain.com` |
| `sip_auth` | object | `{"username": "...", "password": "..."}` |
| `agent_gives_first_message` | boolean\|null | Agent speaks first; null = auto-detect |
| `auto_sync_prompt_enabled` | boolean | Sync description from provider every 30s (VAPI/Retell/ElevenLabs) |
| `auto_fetch_calls_enabled` | boolean | Auto-import calls every 30s (VAPI/Retell/ElevenLabs) |
| `outbound_auto_call` | boolean | Auto-place outbound calls (VAPI/Retell only) |
| `outbound_numbers` | array | Phone numbers for outbound webhook validation |
| `llm_model` | enum | Caller simulation LLM: `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`, `claude-sonnet-4-5` |
| `llm_temperature` | float | 0.0–2.0, default 0.0 |
| `llm_max_tokens` | integer | Default 4096 |
| `llm_system_prompt` | string | Custom caller persona |
| `pronunciation_words` | array | `[["word", "phoneme"]]` |
| `spelling_word_types` | array | `["name", "postcode", "email"]` |
| `topic_nodes` | object | `{"billing": "handle_billing"}` |
| `dropoff_nodes` | object | `{"timeout": 30}` |
| `auto_update_topic_nodes` | boolean | Auto-infer topics from description |
| `auto_update_dropoff_nodes` | boolean | Auto-infer dropoffs from description |
| `hallucination_metric_kb_files` | array | KB file IDs for hallucination detection |
| `predefined_metrics` | write-only | Assign predefined metrics on create |

## Mock Tool Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/aiagents/{agent_id}/tools/` | Create mock tool |
| GET | `/test_framework/v1/aiagents/{agent_id}/tools/` | List mock tools |
| GET | `/test_framework/v1/mock-tools/{tool_id}/` | Get mock tool |
| PATCH | `/test_framework/v1/mock-tools/{tool_id}/` | Update mock tool |
| DELETE | `/test_framework/v1/mock-tools/{tool_id}/` | Delete mock tool |

### Create Mock Tool Schema

```json
POST /test_framework/v1/aiagents/{agent_id}/tools/
{
  "name": "string (required, max 64 chars, alphanumeric + _ + -)",
  "description": "string",
  "information": [
    {"input": {"param": "value"}, "output": {"result": "value"}}
  ],
  "freetext_params": ["notes", "reason"]
}
```

`name` must exactly match the tool name in the agent description. `information` is input→output mappings. **Critical: Append-not-replace** — GET existing data first, merge, then PATCH the full array.

## Knowledge Base

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/aiagents/{id}/upload_knowledge_base/` | Upload KB files |

```
POST /test_framework/v1/aiagents/{id}/upload_knowledge_base/
Content-Type: multipart/form-data
files: <file1>, <file2>
```

After upload, link to hallucination detection:
```json
PATCH /test_framework/v1/aiagents/{id}/
{ "hallucination_metric_kb_files": [<file_id_1>, <file_id_2>] }
```

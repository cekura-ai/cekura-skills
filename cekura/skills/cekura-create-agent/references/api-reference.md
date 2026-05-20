# Agent API Reference

## Authentication
All requests: `X-CEKURA-API-KEY: <key>` header. Base URL: `https://api.cekura.ai`

Docs: https://vocera-v2-agent-api-restructure.mintlify.app/api-reference/test_framework/create-agent

## Agent CRUD

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v2/aiagents/` | Create agent |
| GET | `/test_framework/v2/aiagents/` | List agents (`?project_id=X`) |
| GET | `/test_framework/v2/aiagents/{id}/` | Get agent details |
| PATCH | `/test_framework/v2/aiagents/{id}/` | Partial update (preferred) |
| PUT | `/test_framework/v2/aiagents/{id}/` | Full update |
| DELETE | `/test_framework/v2/aiagents/{id}/` | Delete agent |
| POST | `/test_framework/v2/aiagents/{id}/duplicate/` | Duplicate agent |

## Create Agent Schema (v2)

**Required:** `name`, `description`, `project`

```json
POST /test_framework/v2/aiagents/
{
  "name": "string (max 255)",
  "description": "string (full system prompt)",
  "project": "integer (project ID)",
  "language": "string (BCP-47, default 'en')",
  "agent_speaks_first": "boolean|null",
  "provider": { ... see below ... },

  "telephony": {
    "phone_number": "string (E.164, e.g. '+14155551234')",
    "inbound": "boolean (default false)",
    "sip_uri": "string (e.g. 'sip:agent@domain.com')",
    "sip_auth": {"username": "...", "password": "..."},
    "outbound_numbers": ["string"]
  }
}
```

## Provider Block

```json
"provider": {
  "type": "vapi|retell|elevenlabs|bland|livekit|pipecat|agentforce|trillet|self_hosted|...",
  "agent_id": "string|null (voice agent ID on provider platform)",
  "credentials": {
    "api_key": "string (write-only)",
    "config": { ... provider-specific ... }
  },
  "chat_agent_details": {
    "type": "string",
    "config": { ... }
  },
  "auto_sync_prompt": "boolean|null",
  "auto_import_calls": "boolean|null",
  "auto_dial_outbound": "boolean|null"
}
```

## credentials.config Keys by Provider

| Provider | Required config keys | Optional config keys |
|----------|---------------------|---------------------|
| `vapi` | — | `public_key`, `trigger_url` |
| `retell` | — | `trigger_url`, `livekit_server_url` |
| `elevenlabs` | — | `trigger_url`, `elevenlabs_base_url_override` |
| `bland` | — | `encrypted_key` (Twilio bundle) |
| `livekit` | `api_secret`, `url` | `agent_name`, `config`, `tracing_enabled`, `trigger_url` |
| `pipecat` | `pipecat_agent_name` | `webhook_url`, `config`, `room_properties`, `tracing_enabled` |
| `trillet` | `workspace_id` | — |
| `koreai` | `client_id`, `bot_id` | `host` (default: https://bots.kore.ai) |
| `genesys` | `client_id`, `region` | — |
| `synthflow` | — | `synthflow_base_url_override` |
| `chirp` | `chirp_websocket_url` | `chirp_basic_auth_username`, `chirp_basic_auth_password` |
| `cisco` | — | — (no credentials needed) |
| `self_hosted` | — | `send_post_conversation_metadata` |

## chat_agent_details by Provider

| Provider | Structure |
|----------|-----------|
| Retell | `{"type": "retell", "config": {"agent_id": "..."}}` |
| VAPI | `{"type": "vapi", "config": {"agent_id": "..."}}` |
| ElevenLabs | `{"type": "elevenlabs", "config": {"agent_id": "..."}}` |
| Self-hosted | `{"type": "self_hosted", "config": {"url": "wss://...", "headers": {...}}}` |

## Additional Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
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
  "name": "string (required, max 64 chars)",
  "description": "string",
  "information": [
    {"input": {"param": "value"}, "output": {"result": "value"}}
  ],
  "freetext_params": ["notes", "reason"]
}
```

**Critical: Append-not-replace** — GET existing `information` first, merge, then PATCH the full array.

## Knowledge Base

```
POST /test_framework/v2/aiagents/{id}/upload_knowledge_base/
Content-Type: multipart/form-data
files: <file1>, <file2>
```

After upload, link to hallucination detection:
```json
PATCH /test_framework/v2/aiagents/{id}/
{ "hallucination_metric_kb_files": [<file_id_1>, <file_id_2>] }
```

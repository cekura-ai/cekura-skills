# Agent API Reference

## Authentication
All requests: `X-CEKURA-API-KEY: <key>` header. Base URL: `https://api.cekura.ai`

Docs: https://vocera-v2-agent-api-restructure.mintlify.app/api-reference/test_framework/create-agent

## Agent CRUD

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v2/aiagents/` | Create agent |
| GET | `/test_framework/v2/aiagents/` | List agents (`?project_id=X`) |
| GET | `/test_framework/v2/aiagents/{id}/` | Get agent |
| PATCH | `/test_framework/v2/aiagents/{id}/` | Partial update (preferred) |
| PUT | `/test_framework/v2/aiagents/{id}/` | Full update |
| DELETE | `/test_framework/v2/aiagents/{id}/` | Delete agent |
| POST | `/test_framework/v2/aiagents/{id}/duplicate/` | Duplicate agent |

## Create/Update Agent Schema (AIAgentV2)

**Required for POST:** `name`, `description`, `project`  
All other fields are optional. PATCH requires no mandatory fields.

### Top-level fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | string (max 255) | Agent name |
| `description` | string | Full system prompt |
| `project` | integer | Project ID |
| `language` | string | BCP-47, default `en` |
| `agent_speaks_first` | boolean\|null | `null` = auto-detect |
| `telephony` | AgentTelephony (write-only) | Phone/SIP config |
| `provider` | AgentProvider (write-only) | Provider credentials |
| `predefined_metrics` | write-only | Assign predefined metrics |

### AgentTelephony (all fields optional)

| Field | Type | Notes |
|-------|------|-------|
| `phone_number` | string | E.164, e.g. `+14155551234` |
| `inbound` | boolean | Default `false` |
| `sip_uri` | string\|null | e.g. `sip:user@domain.com` |
| `sip_auth` | object\|null | `{username, password}` |
| `outbound_numbers` | string[] | E.164 numbers for outbound webhook validation |

### AgentProvider

| Field | Type | Notes |
|-------|------|-------|
| `type` | enum | `vapi\|retell\|elevenlabs\|bland\|livekit\|pipecat\|synthflow\|chirp\|koreai\|genesys\|trillet\|cisco\|self_hosted` |
| `agent_id` | string\|null | Voice agent ID on provider platform |
| `credentials` | AgentCredentials\|null | `{api_key (write-only), config}` |
| `chat_agent_details` | ChatAgentDetails\|null | `{type, config}` |
| `auto_sync_prompt` | boolean\|null | Sync every 30s (vapi, retell, elevenlabs, synthflow) |
| `auto_import_calls` | boolean\|null | Import calls every 30s (vapi, retell, elevenlabs) |
| `auto_dial_outbound` | boolean\|null | Auto-dial outbound (vapi, retell, elevenlabs, bland, livekit) |

## credentials.config Keys by Provider

| Provider | Required | Optional |
|----------|---------|---------|
| `vapi` | — | `public_key`, `trigger_url` |
| `retell` | — | `trigger_url`, `livekit_server_url` |
| `elevenlabs` | — | `trigger_url`, `elevenlabs_base_url_override` |
| `bland` | — | `encrypted_key` (Twilio bundle) |
| `livekit` | `api_secret`, `url` | `agent_name`, `config`, `tracing_enabled`, `trigger_url` |
| `pipecat` | — | `pipecat_agent_name`, `webhook_url`, `config`, `room_properties`, `tracing_enabled` |
| `synthflow` | — | `synthflow_base_url_override` |
| `chirp` | `chirp_websocket_url` | `chirp_basic_auth_username`, `chirp_basic_auth_password` |
| `koreai` | `client_id`, `bot_id` | `host` (default: https://bots.kore.ai) |
| `genesys` | `client_id`, `region` | — |
| `trillet` | `workspace_id` | — |
| `cisco` | — | — |
| `self_hosted` | — | `send_post_conversation_metadata` |

## chat_agent_details by type

| `type` | Required config | Optional config |
|--------|----------------|----------------|
| `retell` | `agent_id` | — |
| `bland` | `agent_id` (= pathway_id) | — |
| `vapi` | — | `agent_id` |
| `elevenlabs` | — | `agent_id` |
| `agentforce` | `agent_id`, `client_id`, `client_secret`, `domain` | — |
| `self_hosted` | `url` (wss://) | `headers` |
| `sms` | — | — |
| `whatsapp` | — | — |

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
  "information": [{"input": {}, "output": {}}],
  "freetext_params": ["notes"]
}
```

**Critical: Append-not-replace** — GET existing `information` first, merge, then PATCH the full array.

## Knowledge Base

```
POST /test_framework/v2/aiagents/{id}/upload_knowledge_base/
Content-Type: multipart/form-data
files: <file1>, <file2>
```

## Dynamic Variables

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/aiagents/{agent_id}/dynamic-variables/` | Upsert dynamic variables |
| GET | `/test_framework/v1/aiagents/{agent_id}/dynamic-variables/` | List dynamic variables |

### Upsert Schema

```json
POST /test_framework/v1/aiagents/{agent_id}/dynamic-variables/
[
  {
    "name": "string (required, snake_case — variable identifier)",
    "description": "string (required — what it represents, format/type, full structure, constraints, complete example)"
  }
]
```

- **Upsert** — POST the full array each time; creates new variables and updates existing ones
- Returns 201 with the complete variable list after upsert
- `name` is the variable identifier — must be unique per agent
- `description` should be as detailed as possible: full structure, all fields, constraints, example values

# Agent API Reference

## Authentication
All requests: `X-CEKURA-API-KEY: <key>` header. Base URL: `https://api.cekura.ai`

Docs: https://docs.cekura.ai/api-reference/test_framework/create-agent

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
| `websocket_url` | string\|null | Raw-PCM 16 kHz WebSocket voice endpoint (`wss://…`); runs via `scenarios_run_chirp` |
| `websocket_auth` | object\|null | `{username, password}` basic-auth for the WebSocket endpoint |
| `outbound_numbers` | string[] | E.164 numbers for outbound webhook validation |

### AgentProvider

| Field | Type | Notes |
|-------|------|-------|
| `type` | enum | `vapi\|retell\|elevenlabs\|bland\|livekit\|pipecat\|synthflow\|agora\|koreai\|genesys\|cisco\|amazon_connect\|telnyx\|custom` — `self_hosted` is rejected here; it is a `chat_agent_details.type` only |
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
| `koreai` | `client_id`, `bot_id` | `host` (default: https://bots.kore.ai) |
| `genesys` | `client_id`, `region` | — |
| `cisco` | — | — |
| `custom` | — | — (use `provider.send_post_conversation_metadata` at provider level) |

## chat_agent_details by type

| `type` | Required config | Optional config |
|--------|----------------|----------------|
| `retell` | `agent_id` | — |
| `bland` | `agent_id` (= Pathway ID) | — |
| `vapi` | — | `agent_id` |
| `elevenlabs` | — | `agent_id` |
| `agentforce` | `agent_id`, `client_id`, `client_secret`, `domain` | — |
| `self_hosted` | `url` (wss://) | `headers` |
| `sms` | — | — |
| `whatsapp` | — | — |

## Mock Tool Endpoints

Mock tools are managed via the agent's `mock_tools` field:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/test_framework/v2/aiagents/{id}/?ql={mock_tools}` | List mock tools |
| PATCH | `/test_framework/v2/aiagents/{id}/` | Create / update / delete mock tools (via `mock_tools` field) |
| POST | `/test_framework/v2/aiagents/{id}/auto-fetch/` | Auto-fetch tools from provider |
| POST | `/test_framework/v1/aiagents/{id}/run_scenarios/` | Run scenarios — pass `mock_tool_names` to activate per-run mocking |

### Update Mock Tools Schema

```json
PATCH /test_framework/v2/aiagents/{agent_id}/
{
  "mock_tools": [
    {
      "name": "string (required, max 64 chars)",
      "description": "string",
      "mock_data": [{"input": {}, "output": {}}],
      "freetext_params": ["notes"]
    }
  ]
}
```

**Critical: Full-list replace** — always include all tools; omitting a tool removes it. GET existing `mock_tools` first, merge, then PATCH the full list.

### Custom (self-hosted) MCP mock endpoints — REST only

For self-hosted agents with their own MCP server, use `provider="custom"` to auto-discover tools; Cekura hosts a drop-in mock MCP endpoint the agent points at. These are **REST-only** (not exposed as MCP tools) — call with the `X-CEKURA-API-KEY` header. There is **no enable/disable step** for custom: auto-fetch sets up the mock MCP, and enabling/disabling is customer-side (point the agent's MCP client at the URL, or back at the real server).

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/aiagents/{agent_id}/tools/auto-fetch/` | Discover tools + generate mock data + register the mock MCP endpoint. `provider` ∈ `vapi\|retell\|elevenlabs\|custom`; custom needs `mcp_server_url` (+ optional `mcp_server_headers`) |
| GET | `/test_framework/v1/aiagents/{agent_id}/tools/auto-fetch-progress/` | Poll auto-fetch (`?progress_id=`) |
| GET | `/test_framework/v1/aiagents/{agent_id}/tools/mock-status/` | Current state; custom agents surface the stable `/mcp/1/` under `mcp_endpoints[]` (env-correct URLs) |

**Runtime endpoint** (called by the agent under test; no auth):
- `POST /test_framework/v1/aiagents/{agent_id}/mcp/{mock_index}/` — mock MCP server (JSON-RPC 2.0: `initialize`, `tools/list`, `tools/call`). Custom agents point their MCP client here.

For custom agents: `mcp_server_url` is SSRF-validated (http/https only; private/loopback/metadata IPs blocked; `Host`/`Cookie`/`X-Forwarded-*` headers rejected), headers are stored encrypted, and an agent is pinned to a single MCP server.

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
- `name` is the variable identifier — must be unique per main agent
- `description` should be as detailed as possible: full structure, all fields, constraints, example values

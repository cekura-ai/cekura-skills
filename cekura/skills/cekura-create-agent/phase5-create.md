# Phase 5 — Create the Agent

Create the agent record using the live v1 API with data from Phases 1–4.

---

## 5a. v1 API — field reference

**Endpoint:** `POST https://api.cekura.ai/test_framework/v1/aiagents/`  
**Required fields:** `agent_name`, `description`, `inbound`, `project`, `assistant_provider`

| Field | Type | Notes |
|-------|------|-------|
| `agent_name` | string (max 255) | Display name |
| `description` | string | Full system prompt or exported config |
| `inbound` | boolean | `true` = receives calls, `false` = makes calls |
| `project` | integer | Project ID from Phase 1 |
| `assistant_provider` | enum | Provider type — see table in Phase 2 |
| `contact_number` | string | E.164 phone number (or Pipecat agent name) |
| `language` | string | BCP-47 locale, default `en` |
| `assistant_id` | string (min 10) | Provider agent ID — VAPI, ElevenLabs |
| `chat_assistant_id` | string | Provider agent ID — **Retell, Bland, SMS, WhatsApp** |
| `websocket_url` | string | WebSocket endpoint for self-hosted text-mode testing |
| `websocket_headers` | object | Headers sent to WebSocket server |
| `sip_endpoint` | string | SIP URI, e.g. `sip:agent@domain.com` |
| `sip_auth` | object | `{"username": "...", "password": "..."}` |
| `agent_gives_first_message` | boolean\|null | `true` = agent speaks first; `null` = auto-detect |
| `auto_sync_prompt_enabled` | boolean | Auto-sync description from provider every 30s |
| `auto_fetch_calls_enabled` | boolean | Auto-import production calls every 30s |
| `outbound_auto_call` | boolean | Auto-place outbound calls (VAPI/Retell only) |
| `outbound_numbers` | array | Numbers authorized for outbound webhook validation |
| `transcript_provider` | enum | STT vendor; usually set to match `assistant_provider` |

Provider credentials (all write-only, never returned):

| Provider | API key field | Config data field | Agent ID field |
|----------|--------------|------------------|----------------|
| VAPI | `vapi_api_key` | `vapi_data` (`public_key`, `trigger_url`) | `assistant_id` |
| Retell | `retell_api_key` | `retell_data` (`trigger_url`) | `chat_assistant_id` |
| ElevenLabs | `elevenlabs_api_key` | `elevenlabs_data` | `assistant_id` |
| LiveKit | `livekit_api_key` | `livekit_data` (`api_secret` required, `url` required) | — |
| Pipecat | `pipecat_api_key` | `pipecat_data` (`webhook_url`) | — (use `contact_number` = agent name) |
| Bland | `bland_api_key` | `bland_data` (`encrypted_key` for Twilio) | `chat_assistant_id` (= pathway_id) |
| Agentforce | `agentforce_client_secret` | `agentforce_data` (`client_id`, `domain`, `agent_id`) | — |
| Trillet | `trillet_api_key` | `trillet_data` (`workspace_id`) | — |

---

## 5b. Example payloads by provider

### Self-hosted (phone only — most common)
```json
{
  "agent_name": "Support Bot",
  "description": "Handles inbound support calls for ACME Inc.",
  "inbound": true,
  "project": 123,
  "contact_number": "+14155551234",
  "language": "en",
  "assistant_provider": "self_hosted"
}
```
No credentials needed — Cekura observes calls on that number.

### VAPI — assistant
```json
{
  "agent_name": "VAPI Sales Agent",
  "description": "Auto-syncing from provider",
  "inbound": false,
  "project": 123,
  "contact_number": "+14155551234",
  "language": "en",
  "assistant_provider": "vapi",
  "vapi_api_key": "vapi_sk_xxx",
  "vapi_data": {"public_key": "vapi_pk_xxx"},
  "assistant_id": "asst_abc123",
  "auto_sync_prompt_enabled": true
}
```

### VAPI — squad (multi-agent workflow)
```json
{
  "agent_name": "VAPI Multi-Agent Workflow",
  "description": "Auto-syncing from provider",
  "inbound": true,
  "project": 123,
  "contact_number": "+14155551234",
  "language": "en",
  "assistant_provider": "vapi",
  "vapi_api_key": "vapi_sk_xxx",
  "vapi_data": {"public_key": "vapi_pk_xxx"},
  "assistant_id": "squad_abc123",
  "auto_sync_prompt_enabled": true
}
```
Squad ID goes in `assistant_id` — same field, different ID format. Auto-sync tries `/assistant/{id}` first, falls back to `/squad/{id}`.

### Retell
```json
{
  "agent_name": "Retell Booking Agent",
  "description": "Auto-syncing from provider",
  "inbound": true,
  "project": 123,
  "contact_number": "+14155551234",
  "language": "en",
  "assistant_provider": "retell",
  "retell_api_key": "key_xxx",
  "chat_assistant_id": "retell_agent_abc123",
  "retell_data": {"trigger_url": "https://api.retellai.com/create-phone-call"},
  "auto_sync_prompt_enabled": true
}
```
⚠️ Retell uses **`chat_assistant_id`** (not `assistant_id`) for **both voice and text-mode**. If the user has a separate chat agent, set it via PATCH after creation.

### ElevenLabs
```json
{
  "agent_name": "ElevenLabs Voice Agent",
  "description": "Auto-syncing from provider",
  "inbound": true,
  "project": 123,
  "contact_number": "+14155551234",
  "language": "en",
  "assistant_provider": "elevenlabs",
  "elevenlabs_api_key": "el_sk_xxx",
  "assistant_id": "el_agent_abc123",
  "auto_sync_prompt_enabled": true
}
```

### LiveKit
```json
{
  "agent_name": "LiveKit Concierge",
  "description": "Multi-modal front-desk agent",
  "inbound": true,
  "project": 123,
  "language": "en",
  "assistant_provider": "livekit",
  "livekit_api_key": "APIxxx",
  "livekit_data": {
    "api_secret": "secret_xxx",
    "url": "wss://acme.livekit.cloud"
  }
}
```

### Pipecat Cloud
```json
{
  "agent_name": "Pipecat Support Agent",
  "description": "Voice agent deployed on Pipecat Cloud",
  "inbound": true,
  "project": 123,
  "contact_number": "my-support-agent",
  "language": "en",
  "assistant_provider": "pipecat",
  "pipecat_api_key": "pipecat_key_xxx",
  "pipecat_data": {"webhook_url": "https://your-server.com/webhook"}
}
```
`contact_number` = Pipecat **agent name** (not a phone number).

### Bland
```json
{
  "agent_name": "Bland Support Agent",
  "description": "Handles tier-1 billing questions",
  "inbound": true,
  "project": 123,
  "contact_number": "+14155551234",
  "language": "en",
  "assistant_provider": "bland",
  "bland_api_key": "bland_xxx",
  "chat_assistant_id": "bland_pathway_xyz",
  "bland_data": {"encrypted_key": "twilio_bundle_xxx"}
}
```
`chat_assistant_id` = Bland pathway_id.

### Self-hosted via WebSocket (text-mode)
```json
{
  "agent_name": "Internal Test Agent",
  "description": "Staging build of the support flow",
  "inbound": false,
  "project": 123,
  "language": "en",
  "assistant_provider": "self_hosted",
  "websocket_url": "wss://staging.example.com/agent",
  "websocket_headers": {"Authorization": "Bearer token_xxx"}
}
```

---

## 5c. POST the agent

### Via MCP (description ≤ 4 KB)
```
mcp__cekura__aiagents_create with the payload above
```

### Via curl (always safe; required for descriptions > 4 KB)
```bash
curl -X POST https://api.cekura.ai/test_framework/v1/aiagents/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @agent.json
```

Or use the helper:
```bash
scripts/upload-agent.sh agent.json          # create new
scripts/upload-agent.sh agent.json <id>     # update existing
```

---

## 5d. Save the agent ID

The response includes an `id` field. **Record it — every subsequent step requires it.**

---

## Phase 5 Gate

**Do not proceed until the agent is created and you have its `id`.**

Move to [Phase 6 — Connection Type](phase6-connection.md).

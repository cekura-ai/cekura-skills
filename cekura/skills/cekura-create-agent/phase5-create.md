# Phase 5 — Create the Agent

Create the agent record using the v2 API with data from Phases 1–4.

---

## 5a. v2 API — field names and provider block

**Endpoint:** `POST /test_framework/v2/aiagents/`  
**Required fields:** `name`, `description`, `inbound`, `project`

**Field names changed from v1 → v2:**

| v1 | v2 |
|----|----|
| `agent_name` | `name` |
| `contact_number` | `phone_number` |
| `sip_endpoint` | `sip_uri` |
| `outbound_auto_call` | `auto_dial_outbound` |
| `auto_fetch_calls_enabled` | `auto_import_calls` |
| `auto_sync_prompt_enabled` | `auto_sync_prompt` |
| `agent_gives_first_message` | `agent_speaks_first` |
| `assistant_provider` + flat `{n}_api_key` fields | `provider.{type, agent_id, credentials}` |

`transcript_provider` defaults to `provider.type` — usually no need to set it separately.

---

## 5b. Provider block structure

```json
"provider": {
  "type": "<provider_type>",
  "agent_id": "<voice/phone agent ID>",
  "chat_agent_id": "<text-mode agent ID — Retell only, optional>",
  "credentials": {
    "api_key": "<provider API key (write-only)>",
    "config": { ... provider-specific keys ... }
  }
}
```

**`credentials.config` keys by provider:**

| Provider | Required config keys | Optional config keys |
|----------|---------------------|---------------------|
| `vapi` | — | `public_key`, `trigger_url` |
| `retell` | — | `trigger_url` |
| `elevenlabs` | — | `trigger_url` |
| `bland` | — | `encrypted_key` (Twilio bundle) |
| `livekit` | `api_secret`, `url` | `tracing_enabled` |
| `agentforce` | `client_id`, `domain`, `agent_id` | — |
| `trillet` | `workspace_id` | — |
| `self_hosted` | `url` (wss://) | `headers` |

---

## 5c. Example payloads by provider

### Self-hosted (phone only — most common)
```json
{
  "name": "Support Bot",
  "description": "Handles inbound support calls...",
  "inbound": true,
  "project": 123,
  "phone_number": "+14155551234",
  "language": "en",
  "provider": {"type": "self_hosted"}
}
```

### VAPI
```json
{
  "name": "VAPI Sales Agent",
  "description": "Auto-syncing from provider",
  "inbound": false,
  "project": 123,
  "phone_number": "+14155551234",
  "language": "en",
  "auto_sync_prompt": true,
  "provider": {
    "type": "vapi",
    "agent_id": "asst_abc123",
    "credentials": {
      "api_key": "vapi_sk_xxx",
      "config": {"public_key": "vapi_pk_xxx"}
    }
  }
}
```
`auto_sync_prompt: true` — Cekura fetches the system message from VAPI within ~30 seconds. Pass a placeholder for `description`.

### Retell
```json
{
  "name": "Retell Booking Agent",
  "description": "Auto-syncing from provider",
  "inbound": true,
  "project": 123,
  "phone_number": "+14155551234",
  "language": "en",
  "auto_sync_prompt": true,
  "provider": {
    "type": "retell",
    "agent_id": "retell_voice_agent_abc",
    "chat_agent_id": "retell_chat_agent_xyz",
    "credentials": {
      "api_key": "key_xxx",
      "config": {"trigger_url": "https://api.retellai.com/create-phone-call"}
    }
  }
}
```
- `agent_id` = Retell agent for **voice/phone** calls
- `chat_agent_id` = separate Retell agent for **text-mode** test runs (optional — omit if same agent handles both)
- `auto_sync_prompt: true` — fetches `general_prompt` (retell-llm) or full flow JSON (conversation-flow)

### ElevenLabs
```json
{
  "name": "ElevenLabs Voice Agent",
  "description": "Auto-syncing from provider",
  "inbound": true,
  "project": 123,
  "phone_number": "+14155551234",
  "language": "en",
  "auto_sync_prompt": true,
  "provider": {
    "type": "elevenlabs",
    "agent_id": "el_agent_abc123",
    "credentials": {"api_key": "el_sk_xxx"}
  }
}
```
`auto_sync_prompt: true` — fetches from `conversation_config.agent.prompt.prompt`.

### LiveKit
```json
{
  "name": "LiveKit Concierge",
  "description": "Multi-modal front-desk agent",
  "inbound": true,
  "project": 123,
  "language": "en",
  "provider": {
    "type": "livekit",
    "credentials": {
      "api_key": "APIxxx",
      "config": {
        "api_secret": "secret_xxx",
        "url": "wss://acme.livekit.cloud"
      }
    }
  }
}
```

### Bland
```json
{
  "name": "Bland Support Agent",
  "description": "...",
  "inbound": true,
  "project": 123,
  "phone_number": "+14155551234",
  "language": "en",
  "provider": {
    "type": "bland",
    "agent_id": "bland_pathway_xyz",
    "credentials": {
      "api_key": "bland_xxx",
      "config": {"encrypted_key": "twilio_bundle_xxx"}
    }
  }
}
```
`provider.agent_id` = Bland pathway_id.

### Self-hosted via WebSocket (text-mode)
```json
{
  "name": "Internal Test Agent",
  "description": "Staging build of the support flow",
  "inbound": false,
  "project": 123,
  "language": "en",
  "provider": {
    "type": "self_hosted",
    "credentials": {
      "config": {
        "url": "wss://staging.example.com/agent",
        "headers": {"Authorization": "Bearer token_xxx"}
      }
    }
  }
}
```

---

## 5d. POST the agent

### Via MCP (description ≤ 4 KB)
```
mcp__cekura__aiagents_create with the payload above
```

### Via curl (always safe; required for descriptions > 4 KB)
```bash
curl -X POST https://api.cekura.ai/test_framework/v2/aiagents/ \
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

## 5e. Save the agent ID

The response includes an `id` field. **Record it — every subsequent step requires it.**

---

## Phase 5 Gate

**Do not proceed until the agent is created and you have its `id`.**

Move to [Phase 6 — Connection Type](phase6-connection.md).

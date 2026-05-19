# Phase 5 — Create the Agent

Create the agent record using the v2 API with the data collected in Phases 1–4.

---

## 5a. v2 API — field names and provider block

The v2 endpoint uses cleaner field names and a **nested `provider` block** instead of flat `{provider}_api_key` fields.

**Required fields:** `name`, `description`, `inbound`, `project`

**Field names changed from v1:**

| v1 field | v2 field |
|----------|---------|
| `agent_name` | `name` |
| `contact_number` | `phone_number` |
| `sip_endpoint` | `sip_uri` |
| `outbound_auto_call` | `auto_dial_outbound` |
| `auto_fetch_calls_enabled` | `auto_import_calls` |
| `auto_sync_prompt_enabled` | `auto_sync_prompt` |
| `agent_gives_first_message` | `agent_speaks_first` |
| `assistant_provider` + flat API key fields | `provider.{type, agent_id, credentials}` |

---

## 5b. Provider block shape

```json
"provider": {
  "type": "<provider_type>",
  "agent_id": "<assistant_id or chat_assistant_id>",
  "credentials": {
    "api_key": "<api_key>",
    "config": { ... provider-specific data ... }
  }
}
```

`transcript_provider` defaults to `provider.type` when omitted — you usually don't need to set it separately.

---

## 5c. Example payloads by provider

### Self-hosted (phone number only — most common)
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
  "description": "Outbound sales qualification calls",
  "inbound": false,
  "project": 123,
  "phone_number": "+14155551234",
  "language": "en",
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

### Retell
```json
{
  "name": "Retell Booking Agent",
  "description": "Schedules dental appointments",
  "inbound": true,
  "project": 123,
  "phone_number": "+14155551234",
  "language": "en",
  "provider": {
    "type": "retell",
    "agent_id": "retell_agent_abc123",
    "credentials": {"api_key": "key_xxx"}
  }
}
```
⚠️ Retell maps `provider.agent_id` to `chat_assistant_id` (used for voice too, despite the name).

### ElevenLabs
```json
{
  "name": "ElevenLabs Support Agent",
  "description": "...",
  "inbound": true,
  "project": 123,
  "phone_number": "+14155551234",
  "language": "en",
  "provider": {
    "type": "elevenlabs",
    "agent_id": "el_agent_abc123",
    "credentials": {"api_key": "el_sk_xxx"}
  }
}
```

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
      "config": {"api_secret": "secret_xxx", "url": "wss://acme.livekit.cloud"}
    }
  }
}
```

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

Note: MCP tools still call the underlying API — use for short descriptions only.

### Via curl (always safe, required for descriptions > 4 KB)

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

# Phase 5 — Create the Agent

Create the agent record using the v2 API with data from Phases 1–4.

---

## 5a. v2 API — field reference

**Endpoint:** `POST https://api.cekura.ai/test_framework/v2/aiagents/`  
**Required fields:** `name`, `description`, `project`, `inbound`

| Field | Type | Notes |
|-------|------|-------|
| `name` | string (max 255) | Display name |
| `description` | string | Full system prompt or exported config |
| `project` | integer | Project ID from Phase 1 |
| `language` | string | BCP-47 locale, default `en` |
| `agent_speaks_first` | boolean\|null | Agent speaks first; `null` = auto-detect |
| `telephony` | object | All phone/SIP fields — see below |
| `provider` | object | Provider block — see 5b |

**`telephony` block:**

| Field | Type | Notes |
|-------|------|-------|
| `telephony.phone_number` | string | E.164 format, e.g. `+14155551234` |
| `telephony.inbound` | boolean | `true` = receives calls, `false` = makes calls |
| `telephony.sip_uri` | string | SIP URI, e.g. `sip:agent@domain.com` |
| `telephony.sip_auth` | object | `{"username": "...", "password": "..."}` |
| `telephony.outbound_numbers` | array | Numbers for outbound webhook validation |

---

## 5b. Provider block structure

```json
"provider": {
  "type": "<provider_type>",
  "agent_id": "<voice agent ID on provider platform>",
  "credentials": {
    "api_key": "<provider API key (write-only)>",
    "config": { ... provider-specific keys ... }
  },
  "chat_agent_details": {
    "type": "<provider_type>",
    "config": { ... }
  },
  "auto_sync_prompt": true,
  "auto_import_calls": true,
  "auto_dial_outbound": false
}
```

`auto_sync_prompt`, `auto_import_calls`, and `auto_dial_outbound` live **inside the provider block**, not at the top level.

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
| `pipecat` | `pipecat_agent_name` | `webhook_url`, `config`, `room_properties` |
| `self_hosted` | — | — |

**`chat_agent_details.config` keys by provider:**

| Provider | Config keys |
|----------|-------------|
| Retell | `agent_id` (required) |
| Bland | `agent_id` (required, = pathway_id) |
| VAPI | `agent_id` |
| ElevenLabs | `agent_id` |
| Self-hosted | `url` (required, wss://), `headers` |

---

## 5c. Example payloads by provider

### Self-hosted (phone only — most common)
```json
{
  "name": "Support Bot",
  "description": "Handles inbound support calls for ACME Inc.",
  "project": 123,
  "telephony": {
    "phone_number": "+14155551234",
    "inbound": true
  },
  "language": "en",
  "provider": {"type": "self_hosted"}
}
```

### Self-hosted via WebSocket (text-mode)
```json
{
  "name": "Internal Test Agent",
  "description": "Staging build of the support flow",
  "project": 123,
  "telephony": {"inbound": false},
  "language": "en",
  "provider": {
    "type": "self_hosted",
    "chat_agent_details": {
      "type": "self_hosted",
      "config": {
        "url": "wss://staging.example.com/agent",
        "headers": {"Authorization": "Bearer token_xxx"}
      }
    }
  }
}
```

### VAPI — assistant
```json
{
  "name": "VAPI Sales Agent",
  "description": "Auto-syncing from provider",
  "project": 123,
  "telephony": {
    "phone_number": "+14155551234",
    "inbound": false
  },
  "language": "en",
  "provider": {
    "type": "vapi",
    "agent_id": "asst_abc123",
    "credentials": {
      "api_key": "vapi_sk_xxx",
      "config": {"public_key": "vapi_pk_xxx"}
    },
    "auto_sync_prompt": true,
    "auto_import_calls": true
  }
}
```

### VAPI — squad (multi-agent workflow)
```json
{
  "name": "VAPI Multi-Agent Workflow",
  "description": "Auto-syncing from provider",
  "project": 123,
  "telephony": {
    "phone_number": "+14155551234",
    "inbound": true
  },
  "language": "en",
  "provider": {
    "type": "vapi",
    "agent_id": "squad_abc123",
    "credentials": {
      "api_key": "vapi_sk_xxx",
      "config": {"public_key": "vapi_pk_xxx"}
    },
    "auto_sync_prompt": true
  }
}
```
Squad ID goes in `agent_id`. Auto-sync tries `/assistant/{id}` first, falls back to `/squad/{id}`.

### Retell
```json
{
  "name": "Retell Booking Agent",
  "description": "Auto-syncing from provider",
  "project": 123,
  "telephony": {
    "phone_number": "+14155551234",
    "inbound": true
  },
  "language": "en",
  "provider": {
    "type": "retell",
    "agent_id": "retell_voice_agent_abc",
    "credentials": {
      "api_key": "key_xxx",
      "config": {"trigger_url": "https://api.retellai.com/create-phone-call"}
    },
    "chat_agent_details": {
      "type": "retell",
      "config": {"agent_id": "retell_chat_agent_xyz"}
    },
    "auto_sync_prompt": true,
    "auto_import_calls": true
  }
}
```
- `provider.agent_id` = Retell **voice** agent
- `chat_agent_details.config.agent_id` = Retell **chat/text-mode** agent (optional — omit if same agent handles both)

### ElevenLabs
```json
{
  "name": "ElevenLabs Voice Agent",
  "description": "Auto-syncing from provider",
  "project": 123,
  "telephony": {
    "phone_number": "+14155551234",
    "inbound": true
  },
  "language": "en",
  "provider": {
    "type": "elevenlabs",
    "agent_id": "el_agent_abc123",
    "credentials": {"api_key": "el_sk_xxx"},
    "auto_sync_prompt": true
  }
}
```

### LiveKit
```json
{
  "name": "LiveKit Concierge",
  "description": "Multi-modal front-desk agent",
  "project": 123,
  "telephony": {"inbound": true},
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

### Pipecat Cloud
```json
{
  "name": "Pipecat Support Agent",
  "description": "Voice agent deployed on Pipecat Cloud",
  "project": 123,
  "telephony": {"inbound": true},
  "language": "en",
  "provider": {
    "type": "pipecat",
    "credentials": {
      "api_key": "pipecat_key_xxx",
      "config": {
        "pipecat_agent_name": "my-support-agent",
        "webhook_url": "https://your-server.com/webhook"
      }
    }
  }
}
```
Agent name goes in `credentials.config.pipecat_agent_name` — not in `telephony.phone_number`.

### Bland
```json
{
  "name": "Bland Support Agent",
  "description": "Handles tier-1 billing questions",
  "project": 123,
  "telephony": {
    "phone_number": "+14155551234",
    "inbound": true
  },
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

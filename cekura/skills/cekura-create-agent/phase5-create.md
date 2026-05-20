# Phase 5 — Create the Agent

**Endpoint:** `POST https://api.cekura.ai/test_framework/v2/aiagents/`

**Required fields:** `name`, `description`, `project` — everything else is optional.

---

## 5a. Top-level fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | string (max 255) | **Required** |
| `description` | string | **Required** — full system prompt or placeholder if using auto-sync |
| `project` | integer | **Required** — project ID from Phase 1 |
| `language` | string | BCP-47 locale, default `en` |
| `agent_speaks_first` | boolean\|null | `null` = auto-detect |
| `telephony` | object (write-only) | Phone/SIP config — all fields optional |
| `provider` | object (write-only) | Provider credentials and settings |

**`telephony` block** (all optional):

| Field | Notes |
|-------|-------|
| `telephony.phone_number` | E.164, e.g. `+14155551234` |
| `telephony.inbound` | boolean, default `false` |
| `telephony.sip_uri` | e.g. `sip:agent@domain.com` |
| `telephony.sip_auth` | `{"username": "...", "password": "..."}` |
| `telephony.outbound_numbers` | Array of E.164 numbers for outbound webhook validation |

---

## 5b. Provider block

```json
"provider": {
  "type": "vapi|retell|elevenlabs|bland|livekit|pipecat|synthflow|chirp|koreai|genesys|trillet|cisco|self_hosted",
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

**`credentials.config` keys by provider:**

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
| `koreai` | `client_id`, `bot_id` | `host` |
| `genesys` | `client_id`, `region` | — |
| `trillet` | `workspace_id` | — |
| `cisco` | — | — |
| `self_hosted` | — | `send_post_conversation_metadata` |

**`chat_agent_details.config` by provider:**

| `type` | Config keys |
|--------|-------------|
| `retell` | `agent_id` (required) |
| `bland` | `agent_id` (required, = pathway_id) |
| `vapi` | `agent_id` |
| `elevenlabs` | `agent_id` |
| `agentforce` | `agent_id`, `client_id`, `client_secret`, `domain` (all required) |
| `self_hosted` | `url` (required, wss://), `headers` |

---

## 5c. Example payloads by provider

### Self-hosted (phone — most common)
```json
{
  "name": "Support Bot",
  "description": "Handles inbound support calls for ACME Inc.",
  "project": 123,
  "language": "en",
  "provider": {"type": "self_hosted"},
  "telephony": {
    "phone_number": "+14155551234",
    "inbound": true
  }
}
```

### Self-hosted via WebSocket (text-mode)
```json
{
  "name": "Internal Test Agent",
  "description": "Staging build of the support flow",
  "project": 123,
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
  },
  "telephony": {"inbound": false}
}
```

### VAPI — assistant
```json
{
  "name": "VAPI Sales Agent",
  "description": "Auto-syncing from provider",
  "project": 123,
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
  },
  "telephony": {
    "phone_number": "+14155551234",
    "inbound": false
  }
}
```

### VAPI — squad (multi-agent)
Same as above but `agent_id` = squad ID. Auto-sync tries `/assistant/{id}` first, falls back to `/squad/{id}`.

### Retell
```json
{
  "name": "Retell Booking Agent",
  "description": "Auto-syncing from provider",
  "project": 123,
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
  },
  "telephony": {
    "phone_number": "+14155551234",
    "inbound": true
  }
}
```
`chat_agent_details` is optional — omit if the same agent handles voice and text.

### ElevenLabs
```json
{
  "name": "ElevenLabs Voice Agent",
  "description": "Auto-syncing from provider",
  "project": 123,
  "language": "en",
  "provider": {
    "type": "elevenlabs",
    "agent_id": "el_agent_abc123",
    "credentials": {"api_key": "el_sk_xxx"},
    "auto_sync_prompt": true
  },
  "telephony": {
    "phone_number": "+14155551234",
    "inbound": true
  }
}
```

### LiveKit
```json
{
  "name": "LiveKit Concierge",
  "description": "Multi-modal front-desk agent",
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
  },
  "telephony": {"inbound": true}
}
```

### Bland
```json
{
  "name": "Bland Support Agent",
  "description": "Handles tier-1 billing questions",
  "project": 123,
  "language": "en",
  "provider": {
    "type": "bland",
    "agent_id": "bland_pathway_xyz",
    "credentials": {
      "api_key": "bland_xxx",
      "config": {"encrypted_key": "twilio_bundle_xxx"}
    }
  },
  "telephony": {
    "phone_number": "+14155551234",
    "inbound": true
  }
}
```

### Pipecat Cloud
```json
{
  "name": "Pipecat Support Agent",
  "description": "Voice agent deployed on Pipecat Cloud",
  "project": 123,
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
  },
  "telephony": {"inbound": true}
}
```

### Chirp
```json
{
  "name": "Chirp Voice Agent",
  "description": "WebSocket voice agent",
  "project": 123,
  "language": "en",
  "provider": {
    "type": "chirp",
    "credentials": {
      "config": {
        "chirp_websocket_url": "wss://your-host/voice",
        "chirp_basic_auth_username": "user",
        "chirp_basic_auth_password": "pass"
      }
    }
  }
}
```

---

## 5d. POST the agent

### Via API (descriptions > 4 KB — always safe)
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

The response `id` is needed for all subsequent steps.

---

## Phase 5 Gate

**Do not proceed until the agent is created and you have its `id`.**

Move to [Phase 6 — Connection Type](phase6-connection.md).

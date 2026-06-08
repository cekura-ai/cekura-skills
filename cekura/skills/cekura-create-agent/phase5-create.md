# Phase 5 — Create the Main Agent

**Endpoint:** `POST https://api.cekura.ai/test_framework/v2/aiagents/`

**Required fields:** `name`, `description`, `project` — everything else is optional.

---

> **Start:** Announce "Starting Phase 5 — Create the Main Agent" before doing anything in this phase.

## Auto-import path (VAPI / Retell / ElevenLabs / Synthflow)

For these four providers, use `configure_from_provider: true`. The backend imports name, description (system prompt), language, phone number, connection type, tools, knowledge base, and dynamic variables automatically. Phases 3, 4, 6, 7, and 8 are all skipped.

**Minimal payload:**
```json
{
  "project": 123,
  "provider": {
    "type": "vapi|retell|elevenlabs|synthflow",
    "agent_id": "<assistant/agent ID on provider platform>",
    "credentials": {
      "api_key": "<provider API key>"
    },
    "configure_from_provider": true
  }
}
```

**POST** `https://api.cekura.ai/test_framework/v2/aiagents/`  
Response: **202 Accepted** — `{ "progress_id": "abc123..." }`

**Poll progress:**
```bash
curl -s "https://api.cekura.ai/test_framework/v2/aiagents/import-progress/?progress_id=<progress_id>" \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY"
```

Import stages (in order):

| Stage | What happens |
|-------|-------------|
| `validate` | Connecting to provider, validating credentials |
| `prompt` | Importing system prompt / description |
| `settings` | Importing name, language, and call settings |
| `phone` | Importing phone number and inbound/outbound direction |
| `tools` | Fetching tool definitions and generating mock data |
| `dynamic_variables` | Extracting dynamic variable slots |
| `kb` | Importing knowledge base files |
| `finalize` | Finalising agent record — returns `agent_id` |

Keep polling until `status` is `completed`. The response at `finalize` includes the created agent's `id` — save it for all subsequent steps.

**Example: VAPI auto-import**
```json
{
  "project": 123,
  "provider": {
    "type": "vapi",
    "agent_id": "asst_abc123",
    "credentials": {
      "api_key": "vapi_sk_xxx"
    },
    "configure_from_provider": true
  }
}
```

**Example: Retell auto-import**
```json
{
  "project": 123,
  "provider": {
    "type": "retell",
    "agent_id": "retell_voice_agent_abc",
    "credentials": {
      "api_key": "key_xxx"
    },
    "configure_from_provider": true
  }
}
```

**Example: ElevenLabs auto-import**
```json
{
  "project": 123,
  "provider": {
    "type": "elevenlabs",
    "agent_id": "el_agent_abc123",
    "credentials": {
      "api_key": "el_sk_xxx"
    },
    "configure_from_provider": true
  }
}
```

**Example: Synthflow auto-import**
```json
{
  "project": 123,
  "provider": {
    "type": "synthflow",
    "agent_id": "synthflow_agent_abc",
    "credentials": {
      "api_key": "synthflow_sk_xxx"
    },
    "configure_from_provider": true
  }
}
```

After the import completes, retrieve the agent via `mcp__cekura__aiagents_tool_retrieve` to confirm name, description, phone number, and provider settings were populated. Then skip directly to [Phase 9 — Advanced Configuration](phase9-advanced.md).

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
  "type": "vapi|retell|elevenlabs|bland|livekit|pipecat|synthflow|chirp|koreai|genesys|cisco|self_hosted",
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
| `synthflow` | `agent_id` (top-level `provider.agent_id`) | `synthflow_base_url_override` |
| `chirp` | `chirp_websocket_url` | `chirp_basic_auth_username`, `chirp_basic_auth_password` |
| `koreai` | `client_id`, `bot_id` | `host` |
| `genesys` | `client_id`, `region` | — |
| `cisco` | — | — |
| `self_hosted` | — | — |

> **`send_post_conversation_metadata`** for `self_hosted` is set at the **provider level** (not inside `credentials.config`): `"provider": {"type": "self_hosted", "send_post_conversation_metadata": true}`

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
> **Recommended:** use the auto-import path at the top of this phase instead. The examples below are for manual / advanced setup only.

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
> **Recommended:** use the auto-import path at the top of this phase instead. The example below is for manual / advanced setup only.

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
> **Recommended:** use the auto-import path at the top of this phase instead. The example below is for manual / advanced setup only.

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
  "telephony": {"inbound": true},
  "provider": {
    "type": "pipecat",
    "credentials": {
      "api_key": "<Pipecat Cloud API Key from pipecat.daily.co>",
      "config": {
        "pipecat_agent_name": "<agent name from Pipecat dashboard>",
        "webhook_url": "<optional — webhook URL for call events>",
        "config": {},
        "room_properties": {},
        "tracing_enabled": false
      }
    }
  }
}
```

- `pipecat_agent_name` — required when `tracing_enabled` is false; the name of the agent as deployed in Pipecat Cloud
- `config` — additional agent configuration as JSON (optional)
- `room_properties` — Daily.co room properties configuration as JSON (optional)
- `webhook_url` — webhook URL for Pipecat call events (optional)
- `tracing_enabled` — enable Pipecat tracing (optional, default false)

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

### Synthflow
```json
{
  "project": 123,
  "provider": {
    "type": "synthflow",
    "agent_id": "<Synthflow agent ID>",
    "credentials": {
      "api_key": "<Synthflow API Key>",
      "config": {
        "synthflow_base_url_override": "<optional — custom base URL for EU or specific regions>"
      }
    },
    "configure_from_provider": true
  }
}
```

### KoreAI
```json
{
  "name": "KoreAI Agent",
  "description": "...",
  "project": 123,
  "language": "en",
  "provider": {
    "type": "koreai",
    "credentials": {
      "api_key": "<KoreAI client secret>",
      "config": {
        "client_id": "<OAuth2 Client ID — required>",
        "bot_id": "<KoreAI Bot ID — required>",
        "host": "<optional — defaults to https://bots.kore.ai>"
      }
    }
  }
}
```

### Genesys
```json
{
  "name": "Genesys Agent",
  "description": "...",
  "project": 123,
  "language": "en",
  "provider": {
    "type": "genesys",
    "credentials": {
      "api_key": "<Genesys client secret>",
      "config": {
        "client_id": "<OAuth2 Client ID — required>",
        "region": "<Genesys Cloud region, e.g. us-east-1 — required>"
      }
    }
  }
}
```

### Cisco
```json
{
  "name": "Cisco Agent",
  "description": "...",
  "project": 123,
  "language": "en",
  "telephony": {"phone_number": "+14155551234", "inbound": true},
  "provider": {
    "type": "cisco"
  }
}
```
No credentials needed for Cisco.

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

**Do not proceed until the main agent is created and you have its `id`.**

**Creating the main agent record is NOT the end of setup.** Move immediately to the next phase.

- **Auto-import providers (VAPI / Retell / ElevenLabs / Synthflow):** Tools, KB, and dynamic variables were auto-populated. Skip Phases 6, 7, and 8. Go directly to [Phase 9 — Advanced Configuration](phase9-advanced.md).
- **All other providers:** Mock tools, knowledge base, and dynamic variables still need manual setup. Proceed to [Phase 6 — Mock Tools](phase6-mock-tools.md).

Announce: "Phase 5 complete." Then immediately begin the next applicable phase without waiting for the user.

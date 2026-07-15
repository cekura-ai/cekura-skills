# Provider Integration Reference

All examples use the v2 API (`/test_framework/v2/aiagents/`) with the nested `provider` block.

---

## VAPI

**Auto-import (recommended):**
```json
{
  "project": 123,
  "provider": {
    "type": "vapi",
    "agent_id": "<VAPI Assistant ID or Squad ID>",
    "credentials": {"api_key": "<VAPI Private API Key>"},
    "configure_from_provider": true
  }
}
```

**Manual setup:**
```json
{
  "name": "VAPI Agent",
  "description": "...",
  "project": 123,
  "telephony": {"phone_number": "+14155551234", "inbound": true},
  "provider": {
    "type": "vapi",
    "agent_id": "<VAPI Assistant ID or Squad ID>",
    "credentials": {
      "api_key": "<VAPI Private API Key>",
      "config": {
        "public_key": "<VAPI Public Key — WebRTC only>",
        "trigger_url": "<optional — outbound call trigger URL>"
      }
    },
    "auto_sync_prompt": true,
    "auto_import_calls": true
  }
}
```

**Credentials:** VAPI Dashboard → Organization Settings → API Keys  
**Agent ID:** Assistants → Select → copy from URL. For squads, use the squad ID.  
**Docs:** https://docs.vapi.ai/api-reference/assistants/get | https://docs.vapi.ai/api-reference/squads/get

**Chat setup:** Set `chat_agent_details: {"type": "vapi", "config": {"agent_id": "<chat assistant ID>"}}`

---

## Retell

**Auto-import (recommended):**
```json
{
  "project": 123,
  "provider": {
    "type": "retell",
    "agent_id": "<Retell voice agent ID>",
    "credentials": {"api_key": "<Retell API Key>"},
    "configure_from_provider": true
  }
}
```

**Manual setup:**
```json
{
  "name": "Retell Agent",
  "description": "...",
  "project": 123,
  "telephony": {"phone_number": "+14155551234", "inbound": true},
  "provider": {
    "type": "retell",
    "agent_id": "<Retell voice agent ID>",
    "credentials": {
      "api_key": "<Retell API Key>",
      "config": {
        "trigger_url": "<optional — outbound call trigger URL>",
        "livekit_server_url": "<optional — override Retell LiveKit server>"
      }
    },
    "chat_agent_details": {
      "type": "retell",
      "config": {"agent_id": "<Retell chat agent ID — omit if same agent>"}
    },
    "auto_sync_prompt": true,
    "auto_import_calls": true
  }
}
```

**Credentials:** Retell Dashboard → Settings → API Keys  
**Agent ID:** Agents → Select → ID in URL  
**Chat agent:** In Retell, use "Copy as chat agent" to create a text-mode version  
**Auto-sync:** Supports `retell-llm` (fetches `general_prompt`) and `conversation-flow` (fetches full flow JSON)  
**Docs:** https://docs.retellai.com/api-references/get-agent.md

---

## ElevenLabs

**Auto-import (recommended):**
```json
{
  "project": 123,
  "provider": {
    "type": "elevenlabs",
    "agent_id": "<ElevenLabs Agent ID>",
    "credentials": {"api_key": "<ElevenLabs API Key>"},
    "configure_from_provider": true
  }
}
```

**Manual setup:**
```json
{
  "name": "ElevenLabs Agent",
  "description": "...",
  "project": 123,
  "telephony": {"phone_number": "+14155551234", "inbound": true},
  "provider": {
    "type": "elevenlabs",
    "agent_id": "<ElevenLabs Agent ID>",
    "credentials": {
      "api_key": "<ElevenLabs API Key>",
      "config": {
        "trigger_url": "<optional>",
        "elevenlabs_base_url_override": "<optional>"
      }
    },
    "auto_sync_prompt": true,
    "auto_import_calls": true
  }
}
```

**Credentials:** ElevenLabs Dashboard → Profile → API Keys  
**Agent ID:** Conversational AI → Select agent → ID in settings  
**Auto-sync:** Fetches from `conversation_config.agent.prompt.prompt`  
**Docs:** https://elevenlabs.io/docs/api-reference/conversational-ai/get-agent

---

## LiveKit

Keep `provider.type = livekit` regardless of connection mode (phone, WebRTC, chat). LiveKit/Pipecat phone agents should not be classified as `self_hosted`.

**Recommended payload (SDK integration + WebRTC Automated, also covers Telephony):**

```json
{
  "name": "LiveKit Agent",
  "description": "...",
  "project": 123,
  "telephony": {"phone_number": "+14155551234", "inbound": true},
  "provider": {
    "type": "livekit",
    "credentials": {
      "api_key": "<LiveKit API Key>",
      "config": {
        "api_secret": "<LiveKit API Secret>",
        "url": "<wss://your-server.livekit.cloud>",
        "agent_name": "<worker agent_name>",
        "config": {"empty_timeout": 300},
        "tracing_enabled": true
      }
    },
    "auto_dial_outbound": true
  }
}
```

- `tracing_enabled: true` — Cekura waits for the Cekura SDK to confirm test-run data. Phase 6 of `cekura-create-agent` integrates the SDK in the user's agent code. If the SDK is not integrated, set this to `false`.
- `agent_name` must match `@server.rtc_session(agent_name=...)` in the agent code (required for WebRTC Automated and Chat connections).
- `credentials.config.config` — JSON injected into `ctx.room.metadata` during dispatch. Populate with the keys the agent reads.
- Required credentials by connection mode:
  - **Telephony only:** none on the agent record (Cekura dials the phone number).
  - **WebRTC Automated or Chat:** `api_key`, `api_secret`, `url`, `agent_name` all required.
  - **WebRTC Manual:** none on the agent record (room URL + token per scenario run via the scenarios-external API).
  - **Observability via Cekura SDK:** `api_key`, `api_secret`, `url` required for LiveKit egress audio recording; `agent_name` optional.

**Credentials:** LiveKit Cloud Dashboard → Settings → Keys  
**SDK setup:** see `references/livekit-tracing.md`  
**Latency metrics:** `metadata.raw_metrics` with per-component latency (LLM TTFT, TTS TTFB, EOU delay)

---

## Pipecat Cloud

Keep `provider.type = pipecat` regardless of connection mode.

**Recommended payload (SDK integration + WebRTC Automated, also covers Telephony):**

```json
{
  "name": "Pipecat Agent",
  "description": "...",
  "project": 123,
  "telephony": {"phone_number": "+14155551234", "inbound": true},
  "provider": {
    "type": "pipecat",
    "credentials": {
      "api_key": "<Pipecat Cloud API Key>",
      "config": {
        "pipecat_agent_name": "<agent name from Pipecat dashboard>",
        "webhook_url": "<optional>",
        "config": {},
        "room_properties": {},
        "tracing_enabled": true
      }
    }
  }
}
```

- `tracing_enabled: true` — Cekura waits for the Cekura SDK to confirm test-run data. Phase 6 of `cekura-create-agent` integrates the SDK in the user's agent code. If the SDK is not integrated, set this to `false`.
- `credentials.config.config` — optional Pipecat agent configuration JSON used when Cekura starts the session.
- `credentials.config.room_properties` — optional Daily.co room properties JSON applied when Cekura creates the room.
- Required credentials by connection mode:
  - **Telephony only:** none on the agent record (Cekura dials the phone number).
  - **WebRTC Automated:** `api_key`, `pipecat_agent_name` both required.
  - **WebRTC Manual:** none on the agent record (room URL + token per scenario run via the scenarios-external API).
  - **Observability via Cekura SDK:** none on the agent record — the SDK records audio in-process via its own audio frame processor.

**Credentials:** pipecat.daily.co → Settings → API Keys  
**Agent name:** use the name given when deploying to Pipecat Cloud  
**SDK setup:** see `references/pipecat-tracing.md`  
**Docs:** https://docs.pipecat.ai

---

## Bland

```json
{
  "name": "Bland Agent",
  "description": "...",
  "project": 123,
  "telephony": {"phone_number": "+14155551234", "inbound": true},
  "provider": {
    "type": "bland",
    "agent_id": "<Bland pathway_id>",
    "credentials": {
      "api_key": "<Bland API Key>",
      "config": {
        "encrypted_key": "<Twilio credential bundle — optional>"
      }
    },
    "auto_dial_outbound": true
  }
}
```

**Credentials:** Bland Dashboard → API Keys  
**`agent_id`:** Bland pathway_id — Pathways → Select → copy ID  
**Docs:** https://docs.bland.ai

---

## Synthflow

```json
{
  "project": 123,
  "provider": {
    "type": "synthflow",
    "agent_id": "<Synthflow Agent ID>",
    "credentials": {
      "api_key": "<Synthflow API Key>",
      "config": {
        "synthflow_base_url_override": "<optional>"
      }
    },
    "configure_from_provider": true
  }
}
```

**Agent ID:** Synthflow Dashboard → Select agent → copy ID  
**Auto-import:** Imports name, prompt, phone, tools, KB, and dynamic variables automatically.

---

## WebSocket voice (raw-PCM)

Cekura dials your `wss://` endpoint and streams 16 kHz raw PCM (the CHIRP protocol).
Create as `provider.type = "custom"` with the endpoint under `telephony`:

```json
{
  "name": "WebSocket Voice Agent",
  "description": "...",
  "project": 123,
  "provider": {
    "type": "custom"
  },
  "telephony": {
    "websocket_url": "<wss://your-host/voice — required, raw PCM 16 kHz>",
    "inbound": true,
    "websocket_auth": { "username": "<optional>", "password": "<optional>" }
  }
}
```

---

## KoreAI

```json
{
  "name": "KoreAI Agent",
  "description": "...",
  "project": 123,
  "provider": {
    "type": "koreai",
    "credentials": {
      "api_key": "<KoreAI client secret>",
      "config": {
        "client_id": "<required>",
        "bot_id": "<required>",
        "host": "<optional — default: https://bots.kore.ai>"
      }
    }
  }
}
```

---

## Genesys

```json
{
  "name": "Genesys Agent",
  "description": "...",
  "project": 123,
  "provider": {
    "type": "genesys",
    "credentials": {
      "api_key": "<Genesys client secret>",
      "config": {
        "client_id": "<required>",
        "region": "<required — e.g. us-east-1>"
      }
    }
  }
}
```

---

## Cisco

Cisco Webex is a specialized webhook-based integration — Cekura receives a `botDescription` + `userEmail` from Cisco and generates/runs scenarios automatically. It uses a pre-configured agent on the Cekura side rather than user-supplied credentials.

Contact Cekura support to set up the Cisco Webex integration for your organization.

---

## Self-hosted (phone / SIP)

```json
{
  "name": "Self-hosted Agent",
  "description": "...",
  "project": 123,
  "telephony": {
    "phone_number": "+14155551234",
    "inbound": true,
    "sip_uri": "sip:agent@yourdomain.com",
    "sip_auth": {"username": "user", "password": "pass"}
  },
  "provider": {"type": "self_hosted"}
}
```

SIP headers: Cekura injects `X-Run-Id`, `X-Scenario-Id`, and `X-Result-Id` on every test call. To send your own custom headers, add `X-` prefixed keys to a test profile's `main_agent_variables` and attach that profile to the run (`test_profile_ids`) — headers cannot be configured on the agent itself or in the run request.

---

## Self-hosted (WebSocket / text-mode)

```json
{
  "name": "WebSocket Agent",
  "description": "...",
  "project": 123,
  "telephony": {"inbound": false},
  "provider": {
    "type": "self_hosted",
    "chat_agent_details": {
      "type": "self_hosted",
      "config": {
        "url": "wss://your-server.com/agent",
        "headers": {"Authorization": "Bearer token"}
      }
    }
  }
}
```

**WebSocket message format:**
- Regular: `{"content": "message"}`
- Function call: `{"role": "Function Call", "data": {"id": "...", "name": "...", "arguments": "{}"}}`
- Function result: `{"role": "Function Call Result", "data": {"id": "...", "result": "{}"}}`
- End call: `{"content": "...", "type": "end_call"}`

**Headers sent by Cekura:** `X-VOCERA-SECRET`, `X-VOCERA-SCENARIO-ID`, `X-VOCERA-RESULT-ID`, `X-VOCERA-RUN-ID`, any test profile fields starting with `X-`.

---

## Custom Integration (Webhook / Observe)

For providers without first-class integration — push call data to Cekura after calls complete.

```json
POST https://api.cekura.ai/observability/v1/observe/
X-CEKURA-API-KEY: <key>

{
  "agent_id": 123,
  "calls": [{
    "id": "unique-call-id",
    "startedAt": "2024-01-01T00:00:00Z",
    "endedAt": "2024-01-01T00:05:00Z",
    "to_phone_number": "+14155551234",
    "from_phone_number": "+14155559876",
    "messages": [
      {"role": "bot", "content": "Hello", "start_time": 0, "end_time": 1500},
      {"role": "user", "content": "Hi", "start_time": 2000, "end_time": 3500}
    ],
    "metadata": {},
    "endedReason": "customer-hungup"
  }]
}
```

Message roles: `bot`, `user`, `system`, `function_call`, `function_call_result`  
`start_time`/`end_time` in milliseconds. Must send within 5 minutes of call end.

---

## Outbound Agents

```json
{
  "telephony": {"inbound": false, "outbound_numbers": ["+14155551234"]},
  "provider": {
    "type": "vapi",
    "auto_dial_outbound": true,
    "credentials": {...}
  }
}
```

`auto_dial_outbound` triggers Cekura to place the call via the provider. Test profile fields are forwarded as dynamic variables. Supported for: VAPI, Retell, ElevenLabs, LiveKit, Bland.

---

## Provider Comparison

Provider rows only. Connection modes (SIP, WebSocket, chat, PSTN, WebRTC) are picked independently.

| Feature | VAPI | Retell | ElevenLabs | LiveKit | Pipecat | Bland | Synthflow | Cisco | KoreAI | Genesys | Self-hosted |
|---------|------|--------|------------|---------|---------|-------|-----------|-------|--------|---------|-------------|
| Phone (PSTN) | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No | No | Yes |
| WebRTC | Yes | Yes | No | Yes | Yes | No | No | No | No | No | No |
| WebSocket voice | No | No | No | No | No | No | No | No | No | No | Yes |
| Chat / Text | Yes | Yes | Yes | Yes | No | Yes | No | No | Yes | Yes | Yes |
| **Auto-import agent** | Yes | Yes | Yes | No | No | No | Yes | No | No | No | No |
| Auto-fetch calls | Yes | Yes | Yes | No | No | No | Yes | No | No | No | No |
| Auto-fetch tools | Yes | Yes | Yes | No | Yes | No | No | No | No | No | No |
| Auto-sync prompt | Yes | Yes | Yes | No | No | No | Yes | No | No | No | No |
| Outbound auto-call | Yes | Yes | Yes | Yes | No | Yes | No | No | No | No | No |
| Latency metrics | No | No | No | Yes | No | No | No | No | No | No | No |

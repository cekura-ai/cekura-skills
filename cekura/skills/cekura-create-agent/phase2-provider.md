# Phase 2 — Provider Selection

Identify the provider upfront — it determines what credentials to collect, what connection types are available, and which automated features work.

---

> **Start:** Announce "Starting Phase 2 — Provider Selection" before doing anything in this phase.

## 2a. Which provider?

Ask: "What provider does your main agent run on?"

| Provider | `provider.type` | Notes |
|----------|----------------|-------|
| **VAPI** | `vapi` | Assistants and squads (multi-agent); phone + WebRTC + chat |
| **Retell** | `retell` | Auto-sync prompt; separate voice `agent_id` and chat `chat_agent_details` |
| **ElevenLabs** | `elevenlabs` | Phone + chat; auto-sync prompt |
| **LiveKit** | `livekit` | Phone + WebRTC + chat |
| **Pipecat Cloud** | `pipecat` | Phone + WebRTC; agent name in `credentials.config.pipecat_agent_name` |
| **Bland** | `bland` | Phone + chat; `provider.agent_id` = pathway_id |
| **Synthflow** | `synthflow` | Phone; auto-sync prompt supported |
| **Chirp** | `chirp` | WebSocket voice (raw PCM 16 kHz) |
| **KoreAI** | `koreai` | Chat/text only |
| **Genesys** | `genesys` | Chat/text only |
| **Trillet** | `trillet` | Phone |
| **Cisco** | `cisco` | Phone; no credentials needed |
| **SIP / self-hosted (phone)** | `self_hosted` | Observation-only; phone number required |
| **Self-hosted (WebSocket)** | `self_hosted` | Text-mode via `chat_agent_details` |

**Text-only channels** (set in `chat_agent_details.type`, not `provider.type`): `agentforce`, `sms`, `whatsapp`

---

## 2b. Collect credentials by provider

### VAPI
- **`credentials.api_key`** (Private): VAPI Dashboard → Organization Settings → API Keys → Private Key
- **`provider.agent_id`**: Assistants → Select → copy ID. For squads, use the squad ID (same field).
- **`credentials.config.public_key`** (WebRTC only): Organization Settings → Public Key
- **`credentials.config.trigger_url`** (optional)
- **Docs:** https://docs.vapi.ai/api-reference/assistants/get | https://docs.vapi.ai/api-reference/squads/get

### Retell
- **`credentials.api_key`**: Retell Dashboard → Settings → API Keys
- **`provider.agent_id`**: Retell voice agent ID — Agents → Select → ID in URL
- **`chat_agent_details.config.agent_id`** (optional): Separate Retell chat agent ID for text-mode test runs
- **`credentials.config.trigger_url`** (optional)
- **Docs:** https://docs.retellai.com/api-references/get-agent.md

### ElevenLabs
- **`credentials.api_key`**: Profile → API Keys
- **`provider.agent_id`**: Conversational AI → Select agent → ID in settings
- **`credentials.config.trigger_url`** (optional)
- **Docs:** https://elevenlabs.io/docs/api-reference/conversational-ai/get-agent

### LiveKit
- **`credentials.api_key`**: LiveKit Cloud Dashboard → Settings → Keys
- **`credentials.config.api_secret`** (required)
- **`credentials.config.url`** (required): wss:// format
- **`credentials.config.agent_name`** (optional)

### Pipecat Cloud
- **`credentials.api_key`**: pipecat.daily.co → Settings → API Keys
- **`credentials.config.pipecat_agent_name`**: Pipecat agent name from dashboard (required when `tracing_enabled` is false)
- **`credentials.config.webhook_url`** (optional): webhook URL for call events
- **`credentials.config.config`** (optional): additional agent configuration as JSON object
- **`credentials.config.room_properties`** (optional): Daily.co room properties as JSON object
- **`credentials.config.tracing_enabled`** (optional): boolean, default false
- **Docs:** https://docs.pipecat.ai

### Bland
- **`credentials.api_key`**: Bland Dashboard → API Keys
- **`provider.agent_id`**: Bland pathway_id — Pathways → Select → copy ID
- **`credentials.config.encrypted_key`** (optional): Twilio credential bundle
- **Docs:** https://docs.bland.ai

### Synthflow
- **`credentials.api_key`**: Synthflow API Key
- **`credentials.config.synthflow_base_url_override`** (optional)

### Chirp
- **`credentials.config.chirp_websocket_url`** (required): Raw PCM 16 kHz endpoint
- **`credentials.config.chirp_basic_auth_username`** (optional)
- **`credentials.config.chirp_basic_auth_password`** (optional, write-only)

### KoreAI
- **`credentials.api_key`**: KoreAI client secret
- **`credentials.config.client_id`** (required)
- **`credentials.config.bot_id`** (required)
- **`credentials.config.host`** (optional, default: https://bots.kore.ai)

### Genesys
- **`credentials.api_key`**: Genesys client secret
- **`credentials.config.client_id`** (required)
- **`credentials.config.region`** (required)

### Trillet
- **`credentials.api_key`**: Trillet API Key
- **`credentials.config.workspace_id`** (required)

### Cisco
- No credentials needed

### SIP / self-hosted (phone)
- **`telephony.phone_number`**: E.164 phone number
- **`telephony.sip_uri`** (optional): `sip:agent@yourdomain.com`
- **`telephony.sip_auth`** (optional): `{"username": "...", "password": "..."}`

### Self-hosted via WebSocket
- **`chat_agent_details.type`**: `"self_hosted"`
- **`chat_agent_details.config.url`** (required): `wss://your-server.com/agent`
- **`chat_agent_details.config.headers`** (optional)

### Agentforce (text/chat only)
Set in `chat_agent_details`, not `provider.type`:
```json
"chat_agent_details": {
  "type": "agentforce",
  "config": {
    "agent_id": "...",
    "client_id": "...",
    "client_secret": "...",
    "domain": "..."
  }
}
```

---

## 2c. Provider capabilities quick reference

| Feature | VAPI | Retell | ElevenLabs | LiveKit | Pipecat | Bland | Synthflow | Trillet | Cisco | Chirp | KoreAI | Genesys | Self-hosted |
|---------|------|--------|------------|---------|---------|-------|-----------|---------|-------|-------|--------|---------|-------------|
| Phone | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — | ✓ |
| WebRTC | ✓ | ✓ | — | ✓ | ✓ | — | — | — | — | — | — | — | — |
| WebSocket voice | — | — | — | — | — | — | — | — | — | ✓ | — | — | — |
| Chat/Text | ✓ | ✓ | ✓ | ✓ | — | ✓ | — | — | — | — | ✓ | ✓ | ✓ |
| Auto-import calls | ✓ | ✓ | ✓ | — | — | — | — | — | — | — | — | — | — |
| Auto-sync prompt | ✓ | ✓ | ✓ | — | — | — | ✓ | — | — | — | — | — | — |
| Auto-dial outbound | ✓ | ✓ | ✓ | ✓ | — | ✓ | — | — | — | — | — | — | — |
| Auto-fetch tools | ✓ | ✓ | ✓ | — | ✓ | — | — | — | — | — | — | — | — |
| Fetch main agent config | ✓ | ✓ | ✓ | — | — | ✓ | — | — | — | — | — | — | — |
| Squads / multi-agent | ✓ | ✓ | ✓ | — | ✓ | ✓ | — | — | — | — | — | — | — |

---

## Phase 2 Gate

**Do not proceed until you know the provider and have all required credentials noted.**

Announce: "Phase 2 complete." Then immediately begin [Phase 3 — Agent Basics & Connection Type](phase3-basics.md) without waiting for the user.

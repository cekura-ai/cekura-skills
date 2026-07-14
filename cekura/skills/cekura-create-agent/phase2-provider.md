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
| **WebSocket voice (raw-PCM)** | `custom` | Cekura dials your `wss://` endpoint (16 kHz raw PCM); set `telephony.websocket_url` (+ optional `telephony.websocket_auth`). Runs via the CHIRP protocol. |
| **KoreAI** | `koreai` | Chat/text only |
| **Genesys** | `genesys` | Chat/text only |
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

> **Fast path:** VAPI supports `configure_from_provider` — just collect `api_key` + `agent_id`. Everything else (name, description, phone number, tools, knowledge base, dynamic variables) is auto-imported. See Phase 5 for the import flow.

### Retell
- **`credentials.api_key`**: Retell Dashboard → Settings → API Keys
- **`provider.agent_id`**: Retell voice agent ID — Agents → Select → ID in URL
- **`chat_agent_details.config.agent_id`** (optional): Separate Retell chat agent ID for text-mode test runs
- **`credentials.config.trigger_url`** (optional)
- **Docs:** https://docs.retellai.com/api-references/get-agent.md

> **Fast path:** Retell supports `configure_from_provider` — just collect `api_key` + `agent_id`. Everything else (name, description, phone number, tools, knowledge base, dynamic variables) is auto-imported. See Phase 5 for the import flow.

### ElevenLabs
- **`credentials.api_key`**: Profile → API Keys
- **`provider.agent_id`**: Conversational AI → Select agent → ID in settings
- **`credentials.config.trigger_url`** (optional)
- **Docs:** https://elevenlabs.io/docs/api-reference/conversational-ai/get-agent

> **Fast path:** ElevenLabs supports `configure_from_provider` — just collect `api_key` + `agent_id`. Everything else (name, description, phone number, tools, knowledge base, dynamic variables) is auto-imported. See Phase 5 for the import flow.

### LiveKit
Ask for all four credentials by default. Whether each is strictly required depends on the connection mode(s) chosen in Phase 3 and whether the Cekura SDK is in scope.

- **`credentials.api_key`**: LiveKit Cloud Dashboard → Settings → Keys
- **`credentials.config.api_secret`**
- **`credentials.config.url`** (wss:// format)
- **`credentials.config.agent_name`**

**When each is required:**

| Setup | api_key | api_secret | url | agent_name |
|-------|---------|------------|-----|------------|
| Testing — Telephony only | – | – | – | – |
| Testing — WebRTC Automated or Chat | R | R | R | R |
| Testing — WebRTC Manual | – | – | – | – |
| Observability with Cekura SDK (audio egress) | R | R | R | optional |

If only telephony / WebRTC Manual is in scope, the LiveKit Cloud credentials are not strictly needed — collect them only if the user has them handy.

**Session config (WebRTC Automated only):** `credentials.config.config` is a JSON object Cekura injects into `ctx.room.metadata` when it creates the room. If the agent reads room metadata (e.g. `empty_timeout`, `max_participants`, agent-specific knobs), scan the codebase to determine the expected shape and populate this field. Confirm values with the user. Cekura also injects `scenario_id`, `run_id`, and `test_profile_data` into `ctx.job.metadata` during dispatch — no configuration required for those.

**Docs:** https://docs.livekit.io

### Pipecat Cloud
Ask for all credentials by default. Required fields depend on the connection mode(s) chosen in Phase 3.

- **`credentials.api_key`**: pipecat.daily.co → Settings → API Keys
- **`credentials.config.pipecat_agent_name`**: Pipecat agent name from dashboard
- **`credentials.config.webhook_url`** (optional): webhook URL for call events
- **`credentials.config.config`** (optional): additional agent configuration as JSON object — used by Cekura when starting the session; accessible inside the agent
- **`credentials.config.room_properties`** (optional): Daily.co room properties as JSON object — applied when Cekura creates the WebRTC session
- **`credentials.config.tracing_enabled`** (set by Phase 6 when the SDK is wired and testing is in scope; otherwise leave false)

**When each is required:**

| Setup | api_key | pipecat_agent_name |
|-------|---------|--------------------|
| Testing — Telephony only | – | – |
| Testing — WebRTC Automated | R | R |
| Testing — WebRTC Manual | – | – |
| Observability with Cekura SDK | – | – |

Pipecat observability via the SDK does not need provider creds — the SDK handles audio recording in-process via its own audio frame processor.

**Session config (WebRTC Automated only):** scan the agent codebase for keys/options it expects at session start (Daily.co room properties, Pipecat agent runtime config). Populate `credentials.config.config` and `credentials.config.room_properties` accordingly. Confirm with the user.

**Docs:** https://docs.pipecat.ai

### Bland
- **`credentials.api_key`**: Bland Dashboard → API Keys
- **`provider.agent_id`**: Bland pathway_id — Pathways → Select → copy ID
- **`credentials.config.encrypted_key`** (optional): Twilio credential bundle
- **Docs:** https://docs.bland.ai

### Synthflow
- **`credentials.api_key`**: Synthflow API Key
- **`provider.agent_id`**: Synthflow Dashboard → Select agent → copy ID
- **`credentials.config.synthflow_base_url_override`** (optional)

> **Fast path:** Synthflow supports `configure_from_provider` — just collect `api_key` + `agent_id`. Everything else (name, description, phone number, tools, knowledge base, dynamic variables) is auto-imported. See Phase 5 for the import flow.

### WebSocket voice (raw-PCM)
Use `provider.type = "custom"` and put the endpoint under `telephony`:
- **`telephony.websocket_url`** (required): Raw PCM 16 kHz `wss://` endpoint Cekura dials
- **`telephony.websocket_auth`** (optional): HTTP Basic Auth `{username, password}` for the websocket upgrade
- **`telephony.inbound`** (optional): `true` if the agent receives inbound calls

Runs over the CHIRP protocol (see `run_scenarios_chirp`).

### KoreAI
- **`credentials.api_key`**: KoreAI client secret
- **`credentials.config.client_id`** (required)
- **`credentials.config.bot_id`** (required)
- **`credentials.config.host`** (optional, default: https://bots.kore.ai)

### Genesys
- **`credentials.api_key`**: Genesys client secret
- **`credentials.config.client_id`** (required)
- **`credentials.config.region`** (required)

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

| Feature | VAPI | Retell | ElevenLabs | LiveKit | Pipecat | Bland | Synthflow | Cisco | KoreAI | Genesys | Self-hosted |
|---------|------|--------|------------|---------|---------|-------|-----------|-------|--------|---------|-------------|
| Phone | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | ✓ |
| WebRTC | ✓ | ✓ | — | ✓ | ✓ | — | — | — | — | — | — |
| WebSocket voice | — | — | — | — | — | — | — | — | — | — | ✓ |
| Chat/Text | ✓ | ✓ | ✓ | ✓ | — | ✓ | — | — | ✓ | ✓ | ✓ |
| **Auto-import agent** | ✓ | ✓ | ✓ | — | — | — | ✓ | — | — | — | — |
| Auto-import calls | ✓ | ✓ | ✓ | — | — | — | ✓ | — | — | — | — |
| Auto-sync prompt | ✓ | ✓ | ✓ | — | — | — | ✓ | — | — | — | — |
| Auto-dial outbound | ✓ | ✓ | ✓ | ✓ | — | ✓ | — | — | — | — | — |
| Auto-fetch tools | ✓ | ✓ | ✓ | — | ✓ | — | — | — | — | — | — |
| Squads / multi-agent | ✓ | ✓ | ✓ | — | ✓ | ✓ | — | — | — | — | — |

---

## Phase 2 Gate

**Do not proceed until you know the provider and have all required credentials noted.**

Announce: "Phase 2 complete." Then immediately begin [Phase 3 — Agent Basics & Connection Type](phase3-basics.md) without waiting for the user.

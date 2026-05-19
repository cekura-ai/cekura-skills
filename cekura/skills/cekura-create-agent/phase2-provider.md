# Phase 2 — Provider Selection

Identify the provider upfront — it determines what credentials to collect, what connection types are available, and whether auto-fetch works for mock tools.

---

## 2a. Which provider?

Ask: "What provider does your agent run on?"

| Provider | `provider.type` | Notes |
|----------|----------------|-------|
| **VAPI** | `vapi` | Most common; phone + WebRTC + chat |
| **Retell** | `retell` | Auto-sync prompt; requires `chat_assistant_id` for voice (not `assistant_id`) |
| **ElevenLabs** | `elevenlabs` | Phone + WebSocket + chat |
| **LiveKit** | `livekit` | WebRTC only; no phone number needed |
| **Pipecat** | `pipecat` | WebRTC; agent name goes in `phone_number` field |
| **Bland** | `bland` | Requires `pathway_id` (via `chat_assistant_id`) |
| **SIP / self-hosted (phone)** | `self_hosted` | Bring your own SIP or observation-only phone agent |
| **Self-hosted (WebSocket)** | `self_hosted` | Text-mode testing via `provider.credentials.config.url` |
| **Custom webhook** | (none needed) | Client pushes calls to `/observability/v1/observe/` — no provider block |

---

## 2b. Collect credentials for the chosen provider

### VAPI
- **API Key** (Private): VAPI Dashboard → Organization Settings → API Keys → Private Key
- **Agent ID**: Assistants → Select → copy ID from URL
- **Public Key** (for WebRTC only): Organization Settings → Public Key

### Retell
- **API Key**: Retell Dashboard → Settings → API Keys
- **Agent ID**: Agents → Select → ID in URL  
  ⚠️ Retell uses `chat_assistant_id` / `provider.agent_id` for voice calls too, despite the field name.

### ElevenLabs
- **API Key**: Profile → API Keys
- **Agent ID**: Conversational AI → Select agent → ID in settings

### LiveKit
- **API Key + Secret**: LiveKit Cloud Dashboard → Settings → Keys
- **URL**: your LiveKit server URL (wss:// format)

### Pipecat
- **API Key**: pipecat.daily.co → Settings → API Keys
- **Agent Name**: used as the `phone_number` field (not an actual phone number)

### Bland
- **API Key**: Bland Dashboard → API Keys
- **Pathway ID**: Bland Dashboard → Pathways → Select → copy ID  
  (Bland calls this `pathway_id` internally; maps to `provider.agent_id` / `chat_assistant_id`)
- **Encrypted Twilio Key** (optional): `bland_data.encrypted_key`

### SIP / self-hosted
- **SIP URI**: `sip:agent@yourdomain.com` or `sip:192.168.1.100:5060`
- **SIP auth** (optional): `{"username": "...", "password": "..."}`

### Self-hosted via WebSocket
- **WebSocket URL**: `wss://your-server.com/agent`
- **Headers** (optional): e.g. `{"Authorization": "Bearer token"}`

---

## 2c. Provider capabilities quick reference

| Feature | VAPI | Retell | ElevenLabs | LiveKit | Pipecat | Bland | SIP | Custom |
|---------|------|--------|------------|---------|---------|-------|-----|--------|
| Phone | ✓ | ✓ | ✓ | — | — | ✓ | ✓ | — |
| WebRTC | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — |
| Chat/Text | ✓ | ✓ | ✓ | — | — | — | — | ✓ |
| Auto-fetch calls | ✓ | ✓ | — | — | — | — | — | — |
| Auto-fetch tools | ✓ | ✓ | ✓ | — | ✓ | — | — | — |
| Auto-sync prompt | — | ✓ | — | — | — | — | — | — |

---

## Phase 2 Gate

**Do not proceed until you know the provider and have collected all required credentials.**

Move to [Phase 3 — Agent Basics](phase3-basics.md).

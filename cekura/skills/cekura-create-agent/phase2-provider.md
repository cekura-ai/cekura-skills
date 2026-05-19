# Phase 2 — Provider Selection

Identify the provider upfront — it determines what credentials to collect, what connection types are available, and whether auto-fetch works for mock tools.

---

## 2a. Which provider?

Ask: "What provider does your agent run on?"

| Provider | `provider.type` | Notes |
|----------|----------------|-------|
| **VAPI** | `vapi` | Phone + WebRTC + chat |
| **Retell** | `retell` | Auto-sync prompt; separate `agent_id` (voice) and `chat_agent_id` (text-mode) |
| **ElevenLabs** | `elevenlabs` | Phone + WebSocket + chat |
| **LiveKit** | `livekit` | WebRTC only; no phone number needed |
| **Bland** | `bland` | `provider.agent_id` = Bland pathway_id |
| **Agentforce** | `agentforce` | Salesforce Agentforce |
| **Trillet** | `trillet` | Requires `credentials.config.workspace_id` |
| **SIP / self-hosted (phone)** | `self_hosted` | Observation-only; phone number required |
| **Self-hosted (WebSocket)** | `self_hosted` | Text-mode via `credentials.config.url` |
| **Custom webhook** | (none needed) | Client pushes calls to `/observability/v1/observe/` |

---

## 2b. Collect credentials by provider

### VAPI
- **`credentials.api_key`** (Private API Key): VAPI Dashboard → Organization Settings → API Keys → Private Key
- **`provider.agent_id`**: Assistants → Select → copy ID from URL
- **`credentials.config.public_key`** (WebRTC only): Organization Settings → Public Key
- **`credentials.config.trigger_url`** (optional): VAPI webhook trigger URL

### Retell
- **`credentials.api_key`**: Retell Dashboard → Settings → API Keys
- **`provider.agent_id`**: Retell agent for **voice/phone** calls — Agents → Select → ID in URL
- **`provider.chat_agent_id`** (optional): Separate Retell agent for **text-mode** test runs. Only needed when your chat agent differs from your voice agent. Omit if the same agent handles both.
- **`credentials.config.trigger_url`** (optional): Retell webhook trigger URL

### ElevenLabs
- **`credentials.api_key`**: Profile → API Keys
- **`provider.agent_id`**: Conversational AI → Select agent → ID in settings
- **`credentials.config.trigger_url`** (optional): ElevenLabs webhook trigger URL

### LiveKit
- **`credentials.api_key`**: LiveKit Cloud Dashboard → Settings → Keys
- **`credentials.config.api_secret`** (required): LiveKit API Secret, same location
- **`credentials.config.url`** (required): your LiveKit server URL (wss:// format)
- **`credentials.config.tracing_enabled`** (optional): boolean

### Bland
- **`credentials.api_key`**: Bland Dashboard → API Keys
- **`provider.agent_id`**: Bland pathway_id — Pathways → Select → copy ID
- **`credentials.config.encrypted_key`** (optional): Twilio credential bundle

### Agentforce
- **`credentials.api_key`**: Salesforce client_secret
- **`credentials.config.client_id`** (required): Salesforce connected app client ID
- **`credentials.config.domain`** (required): your Salesforce domain
- **`credentials.config.agent_id`** (required): Agentforce agent ID

### Trillet
- **`credentials.api_key`**: Trillet API Key
- **`credentials.config.workspace_id`** (required): Trillet workspace ID

### SIP / self-hosted (phone)
- **`phone_number`** (Phase 3): the SIP or PSTN number
- **`sip_uri`** (optional): `sip:agent@yourdomain.com` or `sip:192.168.1.100:5060`
- **`sip_auth`** (optional): `{"username": "...", "password": "..."}`

### Self-hosted via WebSocket
- **`credentials.config.url`** (required): `wss://your-server.com/agent`
- **`credentials.config.headers`** (optional): e.g. `{"Authorization": "Bearer token"}`

---

## 2c. Provider capabilities quick reference

| Feature | VAPI | Retell | ElevenLabs | LiveKit | Bland | SIP | Custom |
|---------|------|--------|------------|---------|-------|-----|--------|
| Phone | ✓ | ✓ | ✓ | — | ✓ | ✓ | — |
| WebRTC | ✓ | ✓ | ✓ | ✓ | — | — | — |
| Chat/Text | ✓ | ✓ | ✓ | — | — | — | ✓ |
| Auto-fetch calls | ✓ | ✓ | — | — | — | — | — |
| Auto-fetch tools | ✓ | ✓ | ✓ | — | — | — | — |
| Auto-sync prompt | — | ✓ | — | — | — | — | — |

---

## Phase 2 Gate

**Do not proceed until you know the provider and have all required credentials noted.**

Move to [Phase 3 — Agent Basics](phase3-basics.md).

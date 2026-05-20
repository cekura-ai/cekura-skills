# Phase 2 — Provider Selection

Identify the provider upfront — it determines what credentials to collect, what connection types are available, and whether auto-fetch works for mock tools.

---

## 2a. Which provider?

Ask: "What provider does your agent run on?"

| Provider | `provider.type` | Notes |
|----------|----------------|-------|
| **VAPI** | `vapi` | Assistants and squads (multi-agent); phone + WebRTC + chat |
| **Retell** | `retell` | Auto-sync prompt; separate voice `agent_id` and chat `chat_agent_details` |
| **ElevenLabs** | `elevenlabs` | Phone + WebSocket + chat |
| **LiveKit** | `livekit` | WebRTC only; no phone number needed |
| **Pipecat Cloud** | `pipecat` | WebRTC; agent name goes in `credentials.config.pipecat_agent_name` |
| **Bland** | `bland` | `provider.agent_id` = Bland pathway_id |
| **Trillet** | `trillet` | Requires `credentials.config.workspace_id` |
| **SIP / self-hosted (phone)** | `self_hosted` | Observation-only; phone number required |
| **Self-hosted (WebSocket)** | `self_hosted` | Text-mode via `chat_agent_details` |
| **Custom webhook** | `self_hosted` | Client pushes calls to `/observability/v1/observe/` |

---

## 2b. Collect credentials by provider

### VAPI
- **`credentials.api_key`** (Private): VAPI Dashboard → Organization Settings → API Keys → Private Key
- **`provider.agent_id`**: Assistants → Select → copy ID from URL. **For squads**, use the squad ID (same field).
- **`credentials.config.public_key`** (WebRTC only): Organization Settings → Public Key
- **`credentials.config.trigger_url`** (optional): VAPI webhook trigger URL
- **Docs:** https://docs.vapi.ai/api-reference/assistants/get | https://docs.vapi.ai/api-reference/squads/get

### Retell
- **`credentials.api_key`**: Retell Dashboard → Settings → API Keys
- **`provider.agent_id`**: Retell voice agent ID — Agents → Select → ID in URL
- **`chat_agent_details.config.agent_id`** (optional): Separate Retell chat agent for text-mode test runs. Only needed when chat agent differs from voice agent.
- **`credentials.config.trigger_url`** (optional): Retell webhook trigger URL
- **Docs:** https://docs.retellai.com/api-references/get-agent.md | https://docs.retellai.com/api-references/get-chat-agent.md

### ElevenLabs
- **`credentials.api_key`**: Profile → API Keys
- **`provider.agent_id`**: Conversational AI → Select agent → ID in settings
- **`credentials.config.trigger_url`** (optional): webhook trigger URL
- **Docs:** https://elevenlabs.io/docs/api-reference/conversational-ai/get-agent

### LiveKit
- **`credentials.api_key`**: LiveKit Cloud Dashboard → Settings → Keys
- **`credentials.config.api_secret`** (required): same location
- **`credentials.config.url`** (required): your LiveKit server URL (`wss://` format)
- **`credentials.config.tracing_enabled`** (optional): boolean

### Pipecat Cloud
- **`credentials.api_key`**: pipecat.daily.co → Settings → API Keys
- **`credentials.config.pipecat_agent_name`** (required): your Pipecat agent name, e.g. `"my-support-agent"`. This is the name you gave the agent when deploying to Pipecat Cloud.
- **`credentials.config.webhook_url`** (optional): webhook URL for call events
- **`credentials.config.config`** (optional): JSON agent configuration
- **`credentials.config.room_properties`** (optional): Daily.co room properties JSON
- No `agent_id` or `telephony.phone_number` needed
- **Docs:** https://docs.pipecat.ai

### Bland
- **`credentials.api_key`**: Bland Dashboard → API Keys
- **`provider.agent_id`**: Bland pathway_id — Pathways → Select → copy ID
- **`credentials.config.encrypted_key`** (optional): Twilio credential bundle
- **Docs:** https://docs.bland.ai/api-v1/get/agents-id

### Agentforce (text/chat only)
Agentforce is a **text-mode channel only** — set it in `chat_agent_details`, not as `provider.type`:
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
Set `provider.type` to `self_hosted` for the voice side (or omit provider if text-only).

### Trillet
- **`credentials.api_key`**: Trillet API Key
- **`credentials.config.workspace_id`** (required)

### SIP / self-hosted (phone)
- **`phone_number`** (Phase 3): E.164 phone number
- **`sip_uri`** (optional): `sip:agent@yourdomain.com` or `sip:192.168.1.100:5060`
- **`sip_auth`** (optional): `{"username": "...", "password": "..."}`

### Self-hosted via WebSocket
- **`chat_agent_details.type`**: `"self_hosted"`
- **`chat_agent_details.config.url`** (required): `wss://your-server.com/agent`
- **`chat_agent_details.config.headers`** (optional): e.g. `{"Authorization": "Bearer token"}`

---

## 2c. Provider capabilities quick reference

| Feature | VAPI | Retell | ElevenLabs | LiveKit | Pipecat | Bland | SIP | Custom |
|---------|------|--------|------------|---------|---------|-------|-----|--------|
| Phone | ✓ | ✓ | ✓ | — | — | ✓ | ✓ | — |
| WebRTC | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — |
| Chat/Text | ✓ | ✓ | ✓ | — | — | — | — | ✓ |
| Auto-fetch calls | ✓ | ✓ | ✓ | — | — | — | — | — |
| Auto-fetch tools | ✓ | ✓ | ✓ | — | ✓ | — | — | — |
| Auto-sync prompt | ✓ | ✓ | ✓ | — | — | — | — | — |
| Fetch agent config | ✓ | ✓ | ✓ | — | — | ✓ | — | — |
| Squads / multi-agent | ✓ | — | — | — | — | — | — | — |

**Auto-sync/import/dial** are set inside the `provider` block (`provider.auto_sync_prompt`, `provider.auto_import_calls`, `provider.auto_dial_outbound`).

`auto_sync_prompt` is supported for: VAPI, Retell, ElevenLabs, **Synthflow** (not shown in table above as Synthflow is a less common provider).

---

## Phase 2 Gate

**Do not proceed until you know the provider and have all required credentials noted.**

Move to [Phase 3 — Agent Basics](phase3-basics.md).

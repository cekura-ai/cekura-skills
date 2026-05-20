# Phase 2 — Provider Selection

Identify the provider upfront — it determines what credentials to collect, what connection types are available, and whether auto-fetch works for mock tools.

---

## 2a. Which provider?

Ask: "What provider does your agent run on?"

| Provider | `assistant_provider` | Notes |
|----------|---------------------|-------|
| **VAPI** | `vapi` | Assistants and squads (multi-agent); phone + WebRTC + chat |
| **Retell** | `retell` | Auto-sync prompt; uses `chat_assistant_id` for both voice and text |
| **ElevenLabs** | `elevenlabs` | Phone + WebSocket + chat |
| **LiveKit** | `livekit` | WebRTC only; no phone number needed |
| **Pipecat Cloud** | `pipecat` | WebRTC; `contact_number` = agent name (not phone) |
| **Bland** | `bland` | `chat_assistant_id` = Bland pathway_id |
| **Agentforce** | `agentforce` | Salesforce Agentforce |
| **Trillet** | `trillet` | Requires `trillet_data.workspace_id` |
| **SIP / self-hosted (phone)** | `self_hosted` | Observation-only; phone number required |
| **Self-hosted (WebSocket)** | `self_hosted` | Text-mode via `websocket_url` |
| **Custom webhook** | `self_hosted` | Client pushes calls to `/observability/v1/observe/` |

---

## 2b. Collect credentials by provider

### VAPI
- **`vapi_api_key`** (Private): VAPI Dashboard → Organization Settings → API Keys → Private Key
- **`assistant_id`**: Assistants → Select → copy ID from URL. **For squads**, use the squad ID (same field).
- **`vapi_data.public_key`** (WebRTC only): Organization Settings → Public Key
- **`vapi_data.trigger_url`** (optional): VAPI webhook trigger URL
- **Docs:** https://docs.vapi.ai/api-reference/assistants/get | https://docs.vapi.ai/api-reference/squads/get

### Retell
- **`retell_api_key`**: Retell Dashboard → Settings → API Keys
- **`chat_assistant_id`**: Retell agent ID — Agents → Select → ID in URL. ⚠️ This field is used for **both voice and text-mode** in Retell (despite the `chat_` prefix).
- If text-mode agent differs from voice: set a separate `chat_assistant_id` for text via PATCH after creation.
- **`retell_data.trigger_url`** (optional): Retell webhook trigger URL
- **Docs:** https://docs.retellai.com/api-references/get-agent.md | https://docs.retellai.com/api-references/get-chat-agent.md

### ElevenLabs
- **`elevenlabs_api_key`**: Profile → API Keys
- **`assistant_id`**: Conversational AI → Select agent → ID in settings
- **`elevenlabs_data.trigger_url`** (optional): webhook trigger URL
- **Docs:** https://elevenlabs.io/docs/api-reference/conversational-ai/get-agent

### LiveKit
- **`livekit_api_key`**: LiveKit Cloud Dashboard → Settings → Keys
- **`livekit_data.api_secret`** (required): same location as API key
- **`livekit_data.url`** (required): your LiveKit server URL (`wss://` format)
- **`livekit_data.tracing_enabled`** (optional): boolean

### Pipecat Cloud
- **`pipecat_api_key`**: pipecat.daily.co → Settings → API Keys
- **`contact_number`**: your **Pipecat agent name** (not a real phone number), e.g. `"my-support-agent"`. This is the name you gave the agent when deploying to Pipecat Cloud.
- **`pipecat_data.webhook_url`** (optional): webhook URL for call events
- No `assistant_id` needed — agent is identified by the name in `contact_number`
- **Docs:** https://docs.pipecat.ai

### Bland
- **`bland_api_key`**: Bland Dashboard → API Keys
- **`chat_assistant_id`**: Bland pathway_id — Pathways → Select → copy ID
- **`bland_data.encrypted_key`** (optional): Twilio credential bundle
- **Docs:** https://docs.bland.ai/api-v1/get/agents-id

### Agentforce
- **`agentforce_client_secret`**: Salesforce client secret
- **`agentforce_data.client_id`** (required): Salesforce connected app client ID
- **`agentforce_data.domain`** (required): your Salesforce domain
- **`agentforce_data.agent_id`** (required): Agentforce agent ID

### Trillet
- **`trillet_api_key`**: Trillet API Key
- **`trillet_data.workspace_id`** (required): Trillet workspace ID

### SIP / self-hosted (phone)
- **`contact_number`** (Phase 3): E.164 phone number
- **`sip_endpoint`** (optional): `sip:agent@yourdomain.com` or `sip:192.168.1.100:5060`
- **`sip_auth`** (optional): `{"username": "...", "password": "..."}`

### Self-hosted via WebSocket
- **`websocket_url`** (required): `wss://your-server.com/agent`
- **`websocket_headers`** (optional): e.g. `{"Authorization": "Bearer token"}`

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

**Auto-sync prompt** (VAPI/Retell/ElevenLabs): enabled by `auto_sync_prompt_enabled: true`. VAPI fetches system message (tries `/assistant/{id}`, falls back to `/squad/{id}`). Retell fetches `general_prompt` or full flow JSON. ElevenLabs reads `conversation_config.agent.prompt.prompt`.

**Fetch agent config** (Phase 3): use the provider API directly to pre-populate name, description, language. Phone number is NOT in any provider's agent object — always collect manually.

---

## Phase 2 Gate

**Do not proceed until you know the provider and have all required credentials noted.**

Move to [Phase 3 — Agent Basics](phase3-basics.md).

# Phase 3 — Agent Basics & Connection Type

Collect the fields needed to identify the agent and determine how Cekura will connect to it. Connection type is part of basics — the phone number itself is a connection choice.

---

## 3a. Fields to collect

**Truly required** (API will reject without these):

| Field | API field | Notes |
|-------|-----------|-------|
| **Agent name** | `name` | Descriptive: "Customer Support Bot", "Scheduling Assistant" (max 255 chars) |
| **Description** | `description` | Full system prompt — see Phase 4. Placeholder OK if using auto-sync. |
| **Project** | `project` | Project ID from Phase 1 |

**Optional but usually needed:**

| Field | Location | Notes |
|-------|----------|-------|
| **Language** | `language` | BCP-47 locale, default `en`. Codes: `af ar bn bg zh cs da nl en et fi fr de el gu hi he hu id it ja kn ko ms ml mr multi no pl pa pt ro ru sk es sv th tr tl ta te uk vi` |
| **Phone number** | `telephony.phone_number` | E.164 format, e.g. `+14155551234`. Determines connection type — see 3c. |
| **Inbound/Outbound** | `telephony.inbound` | `true` = receives calls, default `false`. |

---

## 3b. What to collect per provider

| Provider | Phone number? | Description source | Notes |
|----------|--------------|-------------------|-------|
| **VAPI** | Yes | Auto-fetch or paste | `agent_id` = assistant or squad ID |
| **Retell** | Yes | Auto-fetch or paste | Separate `agent_id` (voice) and `chat_agent_id` (text) |
| **ElevenLabs** | Yes | Auto-fetch or paste | |
| **Synthflow** | Yes | Auto-fetch or paste | |
| **Bland** | Yes | Fetch prompt, ask user for name | `agent_id` = pathway_id; name not returned by API |
| **LiveKit** | No | Ask user | WebRTC only |
| **Pipecat** | No | Ask user | Agent identified by `credentials.config.pipecat_agent_name` |
| **Chirp** | No | Ask user | Connects via `chirp_websocket_url` |
| **KoreAI** | No | Ask user | Text/chat only |
| **Genesys** | No | Ask user | Text/chat only |
| **Trillet** | Yes | Ask user | |
| **Cisco** | Yes | Ask user | Pre-configured integration |
| **Self-hosted (phone/SIP)** | Yes | Ask user | |
| **Self-hosted (WebSocket)** | No | Ask user | Text-mode only |

---

## 3c. Connection type

The connection type is determined by what you configure — ask the user which they want if not obvious from the provider.

| Mode | When | What to set |
|------|------|-------------|
| **Phone (PSTN)** | Agent has a phone number | `telephony.phone_number` + `telephony.inbound` |
| **WebRTC** | Lower latency, no telephony costs | Provider-specific — see below |
| **WebSocket endpoint** | Agent exposes a `wss://` URL that Cekura connects to | `provider.chat_agent_details.type: self_hosted, config.url: wss://...` — see 3d |
| **Chat / Text (provider)** | Provider has a separate chat agent | `provider.chat_agent_details` with provider type — see 3d |
| **SIP** | Custom SIP endpoint | `telephony.sip_uri` + optional `telephony.sip_auth` |

A single agent can support multiple connection modes (e.g. phone + WebSocket). Ask the user which they want to use.

> **WebSocket endpoint:** If the user's agent (or simulation runner) exposes a `wss://` URL, Cekura connects to it as a client. Ask for the WebSocket URL and any auth headers needed.

### WebRTC per provider

| Provider | Extra requirement |
|----------|------------------|
| VAPI | `credentials.config.public_key` (VAPI Dashboard → Organization Settings → Public Key) |
| Retell | No extra fields |
| ElevenLabs | No extra fields |
| LiveKit | Cekura manages room creation automatically |
| Pipecat | Cekura dispatches the job |

---

## 3d. WebSocket / chat setup

Set `provider.chat_agent_details` to configure a WebSocket or text-based connection. Apply via PATCH after creating the agent in Phase 5, or include in the create payload.

| Connection | `chat_agent_details` |
|------------|---------------------|
| **Self-hosted WebSocket** (agent exposes `wss://`) | `{"type": "self_hosted", "config": {"url": "wss://your-server/agent", "headers": {"Authorization": "Bearer ..."}}}` |
| Retell chat agent | `{"type": "retell", "config": {"agent_id": "<chat agent ID>"}}` |
| VAPI chat assistant | `{"type": "vapi", "config": {"agent_id": "<chat assistant ID>"}}` |
| ElevenLabs | `{"type": "elevenlabs", "config": {"agent_id": "<agent ID>"}}` |

> **Retell:** In Retell Dashboard, use "Copy as chat agent" to create a separate text-mode agent, then use that agent's ID here.

---

## 3e. Auto-fetch from provider API

For providers with an API, fetch name, description, and language directly:

### VAPI
```bash
curl -s https://api.vapi.ai/assistant/{assistant_id} \
  -H "Authorization: Bearer {vapi_api_key}" | jq '{name, description: (.model.messages[] | select(.role=="system") | .content), language: .transcriber.language}'
# For squads: curl -s https://api.vapi.ai/squad/{squad_id} ...
```
**Docs:** https://docs.vapi.ai/api-reference/assistants/get | https://docs.vapi.ai/api-reference/squads/get

### Retell
```bash
curl -s https://api.retellai.com/get-agent/{agent_id} \
  -H "Authorization: Bearer {retell_api_key}" | jq '{agent_name, language, response_engine}'
# retell-llm → GET /get-retell-llm/{llm_id} → .general_prompt
# conversation-flow → GET /get-conversation-flow/{flow_id} → full JSON
```
**Docs:** https://docs.retellai.com/api-references/get-agent.md

### ElevenLabs
```bash
curl -s https://api.elevenlabs.io/v1/convai/agents/{agent_id} \
  -H "xi-api-key: {elevenlabs_api_key}" | jq '{name, description: .conversation_config.agent.prompt.prompt}'
```
**Docs:** https://elevenlabs.io/docs/api-reference/conversational-ai/get-agent

### Bland
```bash
curl -s https://api.bland.ai/agents/{pathway_id} \
  -H "authorization: {bland_api_key}" | jq '{prompt, language, voice}'
```
Returns `prompt` (description) but NOT `name` — ask the user for a display name.

---

## 3f. Auto-sync description (VAPI / Retell / ElevenLabs / Synthflow)

Enable `provider.auto_sync_prompt: true` at create time (Phase 5). Cekura fetches the description from the provider within ~30 seconds. Pass a placeholder for the required `description` field.

See [Phase 4](phase4-description.md) for what makes a good description.

---

## 3g. Outbound agents

If `telephony.inbound: false`, also collect:
- Auto-dial? (`provider.auto_dial_outbound: true` — VAPI, Retell, ElevenLabs, LiveKit, Bland)
- Outbound numbers: `telephony.outbound_numbers: ["+1..."]`

---

## 3h. Agent speaks first?

Optional. `agent_speaks_first: true / false / null` (null = auto-detect).

---

## Phase 3 Gate

**Do not proceed until you have: name, language, connection type confirmed, and phone number (if using phone/SIP). Description can be a placeholder if using auto-sync.**

Collecting description manually → [Phase 4 — Agent Description](phase4-description.md).
Using auto-sync → skip to [Phase 5 — Create the Agent](phase5-create.md).

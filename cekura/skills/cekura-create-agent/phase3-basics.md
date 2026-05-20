# Phase 3 — Agent Basics

Collect the fields needed to create and identify the agent. What you need depends on the provider chosen in Phase 2.

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
| **Phone number** | `telephony.phone_number` | E.164 format, e.g. `+14155551234`. Provider notes in 3c. |
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
| **LiveKit** | No | Ask user | WebRTC only; no phone number |
| **Pipecat** | No | Ask user | Agent identified by `credentials.config.pipecat_agent_name`; no phone |
| **Chirp** | No | Ask user | Connects via `chirp_websocket_url`; no phone |
| **KoreAI** | No | Ask user | Text/chat only |
| **Genesys** | No | Ask user | Text/chat only |
| **Trillet** | Yes | Ask user | No provider API to fetch description |
| **Cisco** | Yes | Ask user | Pre-configured integration; contact Cekura support |
| **Self-hosted (phone/SIP)** | Yes | Ask user | No provider API to fetch from |
| **Self-hosted (WebSocket)** | No | Ask user | Text-mode; no phone |

---

## 3c. Auto-fetch from provider API

For providers with an API, fetch name, description, and language directly rather than asking the user:

### VAPI — assistants and squads
```bash
# Fetch assistant
curl -s https://api.vapi.ai/assistant/{assistant_id} \
  -H "Authorization: Bearer {vapi_api_key}" | jq '{name, description: (.model.messages[] | select(.role=="system") | .content), language: .transcriber.language}'

# For squad agents
curl -s https://api.vapi.ai/squad/{squad_id} \
  -H "Authorization: Bearer {vapi_api_key}" | jq '{name}'
```
**Docs:** https://docs.vapi.ai/api-reference/assistants/get | https://docs.vapi.ai/api-reference/squads/get

### Retell
```bash
curl -s https://api.retellai.com/get-agent/{agent_id} \
  -H "Authorization: Bearer {retell_api_key}" | jq '{agent_name, language, voice_id, response_engine}'
# Fetch prompt based on response_engine.type:
# retell-llm → GET /get-retell-llm/{llm_id} → .general_prompt
# conversation-flow → GET /get-conversation-flow/{flow_id} → full JSON
```
**Docs:** https://docs.retellai.com/api-references/get-agent.md

### ElevenLabs
```bash
curl -s https://api.elevenlabs.io/v1/convai/agents/{agent_id} \
  -H "xi-api-key: {elevenlabs_api_key}" | jq '{name, description: .conversation_config.agent.prompt.prompt, language: .conversation_config.agent.language}'
```
**Docs:** https://elevenlabs.io/docs/api-reference/conversational-ai/get-agent

### Bland
```bash
curl -s https://api.bland.ai/agents/{pathway_id} \
  -H "authorization: {bland_api_key}" | jq '{prompt, language, voice}'
```
Returns `prompt` (description), `language`, `voice` — but NOT `name`. Ask the user for a display name.
**Docs:** https://docs.bland.ai/api-v1/get/agents-id

---

## 3d. Auto-sync description (VAPI / Retell / ElevenLabs / Synthflow)

Instead of pasting the prompt, enable `provider.auto_sync_prompt: true` at create time (Phase 5). Cekura fetches the description from the provider within ~30 seconds. Pass a placeholder for the required `description` field.

The description drives scenario generation — the more complete it is, the better the scenarios. See [Phase 4](phase4-description.md).

---

## 3e. Outbound agents

If `telephony.inbound: false`, also collect:
- Auto-dial? (`provider.auto_dial_outbound: true` — VAPI, Retell, ElevenLabs, LiveKit, Bland)
- Outbound numbers: `telephony.outbound_numbers: ["+1..."]`

---

## 3f. Agent speaks first?

Optional. `agent_speaks_first: true / false / null` (null = auto-detect).

---

## Phase 3 Gate

**Do not proceed until you have: name, language, and phone number (if applicable). Description can be a placeholder if using auto-sync.**

Collecting description manually → [Phase 4 — Agent Description](phase4-description.md).
Using auto-sync → skip to [Phase 5 — Create the Agent](phase5-create.md).

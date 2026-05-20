# Phase 3 — Agent Basics

Collect the fields needed to create and identify the agent.

---

## 3a. Fields to collect

**Truly required** (API will reject without these):

| Field | API field | Notes |
|-------|-----------|-------|
| **Agent name** | `name` | Descriptive: "Customer Support Bot", "Scheduling Assistant" (max 255 chars) |
| **Description** | `description` | Full system prompt or exported config — see Phase 4 |
| **Project** | `project` | Project ID from Phase 1 |

**Commonly needed** (optional in the API, but needed for most setups):

| Field | Location | Notes |
|-------|----------|-------|
| **Language** | `language` | BCP-47 locale, default `en`. Codes: `af ar bn bg zh cs da nl en et fi fr de el gu hi he hu id it ja kn ko ms ml mr multi no pl pa pt ro ru sk es sv th tr tl ta te uk vi` |
| **Phone number** | `telephony.phone_number` | E.164 format, e.g. `+14155551234`. Skip for WebRTC-only or Pipecat. |
| **Inbound/Outbound** | `telephony.inbound` | `true` = receives calls (default `false`). |

---

## 3b. Auto-fetch from provider API

For VAPI, Retell, ElevenLabs, Bland — fetch name, description, and language from the provider rather than asking the user to type them:

### VAPI — assistants and squads
```bash
# Fetch assistant
curl -s https://api.vapi.ai/assistant/{assistant_id} \
  -H "Authorization: Bearer {vapi_api_key}" | jq '{name, description: (.model.messages[] | select(.role=="system") | .content), language: .transcriber.language}'

# For squad agents (multi-agent workflows)
curl -s https://api.vapi.ai/squad/{squad_id} \
  -H "Authorization: Bearer {vapi_api_key}" | jq '{name}'
```
**Docs:** https://docs.vapi.ai/api-reference/assistants/get | https://docs.vapi.ai/api-reference/squads/get

### Retell
```bash
curl -s https://api.retellai.com/get-agent/{agent_id} \
  -H "Authorization: Bearer {retell_api_key}" | jq '{agent_name, language, voice_id, response_engine}'
# Then fetch prompt based on response_engine.type:
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
`name` is not returned by Bland — ask the user. **Docs:** https://docs.bland.ai/api-v1/get/agents-id

---

## 3c. Provider-specific telephony notes

| Provider | `telephony.phone_number` |
|----------|-----------------------|
| VAPI, Retell, ElevenLabs, Bland, Trillet, Cisco, Synthflow | E.164 phone number, e.g. `+14155551234` |
| LiveKit | Omit — WebRTC, no phone number needed |
| Chirp | Omit — connects via `credentials.config.chirp_websocket_url` |
| Pipecat | Omit — agent identified by `credentials.config.pipecat_agent_name` |
| Self-hosted (WebSocket only) | Omit |

---

## 3d. Description — auto-sync for VAPI / Retell / ElevenLabs / Synthflow

Enable `provider.auto_sync_prompt: true` when creating the agent (Phase 5). Cekura fetches the description from the provider within ~30 seconds. Pass a placeholder for the required `description` field on create.

---

## 3e. Outbound agents

If `telephony.inbound: false`, also collect:
- Auto-dial? (`provider.auto_dial_outbound: true`)
- Outbound numbers: `telephony.outbound_numbers: ["+1..."]`

## 3f. Agent speaks first?

Optional. `agent_speaks_first: true / false / null` (null = auto-detect).

---

## Phase 3 Gate

**Do not proceed until you have: name, language, and phone number (if applicable). Description can be a placeholder if auto_sync_prompt will be enabled.**

If collecting description manually → [Phase 4 — Agent Description](phase4-description.md).
If using auto-sync → skip to [Phase 5 — Create the Agent](phase5-create.md).

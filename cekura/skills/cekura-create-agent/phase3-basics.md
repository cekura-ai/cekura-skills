# Phase 3 — Agent Basics

Collect the identifying fields for the agent. For most cloud providers, name, description, and language can be auto-fetched from the provider API using the credentials collected in Phase 2.

---

## 3a. Required fields

| Field | API field | Notes |
|-------|-----------|-------|
| **Agent name** | `name` | Descriptive: "Customer Support Bot", "Scheduling Assistant" |
| **Language** | `language` | Primary language (default `en`). Codes: `af ar bn bg zh cs da nl en et fi fr de el gu hi he hu id it ja kn ko ms ml mr multi no pl pa pt ro ru sk es sv th tr tl ta te uk vi` |
| **Inbound vs Outbound** | `inbound` | Receives calls (`true`, default) or makes calls (`false`)? |
| **Phone number** | `phone_number` | E.164 format `+1234567890`. See provider notes below. |

---

## 3b. Auto-fetch from provider API

For cloud providers with API key + agent ID from Phase 2, fetch agent details rather than asking the user to type them:

### VAPI — assistants and squads

```bash
# Fetch assistant
curl -s https://api.vapi.ai/assistant/{assistant_id} \
  -H "Authorization: Bearer {vapi_api_key}" | jq '{name, description: (.model.messages[] | select(.role=="system") | .content), language: .transcriber.language}'

# For squad agents (multi-agent workflows)
curl -s https://api.vapi.ai/squad/{squad_id} \
  -H "Authorization: Bearer {vapi_api_key}" | jq '{name, members: .members}'
```

**What you get:** `name`, system prompt, `transcriber.language`
**Docs:** https://docs.vapi.ai/api-reference/assistants/get | https://docs.vapi.ai/api-reference/squads/get

### Retell

```bash
# Get voice agent
curl -s https://api.retellai.com/get-agent/{agent_id} \
  -H "Authorization: Bearer {retell_api_key}" | jq '{agent_name, language, voice_id, response_engine}'

# Then fetch prompt based on engine type:
# retell-llm → GET /get-retell-llm/{llm_id} → .general_prompt
# conversation-flow → GET /get-conversation-flow/{flow_id} → full JSON

# Get chat agent
curl -s https://api.retellai.com/get-chat-agent/{chat_agent_id} \
  -H "Authorization: Bearer {retell_api_key}"
```

**What you get:** `agent_name`, `language`, `voice_id`, description via response_engine chain
**Docs:** https://docs.retellai.com/api-references/get-agent.md | https://docs.retellai.com/api-references/get-chat-agent.md

### ElevenLabs

```bash
curl -s https://api.elevenlabs.io/v1/convai/agents/{agent_id} \
  -H "xi-api-key: {elevenlabs_api_key}" | jq '{name, description: .conversation_config.agent.prompt.prompt, language: .conversation_config.agent.language}'
```

**What you get:** `name`, `description`, `language`
**Docs:** https://elevenlabs.io/docs/api-reference/conversational-ai/get-agent

### Bland

```bash
curl -s https://api.bland.ai/agents/{pathway_id} \
  -H "authorization: {bland_api_key}" | jq '{prompt, language, voice, tools}'
```

**What you get:** `prompt` (description), `language`, `voice`, `tools`
**Note:** Bland does not return `name` — ask the user for a display name.
**Docs:** https://docs.bland.ai/api-v1/get/agents-id

---

## 3c. What is NOT fetchable from any provider API

| Field | Status | Action |
|-------|--------|--------|
| **Phone number** | ✗ Not in agent objects | Always ask the user |
| **Bland agent name** | ✗ Not returned | Ask user for a display name |

---

## 3d. Provider-specific `telephony.phone_number` notes

| Provider | `telephony.phone_number` value |
|----------|-----------------------------|
| VAPI, Retell, ElevenLabs, Bland | Actual E.164 phone number, e.g. `+14155551234` |
| LiveKit | Not needed — omit telephony block |
| Pipecat | No phone number — agent name goes in `credentials.config.pipecat_agent_name` instead |
| Self-hosted (WebSocket only) | Not needed — omit telephony block |

---

## 3e. Pipecat Cloud — no agent config to fetch

Pipecat Cloud is a deployment platform — the agent logic lives in your Python code. What you need:
- **Agent name**: the name given to the agent in Pipecat Cloud dashboard → goes in `credentials.config.pipecat_agent_name`
- **Description**: ask the user or paste from their Python code
- No `telephony.phone_number` needed
- **Docs:** https://docs.pipecat.ai

---

## 3f. Description — auto-sync option for VAPI / Retell / ElevenLabs

If the user doesn't want to paste the prompt, enable `provider.auto_sync_prompt: true` at create time (Phase 5). Cekura fetches the description from the provider within ~30 seconds. Pass a short placeholder (`"Auto-syncing from provider"`) for the required `description` field on create.

Does **not** work for Bland, Pipecat, LiveKit, or self-hosted.

---

## 3g. Outbound agents

If `inbound: false`, also collect:
- Auto-dial? (`provider.auto_dial_outbound: true` — VAPI and Retell only)
- Outbound numbers: goes in `telephony.outbound_numbers: ["+1..."]` — used for webhook validation (not a top-level field in v2)

## 3h. Agent speaks first?

Optional: "Does your agent speak first when a call connects?"
- `agent_speaks_first: true` / `false` / `null` (auto-detect)

---

## Phase 3 Gate

**Do not proceed until you have: name, language, inbound/outbound, and phone number (or confirmed not needed). Description can be a placeholder if auto_sync_prompt will be enabled in Phase 5.**

If collecting description manually → [Phase 4 — Agent Description](phase4-description.md).
If using auto-sync → skip to [Phase 5 — Create the Agent](phase5-create.md).

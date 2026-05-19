# Phase 3 — Agent Basics

Collect the identifying fields for the agent. For most cloud providers, name, description, and language can be auto-fetched from the provider API using the credentials collected in Phase 2 — reducing manual input.

---

## 3a. Required fields

| Field | v2 name | Notes |
|-------|---------|-------|
| **Agent name** | `name` | Descriptive: "Customer Support Bot", "Scheduling Assistant" |
| **Language** | `language` | Primary language (default `en`). Codes: `af ar bn bg zh cs da nl en et fi fr de el gu hi he hu id it ja kn ko ms ml mr multi no pl pa pt ro ru sk es sv th tr tl ta te uk vi` |
| **Inbound vs Outbound** | `inbound` | Receives calls (`true`, default) or makes calls (`false`)? |
| **Phone number** | `phone_number` | E.164 format `+1234567890`. See provider notes below. |

---

## 3b. Auto-fetch from provider API

For cloud providers with API key + agent ID collected in Phase 2, fetch agent details directly rather than asking the user to type them:

### VAPI — assistants and squads

```bash
# Fetch assistant
curl -s https://api.vapi.ai/assistant/{assistant_id} \
  -H "Authorization: Bearer {vapi_api_key}" | jq '{name, description: .model.messages[] | select(.role=="system") | .content, language: .transcriber.language}'

# For squad agents (multi-agent workflows)
curl -s https://api.vapi.ai/squad/{squad_id} \
  -H "Authorization: Bearer {vapi_api_key}" | jq '{name, members: .members}'
```

**What you get:** `name`, system prompt (`model.messages[role=system].content`), `transcriber.language`
**Docs:** https://docs.vapi.ai/api-reference/assistants/get | https://docs.vapi.ai/api-reference/squads/get

> **VAPI note:** Assistants and squads are separate resources. If the user has a multi-agent workflow (squad), use the `/squad/{id}` endpoint instead. The backend auto-sync already handles both (tries `/assistant/{id}` first, falls back to `/squad/{id}`).

### Retell

```bash
# Get agent (voice)
curl -s https://api.retellai.com/get-agent/{agent_id} \
  -H "Authorization: Bearer {retell_api_key}" | jq '{agent_name, language, voice_id, response_engine}'

# Then fetch prompt based on engine type:
# retell-llm → GET /get-retell-llm/{llm_id} → .general_prompt
# conversation-flow → GET /get-conversation-flow/{flow_id} → full JSON

# Get chat agent (for text-mode ID)
curl -s https://api.retellai.com/get-chat-agent/{chat_agent_id} \
  -H "Authorization: Bearer {retell_api_key}"
```

**What you get:** `agent_name`, `language`, `voice_id`, description (via response_engine chain)
**Docs:** https://docs.retellai.com/api-references/get-agent.md | https://docs.retellai.com/api-references/get-chat-agent.md

### ElevenLabs

```bash
curl -s https://api.elevenlabs.io/v1/convai/agents/{agent_id} \
  -H "xi-api-key: {elevenlabs_api_key}" | jq '{name, description: .conversation_config.agent.prompt.prompt, language: .conversation_config.agent.language}'
```

**What you get:** `name`, `description` (`conversation_config.agent.prompt.prompt`), `language`
**Docs:** https://elevenlabs.io/docs/api-reference/conversational-ai/get-agent

### Bland

```bash
curl -s https://api.bland.ai/agents/{pathway_id} \
  -H "authorization: {bland_api_key}" | jq '{prompt, language, voice, tools}'
```

**What you get:** `prompt` (description), `language`, `voice`, `tools`
**Note:** Bland does not return `name` in the agent response — ask the user for a display name separately.
**Docs:** https://docs.bland.ai/api-v1/get/agents-id

---

## 3c. What is NOT fetchable from any provider API

| Field | Status | Action |
|-------|--------|--------|
| **Phone number** | ✗ Not in agent objects | Always ask the user — it's a separate resource in all providers |
| **Bland agent name** | ✗ Not returned | Ask user for a display name |

---

## 3d. Provider-specific phone number notes

| Provider | `phone_number` value |
|----------|--------------------|
| VAPI, Retell, ElevenLabs, Bland | Actual E.164 phone number, e.g. `+14155551234` |
| LiveKit | Not needed for WebRTC — omit |
| Pipecat | Agent name from Pipecat dashboard (not a phone number), e.g. `"my-agent"` |
| Self-hosted (WebSocket only) | Omit |

---

## 3e. Pipecat Cloud — no agent config to fetch

Pipecat Cloud is a deployment platform — the agent logic lives in your code (Python), not in a config object fetchable via API. What you need instead:

- **Agent name**: the name you gave the agent in your Pipecat Cloud dashboard. This goes into `phone_number` on the Cekura agent.
- **Pipecat API key**: from pipecat.daily.co → Settings → API Keys
- **Description**: ask the user for their agent's purpose/system prompt (or paste from their Python code)
- **Docs:** https://docs.pipecat.ai

---

## 3f. Description — auto-sync option for VAPI / Retell / ElevenLabs

If the user doesn't want to paste the prompt, enable `auto_sync_prompt: true` at create time (Phase 5). Cekura fetches the description from the provider within ~30 seconds. Pass a short placeholder (`"Auto-syncing from provider"`) for the required `description` field on create.

This does **not** work for Bland, Pipecat, LiveKit, or self-hosted.

---

## 3g. Outbound agents

If `inbound: false`, also collect:
- Auto-dial? (`auto_dial_outbound: true` — VAPI and Retell only)
- Outbound numbers: (`outbound_numbers: ["+1..."]` — used for webhook validation)

## 3h. Agent speaks first?

Optional: "Does your agent speak first when a call connects, or does the caller speak first?"
- `agent_speaks_first: true` / `false` / `null` (auto-detect from description)

---

## Phase 3 Gate

**Do not proceed until you have: name, language, inbound/outbound, and phone number (or confirmed not needed). Description can be a placeholder if auto_sync_prompt will be enabled in Phase 5.**

If collecting description manually → [Phase 4 — Agent Description](phase4-description.md).
If using auto_sync_prompt → skip to [Phase 5 — Create the Agent](phase5-create.md).

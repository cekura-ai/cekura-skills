# Phase 3 — Agent Basics

Collect the identifying fields for the agent. For cloud providers (VAPI, Retell, ElevenLabs), the agent description can be auto-fetched from the provider — the user does not need to paste it manually.

---

## 3a. Required fields

| Field | v2 name | Notes |
|-------|---------|-------|
| **Agent name** | `name` | Descriptive: "Customer Support Bot", "Scheduling Assistant" |
| **Language** | `language` | Primary language (default `en`). Codes: `af ar bn bg zh cs da nl en et fi fr de el gu hi he hu id it ja kn ko ms ml mr multi no pl pa pt ro ru sk es sv th tr tl ta te uk vi` |
| **Inbound vs Outbound** | `inbound` | Receives calls (`true`, default) or makes calls (`false`)? |
| **Phone number** | `phone_number` | E.164 format `+1234567890`. Provider-specific notes below. |

## 3b. Provider-specific phone number notes

| Provider | `phone_number` value |
|----------|--------------------|
| VAPI, Retell, ElevenLabs, Bland, SIP | Actual E.164 phone number, e.g. `+14155551234` |
| LiveKit | Not needed for WebRTC — omit |
| Pipecat | Agent name (not a phone number), e.g. `"my-agent"` |
| Self-hosted (WebSocket only) | Omit |

> **Phone number is always provided manually.** There is no mechanism to auto-fetch it from the provider.

## 3c. Agent description — cloud providers vs manual

### VAPI / Retell / ElevenLabs (credentials collected in Phase 2)

The description can be **auto-synced from the provider** rather than pasted manually:

- Set `auto_sync_prompt: true` when creating the agent in Phase 5
- Cekura will fetch the description from the provider within ~30 seconds
- Pass a short placeholder (`"Auto-syncing from provider"`) for the required `description` field on create

**What gets synced per provider:**

| Provider | What is fetched |
|----------|----------------|
| Retell | `retell-llm`: `general_prompt`. `conversation-flow`: full flow JSON |
| VAPI | System message from `model.messages[role=system]`; falls back to squad endpoint if assistant 404 |
| ElevenLabs | `conversation_config.agent.prompt.prompt` |

If the user prefers to paste their prompt manually (for faster setup without waiting), they can — just skip enabling `auto_sync_prompt`.

### LiveKit / Pipecat / Bland / SIP / self-hosted

No auto-sync available. Ask: "Can you paste your agent's full system prompt or exported config?"

- For Retell/VAPI: Agents → Select → Export / Code button → Copy full JSON
- For multi-state agents: paste the complete JSON (all nodes and transitions)
- For custom/self-hosted: paste the full system prompt text

> **No truncation.** Descriptions >10 KB are fine — Cekura handles them. See Phase 5 for the large-payload workaround.

## 3d. Dynamic variable patterns

If the description contains `{{variableName}}` placeholders, note them — Cekura auto-detects them after agent creation. Covered in [Phase 9](phase9-dynamic-variables.md).

## 3e. Outbound agents — additional fields

If `inbound: false`, also ask:
- Should Cekura auto-dial outbound calls? (`auto_dial_outbound: true` — VAPI and Retell only)
- What number(s) should Cekura call? (`outbound_numbers: ["+1..."]` — used for webhook validation)

## 3f. Agent speaks first?

Optional: "Does your agent speak first when a call connects, or does the caller speak first?"
- `agent_speaks_first: true` — agent opens the conversation
- `agent_speaks_first: false` — caller speaks first
- Omit (null, default) — Cekura auto-detects from the description

---

## Phase 3 Gate

**Do not proceed until you have: name, language, inbound/outbound, and either (a) phone number or (b) confirmed it's not needed for this provider. Description can be a placeholder if auto_sync_prompt will be enabled.**

Move to [Phase 4 — Agent Description](phase4-description.md) (if collecting description manually) or skip directly to [Phase 5 — Create the Agent](phase5-create.md) (if using auto-sync).

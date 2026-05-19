# Phase 3 — Agent Basics

Collect the identifying fields for the agent. Some depend on the provider chosen in Phase 2.

---

## 3a. Required fields

| Field | v2 name | Notes |
|-------|---------|-------|
| **Agent name** | `name` | Descriptive: "Customer Support Bot", "Scheduling Assistant" |
| **Language** | `language` | Primary language (default `en`). Codes: `af ar bn bg zh cs da nl en et fi fr de el gu hi he hu id it ja kn ko ms ml mr multi no pl pa pt ro ru sk es sv th tr tl ta te uk vi` |
| **Inbound vs Outbound** | `inbound` | Receives calls (`true`, default) or makes calls (`false`)? |
| **Phone number** | `phone_number` | Format `+1234567890` (E.164). Provider-specific notes below. |

## 3b. Provider-specific phone number notes

| Provider | phone_number value |
|----------|--------------------|
| VAPI, Retell, ElevenLabs, Bland, SIP | Actual E.164 phone number, e.g. `+14155551234` |
| LiveKit | Not needed for WebRTC — omit |
| Pipecat | Agent name (not a phone number), e.g. `"my-agent"` |
| Self-hosted (WebSocket only) | Omit |

## 3c. Outbound agents — additional fields

If `inbound: false`, also ask:

- Should Cekura auto-dial outbound calls? (`auto_dial_outbound: true` — VAPI and Retell only)
- What number(s) should Cekura call? (`outbound_numbers: ["+1..."]` — used for webhook validation)

## 3d. Agent speaks first?

Ask (optional): "Does your agent speak first when a call connects, or does the caller speak first?"

- `agent_speaks_first: true` — agent opens the conversation
- `agent_speaks_first: false` — caller speaks first
- `agent_speaks_first: null` (default) — auto-detect from the agent description

---

## Phase 3 Gate

**Do not proceed until you have: name, language, inbound/outbound, and phone number (or confirmed not needed for this provider).**

Move to [Phase 4 — Agent Description](phase4-description.md).

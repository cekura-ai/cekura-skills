# Phase 2 — Agent Basics

Collect the core identifying fields for the agent before touching the description or provider.

---

## 2a. Required fields

| Field | Notes |
|-------|-------|
| **Agent name** | Descriptive: "Customer Support Bot", "Scheduling Assistant" |
| **Language** | Primary language (default `en`). Codes: `af ar bn bg zh cs da nl en et fi fr de el gu hi he hu id it ja kn ko ms ml mr multi no pl pa pt ro ru sk es sv th tr ta te uk vi` |
| **Inbound vs Outbound** | Does the agent receive calls (`inbound: true`, default) or make calls (`inbound: false`)? |
| **Contact number** | Format `+1234567890` (8–30 chars). Skip if WebRTC/WebSocket-only. |

## 2b. Outbound agents — additional questions

If `inbound: false`, also ask:

- Should Cekura auto-trigger outbound calls? (`outbound_auto_call: true` — VAPI and Retell only)
- What number(s) should Cekura call? (`outbound_numbers: ["+1..."]`)

These get set in Phase 4 (create) or patched in Phase 10 (advanced config).

---

## Phase 2 Gate

**Do not proceed until you have: agent name, language, inbound/outbound, and contact number (or confirmed skip).**

Move to [Phase 3 — Agent Description](phase3-description.md).

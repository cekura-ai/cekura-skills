# Phase 6 — Connection Type

Confirm how Cekura will connect to the agent during test runs. The provider chosen in Phase 2 determines which modes are available.

---

## 6a. Choose a connection mode

| Mode | Best For | What's Needed |
|------|----------|---------------|
| **Phone (PSTN)** | Any phone-based agent | `phone_number` set in Phase 3 |
| **WebRTC** | VAPI, Retell, ElevenLabs, LiveKit, Pipecat | Provider-specific — see 6b |
| **Chat / Text** | Rapid iteration (10× faster, ~90% cheaper than voice) | `chat_assistant_id` or WebSocket URL in provider credentials |
| **Custom WebSocket** | Self-hosted via WebSocket | Already configured via `provider.credentials.config.url` in Phase 5 |

**Recommendation:** Use chat mode during development for fast iteration. Switch to phone or WebRTC for final validation before production.

---

## 6b. WebRTC setup per provider

| Provider | Extra requirement |
|----------|------------------|
| VAPI | Add `vapi_public_key` (VAPI Dashboard → Organization Settings → Public Key) |
| Retell | No extra fields — WebRTC works with existing credentials |
| ElevenLabs | No extra fields |
| LiveKit | Cekura manages room creation and token generation automatically |
| Pipecat | Cekura dispatches the job; `contact_number` is the agent name |

---

## 6c. Chat / text setup per provider

| Provider | Setup |
|----------|-------|
| Retell | In Retell: "Copy as chat agent" → PATCH agent with `chat_assistant_id` to the chat agent ID |
| VAPI | PATCH agent with `chat_assistant_id` to the VAPI chat assistant ID |
| ElevenLabs | PATCH agent with `chat_assistant_id` to the ElevenLabs agent ID |
| Self-hosted | Already set via `provider.credentials.config.url` in Phase 5 |

Apply `chat_assistant_id` via PATCH:

```bash
curl -X PATCH https://api.cekura.ai/test_framework/v1/aiagents/{id}/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"chat_assistant_id": "<id>"}'
```

Full WebSocket message format and injected headers are in `references/integrations.md`.

---

## Phase 6 Gate

**Confirm the connection mode with the user. At least one mode must be configured and confirmed.**

Move to [Phase 7 — Mock Tools](phase7-mock-tools.md).


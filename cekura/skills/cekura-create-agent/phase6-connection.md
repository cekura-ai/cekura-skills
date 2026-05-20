# Phase 6 — Connection Type

Confirm how Cekura will connect to the agent during test runs. The provider chosen in Phase 2 determines which modes are available.

---

## 6a. Choose a connection mode

| Mode | Best For | What's Needed |
|------|----------|---------------|
| **Phone (PSTN)** | Any phone-based agent | `phone_number` set in Phase 3 |
| **WebRTC** | VAPI, Retell, ElevenLabs, LiveKit, Pipecat | Provider-specific — see 6b |
| **Chat / Text** | Rapid iteration (10× faster, ~90% cheaper) | `provider.chat_agent_details` — see 6c |
| **Self-hosted WebSocket** | Custom agents | Set in `provider.chat_agent_details` in Phase 5 |

**Recommendation:** Use chat mode during development for fast iteration. Switch to phone or WebRTC for final validation.

---

## 6b. WebRTC setup per provider

| Provider | Extra requirement |
|----------|------------------|
| VAPI | `credentials.config.public_key` (VAPI Dashboard → Organization Settings → Public Key) |
| Retell | No extra fields — WebRTC works with existing credentials |
| ElevenLabs | No extra fields |
| LiveKit | Cekura manages room creation and token generation automatically |
| Pipecat | Cekura dispatches the job; `phone_number` is the agent name |

---

## 6c. Chat / text setup per provider

Set `chat_agent_details` inside the `provider` block via PATCH:

| Provider | `chat_agent_details` value |
|----------|---------------------------|
| Retell | `{"type": "retell", "config": {"agent_id": "<chat agent ID>"}}` |
| VAPI | `{"type": "vapi", "config": {"agent_id": "<chat assistant ID>"}}` |
| ElevenLabs | `{"type": "elevenlabs", "config": {"agent_id": "<agent ID>"}}` |
| Self-hosted WebSocket | `{"type": "self_hosted", "config": {"url": "wss://...", "headers": {...}}}` |

Apply via PATCH:

```bash
curl -X PATCH https://api.cekura.ai/test_framework/v2/aiagents/{id}/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": {
      "chat_agent_details": {
        "type": "retell",
        "config": {"agent_id": "retell_chat_agent_xyz"}
      }
    }
  }'
```

> **Retell chat setup:** In Retell Dashboard, use "Copy as chat agent" to create a separate chat-optimised agent, then use that agent's ID in `chat_agent_details.config.agent_id`.

Full WebSocket message format and injected headers are in `references/integrations.md`.

---

## Phase 6 Gate

**Confirm the connection mode with the user. At least one mode must be configured and confirmed.**

Move to [Phase 7 — Mock Tools](phase7-mock-tools.md).

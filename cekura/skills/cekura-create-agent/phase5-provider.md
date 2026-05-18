# Phase 5 — Provider Integration

Connect the agent to the voice provider it runs on.

---

## 5a. Identify the provider

Ask: "What provider does your agent use? (VAPI, Retell, ElevenLabs, LiveKit, Pipecat, SIP, or custom/self-hosted?)"

---

## 5b. Required fields by provider

| Provider | `assistant_provider` | Key Fields |
|----------|---------------------|------------|
| **VAPI** | `vapi` | `vapi_api_key`, `assistant_id` |
| **Retell** | `retell` | `retell_api_key`, `assistant_id` |
| **ElevenLabs** | `elevenlabs` | `elevenlabs_api_key`, `assistant_id` |
| **LiveKit** | `livekit` | `livekit_api_key`, `livekit_data` (JSON: `api_secret`, `url`) |
| **Pipecat** | `pipecat` | `pipecat_api_key`, `contact_number` = agent name (not a phone number) |
| **SIP** | `self_hosted` | `sip_endpoint` (e.g. `sip:agent@domain.com`), optional `sip_auth` |
| **Custom webhook** | (none) | Client pushes calls to `/observability/v1/observe/` |

Always set `transcript_provider` to match `assistant_provider` — it controls how call data is ingested.

Full field lists, `livekit_data` JSON structure, SIP auth format, and the custom webhook payload schema are in `references/integrations.md`.

---

## 5c. Where to find credentials

| Provider | API Key | Assistant ID |
|----------|---------|--------------|
| VAPI | Dashboard → Organization Settings → API Keys → Private Key | Assistants → Select → copy from URL |
| Retell | Settings → API Keys | Agents → Select → ID in URL |
| ElevenLabs | Profile → API Keys | Conversational AI → Select → ID in settings |
| LiveKit | Cloud Dashboard → Settings → Keys | N/A — use agent name |
| Pipecat | pipecat.daily.co → Settings → API Keys | N/A |

---

## 5d. Apply provider config via PATCH

```bash
curl -X PATCH https://api.cekura.ai/test_framework/v1/aiagents/{id}/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_provider": "vapi",
    "transcript_provider": "vapi",
    "vapi_api_key": "...",
    "assistant_id": "asst_..."
  }'
```

Or use `mcp__cekura__aiagents_partial_update` with the same fields.

---

## 5e. Optional automation

| Setting | Providers | Effect |
|---------|-----------|--------|
| `auto_fetch_calls_enabled: true` | VAPI, Retell | Auto-imports production calls every ~30–60 s for observability |
| `auto_sync_prompt_enabled: true` | Retell only | Auto-syncs agent prompt from Retell every 30 s |

---

## Phase 5 Gate

**Do not proceed until `assistant_provider`, the provider API key, and `assistant_id` (where applicable) are set on the agent.**

Move to [Phase 6 — Connection Type](phase6-connection.md).

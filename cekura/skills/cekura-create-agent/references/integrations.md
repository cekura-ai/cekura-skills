# Provider Integration Reference

## Provider Selection

Set `assistant_provider` on the agent to one of:
`vapi`, `retell`, `elevenlabs`, `bland`, `livekit`, `vocera`, `sms`, `whatsapp`, `self_hosted`, `agentforce`, `trillet`, `cisco`, `amazon_connect`

> Note: `pipecat` is **not** an `assistant_provider` value — a Pipecat agent uses
> `assistant_provider: "self_hosted"` with `transcript_provider: "pipecat"` and a
> `pipecat_api_key` (see the Pipecat section). `pipecat` is valid only for
> `transcript_provider`.

Set `transcript_provider` to match (controls how call data is ingested):
`vapi`, `retell`, `synthflow`, `elevenlabs`, `bland`, `livekit`, `pipecat`, `koreai`, `custom`, `trillet`, `cisco`

---

## VAPI

### Required Fields
```json
{
  "assistant_provider": "vapi",
  "transcript_provider": "vapi",
  "vapi_api_key": "<VAPI Private API Key>",
  "assistant_id": "<VAPI Assistant ID (min 10 chars)>",
  "contact_number": "+14155551234"
}
```

### Where to Find Credentials
- **API Key:** VAPI Dashboard → Organization Settings → API Keys → Private Key
- **Assistant ID:** VAPI Dashboard → Assistants → Select assistant → copy ID from URL or settings

### Optional Settings
- `vapi_data`: JSON string with additional config (e.g., `{"trigger_url": "..."}`)
- `auto_fetch_calls_enabled: true` — Auto-import production calls every 30 seconds
- `outbound_auto_call: true` — For outbound agents, auto-trigger calls via VAPI

### Chat Setup
- Set `chat_assistant_id` to the VAPI chat assistant ID (if different from voice)

### Features
- Auto-fetch calls from production
- Auto-fetch mock tools
- Outbound auto-call support
- Tool call visibility in transcripts
- Metadata access

---

## Retell

### Required Fields
```json
{
  "assistant_provider": "retell",
  "transcript_provider": "retell",
  "retell_api_key": "<Retell API Key>",
  "assistant_id": "<Retell Agent ID (min 10 chars)>",
  "contact_number": "+14155551234"
}
```

### Where to Find Credentials
- **API Key:** Retell Dashboard → Settings → API Keys
- **Agent ID:** Retell Dashboard → Agents → Select agent → ID in URL

### Optional Settings
- `retell_data`: Additional config JSON
- `auto_sync_prompt_enabled: true` — Auto-sync prompt from Retell every 30 seconds (works for standard LLM and Conversation Flow agents)
- `auto_fetch_calls_enabled: true` — Auto-import production calls

### Chat Setup
1. In Retell: Copy your voice agent as a chat agent ("Copy as chat agent")
2. Set `chat_assistant_id` to the chat agent ID on Cekura

### Features
- Auto-sync prompt (every 30s)
- Auto-fetch calls
- Auto-fetch mock tools
- WebRTC support
- Chat support via separate chat agent

---

## ElevenLabs

### Required Fields
```json
{
  "assistant_provider": "elevenlabs",
  "transcript_provider": "elevenlabs",
  "elevenlabs_api_key": "<ElevenLabs API Key>",
  "assistant_id": "<ElevenLabs Agent ID>",
  "contact_number": "+14155551234"
}
```

### Where to Find Credentials
- **API Key:** ElevenLabs Dashboard → Profile → API Keys
- **Agent ID:** ElevenLabs Dashboard → Conversational AI → Select agent → ID in settings

### Optional Settings
- `elevenlabs_data`: Additional config JSON

### Features
- Phone, WebSocket, and Chat support
- Auto-fetch mock tools

---

## LiveKit

### Required Fields
```json
{
  "assistant_provider": "livekit",
  "transcript_provider": "livekit",
  "livekit_api_key": "<LiveKit API Key>",
  "livekit_data": "{\"api_secret\": \"<secret>\", \"url\": \"wss://your-server.livekit.cloud\"}"
}
```

**Note:** `livekit_data` is a JSON string (not object) with:
- `api_secret` (required): LiveKit API Secret
- `url` (required): LiveKit server URL (wss:// format)
- `config` (optional): Room metadata accessible via `ctx.room.metadata`

### Where to Find Credentials
- **API Key + Secret:** LiveKit Cloud Dashboard → Settings → Keys
- **URL:** LiveKit Cloud Dashboard → your project URL

### Connection
- WebRTC-based (no phone number needed for WebRTC mode)
- Automated room and token management by Cekura

### Features
- `metadata.raw_metrics` with per-component latency (LLM TTFT, TTS TTFB, EOU delay)
- WebRTC testing with automated room management

---

## Pipecat

### Required Fields
```json
{
  "transcript_provider": "pipecat",
  "pipecat_api_key": "<Pipecat Cloud API Key from pipecat.daily.co>",
  "pipecat_data": { "pipecat_agent_name": "<your Pipecat Cloud agent name>" }
}
```

**Note:** Pipecat config is driven by `transcript_provider: "pipecat"`.
- `pipecat_agent_name` MUST go **inside `pipecat_data`** — it is NOT a top-level
  field. Setting `pipecat_agent_name` at the top level fails validation
  (the API only reads `pipecat_data.pipecat_agent_name`).
- `pipecat_api_key` is a top-level field.
- `assistant_provider` is **not** `pipecat` (the backend has no such value) —
  leave it default (`""`) or `self_hosted`; the Pipecat path is selected by
  `transcript_provider`, not `assistant_provider`.

### Test runs (WebRTC)
Run scenarios against a Pipecat agent with **`scenarios_run_pipecat_v2`**
(Pipecat Cloud WebRTC) — it uses the agent's `pipecat_api_key`. This is the
WebRTC path; do not use `scenarios_run_websocket` / `scenarios_run_text` for a
Pipecat agent.

### Optional Settings
- `pipecat_data`: JSON string with room properties (see Daily.co Room Configuration API)
- `assistant_id`: Optional Pipecat assistant ID

### Where to Find Credentials
- **API Key:** pipecat.daily.co → Dashboard → API Keys

---

## SIP — Connection Mode (NOT a provider)

SIP is a **connection mode** used to reach `self_hosted` (or any) agents over a SIP endpoint at test-run time. It is NOT a value for `assistant_provider`. The provider stays whatever platform the agent is built on — most commonly `self_hosted` for agents you reach directly via SIP.

### Required Fields (on the agent record)
```json
{
  "assistant_provider": "self_hosted",
  "sip_endpoint": "sip:agent@yourdomain.com"
}
```

### Optional Auth
```json
{
  "sip_auth": {
    "username": "user123",
    "password": "pass456"
  }
}
```

### Headers
Cekura automatically injects these SIP headers:
- `X-Run-Id`: Run identifier
- `X-Scenario-Id`: Scenario identifier
- `X-Result-Id`: Result identifier
- Any test profile field starting with "X-" becomes a custom SIP header

### Format
`sip_endpoint` accepts:
- Domain: `sip:agent@yourdomain.com`
- IP: `sip:192.168.1.100:5060`

### Running scenarios over SIP
Use the `scenarios_run_sip` tool at run time. The agent's `assistant_provider` is irrelevant to choosing this mode — what matters is that `sip_endpoint` is set.

---

## Custom Integration (Webhook)

For providers without first-class integration — the client pushes call data to Cekura.

### Setup
No provider fields needed on the agent. The client sends call data via webhook:

```json
POST https://api.cekura.ai/observability/v1/observe/
X-CEKURA-API-KEY: <key>

{
  "agent_id": 123,
  "calls": [
    {
      "id": "unique-call-id",
      "startedAt": "2024-01-01T00:00:00Z",
      "endedAt": "2024-01-01T00:05:00Z",
      "to_phone_number": "+14155551234",
      "from_phone_number": "+14155559876",
      "messages": [
        {"role": "bot", "content": "Hello, how can I help?", "start_time": 0, "end_time": 1500},
        {"role": "user", "content": "I need to book an appointment", "start_time": 2000, "end_time": 3500}
      ],
      "metadata": {},
      "endedReason": "customer-hungup"
    }
  ]
}
```

### Message Roles
`bot`, `user`, `system`, `function_call`, `function_call_result`

### Timing
- `start_time` and `end_time` are in milliseconds
- Must send within 5 minutes after call ends

---

## Chat / WebSocket Connection

For text-based testing (10x faster, 90% cheaper than voice).

### Provider-Specific Chat
Most providers support chat mode separately:
- **Retell:** Create a "chat agent" copy, set `chat_assistant_id`
- **VAPI:** Set `chat_assistant_id` to VAPI chat assistant
- **ElevenLabs:** Set `chat_assistant_id` to ElevenLabs agent ID

### Custom WebSocket
```json
{
  "websocket_url": "wss://api.example.com/ws",
  "websocket_headers": {
    "Authorization": "Bearer token",
    "X-Custom": "value"
  }
}
```

### WebSocket Message Format
Cekura sends/receives:
- Regular: `{"content": "message"}`
- Function call: `{"role": "Function Call", "data": {"id": "...", "name": "...", "arguments": "{}"}}`
- Function result: `{"role": "Function Call Result", "data": {"id": "...", "result": "{}"}}`
- End call: `{"content": "...", "type": "end_call"}`

### Headers Sent by Cekura
- `X-VOCERA-SECRET`: Cekura API key
- `X-VOCERA-SCENARIO-ID`, `X-VOCERA-RESULT-ID`, `X-VOCERA-RUN-ID`
- Any test profile fields starting with "X-"

---

## Outbound Agents

For agents that initiate calls (not receive them):

```json
{
  "inbound": false,
  "outbound_auto_call": true,
  "outbound_numbers": ["+14155551234"]
}
```

- `outbound_auto_call: true` — Cekura triggers the call via the provider API
- Test profile fields are sent as dynamic variables to the main agent
- Works with VAPI and Retell

---

## Provider Comparison

Provider rows only. Connection modes (SIP, WebSocket, chat, PSTN, WebRTC) are picked independently — see the integration entries above for which modes each provider supports.

| Feature | VAPI | Retell | ElevenLabs | LiveKit | Pipecat | Self-hosted / Custom |
|---------|------|--------|------------|---------|---------|----------------------|
| Phone (PSTN) | Yes | Yes | Yes | No | No | Yes (via SIP) |
| WebRTC | Yes | Yes | Yes | Yes | Yes | No |
| Chat / WebSocket | Yes | Yes | Yes | No | No | Yes |
| Auto-fetch calls | Yes | Yes | No | No | No | N/A |
| Auto-fetch tools | Yes | Yes | Yes | No | Yes | No |
| Auto-sync prompt | No | Yes | No | No | No | No |
| Outbound auto-call | Yes | Yes | No | No | No | No |
| Latency metrics | No | No | No | Yes | No | No |

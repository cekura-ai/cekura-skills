# Phase 3 — Agent Basics & Connection Type

Collect the fields needed to identify the agent and determine how Cekura will connect to it. Connection type is part of basics — the phone number itself is a connection choice.

---

> **Start:** Announce "Starting Phase 3 — Agent Basics & Connection Type" before doing anything in this phase.

## 3a. Fields to collect

**Truly required** (API will reject without these):

| Field | API field | Notes |
|-------|-----------|-------|
| **Agent name** | `name` | Infer from code/config first — see 3a-name. Only ask the user if it cannot be determined. (max 255 chars) |
| **Description** | `description` | Full system prompt — see Phase 4. Placeholder OK if using auto-sync. |
| **Project** | `project` | Project ID from Phase 1 |

**Also collect:**

| Field | Location | When |
|-------|----------|------|
| **Language** | `language` | Always — see 3a-lang |
| **Connection type** | see 3c | Always — decide this first before asking about phone/inbound |
| **Phone number** | `telephony.phone_number` | Only if connection type is Phone or SIP |
| **Inbound vs outbound** | `telephony.inbound` | Only if connection type is Phone or SIP |

**Decide the connection type (3c) before asking about phone number or inbound/outbound.** For WebSocket, WebRTC, or chat-only agents, skip `telephony.phone_number` and `telephony.inbound` entirely — they do not apply.

### 3a-name. Agent name — infer first, ask only if needed

**If code is available**, infer the name from:
- Named constants or variables: `AGENT_NAME`, `BOT_NAME`, `SERVICE_NAME`
- Config files or environment variables that name the agent
- The agent's persona in the system prompt (e.g. "You are Alex, a support agent for Acme")
- README or project documentation
- The greeting the agent uses to open a call
- The filename or class name if descriptive

**If using a cloud provider**, the name is returned by the provider's API (see 3e auto-fetch) — use that directly.

**Only ask the user for a name if it cannot be determined from any of the above.** When asking, ask for a descriptive name that reflects what the agent does — not a technical identifier.

### 3a-lang. Language selection — explore properly

Do not assume `en`. Actively determine what languages the agent supports:

**Step 1 — Look for explicit language signals only**

Valid signals — things that directly describe what language the agent uses:
- Explicit instructions in the system prompt: "respond in Hindi", "always reply in Spanish"
- A language constant or config value tied to agent behaviour: `LANGUAGE = "hi"`, `agent_language = "es"`
- Language-switching rules in the prompt: "if the user speaks Hindi, respond in Hindi"
- Non-English content in the system prompt itself (the prompt text, not code comments)

**Not valid signals — do not use these:**
- The programming language the codebase is written in
- English variable names, function names, or log messages
- English comments in the code
- The fact that code identifiers are in ASCII

The language of the codebase tells you nothing about the language the agent speaks. Only explicit agent-facing configuration counts.

If no explicit signal is found → skip to Step 2.

**Step 2 — Ask the user directly**

Ask two questions:

1. "What language(s) does your agent support? Does it handle only English, or can it respond in multiple languages?"

2. "Is the language fixed for this agent, or determined at runtime — for example by a personality setting, test profile, or dynamic variable passed in per call?"

If language is determined at runtime (not baked into the agent) → use `"multi"` regardless of what languages are actually supported. The agent's language varies per run, so a fixed code would be wrong.

**Step 3 — Set the correct value**

| Situation | `language` value |
|-----------|-----------------|
| Agent only handles English, fixed | `en` |
| Agent only handles one specific language, fixed | BCP-47 code for that language |
| Agent handles 2+ languages, or detects/switches based on caller | `multi` |
| Agent has a prompt with language-switching rules | `multi` |
| Language is determined at runtime (personality, test profile, dynamic variable) | `multi` |

Available codes: `af ar bn bg zh cs da nl en et fi fr de el gu hi he hu id it ja kn ko ms ml mr multi no pl pa pt ro ru sk es sv th tr tl ta te uk vi`

`multi` is the safe default for any agent whose language is not fixed and known at setup time.

**Simple rule:** if the agent uses an LLM to generate responses, or if it serves callers across multiple locales — use `multi`.

---

## 3b. What to collect per provider

| Provider | Phone number? | Description source | Notes |
|----------|--------------|-------------------|-------|
| **VAPI** | Yes | Auto-fetch or paste | `agent_id` = assistant or squad ID |
| **Retell** | Yes | Auto-fetch or paste | Separate `agent_id` (voice) and `chat_agent_id` (text) |
| **ElevenLabs** | Yes | Auto-fetch or paste | |
| **Synthflow** | Yes | Auto-fetch or paste | |
| **Bland** | Yes | Fetch prompt, ask user for name | `agent_id` = pathway_id; name not returned by API |
| **LiveKit** | No | Ask user | WebRTC only |
| **Pipecat** | No | Ask user | Agent identified by `credentials.config.pipecat_agent_name` |
| **Chirp** | No | Ask user | Connects via `chirp_websocket_url` |
| **KoreAI** | No | Ask user | Text/chat only |
| **Genesys** | No | Ask user | Text/chat only |
| **Trillet** | Yes | Ask user | |
| **Cisco** | Yes | Ask user | Pre-configured integration |
| **Self-hosted (phone/SIP)** | Yes | Ask user | |
| **Self-hosted (WebSocket)** | No | Ask user | Text-mode only |

---

## 3c. Connection type

**Infer connection settings from code/config first — only ask the user for what cannot be determined.**

If code is available, look for:

- **WebSocket URL**: environment variables (`WEBSOCKET_URL`, `WS_URL`, `SERVER_URL`), config files, deployment manifests (fly.toml, docker-compose.yml, .env), or the port the server binds to in startup code
- **Phone number**: config files, environment variables, README, or the number registered with the provider
- **SIP URI**: config files or environment variables
- **Connection headers / auth**: any auth tokens or headers the agent requires on the incoming connection
- **Port / host**: server startup code (e.g. `websockets.serve(host, port)`) — combine with the deployment URL to form the full `wss://` address

The connection type itself is often apparent from the code structure: a WebSocket server suggests WebSocket mode; a phone number in config suggests PSTN; a SIP URI suggests SIP. Only ask the user to confirm or fill gaps.

---

The connection type is determined by what you configure — ask the user to confirm if not clear from code.

| Mode | When | What to set |
|------|------|-------------|
| **Phone (PSTN)** | Agent receives or makes calls via a phone number | `telephony.phone_number` + `telephony.inbound` (true = receives, false = dials out) |
| **SIP** | Agent is reachable via a SIP endpoint | `telephony.sip_uri` + optional `telephony.sip_auth` + `telephony.inbound` |
| **WebRTC** | Lower latency, no telephony costs | Provider-specific — see below |
| **WebSocket endpoint** | Agent exposes a `wss://` URL that Cekura connects to | `provider.chat_agent_details.type: self_hosted, config.url: wss://...` — see 3d |
| **Chat / Text (provider)** | Provider has a separate chat agent | `provider.chat_agent_details` with provider type — see 3d |

> **`telephony.inbound` is only relevant for Phone and SIP modes.** Do not ask about inbound/outbound for WebRTC, WebSocket, or chat-only agents.

A single agent can support multiple connection modes (e.g. phone + WebSocket). Ask the user which they want to use.

> **WebSocket endpoint:** If the user's agent (or simulation runner) exposes a `wss://` URL, Cekura connects to it as a client. Ask for the WebSocket URL and any auth headers needed.
>
> **Don't have a WebSocket server yet?** Offer to create one. See 3d-ws below.

### WebRTC per provider

| Provider | Extra requirement |
|----------|------------------|
| VAPI | `credentials.config.public_key` (VAPI Dashboard → Organization Settings → Public Key) |
| Retell | No extra fields |
| ElevenLabs | No extra fields |
| LiveKit | Cekura manages room creation automatically |
| Pipecat | Cekura dispatches the job |

---

## 3d. WebSocket / chat setup

Set `provider.chat_agent_details` to configure a WebSocket or text-based connection. Apply via PATCH after creating the agent in Phase 5, or include in the create payload.

| Connection | `chat_agent_details` |
|------------|---------------------|
| **Self-hosted WebSocket** (agent exposes `wss://`) | `{"type": "self_hosted", "config": {"url": "wss://your-server/agent", "headers": {"Authorization": "Bearer ..."}}}` |
| Retell chat agent | `{"type": "retell", "config": {"agent_id": "<chat agent ID>"}}` |
| VAPI chat assistant | `{"type": "vapi", "config": {"agent_id": "<chat assistant ID>"}}` |
| ElevenLabs | `{"type": "elevenlabs", "config": {"agent_id": "<agent ID>"}}` |

> **Retell:** In Retell Dashboard, use "Copy as chat agent" to create a separate text-mode agent, then use that agent's ID here.

---

## 3d-ws. Scaffold a WebSocket server (if user doesn't have one)

If the user selects WebSocket endpoint but doesn't have an existing server, **offer to generate one**:

> "Would you like me to write the WebSocket server code for you? It needs to follow Cekura's protocol to accept test connections."

If yes, ask:
1. **Language / framework?** (Python `websockets`, Python FastAPI, Node.js/TypeScript, Go, other)
2. **Does your agent make tool/function calls?** (affects the server skeleton)
3. **Local development or production?** (`ws://` vs `wss://`)

Point them to the **official Cekura WebSocket server example repo**:

> **https://github.com/cekura-ai/llm-websocket-server-example**

This is a complete, production-ready Python server that already implements the full Cekura protocol (keepalives, tool call reporting, greeting-first flow). Walk the user through adapting it:

1. Clone the repo and install dependencies
2. Update `SYSTEM_PROMPT` with their agent's prompt
3. Update the LLM credentials
4. Adapt `TOOLS` and `TOOL_URL` if their agent makes tool calls
5. Run locally: `python main.py` → `ws://localhost:8765`
6. Expose publicly: `ngrok http 8765` → `wss://abc123.ngrok.io`
7. Set that URL as `provider.chat_agent_details.config.url` on the Cekura agent

If the user needs a different language or framework, generate a custom server using the protocol details in `references/websocket-server-scaffold.md`.

---

## 3e. Auto-fetch from provider API (when credentials are available)

For providers with an API, fetch name, description, and language directly. **If credentials are not yet available or the fetch fails**, ask the user for the fields manually (name, language — description is handled in Phase 4).

### VAPI
```bash
curl -s https://api.vapi.ai/assistant/{assistant_id} \
  -H "Authorization: Bearer {vapi_api_key}" | jq '{name, description: (.model.messages[] | select(.role=="system") | .content), language: .transcriber.language}'
# For squads: curl -s https://api.vapi.ai/squad/{squad_id} ...
```
**Docs:** https://docs.vapi.ai/api-reference/assistants/get | https://docs.vapi.ai/api-reference/squads/get

### Retell
```bash
curl -s https://api.retellai.com/get-agent/{agent_id} \
  -H "Authorization: Bearer {retell_api_key}" | jq '{agent_name, language, response_engine}'
# retell-llm → GET /get-retell-llm/{llm_id} → .general_prompt
# conversation-flow → GET /get-conversation-flow/{flow_id} → full JSON
```
**Docs:** https://docs.retellai.com/api-references/get-agent.md

### ElevenLabs
```bash
curl -s https://api.elevenlabs.io/v1/convai/agents/{agent_id} \
  -H "xi-api-key: {elevenlabs_api_key}" | jq '{name, description: .conversation_config.agent.prompt.prompt}'
```
**Docs:** https://elevenlabs.io/docs/api-reference/conversational-ai/get-agent

### Bland
```bash
curl -s https://api.bland.ai/agents/{pathway_id} \
  -H "authorization: {bland_api_key}" | jq '{prompt, language, voice}'
```
Returns `prompt` (description) but NOT `name` — ask the user for a display name.

---

## 3f. Auto-sync description (VAPI / Retell / ElevenLabs / Synthflow)

Enable `provider.auto_sync_prompt: true` at create time (Phase 5). Cekura fetches the description from the provider within ~30 seconds. Pass a placeholder for the required `description` field.

See [Phase 4](phase4-description.md) for what makes a good description.

---

## 3g. Outbound agents (phone/SIP only)

Only relevant if using phone or SIP. If `telephony.inbound: false`, also collect:
- Auto-dial? (`provider.auto_dial_outbound: true` — VAPI, Retell, ElevenLabs, LiveKit, Bland)
- Outbound numbers: `telephony.outbound_numbers: ["+1..."]`

---

## 3h. Agent speaks first? (`agent_speaks_first`)

This field controls whether the simulated caller waits for the agent to open the conversation or speaks first. **Getting it wrong breaks every scenario** — the simulated caller and the agent will both wait for each other, or both speak at once.

- `true` — agent sends the opening message immediately on connection; simulated caller waits to hear it before responding
- `false` — simulated caller speaks first; agent waits for the first user message
- `null` — Cekura auto-detects (use only if genuinely uncertain)

This is especially important for **WebSocket agents**: the connection is bidirectional and Cekura needs to know who initiates so scenarios are written correctly from the start.

**Try to determine from code first:**

- Code sends a message immediately on connection before any incoming message is received → `true`
- Code enters a receive loop and waits for the first incoming message before doing anything → `false`
- System prompt or startup code has an explicit greeting or opening line → `true`

**If it cannot be determined from code**, ask the user:

> "When a client connects to your agent, does your agent send a greeting immediately — or does it wait for the user to speak first?"

- Agent opens with a greeting → `true`
- Agent waits for the user → `false`
- Varies or unclear → `null`

---

## Phase 3 Gate

**Do not proceed until you have: name, language, connection type confirmed, and phone number (if using phone/SIP). Description can be a placeholder if using auto-sync.**

Announce: "Phase 3 complete." Then immediately begin the next phase without waiting for the user:
- Collecting description manually → [Phase 4 — Agent Description](phase4-description.md)
- Using auto-sync → [Phase 5 — Create the Agent](phase5-create.md)

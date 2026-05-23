# Phase 3 — Main Agent Basics & Connection Type

Collect the fields needed to identify the main agent and determine how Cekura will connect to it. Connection type is part of basics — the phone number itself is a connection choice.

---

> **Start:** Announce "Starting Phase 3 — Main Agent Basics & Connection Type" before doing anything in this phase.

## 3a. Fields to collect

**Truly required** (API will reject without these):

| Field | API field | Notes |
|-------|-----------|-------|
| **Agent name** | `name` | Infer from code/config first — see 3a-name. Only ask the user if it cannot be determined. (max 255 chars) |
| **Description** | `description` | Full system prompt — see Phase 4. Placeholder OK if using auto-sync. |
| **Project** | `project` | Project ID from Phase 1 |

**Also collect:**

| Field | Notes |
|-------|-------|
| **Language** | Always — see 3a-lang |
| **Connection type** | Decide this first (see 3c) — it determines everything else below |

Connection type sets what telephony fields to collect:

| Connection type | Fields to set |
|----------------|--------------|
| **Phone (PSTN)** | `telephony.phone_number` (E.164) + `telephony.inbound` |
| **SIP** | `telephony.sip_uri` + `telephony.inbound` + optional `telephony.sip_auth` |
| **WebRTC** | Provider-specific credential (see 3c) — no telephony block |
| **WebSocket (voice)** | e.g. Chirp raw PCM, ElevenLabs voice WebSocket — may include `telephony.phone_number` if phone-linked; set `credentials.config` for the WebSocket endpoint |
| **WebSocket (chat/text)** | `provider.chat_agent_details` — no telephony block |
| **Chat (provider)** | `provider.chat_agent_details` — no telephony block |

Phone number is the connection itself for PSTN — it is not a separate field to collect after picking a connection type. SIP uses `sip_uri`, not `phone_number`. Text/chat WebSocket omits the telephony block entirely. Voice WebSocket may still have a phone number if the provider links one.

### 3a-name. Agent name — infer first, ask only if needed

**If code is available**, infer the name from:
- Named constants or variables: `AGENT_NAME`, `BOT_NAME`, `SERVICE_NAME`
- Config files or environment variables that name the main agent
- The main agent's persona in the system prompt (e.g. "You are Alex, a support agent for Acme")
- README or project documentation
- The greeting the main agent uses to open a call
- The filename or class name if descriptive

**If using a cloud provider**, the name is returned by the provider's API (see 3e auto-fetch) — use that directly.

**Only ask the user for a name if it cannot be determined from any of the above.** When asking, ask for a descriptive name that reflects what the main agent does — not a technical identifier.

### 3a-lang. Language selection — explore properly

Do not assume `en`. Actively determine what languages the main agent supports:

**Step 1 — Look for explicit language signals only**

Valid signals — things that directly describe what language the main agent uses:
- Explicit instructions in the system prompt: "respond in Hindi", "always reply in Spanish"
- A language constant or config value tied to main agent behaviour: `LANGUAGE = "hi"`, `agent_language = "es"`
- Language-switching rules in the prompt: "if the testing agent speaks Hindi, respond in Hindi"
- Non-English content in the system prompt itself (the prompt text, not code comments)

**Not valid signals — do not use these:**
- The programming language the codebase is written in
- English variable names, function names, or log messages
- English comments in the code
- The fact that code identifiers are in ASCII

The language of the codebase tells you nothing about the language the main agent speaks. Only explicit agent-facing configuration counts.

If no explicit signal is found → skip to Step 2.

**Step 2 — Ask the user directly**

Ask two questions:

1. "What language(s) does your main agent support? Does it handle only English, or can it respond in multiple languages?"

2. "Is the language fixed for this main agent, or determined at runtime — for example by a runtime variable, configuration passed at call start, or something that varies per run?"

If language is determined at runtime (not baked into the main agent) → use `"multi"` regardless of what languages are actually supported. The agent's language varies per run, so a fixed code would be wrong.

**Step 3 — Set the correct value**

| Situation | `language` value |
|-----------|-----------------|
| Agent only handles English, fixed | `en` |
| Agent only handles one specific language, fixed | BCP-47 code for that language |
| Agent handles 2+ languages, or detects/switches based on caller | `multi` |
| Agent has a prompt with language-switching rules | `multi` |
| Language is determined at runtime (personality, test profile, dynamic variable) | `multi` |

Available codes: `af ar bn bg zh cs da nl en et fi fr de el gu hi he hu id it ja kn ko ms ml mr multi no pl pa pt ro ru sk es sv th tr tl ta te uk vi`

`multi` is the safe default for any main agent whose language is not fixed and known at setup time.

**Simple rule:** if the main agent uses an LLM to generate responses, or if it serves callers across multiple locales — use `multi`.

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
- **Phone number**: config files, environment variables, README, or — for cloud providers — fetch it directly from the provider API (see below)
- **SIP URI**: config files or environment variables
- **Connection headers / auth**: any auth tokens or headers the main agent requires on the incoming connection
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

> **For WebSocket, WebRTC, and chat-only modes: `telephony.phone_number`, `telephony.inbound`, and the entire `telephony` block must NOT be set — not even with a placeholder value.** These fields are phone/SIP-only. Setting them for non-telephony main agents is incorrect.

A single main agent can support multiple connection modes (e.g. phone + WebSocket). Ask the user which they want to use.

> **WebSocket endpoint: the server must be running and publicly reachable before Phase 5.**
>
> There is exactly one path forward: get a working `wss://` URL now. There are no alternatives that involve deferring.
>
> - **If the user has a running public URL** → verify it is reachable and speaks Cekura's WebSocket protocol (JSON text frames: `{"content": "..."}` in, `{"content": "..."}` out). If it is not reachable or uses a different protocol format, treat it as if no URL exists and fall back to creating a local server with ngrok below.
> - **If the production URL exists but is broken or incompatible** → do not try to fix the production server. Create a local WebSocket server instead, expose via ngrok, and use that URL for Cekura testing.
> - **If the server is local only** → run the following yourself using Bash, do not ask the user to do it:
>   1. Start the server in the background using `run_in_background: true`
>   2. Start ngrok in the background: `ngrok http <port> --log=stdout` and capture output to parse the forwarding URL
>   3. Extract the `wss://` URL from ngrok output (the `https://` forwarding URL with `https` replaced by `wss`)
>   4. Continue with that URL
> - **If no server exists** → scaffold one, start it in the background, start ngrok, extract URL, continue
>
> **Never present "create with placeholder URL" or "fill in later" as an option.** There is no such option in this skill. The setup ends with a live verification run — without a working URL, the whole session is wasted. If the server is local, ngrok solves it immediately. Run it yourself — do not give the user terminal commands to run.

### Phone number and inbound/outbound — fetch from provider API

For any cloud provider with an API, fetch phone number and inbound/outbound direction before asking the user. Every major provider exposes a phone number list endpoint — query it and filter by the main agent/squad ID to find the associated number and its direction configuration.

**General approach for all providers:**
1. Call the provider's phone number list endpoint with the API key
2. Filter results by the main agent ID or squad ID
3. Extract: phone number + whether it's configured for inbound or outbound
4. Check the agent config itself as a fallback — outbound main agents typically have an explicit `first_message`, `dial` setting, or outbound flag; inbound agents wait for the caller

**Provider-specific endpoints:**

**VAPI:**
```bash
curl -s https://api.vapi.ai/phone-number \
  -H "Authorization: Bearer {vapi_api_key}" | jq '.[] | select(.assistantId=="{id}" or .squadId=="{id}") | {number, inboundEnabled: .inboundPhoneCallEnabled, outboundEnabled: .outboundPhoneCallEnabled}'
```

**Retell:**
```bash
curl -s https://api.retellai.com/v2/list-phone-numbers \
  -H "Authorization: Bearer {retell_api_key}" | jq '.[] | select(.agent_id=="{agent_id}") | {phone_number, inbound_agent_id, outbound_agent_id}'
```

**ElevenLabs:** check `conversation_config.phone` in the main agent details response.

**Bland, Trillet, Synthflow, and other providers:** check the provider's phone number or agent API for linked numbers and direction configuration. If the provider docs or API doesn't expose this, check the main agent's config object for inbound/outbound flags.

Only ask the user for phone number or inbound/outbound if the provider API genuinely doesn't return it.

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

> **Retell:** In Retell Dashboard, use "Copy as chat agent" to create a separate text-mode agent, then use that main agent's ID here.

---

## 3d-ws. Scaffold a WebSocket server (if user doesn't have one)

**The WebSocket server must be an exact behavioural replica of the main agent — no approximations.** When Cekura runs test scenarios against this server, the conversations must behave identically to what a real caller would experience. This means:

- **Exact system prompt** — use the full, unmodified system prompt from Phase 4, not a summary or simplified version
- **Exact tools** — every tool the main agent calls must be wired up in the server, calling Cekura's mock tool endpoints so responses match what the main agent expects
- **Exact greeting** — if the main agent speaks first, the server must send the same opening message
- **Exact dynamic variable handling** — the server must read and inject dynamic variables exactly as the main agent does
- **Exact language and model** — use the same LLM, same language settings where possible

Any approximation here means the test scenarios won't reflect main agent behaviour, and the verification run proves nothing meaningful.

**Design principle: one server, all scenarios.** Everything that varies between scenarios (caller state, account data, flow type, language, feature flags) must be parameterized — the server reads these from Cekura's per-run context and adapts accordingly. Cekura injects the right values per run.

**Step 1 — Extract the exact main agent configuration from Phase 4**

From the description synthesised in Phase 4, extract:
- The complete, unmodified system prompt
- Every tool definition (name, parameters, what the main agent sends, what it expects back)
- The greeting/opening message (if main agent speaks first)
- Any dynamic variable slots that need to be read per-run

**Step 2 — Build the server as an exact replica**

Use the **official Cekura WebSocket server example repo**:

> **https://github.com/cekura-ai/llm-websocket-server-example**

Wire it up with:
- The exact system prompt from Phase 4
- Each tool calling `https://api.cekura.ai/test_framework/v1/aiagents/{agent_id}/tool/{tool_name}/` (Cekura mock tool endpoint) so responses are controlled
- Dynamic variable injection matching how the main agent reads them
- The exact opening message if the main agent speaks first

**Step 3 — Register all parameters as dynamic variables in Cekura**

Every value the server reads per-run that isn't hardcoded must be registered as a dynamic variable (Phase 8). Cekura will generate appropriate values and pass them to the server at the start of each run.

**Step 4 — Expose publicly**

Run locally and expose via ngrok or Cloudflare Tunnel to get a public `wss://` URL. Set that URL as `provider.chat_agent_details.config.url` on the Cekura agent.

See `references/websocket-server-scaffold.md` for protocol details and code scaffolds.

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

## 3g. Outbound main agents (phone/SIP only)

Only relevant if using phone or SIP. If `telephony.inbound: false`, also collect:
- Auto-dial? (`provider.auto_dial_outbound: true` — VAPI, Retell, ElevenLabs, LiveKit, Bland)
- Outbound numbers: `telephony.outbound_numbers: ["+1..."]`

---

## 3h. Agent speaks first? (`agent_speaks_first`)

This field controls whether the testing agent waits for the agent to open the conversation or speaks first. **Getting it wrong breaks every scenario** — the testing agent and the agent will both wait for each other, or both speak at once.

- `true` — agent sends the opening message immediately on connection; testing agent waits to hear it before responding
- `false` — testing agent speaks first; main agent waits for the first testing agent message
- `null` — Cekura auto-detects (use only if genuinely uncertain)

This is especially important for **WebSocket main agents**: the connection is bidirectional and Cekura needs to know who initiates so scenarios are written correctly from the start.

**Try to determine from code first:**

- Code sends a message immediately on connection before any incoming message is received → `true`
- Code enters a receive loop and waits for the first incoming message before doing anything → `false`
- System prompt or startup code has an explicit greeting or opening line → `true`

**If it cannot be determined from code**, ask the user:

> "When a client connects to your main agent, does your main agent send a greeting immediately — or does it wait for the user to speak first?"

- Agent opens with a greeting → `true`
- Main agent waits for testing agent → `false`
- Varies or unclear → `null`

---

## Phase 3 Gate

**Do not proceed until you have: name, language, connection type confirmed, and phone number (if using phone/SIP). Description can be a placeholder if using auto-sync.**

Announce: "Phase 3 complete." Then immediately begin the next phase without waiting for the user:
- Collecting description manually → [Phase 4 — Agent Description](phase4-description.md)
- Using auto-sync → [Phase 5 — Create the Agent](phase5-create.md)

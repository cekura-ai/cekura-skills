---
name: cekura-create-agent
description: >
  Use when the user asks to "create an agent", "set up an agent", "add my agent to Cekura",
  "configure my voice agent", "connect my agent", "set up mock tools", "add tools to my agent",
  "upload knowledge base", "configure integration", "connect VAPI", "connect Retell",
  "connect LiveKit", "connect ElevenLabs", "add dynamic variables", or needs to onboard
  a voice AI agent onto the Cekura platform. Covers the full agent setup flow: project
  selection, description collection, provider integration, connection type, mock tools,
  knowledge base, dynamic variables, and advanced configuration.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.4.0"
---

# Cekura Create Agent

## Purpose

Walk the user through setting up their voice AI agent on Cekura end-to-end: project context, agent creation, provider integration, mock tools, knowledge base, dynamic variables, and advanced configuration — all in one guided flow.

## Performing Platform Actions

When this skill suggests creating, listing, or updating something, **prefer using available platform tools** (`mcp__cekura__*`) over describing API calls. Fall back to direct API or dashboard guidance only when no tools are available in the session.

## How to Use This Skill

This is an **interactive, multi-phase flow**. Collect what you need conversationally — don't dump a form. The user may have partially completed setup; skip what's already done. Validate each phase before moving to the next.

---

## Phase 1 — Project Selection

If the user doesn't know their project ID, list their projects:

```
mcp__cekura__projects_list → pick the right project → note project_id
```

Ask: "Which Cekura project should this agent live in? I can list your projects if needed."

---

## Phase 2 — Agent Basics

Collect these before doing anything else:

| Field | Notes |
|-------|-------|
| **Agent name** | Descriptive: "Customer Support Bot", "Scheduling Assistant" |
| **Language** | Primary language (default `en`). Codes: `af ar bn bg zh cs da nl en et fi fr de el gu hi he hu id it ja kn ko ms ml mr multi no pl pa pt ro ru sk es sv th tr ta te uk vi` |
| **Inbound vs Outbound** | Does the agent receive calls (`inbound: true`) or make calls (`inbound: false`)? |
| **Contact number** | Format `+1234567890` (8–30 chars). Skip if WebRTC/WebSocket-only. |

For **outbound agents**, also ask:
- Should Cekura auto-trigger outbound calls? (`outbound_auto_call: true`)
- What number(s) should be called? (`outbound_numbers: ["+1..."]`)
- Works with VAPI and Retell only.

---

## Phase 3 — Agent Description

The description is the **most important field**. It powers:
- Automatic evaluator generation
- Metrics that reference `{{agent.description}}`
- Topic/dropoff classification
- Hallucination detection

Ask: "Can you paste your agent's full system prompt or exported config?"

**Provider-specific exports:**
- **Retell**: Agents → Select → Export → downloads `.json`
- **VAPI**: Workflows → Select → Code button → Copy full JSON
- **Multi-state agents**: Paste the complete JSON (all nodes and transitions)
- **Custom/self-hosted**: Paste the full system prompt text

If the description contains `{{variableName}}` patterns, Cekura auto-detects them as dynamic variables (see Phase 9).

**No truncation.** Descriptions >10 KB are fine — Cekura handles them. See Phase 4 for the large-payload workaround.

---

## Phase 4 — Create the Agent

Once you have basics and description, create the agent:

```json
POST /test_framework/v1/aiagents/
{
  "agent_name": "Customer Support Bot",
  "project": 123,
  "language": "en",
  "description": "<full system prompt or exported config>",
  "contact_number": "+14155551234",
  "inbound": true
}
```

Save the returned `id` — needed for all subsequent steps.

### Large Description (>4 KB) — Curl Fallback

MCP tools URL-encode parameters and hit nginx's URI length limit on large payloads. Use curl instead:

```bash
curl -X POST https://api.cekura.ai/test_framework/v1/aiagents/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @agent.json
```

Or use the included helper:
```bash
scripts/upload-agent.sh agent.json            # create
scripts/upload-agent.sh agent.json <id>       # update existing
```

---

## Phase 5 — Provider Integration

Ask: "What provider does your agent use? (VAPI, Retell, ElevenLabs, LiveKit, Pipecat, SIP, or custom/self-hosted?)"

Then collect credentials and configure. Full per-provider field lists are in `references/integrations.md`.

### Quick Reference — Required Fields by Provider

| Provider | `assistant_provider` | Key Fields |
|----------|---------------------|------------|
| **VAPI** | `vapi` | `vapi_api_key`, `assistant_id` |
| **Retell** | `retell` | `retell_api_key`, `assistant_id` |
| **ElevenLabs** | `elevenlabs` | `elevenlabs_api_key`, `assistant_id` |
| **LiveKit** | `livekit` | `livekit_api_key`, `livekit_data` (JSON: `api_secret`, `url`) |
| **Pipecat** | `pipecat` | `pipecat_api_key`, `contact_number` = agent name (not phone) |
| **SIP** | `self_hosted` | `sip_endpoint` (e.g., `sip:agent@domain.com`) |
| **Custom webhook** | (none) | Client pushes calls to `/observability/v1/observe/` |

Always set `transcript_provider` to match `assistant_provider` (controls call data ingestion).

### Where to Find Credentials

| Provider | API Key | Assistant ID |
|----------|---------|--------------|
| VAPI | Dashboard → Organization Settings → API Keys → Private Key | Assistants → Select → copy from URL |
| Retell | Settings → API Keys | Agents → Select → ID in URL |
| ElevenLabs | Profile → API Keys | Conversational AI → Select → ID in settings |
| LiveKit | Cloud Dashboard → Settings → Keys | N/A (use agent name instead) |
| Pipecat | pipecat.daily.co → Settings → API Keys | N/A |

### Apply via PATCH

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

### Optional Automation

| Option | Providers | What It Does |
|--------|-----------|--------------|
| `auto_fetch_calls_enabled: true` | VAPI, Retell | Auto-imports production calls every ~30–60 seconds for observability |
| `auto_sync_prompt_enabled: true` | Retell only | Auto-syncs agent prompt changes every 30 seconds |

---

## Phase 6 — Connection Type

After setting the provider, confirm how Cekura will connect to the agent:

| Mode | Use For | Setup |
|------|---------|-------|
| **Phone (PSTN)** | Any phone-based agent | `contact_number` already set in Phase 2 |
| **WebRTC** | VAPI, Retell, ElevenLabs, LiveKit, Pipecat | Add VAPI `public_key` for VAPI WebRTC; Cekura handles room management for LiveKit/Pipecat |
| **Chat/Text** | Fastest + cheapest (10× faster, ~90% cheaper) | Set `chat_assistant_id` (most providers) or `websocket_url` |
| **Custom WebSocket** | Self-hosted / non-standard providers | Set `websocket_url` + `websocket_headers` |

### Chat Setup per Provider

- **Retell**: In Retell, use "Copy as chat agent" → set `chat_assistant_id` to chat agent ID
- **VAPI**: Set `chat_assistant_id` to VAPI chat assistant ID
- **ElevenLabs**: Set `chat_assistant_id` to ElevenLabs agent ID
- **Custom**: Set `websocket_url: "wss://..."` and optional `websocket_headers`

**Recommendation:** Use chat mode for rapid iteration during development. Switch to phone/WebRTC for final validation before production.

---

## Phase 7 — Mock Tools

Ask: "Does your agent call external APIs or tools during calls? (e.g., booking systems, CRMs, payment APIs)"

If yes, choose a path:

### Option A — Auto-Fetch (VAPI, Retell, ElevenLabs, Pipecat)

If provider API key + assistant ID are set:
1. Go to Agent Settings → Mock Tools → click **Auto-Fetch**
2. Cekura fetches all tool definitions from the provider and generates sample I/O data
3. Review and toggle mock mode per tool

Auto-fetch is UI-only — no direct API equivalent. Manage tools via API afterward.

### Option B — Manual Setup (all providers)

Read the agent description to find all tool names. For each tool, create a mock:

```bash
# Note: mcp__cekura__aiagents_tools_create is not available via MCP — use curl
curl -X POST https://api.cekura.ai/test_framework/v1/aiagents/{agent_id}/tools/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_user_info",
    "description": "Retrieves user data based on phone number",
    "information": [
      {
        "input": {"phone_number": "8645239892"},
        "output": {"borrower_id": "B001", "first_name": "John", "last_name": "Doe"}
      },
      {
        "input": {"phone_number": "18645239892"},
        "output": {"borrower_id": "B001", "first_name": "John", "last_name": "Doe"}
      }
    ],
    "freetext_params": ["notes", "reason"]
  }'
```

### Mock Tool Design Rules

- `name` must **exactly match** the tool name in the agent's config (max 64 chars, `[a-z0-9_-]`)
- `information` is input→output mappings — Cekura fuzzy-matches incoming calls to the closest input
- **Multiple mappings per tool** — one per distinct input the agent might send (different users, topics, error cases)
- **`freetext_params`** — skip these fields during match (free-text like "notes", "reason" that vary per call)
- **Phone format variants** — for phone lookups, add 10-digit, 11-digit-with-1, and E.164 forms
- **Chain dependencies** — if tool B uses output from tool A, mock data must be consistent across tools
- **Append-not-replace** — when adding to `information`, GET first → merge → PATCH full array; partial PATCH replaces all existing mappings

**Full design guide with examples:** `references/mock-tool-design.md`

---

## Phase 8 — Knowledge Base

Ask: "Does your agent reference any knowledge base documents? (FAQs, product guides, policy docs)"

If yes, upload via multipart form:

```bash
curl -X POST https://api.cekura.ai/test_framework/v1/aiagents/{id}/upload_knowledge_base/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -F "files=@faq.pdf" \
  -F "files=@product-guide.pdf"
```

Supported: PDF, text, documents. After upload, optionally link to hallucination detection:

```bash
curl -X PATCH https://api.cekura.ai/test_framework/v1/aiagents/{id}/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"hallucination_metric_kb_files": [<file_id_1>, <file_id_2>]}'
```

**What KB files enable:**
- More accurate evaluator generation (Cekura knows what the agent should and shouldn't say)
- Hallucination detection (responses compared against KB content)
- Richer test scenarios that exercise knowledge retrieval

---

## Phase 9 — Dynamic Variables

Ask: "Does your agent use per-call variables? (e.g., customer name, account ID, different prompts per call flow)"

### Auto-Detection

If the agent description contains `{{variableName}}` patterns, Cekura detects them automatically after agent creation. Check the agent object for detected variables.

### What Dynamic Variables Enable

- **Per-call system prompt injection** — different instructions per caller segment
- **Caller-specific data** — inject name, account ID, employment type, etc.
- **Multi-node / multi-state agents** — use one dynamic variable per node's system prompt instead of embedding all prompts in the description
- **Feature flags** — enable/disable behaviors per call
- **Context injection** — prior call summaries, reconnection context

### Usage Pattern

In the agent description, place `{{variableName}}` where the value should be injected:

```
You are a scheduling assistant. Customer name: {{customer_name}}.
Account type: {{account_type}}.
```

At test time, test profiles supply the values:
```json
{ "customer_name": "Jane Smith", "account_type": "premium" }
```

**Multi-node pattern:** For agents with distinct states (intake, scheduling, billing), store each node's prompt as a separate dynamic variable. Metrics can then reference `{{dynamic_variables.nodeName}}` to evaluate per-node behavior instead of the full description.

---

## Phase 10 — Advanced Configuration

These are optional but valuable for specific use cases:

### LLM Simulation Model

Controls which model simulates the caller during text/chat evaluations:

```json
{
  "llm_model": "gpt-4o",
  "llm_temperature": 0.0,
  "llm_max_tokens": 4096,
  "llm_system_prompt": "<optional: custom caller persona prompt>"
}
```

Options: `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`, `claude-sonnet-4-5`. Default temperature is `0.0` for consistent, reproducible tests.

### Topic Classification

Tell Cekura what topics the agent handles and how calls should be routed:

```json
{
  "topic_nodes": {"billing": "handle_billing", "scheduling": "book_appointment"},
  "auto_update_topic_nodes": true
}
```

`auto_update_topic_nodes: true` infers topic nodes from the agent description automatically.

### Dropoff Detection

Track where callers disengage or abandon the flow:

```json
{
  "dropoff_nodes": {"timeout": 30, "no_response": 15},
  "auto_update_dropoff_nodes": true
}
```

### Pronunciation & Spelling Analysis

For agents that spell out words or names:

```json
{
  "pronunciation_words": [["VAPI", "VAY-pee"], ["Cekura", "SEH-kyoo-rah"]],
  "spelling_word_types": ["name", "postcode", "email"]
}
```

### Outbound Agent Full Config

```json
{
  "inbound": false,
  "outbound_auto_call": true,
  "outbound_numbers": ["+14155551234"]
}
```

Test profile fields are forwarded as dynamic variables when the outbound call is triggered (VAPI and Retell only).

---

## Phase 11 — Verify Setup

After all phases, confirm the agent is ready:

1. GET the agent — verify description, provider, contact number
2. Check provider fields — `assistant_provider`, API key, `assistant_id` present
3. List mock tools — confirm all tools have `information` mappings
4. Check `knowledge_base_files` on the agent object
5. Confirm dynamic variables were detected or manually added
6. Run one simple evaluator to verify end-to-end connectivity

**Verification summary for the user:**

```
Agent: [name] (ID: [id])
Project: [project_id]
Provider: [provider] (assistant: [assistant_id])
Connection mode: [phone/WebRTC/chat]
Mock tools: [count] configured
Knowledge base: [count] files
Dynamic variables: [list or "none detected"]
Advanced: [LLM model / topic nodes / etc. if configured]

Ready for:
  → Generate evaluators: cekura-eval-design skill
  → Create metrics: cekura-metric-design skill
  → Full platform walkthrough: cekura-onboarding skill
```

---

## API Access — Cekura MCP Server

**Prerequisites:** Cekura account + API key or OAuth. Configure MCP:
```bash
claude mcp add --transport http cekura --scope user https://api.cekura.ai/mcp
```

**Tools used in this skill:**

| Tool | Purpose |
|------|---------|
| `mcp__cekura__projects_list` | List projects to find project ID |
| `mcp__cekura__aiagents_create` | Create the agent (small descriptions) |
| `mcp__cekura__aiagents_partial_update` | Configure provider, options |
| `mcp__cekura__aiagents_retrieve` | Verify agent state |
| `mcp__cekura__aiagents_tools_list` | List mock tools |
| `mcp__cekura__aiagents_upload_knowledge_base` | Upload KB files |
| `Bash` | curl for large descriptions, tool creation (MCP limitation) |

**Known MCP Limitations:**
- `aiagents_create` — 414 URI Too Long on descriptions >4 KB. Use curl / `scripts/upload-agent.sh`.
- `aiagents_tools_create` — Not exposed by MCP. Always use curl for mock tool creation.

**Docs:** https://docs.cekura.ai/documentation/integrations/ | https://docs.cekura.ai/mcp/overview

---

## Reference Files

- **`references/integrations.md`** — Full per-provider field lists, chat setup, WebSocket format, outbound config, provider comparison table
- **`references/mock-tool-design.md`** — Per-input branching examples, chain dependency design, append-not-replace pattern
- **`references/api-reference.md`** — Complete agent API endpoints, all field schemas, mock tool and KB endpoints
- **`scripts/upload-agent.sh`** — Curl wrapper for creating/updating agents with large system prompts

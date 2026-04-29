---
name: cekura-create-agent
description: >
  Use when the user asks to "create an agent", "set up an agent", "add my agent to Cekura",
  "configure my voice agent", "connect my agent", "set up mock tools", "add tools to my agent",
  "upload knowledge base", "configure integration", "connect VAPI", "connect Retell",
  "connect LiveKit", "connect ElevenLabs", "add dynamic variables", or needs to onboard
  a voice AI agent onto the Cekura platform. Covers the full agent setup flow: collecting
  context, creating the agent, configuring the provider integration, setting up mock tools,
  uploading knowledge base files, and adding dynamic variables.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Create Agent

## Purpose

Collect comprehensive context about a client's voice AI agent and set it up on Cekura — ready for testing and observability. This is an interactive, multi-step flow that creates the agent, configures provider integration, sets up mock tools, uploads knowledge base files, and adds dynamic variables.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## How to Use This Skill

This is an **interactive collection-and-configuration flow**. Walk the user through each phase:

1. Collect information conversationally — ask for what you need, don't dump a form
2. Perform each step via the Cekura API or dashboard
3. Validate each step before moving to the next
4. The user may already have some steps done — skip what's complete

## Phase 1: Collect Agent Context

### 1.1 Basic Information

Ask for these essentials:
- **Agent name** — Descriptive (e.g., "Customer Support Bot", "Scheduling Assistant")
- **Project ID** — Which Cekura project to add the agent to. If they don't know, list their projects first.
- **Language** — Primary language (default "en"). Supported: af, ar, bn, bg, zh, cs, da, nl, en, et, fi, fr, de, el, gu, hi, he, hu, id, it, ja, kn, ko, ms, ml, mr, multi, no, pl, pa, pt, ro, ru, sk, es, sv, th, tr, ta, te, uk, vi
- **Inbound vs Outbound** — Does the agent receive calls (`inbound: true`, default) or make calls (`inbound: false`)?

### 1.2 Agent Description (Critical)

The agent description is the **most important field**. It powers:
- Automatic evaluator generation
- Metrics that reference `{{agent.description}}`
- Topic/dropoff classification
- Hallucination detection

**Collect the full system prompt.** Ask:
- "Can you paste your agent's full system prompt or agent description?"
- "If your agent has multiple states/nodes, paste the complete configuration (JSON or text)"

**Provider-specific exports:**
- **Retell**: Agents → Select agent → Export (downloads `.json`)
- **VAPI**: Workflows → Select agent → Code button → Copy
- **Multi-state agents**: Can be structured as JSON array
- **Workflow agents**: Paste the full exported workflow JSON

**If the description is very long (>10K chars),** that's fine — Cekura handles it. Don't truncate.

### 1.3 Contact Number (for phone-based agents)

Format: `+1234567890` (must start with `+`, 8-30 chars). This is the number Cekura will call for testing.

Ask: "What's your agent's phone number? This is the number Cekura will call during tests."

If WebRTC/WebSocket only (no phone), this can be skipped.

## Phase 2: Create the Agent

Once you have the basics, create the agent (POST to `/test_framework/v1/aiagents/`) with:

```json
{
  "agent_name": "Customer Support Bot",
  "project": 123,
  "language": "en",
  "description": "<full system prompt>",
  "contact_number": "+14155551234",
  "inbound": true
}
```

Save the returned `id` — you'll need it for all subsequent steps.

### Handling Large Agent Descriptions

For agent descriptions longer than ~4 KB (multi-state agents, full system prompts, exported workflows), send the request as a direct JSON body via the API rather than relying on tools that may URL-encode parameters — large URL-encoded payloads can hit URI length limits.

```bash
curl -X POST https://api.cekura.ai/test_framework/v1/aiagents/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @agent.json
```

Where `agent.json` contains the full payload (including the long `description`). This is the safest way to create agents with long system prompts or large state-machine configs.

## Phase 3: Configure Provider Integration

Ask: "What provider does your agent use? (VAPI, Retell, ElevenLabs, LiveKit, Pipecat, SIP, or custom?)"

Then collect provider-specific credentials and configure. See `references/integrations.md` for full details on each provider.

### Quick Reference — Required Fields by Provider

| Provider | Key Fields |
|----------|-----------|
| **VAPI** | `vapi_api_key`, `assistant_id` |
| **Retell** | `retell_api_key`, `assistant_id` |
| **ElevenLabs** | `elevenlabs_api_key`, `assistant_id` |
| **LiveKit** | `livekit_api_key`, `livekit_data` (JSON with `api_secret`, `url`) |
| **Pipecat** | `pipecat_api_key`, agent name as `contact_number` |
| **SIP** | `sip_endpoint`, optionally `sip_auth` |
| **Custom** | Webhook URL — they push calls to Cekura |

**Apply via** PATCH `/test_framework/v1/aiagents/{id}/`:

```json
{
  "assistant_provider": "vapi",
  "vapi_api_key": "...",
  "assistant_id": "asst_...",
  "transcript_provider": "vapi"
}
```

### Connection Type

After setting the provider, confirm the connection type:
- **Phone (PSTN)** — Add phone number via `contact_number` field. Simplest.
- **WebRTC / SDK** — For LiveKit, Pipecat, ElevenLabs WebSocket. Lower latency.
- **Chat / WebSocket** — Text-based testing. 10x faster, 90% cheaper than voice. Set `chat_assistant_id` and/or `websocket_url`.

Recommend chat/text for initial iteration, voice for final validation.

### Optional: Auto-Fetch and Auto-Sync

For VAPI/Retell, offer to enable:
- `auto_fetch_calls_enabled: true` — Auto-imports production calls every 30 seconds (for observability)
- `auto_sync_prompt_enabled: true` — (Retell only) Auto-syncs prompt changes every 30 seconds

## Phase 4: Set Up Mock Tools

Ask: "Does your agent call external APIs or tools during calls? (e.g., booking systems, CRMs, payment APIs)"

If yes, there are two paths:

### Option A: Auto-Fetch (Recommended for VAPI/Retell/ElevenLabs)

If the provider integration is configured with API key + assistant ID:
1. Tell the user to go to Agent Settings → Mock Tools → click "Auto-Fetch"
2. Cekura fetches all tool definitions from the provider and generates sample I/O data
3. The user can then toggle mock mode per tool

**Note:** Auto-fetch is done in the UI — there's no API-only equivalent. After auto-fetch, you can manage tools via API.

### Option B: Manual Setup (for all providers)

For each tool the agent uses:

1. **Identify tools** — Read the agent description to find all tool references. Ask: "What tools does your agent call? Give me the tool names and what each one does."

2. **Create each mock tool** (POST to `/test_framework/v1/aiagents/{agent_id}/tools/`):

```json
{
  "name": "get_user_info",
  "description": "Retrieves user data based on phone number or user ID",
  "information": [
    {
      "input": {"phone_number": "8645239892"},
      "output": {"borrower_id": "B001", "first_name": "John", "last_name": "Doe", "dob": "01/15/1990"}
    },
    {
      "input": {"phone_number": "18645239892"},
      "output": {"borrower_id": "B001", "first_name": "John", "last_name": "Doe", "dob": "01/15/1990"}
    }
  ],
  "freetext_params": ["notes", "reason"]
}
```

**Key rules:**
- **`name`** must exactly match the tool name in the agent description (max 64 chars, alphanumeric + underscores + hyphens)
- **`information`** is an array of input/output mappings — Cekura matches incoming tool calls to the closest input and returns the corresponding output
- **`freetext_params`** — Parameter names that should be skipped during mock matching (free-text fields like "notes" or "reason" that vary per call)
- **Phone format variants** — For phone-based lookups, add mappings for ALL variants: 10-digit, 11-digit with leading 1, and full E.164
- **Chain dependencies** — If tool B depends on output from tool A (e.g., `get_loans` needs `borrower_id` from `get_user_info`), the mock data must be consistent across tools

### Per-Input Branching — Mock Tools Need Multiple Mappings

**A single input/output mapping per tool is NOT enough.** Each tool needs entries for every distinct input the agent might send during testing. If a tool accepts different parameters that should return different results, each variant needs its own mapping.

**Example:** A `load_game_info` tool that returns different content based on a `topic` parameter:

```json
{
  "name": "load_game_info",
  "description": "Loads game information by topic",
  "information": [
    {
      "input": {"topic": "lore"},
      "output": {"title": "World Lore", "content": "The galaxy was colonized in 2847..."}
    },
    {
      "input": {"topic": "combat"},
      "output": {"title": "Combat Guide", "content": "Weapons have three tiers: basic, advanced, elite..."}
    },
    {
      "input": {"topic": "trading"},
      "output": {"title": "Trading Manual", "content": "Credits can be earned through cargo runs..."}
    }
  ]
}
```

**When designing mock data, think about:**
- What different inputs will the agent send to this tool across all test scenarios?
- What should each distinct input return?
- What error cases matter? (Add a mapping with an error response for tool-failure scenarios)

If you only create one mapping, every tool call — regardless of input — returns the same output. This masks bugs where the agent sends the wrong parameters.

### Tool Data Design

Help the user design mock data by asking:
1. "What are the main tools and what data do they expect as input?"
2. "For each tool, what are the different inputs the agent might send?" (different users, topics, actions, error cases)
3. "What should each distinct input return?"
4. "Do any tools depend on data from other tools?" (chain dependencies — downstream tool inputs must match upstream tool outputs)

For each scenario the user wants to test, they'll need a matching set of mock data across all related tools. Plan the full data graph: user lookup → account data → transaction history → payment methods. All IDs and references must be consistent.

### Critical: Append-Not-Replace

When updating a tool's `information` array to add new scenario data:
1. GET the existing tool to get current mappings
2. Append new mappings to the existing array
3. PATCH with the full combined array

A PATCH with only new mappings **replaces ALL existing mappings**.

## Phase 5: Upload Knowledge Base

Ask: "Does your agent reference any knowledge base documents? (e.g., FAQs, product guides, policy docs)"

If yes, upload files via the agent knowledge base upload endpoint.

Supported formats: PDF, text files, documents.

**Purpose:** Knowledge base files enable:
- More accurate evaluator generation (Cekura understands what the agent should know)
- Hallucination detection (compare agent responses against KB content)
- Richer test scenarios that exercise KB retrieval

After upload, the files appear in Agent Settings → Agent's Knowledge.

**Optional:** Link KB files to hallucination detection by PATCHing the agent with `{"hallucination_metric_kb_files": [<file_id_1>, <file_id_2>]}`.

## Phase 6: Dynamic Variables

Ask: "Does your agent use per-call variables? (e.g., customer name, account ID, appointment details, different system prompts per call)"

### Auto-Detection

If the agent description contains `{{variableName}}` patterns, Cekura auto-detects them. After creating the agent, check if any were detected.

### Manual Addition

If the user has dynamic variables that aren't in the description pattern:

**Via API:** Dynamic variables are managed through the agent description. Add `{{variableName}}` placeholders to the description where the variable should be injected.

**What dynamic variables enable:**
- Per-call system prompt injection (for multi-agent flows)
- Caller-specific data (name, account ID, employment type)
- Feature flags (enable/disable features per call)
- Configuration data (reconnection context, prior call summaries)

**Key insight:** For clients with multi-agent flows where each node has its own system prompt, recommend using dynamic variables (one per node) rather than putting everything in the agent description. This enables per-node metrics using `{{dynamic_variables.nodeName}}`.

## Phase 7: Verify Setup

After all steps are complete, verify:

1. **Agent exists:** GET the agent — confirm description, provider, contact number
2. **Provider connected:** Check that `assistant_provider`, API key, and `assistant_id` are set
3. **Mock tools configured:** List tools on the agent — confirm all tools have mappings
4. **Knowledge base uploaded:** Check `knowledge_base_files` on the agent object
5. **Test connectivity:** Suggest running a single simple evaluator to confirm end-to-end connectivity

**Summary for the user:**
```
Agent: [name] (ID: [id])
Project: [project_id]
Provider: [provider] (assistant: [assistant_id])
Connection: [phone/WebRTC/chat]
Mock tools: [count] configured
Knowledge base: [count] files uploaded
Dynamic variables: [list or "none"]

Ready for: evaluator generation → cekura-eval-design skill
           metric setup → cekura-metric-design skill
```

## Documentation

- Public docs: https://docs.cekura.ai
- Integrations: https://docs.cekura.ai/documentation/integrations/
- Dashboard: https://dashboard.cekura.ai

## Additional Resources

### Reference Files

- **`references/integrations.md`** — Full provider integration details (VAPI, Retell, ElevenLabs, LiveKit, Pipecat, SIP, custom) with exact fields, gotchas, and chat setup
- **`references/api-reference.md`** — Complete agent API endpoints and schemas

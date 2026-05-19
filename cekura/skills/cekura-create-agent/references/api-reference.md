# Agent API Reference

## Authentication
All requests: `X-CEKURA-API-KEY: <key>` header. Base URL: `https://api.cekura.ai`

## Agent CRUD

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v2/aiagents/` | Create agent |
| GET | `/test_framework/v2/aiagents/` | List agents (`?project_id=X`) |
| GET | `/test_framework/v2/aiagents/{id}/` | Get agent details |
| PATCH | `/test_framework/v2/aiagents/{id}/` | Partial update (preferred for config changes) |
| PUT | `/test_framework/v2/aiagents/{id}/` | Full update |
| DELETE | `/test_framework/v2/aiagents/{id}/` | Delete agent |
| POST | `/test_framework/v2/aiagents/{id}/duplicate/` | Duplicate agent |

**Note:** Endpoint is `/aiagents/`, NOT `/agents/`.

## Create Agent Schema (v2)

```json
POST /test_framework/v2/aiagents/
{
  "name": "string (required, max 255 chars)",
  "description": "string (required — agent system prompt)",
  "inbound": "boolean (required)",
  "project": "integer (project ID)",
  "language": "string (default 'en')",
  "phone_number": "string (E.164, e.g. '+14155551234')",
  "sip_uri": "string (e.g. 'sip:agent@domain.com')",
  "sip_auth": {"username": "...", "password": "..."},
  "agent_speaks_first": "boolean|null (null = auto-detect)",
  "provider": {
    "type": "vapi|retell|elevenlabs|bland|livekit|agentforce|trillet|self_hosted|...",
    "agent_id": "string (voice/phone agent ID on provider platform)",
    "chat_agent_id": "string (text-mode agent ID — Retell only, optional)",
    "credentials": {
      "api_key": "string (write-only)",
      "config": { ... provider-specific keys ... }
    }
  },
  "transcript_provider": "string (defaults to provider.type)"
}
```

## credentials.config Keys by Provider

| Provider | Required | Optional |
|----------|---------|---------|
| `vapi` | — | `public_key`, `trigger_url` |
| `retell` | — | `trigger_url` |
| `elevenlabs` | — | `trigger_url` |
| `bland` | — | `encrypted_key` (Twilio bundle) |
| `livekit` | `api_secret`, `url` | `tracing_enabled` |
| `agentforce` | `client_id`, `domain`, `agent_id` | — |
| `trillet` | `workspace_id` | — |
| `self_hosted` | `url` (wss://) | `headers` |

## Additional Agent Fields

| Field | Type | Description |
|-------|------|-------------|
| `auto_import_calls` | boolean | Auto-import production calls every 30s (VAPI/Retell) |
| `auto_sync_prompt` | boolean | Auto-sync prompt from provider every 30s (Retell only) |
| `auto_dial_outbound` | boolean | Auto-trigger outbound calls |
| `outbound_numbers` | array | Phone numbers authorized for outbound (webhook validation) |
| `llm_model` | enum | Simulation LLM: `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`, `claude-sonnet-4-5` |
| `llm_temperature` | float | 0.0–2.0 (default 0.0) |
| `llm_max_tokens` | integer | Default 4096 |
| `llm_system_prompt` | string | Custom caller persona for simulation |
| `pronunciation_words` | array | `[["word", "phoneme"]]` for pronunciation analysis |
| `spelling_word_types` | array | `["name", "postcode", "email"]` for spelling analysis |
| `topic_nodes` | object | `{"billing": "handle_billing"}` for topic classification |
| `dropoff_nodes` | object | `{"timeout": 30}` for dropoff detection |
| `auto_update_topic_nodes` | boolean | Auto-infer topics from description |
| `auto_update_dropoff_nodes` | boolean | Auto-infer dropoffs from description |
| `hallucination_metric_kb_files` | array | KB file IDs linked to hallucination detection |

## Mock Tool Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v2/aiagents/{agent_id}/tools/` | Create mock tool |
| GET | `/test_framework/v2/aiagents/{agent_id}/tools/` | List mock tools |
| GET | `/test_framework/v1/mock-tools/{tool_id}/` | Get mock tool |
| PATCH | `/test_framework/v1/mock-tools/{tool_id}/` | Update mock tool |
| DELETE | `/test_framework/v1/mock-tools/{tool_id}/` | Delete mock tool |

### Create Mock Tool Schema

```json
POST /test_framework/v2/aiagents/{agent_id}/tools/
{
  "name": "string (required, max 64 chars, alphanumeric + _ + -)",
  "description": "string (what the tool does)",
  "information": [
    {
      "input": {"param1": "value1"},
      "output": {"result1": "value1"}
    }
  ],
  "freetext_params": ["notes", "reason"]
}
```

**`name`** must exactly match the tool name in the agent description.

**`information`** is an array of input/output mappings. Each object has `input` (what the agent sends) and `output` (what the mock returns). Cekura matches incoming tool calls to the closest input and returns the corresponding output.

**`freetext_params`** — Parameter names skipped during mock matching. Use for fields that vary per call and shouldn't affect which mock response is selected (e.g., "notes", "reason", "description").

**Critical: Append-not-replace.** When PATCHing `information`, GET existing data first, merge, then PATCH the full array. A PATCH with only new entries replaces all existing ones.

## Knowledge Base

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v2/aiagents/{id}/upload_knowledge_base/` | Upload KB files |

```
POST /test_framework/v2/aiagents/{id}/upload_knowledge_base/
Content-Type: multipart/form-data

files: <file1>, <file2>
```

Supported: PDF, text files, documents. Files appear in agent's `knowledge_base_files` field.

After upload, link to hallucination detection:
```json
PATCH /test_framework/v2/aiagents/{id}/
{ "hallucination_metric_kb_files": [<file_id_1>, <file_id_2>] }
```


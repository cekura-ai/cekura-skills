# Agent API Reference

## Authentication
All requests: `X-CEKURA-API-KEY: <key>` header. Base URL: `https://api.cekura.ai`

## Agent CRUD

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/aiagents/` | Create agent |
| GET | `/test_framework/v1/aiagents/` | List agents (`?project_id=X`) |
| GET | `/test_framework/v1/aiagents/{id}/` | Get agent details |
| PATCH | `/test_framework/v1/aiagents/{id}/` | Partial update (preferred for config changes) |
| PUT | `/test_framework/v1/aiagents/{id}/` | Full update |
| DELETE | `/test_framework/v1/aiagents/{id}/` | Delete agent |
| POST | `/test_framework/v1/aiagents/{id}/duplicate/` | Duplicate agent |

**Note:** Endpoint is `/aiagents/`, NOT `/agents/`.

## Create Agent Schema

```json
POST /test_framework/v1/aiagents/
{
  "agent_name": "string (required, max 255 chars)",
  "project": "integer (project ID)",
  "language": "string (default 'en')",
  "description": "string (agent system prompt — the most important field)",
  "contact_number": "string ('+1234567890', 8-30 chars)",
  "inbound": "boolean (default true)",
  "assistant_provider": "vapi|retell|elevenlabs|livekit|pipecat|bland|self_hosted|...",
  "transcript_provider": "vapi|retell|elevenlabs|livekit|pipecat|custom|...",
  "assistant_id": "string (min 10 chars, provider assistant ID)"
}
```

## Provider-Specific Fields

### VAPI
```json
{ "vapi_api_key": "string", "vapi_data": "JSON string" }
```

### Retell
```json
{ "retell_api_key": "string", "retell_data": "JSON string", "auto_sync_prompt_enabled": "boolean" }
```

### ElevenLabs
```json
{ "elevenlabs_api_key": "string", "elevenlabs_data": "JSON string" }
```

### LiveKit
```json
{ "livekit_api_key": "string", "livekit_data": "JSON string with api_secret, url, config" }
```

### Pipecat
```json
{ "pipecat_api_key": "string", "pipecat_data": "JSON string" }
```

### SIP
```json
{ "sip_endpoint": "string (sip:agent@domain.com)", "sip_auth": {"username": "...", "password": "..."} }
```

### Chat/WebSocket
```json
{ "chat_assistant_id": "string", "websocket_url": "string (wss://...)", "websocket_headers": "object" }
```

## Additional Agent Fields

| Field | Type | Description |
|-------|------|-------------|
| `auto_fetch_calls_enabled` | boolean | Auto-import production calls (VAPI/Retell) |
| `outbound_auto_call` | boolean | Auto-trigger outbound calls |
| `outbound_numbers` | array | List of outbound phone numbers |
| `llm_model` | enum | Simulation LLM: gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini, claude-sonnet-4-5 |
| `llm_temperature` | float | 0.0-2.0 (default 0.0) |
| `llm_max_tokens` | integer | Default 4096 |
| `llm_system_prompt` | string | Custom simulation system prompt |
| `pronunciation_words` | array | `[["word", "phoneme"]]` for pronunciation analysis |
| `spelling_word_types` | array | `["name", "postcode", "email"]` for spelling analysis |
| `topic_nodes` | object | `{"billing": "handle_billing"}` for topic classification |
| `dropoff_nodes` | object | `{"timeout": 30}` for dropoff detection |
| `auto_update_topic_nodes` | boolean | Auto-update topics from description |
| `auto_update_dropoff_nodes` | boolean | Auto-update dropoffs from description |
| `hallucination_metric_kb_files` | array | KB file IDs for hallucination detection |

## Mock Tool Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/aiagents/{agent_id}/tools/` | Create mock tool |
| GET | `/test_framework/v1/aiagents/{agent_id}/tools/` | List mock tools |
| GET | `/test_framework/v1/mock-tools/{tool_id}/` | Get mock tool |
| PATCH | `/test_framework/v1/mock-tools/{tool_id}/` | Update mock tool |
| DELETE | `/test_framework/v1/mock-tools/{tool_id}/` | Delete mock tool |

### Create Mock Tool Schema

```json
POST /test_framework/v1/aiagents/{agent_id}/tools/
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
| POST | `/test_framework/v1/aiagents/{id}/upload_knowledge_base/` | Upload KB files |

```
POST /test_framework/v1/aiagents/{id}/upload_knowledge_base/
Content-Type: multipart/form-data

files: <file1>, <file2>
```

Supported: PDF, text files, documents. Files appear in agent's `knowledge_base_files` field.

After upload, link to hallucination detection:
```json
PATCH /test_framework/v1/aiagents/{id}/
{ "hallucination_metric_kb_files": [<file_id_1>, <file_id_2>] }
```

## MCP Tools

| MCP Tool | Purpose |
|----------|---------|
| `mcp__cekura__aiagents_create` | Create agent |
| `mcp__cekura__aiagents_retrieve` | Get agent |
| `mcp__cekura__aiagents_partial_update` | Update agent |
| `mcp__cekura__aiagents_update` | Full update agent |
| `mcp__cekura__aiagents_list` | List agents |
| `mcp__cekura__aiagents_destroy` | Delete agent |
| `mcp__cekura__aiagents_duplicate_create` | Duplicate agent |
| `mcp__cekura__aiagents_tool_create` | Create mock tool |
| `mcp__cekura__aiagents_tools_list` | List mock tools |
| `mcp__cekura__aiagents_tool_retrieve` | Get mock tool |
| `mcp__cekura__aiagents_tool_partial_update` | Update mock tool |
| `mcp__cekura__aiagents_tool_destroy` | Delete mock tool |
| `mcp__cekura__aiagents_upload_knowledge_base_create` | Upload KB files |
| `mcp__cekura__aiagents_mcp_create` | MCP integration |

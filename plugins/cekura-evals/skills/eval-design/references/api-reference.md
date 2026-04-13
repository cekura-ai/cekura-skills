# Cekura Evaluator/Scenario API Reference

## Authentication

All requests require header: `X-CEKURA-API-KEY: <key>`

## Base URL

`https://api.cekura.ai`

## Agent Endpoints

**Note:** The agent endpoint is `/aiagents/`, NOT `/agents/` — `/agents/` returns 404.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/test_framework/v1/aiagents/` | List agents (filter by `project_id`) |
| GET | `/test_framework/v1/aiagents/{id}/` | Get agent (includes `description` field) |
| GET | `/test_framework/v1/aiagents/{id}/tools/` | List mock tools on agent |
| PATCH | `/test_framework/v1/aiagents/{id}/tools/{tool_id}/` | Update mock tool mappings |

## Evaluator/Scenario Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/scenarios/` | Create evaluator |
| GET | `/test_framework/v1/scenarios/` | List evaluators (filter by agent/project/tags) |
| GET | `/test_framework/v1/scenarios/{id}/` | Get evaluator |
| PATCH | `/test_framework/v1/scenarios/{id}/` | Update evaluator |
| DELETE | `/test_framework/v1/scenarios/{id}/` | Delete evaluator |
| POST | `/test_framework/v1/scenarios/generate-bg/` | Auto-generate evaluators (background) |
| GET | `/test_framework/v1/scenarios/generate-progress/` | Check generation progress (`?progress_id=<id>`) |
| POST | `/test_framework/v1/scenarios/from-transcript/` | Create evaluator from call transcript |
| POST | `/test_framework/v1/scenarios/create_folder/` | Create scenario folder |
| POST | `/test_framework/v1/scenarios/delete_folder/` | Delete scenario folder |
| POST | `/test_framework/v1/scenarios/rename_folder/` | Rename scenario folder |
| POST | `/test_framework/v1/scenarios/move_folder/` | Move scenario to folder |
| GET | `/test_framework/v1/scenarios/folders/` | List scenario folders |

## Execution Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/scenarios/run_scenarios/` | Batch run multiple scenarios (preferred) |
| POST | `/test_framework/v1/scenarios/{id}/run-voice/` | Run single as voice call |
| POST | `/test_framework/v1/scenarios/{id}/run-text/` | Run single as text chat |
| POST | `/test_framework/v1/scenarios/{id}/run-websocket/` | Run single via WebSocket |
| POST | `/test_framework/v1/scenarios/{id}/run-pipecat/` | Run single via Pipecat |

### Batch Run Schema

```json
POST /test_framework/v1/scenarios/run_scenarios/
{
  "agent_id": 12345,
  "scenarios": [111, 222, 333],
  "frequency": 1,
  "personality_ids": [],
  "test_profile_ids": []
}
```

Returns a result object with `id`, `status`, and `runs` array.

## Result Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/test_framework/v1/results/` | List results |
| GET | `/test_framework/v1/results/{id}/` | Get result details |
| POST | `/test_framework/v1/results/{id}/rerun/` | Rerun a result |
| POST | `/test_framework/v1/results/{id}/end-calls/` | End all calls in a result |
| POST | `/test_framework/v1/results/{id}/create-shareable-link/` | Generate shareable link |

## Run Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/test_framework/v1/runs/` | List runs |
| POST | `/test_framework/v1/runs/{id}/end-call/` | End a single call |

## Personality Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/test_framework/v1/personalities/` | List available personalities |

## Create Evaluator Schema

```json
{
  "personality": "integer (required) — caller personality ID",
  "agent": "integer | null — agent ID (either agent or project required)",
  "project": "integer | null — project ID",
  "name": "string (max 80 chars) — scenario name",
  "instructions": "string — what the simulated caller should do",
  "expected_outcome_prompt": "string — what success looks like",
  "metrics": "[integer] — metric IDs to evaluate against",
  "tags": "[string] — tags for filtering",
  "test_profile": "integer — test profile with identity info",
  "tool_ids": "[string] — tools available (e.g., TOOL_DTMF, TOOL_END_CALL)",
  "inbound_phone_number": "integer — inbound phone number ID"
}
```

## Personality Schema

```json
{
  "id": "integer",
  "name": "string — display name",
  "language": "string — ISO language code",
  "accent": "string — voice accent",
  "voice_model": "string — e.g., sonic-3",
  "provider": "string — 11labs or cartesia",
  "interruption_level": "string — how often the caller interrupts",
  "background_noise": "string — ambient sound config"
}
```

## Generation Endpoints

### Auto-Generate Evaluators

```json
POST /test_framework/v1/scenarios/generate-bg/
{
  "agent_id": 12345,
  "num_scenarios": 10,
  "extra_instructions": "Focus on cancellation edge cases and tool failure scenarios",
  "personalities": [693],
  "generate_expected_outcomes": true,
  "folder_path": "My Test Folder",
  "tags": ["generated", "cancellation"],
  "tool_ids": ["TOOL_END_CALL", "TOOL_END_CALL_ON_TRANSFER"]
}
```

Returns `{"progress_id": "<uuid>"}`. Poll with `GET /test_framework/v1/scenarios/generate-progress/?progress_id=<uuid>`.

Progress response:
```json
{
  "total_scenarios": 10,
  "completed_scenarios": 10,
  "failed_scenarios": 0,
  "scenarios_list": [{"id": 123, "name": "..."}]
}
```

**Gotchas:** Generation may produce fewer than requested. `scenario_language` defaults to "en" regardless of content — PATCH after. `first_message` may get greetings instead of exact questions — PATCH after.

### Create Folder

```json
POST /test_framework/v1/scenarios/create_folder/
{
  "name": "Mock Tool Scenarios",
  "project_id": 2998,
  "parent_path": ""
}
```

### Create from Transcript

```json
POST /test_framework/v1/scenarios/from-transcript/
{
  "call_id": 3358270,
  "agent": 12345
}
```

Creates an evaluator based on a real call transcript.

## Test Profile Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/test-profiles/` | Create test profile |
| GET | `/test_framework/v1/test-profiles/` | List profiles (query: `agent_id` or `project_id`) |
| GET | `/test_framework/v1/test-profiles/{id}/` | Get profile |
| PATCH | `/test_framework/v1/test-profiles/{id}/` | Update profile |
| DELETE | `/test_framework/v1/test-profiles/{id}/` | Delete profile |

### Create Test Profile Schema

```json
{
  "name": "string (max 255 chars) — descriptive profile name",
  "agent": "integer | null — agent ID (either agent or project required)",
  "project": "integer | null — project ID",
  "information": {
    "key": "value — arbitrary key-value pairs for identity/context data"
  }
}
```

### Test Profile Response

```json
{
  "id": 123,
  "name": "Sarah Johnson - Scheduling",
  "agent": 12345,
  "project": null,
  "information": {
    "name": "Sarah Johnson",
    "date_of_birth": "01/01/1990",
    "patient_id": "PT-12345"
  }
}
```

## Phone Number Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/test_framework/v1/phone-numbers/` | List phone numbers (`?project=<id>`) |

Filter for unassigned (`scenario_name: null`), US format (`+1` prefix, 12 chars). Assign via `PATCH /scenarios/{id}/` with `inbound_phone_number: <phone_id>`.

## Call Log Endpoints (for transcript-based creation)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/observability/v1/call-logs-external/` | List calls |
| GET | `/observability/v1/call-logs-external/{id}/` | Get call details + transcript |

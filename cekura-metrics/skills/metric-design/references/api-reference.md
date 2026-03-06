# Cekura Metrics API Reference

## Authentication

All requests require header: `X-CEKURA-API-KEY: <key>`

## Base URL

`https://api.cekura.ai`

## Metric Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/metrics/` | Create metric |
| GET | `/test_framework/v1/metrics/` | List metrics (filter by agent/project) |
| GET | `/test_framework/v1/metrics/{id}/` | Get metric |
| PATCH | `/test_framework/v1/metrics/{id}/` | Update metric |
| DELETE | `/test_framework/v1/metrics/{id}/` | Delete metric (returns 204) |
| POST | `/test_framework/v1/metrics/preview/` | Preview metric before creating |
| POST | `/test_framework/v1/metrics/{id}/auto-improve/` | Auto-improve from feedback |
| POST | `/test_framework/v1/metrics/{id}/run-reviews/` | Re-evaluate metric on calls |
| POST | `/test_framework/v1/metrics/generate_evaluation_trigger/` | Auto-generate trigger from description |

## Call / Evaluation Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/observability/v1/call-logs-external/` | List calls |
| GET | `/observability/v1/call-logs-external/{id}/` | Get call details |
| GET | `/observability/v1/call-logs-external/{id}/evaluation/` | Get call evaluation results |
| POST | `/observability/v1/call-logs-external/evaluate_metrics/` | Evaluate specific metrics on calls |
| POST | `/observability/v1/call-logs-external/rerun_evaluation/` | Re-run evaluation |
| POST | `/observability/v1/call-logs-external/{id}/mark_metric_vote/` | Leave feedback on metric result |

## Create Metric Schema

```json
{
  "name": "string (required)",
  "description": "string — FOR llm_judge: this IS the evaluation prompt",
  "type": "llm_judge | custom_code",
  "eval_type": "binary_qualitative | binary_workflow_adherence | enum | numeric | continuous_qualitative",
  "agent": "integer (agent ID)",
  "project": "integer (project ID, alternative to agent)",
  "custom_code": "string — Python code for custom_code type",
  "enum_values": ["array of strings — required when eval_type is enum"],
  "evaluation_trigger": "always | automatic | custom",
  "trigger_type": "llm_judge | custom_code",
  "evaluation_trigger_prompt": "string — natural language trigger condition",
  "evaluation_trigger_custom_code": "string — Python trigger code"
}
```

## Metric Types

| Type | Description |
|------|-------------|
| `llm_judge` | LLM evaluates the prompt in `description` field. Current standard. |
| `custom_code` | Python code in `custom_code` field. Runs on Lambda. |
| `basic` | **DEPRECATED** — API returns 400. |
| `custom_prompt` | **DEPRECATED** — API returns 400. |

## Custom Code Runtime Environment

**Available in `data` dict:**
| Key | Type | Description |
|-----|------|-------------|
| `transcript` | string | Full conversation text |
| `transcript_json` | string | Structured transcript with timestamps |
| `agent_description` | string | Main agent's system prompt |
| `dynamic_variables` | dict | Custom variables from calls |
| `metadata` | dict | Call metadata |
| `call_end_reason` | string | How the call ended |
| `voice_recording` | string | Audio recording URL |

**Available function:**
```python
evaluate_basic_metric(data, api_key, prompt, eval_type=None, enum_values=None)
```
Makes a nested LLM call for evaluation within custom_code. Returns a dict with `result` and `explanation` keys, or a string. The `parse_llm_result` utility handles both return types (see `pythonic-patterns.md`).

**Required output variables:**
- `_result` — bool, float, str, or None
- `_explanation` — string describing the result
- `_extra` — optional dict with additional data

**Accessing upstream metrics:**
```python
upstream_value = data.get("Exact Metric Name")
```
The key must match the upstream metric's `name` field exactly.

## Trigger Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `evaluation_trigger` | string | `"always"` | When to fire: `always`, `automatic`, `custom` |
| `trigger_type` | string | `"llm_judge"` | How trigger is evaluated |
| `evaluation_trigger_prompt` | string | `""` | Natural language trigger condition (for llm_judge trigger) |
| `evaluation_trigger_custom_code` | string | `""` | Python trigger code (for custom_code trigger) |

## Evaluate Metrics on Calls

```json
POST /observability/v1/call-logs-external/evaluate_metrics/
{
  "call_ids": [123, 456],
  "metric_ids": [789, 101]
}
```

## Leave Feedback (Mark Metric Vote)

```json
POST /observability/v1/call-logs-external/{call_id}/mark_metric_vote/
{
  "metric_id": 789,
  "vote": "agree | disagree",
  "feedback": "string — explanation of why the metric result is wrong"
}
```

## Re-run Evaluation

```json
POST /observability/v1/call-logs-external/rerun_evaluation/
{
  "call_ids": [123, 456],
  "metric_ids": [789]
}
```

# API Reference — Predefined Metrics

Public Cekura API endpoints for discovering, enabling, configuring, and attaching predefined metrics. All requests authenticate with the `X-CEKURA-API-KEY` header.

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /test_framework/v1/predefined-metrics/` | List all predefined metrics with their `code`, name, output type, and supported configuration keys |
| `GET /test_framework/v1/projects/{project_id}/` | Read project metric toggles (which predefined metrics are enabled for simulation runs) |
| `PATCH /test_framework/v1/projects/{project_id}/` | Toggle a predefined metric on/off for simulations at the project level |
| `GET /test_framework/v1/aiagents/{agent_id}/metrics/` | List metrics attached to a specific agent/evaluator |
| `POST /test_framework/v1/aiagents/{agent_id}/metrics/` | Attach a predefined metric to an evaluator (by `code`), with optional `configuration` |
| `PATCH /test_framework/v1/aiagents/{agent_id}/metrics/{metric_id}/` | Update a metric attachment (e.g., change configuration values) |
| `DELETE /test_framework/v1/aiagents/{agent_id}/metrics/{metric_id}/` | Detach a metric from an evaluator |
| `GET /observability/v1/projects/{project_id}/predefined-metrics/` | Read observability-side toggles (which predefined metrics fire on real production calls) |
| `PATCH /observability/v1/projects/{project_id}/predefined-metrics/` | Toggle a predefined metric on/off for observability |
| `POST /observability/v1/call-logs/evaluate_metrics/` | Evaluate (or re-evaluate) specific metrics on a set of call IDs |

## Two-step activation

A predefined metric only fires when **both** of these are true:

1. The metric is **toggled on at the project level** (simulation OR observability, depending on where you want it).
2. The metric is **attached to the evaluator** (for simulation) or implicitly applied to all calls in the project (for observability).

Skipping either step results in a metric that appears available in the dashboard but never produces output.

## Example: full attach-with-config flow

### 1. Discover the metric `code`

```
GET /test_framework/v1/predefined-metrics/
X-CEKURA-API-KEY: <key>
```

Response (truncated):
```json
[
  {
    "code": "DROPOFF_NODE",
    "name": "Dropoff Node",
    "output_type": "enum",
    "supported_in": ["observability"],
    "configuration_schema": {
      "dropoff_nodes": {"type": "array", "items": {"type": "string"}, "required": true}
    }
  },
  {
    "code": "DETECT_SILENCE",
    "name": "Detect Silence in Conversation",
    "output_type": "boolean",
    "supported_in": ["simulation", "observability"],
    "configuration_schema": {
      "silence_duration": {"type": "integer", "default": 10}
    }
  }
]
```

### 2. Toggle the metric on at the project level (simulation)

```
PATCH /test_framework/v1/projects/{project_id}/
X-CEKURA-API-KEY: <key>
Content-Type: application/json

{
  "enabled_predefined_metrics": ["DETECT_SILENCE", "EXPECTED_OUTCOME", "TOOL_CALL_SUCCESS"]
}
```

### 3. Attach the metric to an evaluator with configuration

```
POST /test_framework/v1/aiagents/{agent_id}/metrics/
X-CEKURA-API-KEY: <key>
Content-Type: application/json

{
  "predefined_metric_code": "DETECT_SILENCE",
  "configuration": {
    "silence_duration": 8
  }
}
```

### 4. Verify the attachment

```
GET /test_framework/v1/aiagents/{agent_id}/metrics/
X-CEKURA-API-KEY: <key>
```

The response should now include the predefined metric with the configuration you set.

### 5. Enable for observability (separately)

```
PATCH /observability/v1/projects/{project_id}/predefined-metrics/
X-CEKURA-API-KEY: <key>
Content-Type: application/json

{
  "enabled": ["DETECT_SILENCE", "CSAT", "SENTIMENT"]
}
```

## Re-evaluating existing calls

To run a newly enabled predefined metric on calls that have already completed:

```
POST /observability/v1/call-logs/evaluate_metrics/
X-CEKURA-API-KEY: <key>
Content-Type: application/json

{
  "call_log_ids": [5550000, 5550001, 5550002],
  "predefined_metric_codes": ["CSAT", "SENTIMENT"]
}
```

**Cost guard:** Each evaluation costs credits per the cost table in `SKILL.md`. Always query the call count first and confirm with the user before evaluating more than 100 calls.

## Common errors

| Status | Cause | Fix |
|--------|-------|-----|
| `400` | Missing required `configuration` key (e.g., `dropoff_nodes` for Dropoff Node) | Read `configuration_schema` from the predefined-metrics list and supply the required keys |
| `400` | Using a metric `code` not in the predefined-metrics list | List the available codes first; codes are case-sensitive |
| `404` | Toggling a simulation-only metric (Transcription Accuracy, Mock Tool Call Accuracy, Expected Outcome) for observability — or vice versa | Check the `supported_in` field on the predefined metric |
| `409` | Attaching the same predefined metric to the same evaluator twice | PATCH the existing attachment to update configuration instead |

## Related

- Configuration payload examples: `configuration-guide.md`
- Choosing metrics by agent type: `selection-by-use-case.md`

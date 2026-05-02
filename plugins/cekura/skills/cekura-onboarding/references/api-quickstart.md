# Onboarding API Quickstart

## Authentication

All requests: `X-CEKURA-API-KEY: <key>` header. Base URL: `https://api.cekura.ai`

## Essential Endpoints for Setup

### Projects
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/projects/` | Create project |
| GET | `/test_framework/v1/projects/` | List projects |

### Agents
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/aiagents/` | Create agent |
| GET | `/test_framework/v1/aiagents/` | List agents (`?project_id=X`) |
| GET | `/test_framework/v1/aiagents/{id}/` | Get agent details |
| PATCH | `/test_framework/v1/aiagents/{id}/` | Update agent |

**Note:** Endpoint is `/aiagents/`, NOT `/agents/`.

### Agent Schema
```json
{
  "name": "string (required)",
  "project": "integer (project ID)",
  "description": "string (agent system prompt — critical for eval generation)"
}
```

### Evaluator Generation
```json
POST /test_framework/v1/scenarios/generate-bg/
{
  "agent_id": 12345,
  "num_scenarios": 10,
  "personalities": [693],
  "generate_expected_outcomes": true,
  "folder_path": "First Tests",
  "tool_ids": ["TOOL_END_CALL", "TOOL_END_CALL_ON_TRANSFER"]
}
```

Poll: `GET /test_framework/v1/scenarios/generate-progress/?progress_id=<uuid>`

### Running Tests
```json
POST /test_framework/v1/scenarios/run_scenarios/
{
  "agent_id": 12345,
  "scenarios": [111, 222, 333],
  "frequency": 1
}
```

### Checking Results
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/test_framework/v1/results/` | List results |
| GET | `/test_framework/v1/results/{id}/` | Get result details (transcript, metrics, audio) |

### Metrics
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/test_framework/v1/metrics/` | List metrics |
| GET | `/test_framework/v1/predefined-metrics/` | List pre-defined metrics |

### Personalities
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/test_framework/v1/personalities/` | List available personalities |

Default personality: **693** (Normal Male, English/American)

### Folders
```json
POST /test_framework/v1/scenarios/create_folder/
{
  "name": "Folder Name",
  "project_id": 123
}
```

## Verification Checklist

After onboarding, confirm:
- [ ] API key works (`GET /test_framework/v1/metrics/` returns 200)
- [ ] Agent created with full description
- [ ] Provider integration configured
- [ ] Pre-defined metrics enabled at project level
- [ ] At least 5 evaluators generated
- [ ] Metrics attached to evaluators
- [ ] First test run completed successfully
- [ ] Results accessible and interpretable

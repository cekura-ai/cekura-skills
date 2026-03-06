# CSV-to-Evaluator Workflow (Kouper BCHS Pattern)

## CSV Structure

```csv
ID,Category,AI Evaluator Name,Test Agent Behavior,Expected Outcome,Critical Focus,Conversation Nodes,Priority
S-01,Scheduling,New adult patient with insurance,Calls as patient new to clinic provides insurance books appointment,Agent books appointment and instructs patient to bring ID and insurance,"I4a1, V5a, S4c2","O2c, V1a, ...",must have
```

## Column → Field Mapping

| CSV Column | Evaluator Field | Transform |
|------------|----------------|-----------|
| ID + AI Evaluator Name | `name` | `f"{row['ID']} - {row['AI Evaluator Name']}"[:80]` |
| Test Agent Behavior | `instructions` | Wrapped with persona and scenario context |
| Expected Outcome | `expected_outcome_prompt` | Direct mapping |
| Category, Priority, ID | `tags` | `[category, priority, id]` |
| Critical Focus | Included in `instructions` | Added as "KEY INTERACTION POINTS" |

## Instruction Building Pattern

```python
def build_instructions(row):
    parts = [
        f"You are calling a medical clinic as a patient/caller.",
        f"",
        f"SCENARIO: {row['AI Evaluator Name']}",
        f"",
        f"YOUR BEHAVIOR:",
        f"{row['Test Agent Behavior']}",
    ]
    if row.get("Critical Focus", "").strip():
        parts.extend([
            f"",
            f"KEY INTERACTION POINTS: {row['Critical Focus']}",
        ])
    return "\n".join(parts)
```

## Full Create Script Pattern

```python
import csv, json, requests, os

API_URL = "https://api.cekura.ai/test_framework/v1/scenarios/"
API_KEY = os.environ["CEKURA_API_KEY"]
AGENT_ID = int(os.environ["CEKURA_AGENT_ID"])
PERSONALITY_ID = int(os.environ["CEKURA_PERSONALITY_ID"])

HEADERS = {"X-CEKURA-API-KEY": API_KEY, "Content-Type": "application/json"}

def row_to_scenario(row):
    return {
        "name": f"{row['ID']} - {row['AI Evaluator Name']}"[:80],
        "personality": PERSONALITY_ID,
        "agent": AGENT_ID,
        "instructions": build_instructions(row),
        "expected_outcome_prompt": row["Expected Outcome"],
        "tags": [row["Category"], row["Priority"].strip().replace(" ", "-"), row["ID"]],
    }

with open("evals.csv") as f:
    for row in csv.DictReader(f):
        payload = row_to_scenario(row)
        resp = requests.post(API_URL, headers=HEADERS, json=payload)
        print(f"{payload['name']}: {resp.status_code}")
```

## Tips

- Name field has 80-char limit — truncate with `[:80]`
- Personality ID is required — list available ones first via `/test_framework/v1/personalities/`
- Tags enable filtering in the Cekura UI — use consistent category codes
- Add `metrics` field if specific metrics should evaluate the resulting call
- For large CSVs (50+ rows), add error handling and resume capability

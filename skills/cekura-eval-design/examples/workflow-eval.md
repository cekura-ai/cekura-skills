# Example: Workflow Evaluator (Scheduling)

## API Payload

```json
{
  "name": "S-01 - New adult patient with insurance",
  "personality": 42,
  "agent": 12345,
  "instructions": "You are calling a medical clinic as a patient/caller.\n\nSCENARIO: New adult patient with insurance\n\nYOUR BEHAVIOR:\nCalls as patient new to clinic. Provide your insurance information when asked. Accept the first available appointment slot. When asked about the reason for your visit, say you need a general checkup.\n\nKEY INTERACTION POINTS: I4a1, V5a, S4c2",
  "expected_outcome_prompt": "Agent books appointment and instructs patient to bring ID and insurance",
  "tags": ["Scheduling", "must-have", "S-01"],
  "metrics": [120069, 120072]
}
```

## Why This Works

- **Instructions describe behavior**, not a script — the testing agent adapts naturally
- **Persona is clear**: new patient, has insurance
- **Critical focus nodes** tell the testing agent which decision points to exercise
- **Expected outcome** is agent-centric and measurable
- **Tags** enable filtering by category and priority
- **Metrics** automatically evaluate the resulting call

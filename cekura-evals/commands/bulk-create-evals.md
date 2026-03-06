---
name: bulk-create-evals
description: Create multiple Cekura evaluators from CSV, JSON, or structured input
argument-hint: "[path to CSV/JSON file or description of evals to create]"
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "AskUserQuestion"]
---

# Bulk Create Evaluators

Create multiple evaluators at once from structured input. Follows the proven Kouper CSV-to-evaluator pattern.

## Process

1. **Identify the source**: Where do the eval definitions come from?
   - CSV file (recommended for large test suites)
   - JSON array
   - User description to convert into structured evals

2. **Get required config**:
   - Agent ID or project ID
   - Personality ID:
   ```bash
   source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
   list_personalities
   ```
   - Test profiles: List existing or create new ones for identity data:
   ```bash
   list_test_profiles "agent_id=AGENT_ID"
   ```

3. **Parse and validate**: Read the input file and validate each eval has:
   - A name (max 80 chars)
   - Instructions (first-person, behavioral — referencing test profile data, not hardcoding identity)
   - Expected outcome (what the agent should achieve)
   - Tags (category, priority, ID)
   - Test profile assignment (where identity/context data is needed)

4. **Present summary**: Show a table grouped by category:
   ```
   Scheduling: 10 evals (8 must-have, 2 nice-to-have)
   Cancellation: 6 evals (5 must-have, 1 nice-to-have)
   ...
   Total: 54 evals
   ```

5. **Get confirmation**: "Ready to create [N] evaluators for agent [ID]?"

6. **Create sequentially**: Build each eval from the input and submit:
```bash
for each row:
  create_scenario '{"name": "...", "personality": PID, "agent": AID, ...}'
```

7. **Report results**: Show created vs failed, with error details for failures.

## CSV Format (Recommended)

```csv
ID,Category,AI Evaluator Name,Test Agent Behavior,Expected Outcome,Critical Focus,Priority
S-01,Scheduling,New adult patient with insurance,Calls as patient new to clinic...,Agent books appointment...,I4a1 V5a,must have
```

### Column Mapping

| CSV Column | Evaluator Field |
|------------|----------------|
| ID + AI Evaluator Name | `name` (truncated to 80 chars) |
| Test Agent Behavior | `instructions` (wrapped with persona context) |
| Expected Outcome | `expected_outcome_prompt` |
| Category, Priority, ID | `tags` |
| Critical Focus | Appended to `instructions` as "KEY INTERACTION POINTS" |

## JSON Format

```json
[
  {
    "name": "S-01 - New adult patient",
    "instructions": "...",
    "expected_outcome_prompt": "...",
    "tags": ["Scheduling", "must-have", "S-01"]
  }
]
```

## Post-Creation Checklist

After bulk creation, ensure each eval has:
- **Test profiles assigned** — identity data in profiles, not hardcoded in instructions
- **Tools enabled** — `TOOL_END_CALL`, `TOOL_END_CALL_ON_TRANSFER` (for transfer scenarios), `TOOL_DTMF` (for IVR)
- **Baseline metrics attached** — Expected Outcome, Infrastructure Issues, Tool Call Success, Latency (requires project-level toggle + per-evaluator attachment)

## Tips

- For CSV, wrap instructions with persona context: "You are calling [context] as a [persona]."
- Name must be under 80 chars — use `f"{id} - {name}"[:80]`
- Include Critical Focus in instructions as "KEY INTERACTION POINTS"
- Create all evals sequentially with error handling and a summary at the end
- Use `<scenario>` tags with step-by-step numbered format in instructions
- Don't include examples of what the main agent "may say" — reference actions by topic

# Filling Expected Mock Tool Calls for Manual Cekura Scenarios

## Scope

This workflow fills the gap between manual conditional-action authoring and platform auto-generation. The platform's server-side auto-generation produces synchronized test profiles, agent mock-tool entries, **and** the scenario's expected mock tool calls (`generated_mock_tool_entries`). Scenarios authored any other way (an agent following `cekura-eval-design`, a human in the dashboard, a CSV import) get the first two but **not the expected mock tool calls**.

Keep the two straight:

- **Mock responses at run time are served from the agent's mock tools** (`Tool.information`), matched by fuzzy input comparison. The scenario's expected mock tool calls are not consulted for serving — mocks fire whether or not they are set.
- **The expected mock tool calls are the record** read by the *Mock tool call accuracy* metric and the per-run resolved-calls data. Without them, that metric has nothing to compare actual calls against.

This workflow populates the expected mock tool calls and reconciles them with the agent mock data + test profile. It assumes that mock data and profile were **designed** per `cekura-eval-design`'s `references/test-data-design.md`; it does not restate those design rules.

## Platform Fields

Agent mock tools live on the agent. Each tool holds a list of input→output entries. On write, use the `mock_data` key:

```json
{
  "mock_tools": [
    {
      "id": 123,
      "name": "get_user_info",
      "description": "Lookup a user by phone",
      "mock_data": [
        {
          "input": {"phone_number": "8645239892"},
          "output": {"user_id": "U-901", "name": "Sarah Johnson"}
        }
      ],
      "freetext_params": []
    }
  ]
}
```

> When you **read** the agent back, the entries may be echoed under `information` rather than `mock_data`. Mirror whatever shape the read returns when you re-send the list; don't blindly rename it.

The scenario's expected mock calls live on the scenario, in `generated_mock_tool_entries`:

```json
{
  "generated_mock_tool_entries": [
    {
      "tool_id": 123,
      "tool_name": "get_user_info",
      "new_entry": {
        "input": {"phone_number": "8645239892"},
        "output": {"user_id": "U-901", "name": "Sarah Johnson"}
      }
    }
  ]
}
```

Field rules (enforced server-side):

- `tool_name` is **required** on every entry and cannot be empty.
- `tool_id`, when present, **must belong to this scenario's agent** — otherwise the write is rejected. Reuse the agent's existing tool IDs.
- `new_entry.input` and `new_entry.output`, when present, must each be an object.
- `new_entry` is the scenario's expected entry, even when the entry was reused from existing agent mock data rather than newly created.

The test profile uses the sectioned shape (see `test-data-design.md` for the `main_agent_variables` vs `testing_agent_variables` split):

```json
{
  "information": {
    "main_agent_variables": {
      "customer_phone_number": "8645239892",
      "user_id": "U-901"
    },
    "testing_agent_variables": {
      "customer_name": "Sarah Johnson",
      "date_of_birth": "03/14/1982"
    }
  }
}
```

## Write Paths

Prefer the auto-configured Cekura platform tools when available.

- **Retrieve the scenario / agent mock tools / test profiles** with the corresponding platform read operations, or the public REST reads:
  - `GET /test_framework/v2/aiagents/{id}/?ql={mock_tools}` for agent mock tools.
- **Patch agent mock tools:** send the **full** `mock_tools` list (Cekura replaces the whole list) via the agent update operation, or `PATCH /test_framework/v2/aiagents/{id}/`.
- **Attach the expected mock tool calls — REST only:** write `generated_mock_tool_entries` with `PATCH /test_framework/v1/scenarios/{id}/`. This field is **not in the scenario create/update request schema**, so the create/update platform operations cannot carry it — they simply have no parameter for it. The REST scenario endpoint goes through the full serializer, which accepts and validates the field. Always confirm on retrieve that it persisted.

All Cekura REST calls use the `X-CEKURA-API-KEY: <key>` header. For large mock payloads, send the JSON from a file (`curl ... -d @file.json`) — URL-encoded parameters can exceed the server's URI length limit.

## Fill-In Procedure

### 1. Normalize Inputs

For the scenario, collect:

- `id`, `name`, `agent`, `project`, `scenario_type`.
- `conditional_actions.role` and `conditional_actions.conditions`.
- `expected_outcome_prompt`.
- Attached `test_profile` and `test_profile_data`, if any.
- `tool_ids`, metrics, folder, personality, and language.

Abort if `conditional_actions` is missing and the user did not ask to convert the scenario.

### 2. Determine Exercised Tools

Use the agent description and existing mock tool names as the source of truth. For the scenario, identify:

- Which tool calls should occur, and the call order if tools depend on one another.
- Input fields the agent is likely to send, and output fields needed for the scenario to proceed.
- Which fields the caller must know (→ `testing_agent_variables`) vs. which the main agent receives at call start (→ `main_agent_variables`).

Ask before writing if two or more tool choices are plausible and would produce different expected calls.

### 3. Design or Reuse the Backing Data

Design the mock entries and test profile **per `cekura-eval-design`'s `references/test-data-design.md`** — reuse rules, cardinality / not-found / validation-failure patterns, phone-format variants, `freetext_params`, and the profile shape all live there. Do not re-derive them here.

The only fill-in constraint: whatever input/output you settle on for each exercised tool must end up **identical** in three places — the agent's mock data, the scenario's `new_entry`, and (for values the caller/agent uses) the test profile.

### 4. Patch Agent Mock Data

Fetch current mock tools first. Merge entries into the matching tool by `id` or exact `name`.

When patching:

- Send the full desired `mock_tools` list.
- Preserve every existing tool and entry unless the user explicitly asked to delete it.
- Preserve every tool's `id`, `name`, `description`, `freetext_params`, and `served_via`.
- Mirror the read shape (`mock_data` vs `information`) as noted above.

### 5. Attach the Expected Mock Tool Calls

For each exercised tool, add an entry:

```json
{
  "tool_id": "<the agent's existing tool id>",
  "tool_name": "<exact tool name>",
  "new_entry": {
    "input": {},
    "output": {}
  }
}
```

The `input` and `output` must exactly match the entry present in the agent's mock data after the patch. Do not summarize or omit fields.

When updating an existing scenario, preserve its current `conditional_actions`, expected outcome, metrics, folder, language, personality, `tool_ids`, and test profile unless a change is required for consistency.

### 6. Validate

Retrieve the scenario and agent after writes. Check:

- `generated_mock_tool_entries` is present and non-empty for tool-dependent scenarios.
- Every entry maps to a real mock tool on this scenario's agent, and every `tool_id` belongs to that agent.
- Every entry's `new_entry` is present in that tool's mock data.
- The scenario has a complete test profile.
- Profile lookup keys, dynamic variables, and mock inputs/outputs are identical where they represent the same fact.
- The final conditional action can end the call, or the scenario has a terminal end-call action.

Do **not** add or enable metrics as part of this validation. Populating expected mock tool calls is independent of which metrics are on — it also feeds the per-run resolved-calls data and observability. Whether to enable the *Mock tool call accuracy* metric is the user's choice; leave metric selection to `cekura-eval-design`.

Recommend a text run for first-pass validation. Voice is only necessary for audio, latency, interruption, IVR, TTS, or provider integration behavior.

## Output Format

When reporting back, include:

- Scenario IDs filled in.
- Tool names and number of mock entries added or reused.
- Test profile IDs created or reused.
- Whether `generated_mock_tool_entries` was verified on retrieve.
- Any assumptions or fields that need user confirmation.

Keep raw mock values concise unless the user asks for the full JSON.

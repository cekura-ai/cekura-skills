# Auto-Generation Reference

Detailed schema and gotchas for the scenario auto-generator. Loaded on demand from `SKILL.md`'s "Auto-Generation" section.

The auto-generator produces **behavioral** evaluators (`scenario_type: "instruction"`). For conditional-actions evaluators, author each scenario directly via the create endpoint — see `references/conditional-actions.md`.

## Endpoint

`POST /test_framework/v1/scenarios/generate-bg/` — preferred workflow for bulk behavioral scenario creation.

## Full schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | integer | Yes | Agent to generate scenarios for |
| `num_scenarios` | integer | Yes | How many to generate |
| `extra_instructions` | string | No | Category-level guidance (e.g., "focus on cancellation edge cases") |
| `personalities` | array[integer] | No | Personality IDs to use |
| `generate_expected_outcomes` | boolean | No | Auto-generate expected outcomes |
| `folder_path` | string | No | Folder to place generated scenarios in (**always set this** — create the folder first) |
| `tags` | array[string] | No | Tags to apply to all generated scenarios |
| `tool_ids` | array[string] | No | Tools to enable (e.g., `TOOL_END_CALL`) |

**Returns:** `{"progress_id": "<uuid>"}`. Poll with `GET /test_framework/v1/scenarios/generate-progress/?progress_id=<id>`.

**Progress response fields:** `total_scenarios`, `completed_scenarios`, `failed_scenarios`, `scenarios_list`.

## Generation Gotchas

1. **Generation can partially complete** — May produce fewer scenarios than requested (e.g., 15/18) with the remainder stuck. After a reasonable timeout, generate the remainder in a smaller batch with more specific `extra_instructions`.

2. **`scenario_language` defaults to "en"** — Auto-gen sets all scenarios to English even when `extra_instructions` specify non-English languages. PATCH each scenario with the correct language code (`ru`, `hi`, `es`, `zh`, `ko`, `pt`, `de`, etc.) after generation. This is required for correct TTS voice/pronunciation.

3. **Auto-gen may add greetings to `first_message`** — When `extra_instructions` specify exact verbatim questions, some scenarios get a greeting (e.g., "Здравствуйте") as the `first_message` while the actual question is in instructions as a follow-up. PATCH `first_message` after generation.

4. **Language-specific personalities may not be enabled per-project** — Non-English personalities (e.g., ID 4566 for Russian) may return "Personality is not enabled" errors. Workaround: use personality 693 (Normal Male English) and rely on `scenario_language` + instructions to drive the language.

5. **Mock tool awareness** — When mock tools are enabled on an agent, the generate endpoint creates tool-aware scenarios automatically.

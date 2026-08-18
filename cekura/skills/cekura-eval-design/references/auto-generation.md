# Auto-Generation Reference

Detailed schema and gotchas for the scenario auto-generator. Loaded on demand from `SKILL.md`'s "Auto-Generation" section.

The auto-generator produces **behavioral** evaluators (`scenario_type: "instruction"`) — it **cannot emit conditional-action** evaluators (`scenario_type: "conditional_actions"`). That makes the split absolute:

- **Behavioral scenarios are always generated here**, never hand-authored via the create endpoint — including a single one (`num_scenarios: 1` with a specific `extra_instructions`).
- **Conditional-action evaluators are always authored directly** via the create endpoint, because generation has no way to produce them — see `references/conditional-actions.md`.

## Endpoint

`POST /test_framework/v1/scenarios/generate-bg/` — the path for every behavioral scenario, one or many.

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

4. **Language-specific personalities may not be enabled per-project** — Non-English personalities (e.g., ID 4566 for Russian) may return "Personality is not enabled" errors. Always try the language-matched personality first (or a multilingual `language=multi` one when the scenario mixes languages); on that error, enable the predefined one for the project or create/fork a Normal personality in the target language and use it (`scenario_language` is coupled to the personality's language by design — mismatches are rejected; multilingual voice models handle any supported language).

5. **Mock tool awareness** — When mock tools are enabled on an agent, the generate endpoint creates tool-aware scenarios automatically.

6. **First messages can come back as meta-instructions** — especially for non-English batches: `first_message` sometimes reads like a directive ("Speak in Tamil and ask about…") instead of actual caller dialogue. Verify every `first_message` is a literal caller utterance in the target language; PATCH the ones that aren't.

7. **Roles can come back inverted** — generated `instructions` occasionally describe the MAIN agent's behavior instead of the caller's. Instructions must be first-person testing-agent (caller) behavior; regenerate or rewrite any scenario whose instructions read like the main agent's script.

8. **Multilingual batches: generate per language** — for "N per language" requests, run one generation per language with that language's personality (see `choosing-personality.md`) instead of one mixed batch. Mixed batches tend to stamp every scenario with a single language and drift the per-language counts.

## Reliability Protocol

The generator is a background pipeline that can stall, partially complete, or drift from the plan. Every generation run follows this protocol:

**Before triggering:**
- **Hard confirmation gate** — never call `scenarios_generate_bg` before the user approves the plan (see the Pre-Creation Checkpoint in SKILL.md). "Proceed autonomously" from the user is the only exception.
- **Verify inputs are readable** — if the plan is based on an attached file, knowledge base, or agent prompt, confirm you can actually read its content first. If the source is unreadable (corrupt, unparseable, empty), **stop and ask for a usable copy — even in autonomous mode**: "proceed autonomously" licenses sensible defaults, not substituting a different source (the agent description, your own guesses) for the one the user supplied. Generating from a stand-in requires the user's explicit OK after being told the source is unreadable.
- **Reconcile counts with the source** — when scenarios come from a file/list, count the actual items. If the user asked for 15 but the source has 14, say so and confirm the real number before generating.
- **Batch large requests** — for `num_scenarios` > 10, split into batches of ≤ 10 (per category or per language) and run them sequentially. Large single batches are the main cause of stalls and partial completion.

**While polling** (`scenarios_generate_progress`, ~10s interval):
- Report progress to the user roughly every 30s — never poll silently for minutes.
- **Stall rule:** if `completed_scenarios` is still 0 after ~2 minutes, stop polling. Tell the user, then retry once with a smaller batch (≤ 5) and tighter `extra_instructions`. Do not loop "keep waiting" indefinitely.
- If progress advances but freezes short of the total (e.g. 53/58) for ~2 minutes, treat the batch as done and handle the shortfall below.

**After completion — verify before reporting success:**
1. **Count** — fetch the created scenarios and compare to the request. If short, generate the remainder in a small batch whose `extra_instructions` name exactly the missing cases.
2. **Plan diff** — map generated scenarios 1:1 against the approved plan. If the generator merged two requested cases into one or invented an extra, create the missing standalone case and flag the extra.
3. **Language** — for non-English requests, check `scenario_language`, the personality's language, and that `first_message`/`instructions` are actually written in the target language (gotchas 2, 6, 8).
4. **Roles** — instructions are caller-side, first person (gotcha 7).
5. **Scaffolding** — every scenario has a non-empty `expected_outcome_prompt` (pass `generate_expected_outcomes: true`; patch any that came back empty), the right tools (`TOOL_END_CALL`; `TOOL_END_CALL_ONLY_ON_TRANSFER` for transfer flows; `TOOL_DTMF` for IVR), and the baseline metrics.

Report the verification result explicitly ("9/9 created, languages verified, 2 first_messages patched") — never report success on the trigger alone.

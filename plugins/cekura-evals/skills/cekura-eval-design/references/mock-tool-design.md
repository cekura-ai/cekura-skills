# Mock Tool Data Design — Approach B Details

Detailed guide for setting up Cekura mock tools (only relevant when using Approach B from `tool-strategies.md`).

## Per-Input Branching — The Core Concept

Cekura matches incoming tool calls to the closest input in the mock's `information` array and returns the corresponding output. **A single input/output mapping per tool is NOT enough.** If a tool accepts different parameters that should return different results, each variant needs its own mapping.

Example: a `get_user_info` tool needs separate mappings for each test user, plus phone format variants:
```json
"information": [
  {"input": {"phone": "8645239892"}, "output": {"id": "B001", "name": "John Doe", "dob": "01/15/1990"}},
  {"input": {"phone": "18645239892"}, "output": {"id": "B001", "name": "John Doe", "dob": "01/15/1990"}},
  {"input": {"phone": "5551234567"}, "output": {"id": "B002", "name": "Jane Smith", "dob": "03/22/1985"}}
]
```

**Think through the full data graph:** user lookup → account data → transaction history → payment methods. All IDs and references must be consistent across tools.

## Setting Up Mock Tools

1. **List existing tools:** GET the agent's tools — check what's already configured
2. **Auto-fetch (if available):** For VAPI/Retell/ElevenLabs, use the UI: Agent Settings → Mock Tools → Auto-Fetch → enable mock mode per tool. This creates tool definitions with sample mappings.
3. **Add per-scenario mappings:** Auto-fetch creates illustrative examples, not exhaustive data. Add the specific input/output pairs each scenario needs by PATCHing the tool.
4. **Validate:** Run one scenario and check the transcript — tool calls should return the expected mock data.

## Critical: Append-Not-Replace

When PATCHing a tool's `information` array, you must GET the existing mappings first, append new ones, then PATCH the full combined array. A PATCH with only new mappings **replaces ALL existing mappings**. Always use the GET → merge → PATCH pattern.

## Phone Number ↔ Mock Data Linkage

For inbound agents, the `inbound_phone_number` on the scenario is the number Cekura calls FROM. The agent sees this as `{{customer.number}}` and uses it to look up the caller. **Critical gotcha: phone format mismatches cause 404s.** Add mappings for ALL format variants:
- 10-digit: `8645239892`
- 11-digit with leading 1: `18645239892`
- Full E.164: `+18645239892`

**Backup phone pattern:** When the primary inbound phone doesn't match, add a fallback:
1. Add a simple 555-XXX-XXXX backup phone to mock mappings pointing to the same data
2. Add instruction: "If the agent says they cannot find your account, provide the alternate number XXX-XXX-XXXX"
3. Update test profile with both `customer_phone_number` and `backup_phone_number`

## Test Profile ↔ Mock Data Alignment

Test profiles must have ALL credentials the testing agent needs. If the agent asks for DOB + SSN last 4 + first name + last name, ALL must be in the test profile. Missing fields = the testing agent improvises or fails authentication.

**Always derive test profile values FROM mock data, not independently.** If `get_user_info` returns `{"dob": "01/15/1990"}`, the test profile must have `"dob": "01/15/1990"` — same format, same value. Creating them separately guarantees mismatches.

## Phone Number Pool

Phone numbers are a shared resource. `GET /test_framework/v1/phone-numbers/?project=<id>` — filter for unassigned ones (`scenario_name: null`), US format (`+1` prefix, 12 chars). Assign via `PATCH /scenarios/{id}/` with `inbound_phone_number: <phone_id>`. Each scenario should get a unique phone to avoid mock data collisions.

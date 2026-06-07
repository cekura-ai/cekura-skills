# Test Data Design — Mock Tools, Test Profiles, and Dynamic Variables

Mock tools, test profiles, and dynamic variables form one cohesive test data set. They must be designed together — inconsistencies between them cause silent failures (wrong mock responses, failed authentication, improvised caller data). This guide covers all three and replaces `tool-strategies.md`, `test-profiles.md`, and `mock-tool-design.md`.

**Design order for Approach B:** mock tool data first → test profile derived from mock outputs → dynamic variables registered from profile fields.
**Design order for Approach A:** discover staging data first → test profile matched to staging formats.
In all cases, the test profile is the runtime container the testing agent reads. Every variable value in scenario instructions must come from `{{test_profile.field_name}}` — never hardcoded.

---

## Step 1 — Choose Your Approach

Pick one approach up front; it shapes all of the below.

### Approach A: Client Staging Backend

The client manages their own mock/staging backend. Cekura doesn't intercept tool calls — the agent hits the real staging endpoints.

**When to use:** Client already has staging data, doesn't want to replicate it in Cekura, or their tool behavior is too complex to mock (multi-step state machines, transactions).

**Workflow:**
1. Ask the user: what test data exists in your staging environment? What formats does it use (dates, phone numbers, IDs)?
2. Check existing profiles first — if one matches the staging formats and values for this scenario, reuse it
3. If not, build a new profile that matches the staging data exactly (same format, same values)
4. Scenario instructions reference profile data generically: "provide your date of birth when asked" — the testing agent reads from the profile; the agent sends it to the real staging backend
5. No Cekura mock tools needed

**Validation:** If the agent says "I couldn't find your account", the profile data doesn't match the staging system — check formats.

### Approach B: Cekura Mock Tools

Cekura intercepts tool calls and returns pre-configured mock responses. The agent never hits a real backend.

**When to use:** No staging environment, want fully isolated tests, need predictable responses, or tools are simple lookups/CRUD.

**Workflow:**
1. Check existing mock tool entries — if they fit the scenario, reuse them and find the corresponding profile (see Step 3)
2. If not, design the full data graph (see Step 2), configure new mock entries, then derive the profile from outputs
3. New entries must be sufficiently distinct from existing ones — fuzzy matching must discriminate between users

### Approach C: Conversational Only

The agent doesn't use external tools, or tools aren't relevant to what you're testing.

**When to use:** Agent is conversational-only, testing tone/adherence rather than tool-dependent workflows, or tools are optional.

**Workflow:** Check existing profiles first — if one has the caller identity fields this scenario needs, reuse it. Otherwise create a new profile with caller identity data (name, DOB, etc.). Write scenarios focused on conversational behavior. Don't include tool results in expected outcomes.

---

## Step 2 — Design Mock Tool Data (Approach B only)

### One Entry Per Tool Per Evaluator

When setting up mock data for a new evaluator, add exactly one input/output entry per tool — the mapping for this scenario's test user. Do not add multiple entries for the same user.

```json
"information": [
  {"input": {"phone": "8645239892"}, "output": {"id": "B001", "name": "John Carter", "dob": "03/14/1982"}}
]
```

The total `information` array across all evaluators will accumulate one entry per test user per tool. Each new evaluator contributes one new entry (append-not-replace — see below).

### Generating Sufficient Variation for Precise Fuzzy Matching

Cekura finds the **closest** input in the `information` array. If entries are too similar, the wrong one gets returned. When creating new mock data:

- **Phone numbers:** aim for 3+ digits of difference between distinct users. Never share a phone prefix across different users.
- **IDs:** use non-overlapping ranges (B001–B009 for one user cluster, B100–B109 for another) or different prefixes entirely.
- **Names:** avoid near-matches like "John Doe" and "Jane Doe" — the fuzzy matcher sees these as close.
- **Dates of birth:** span different decades to prevent partial collisions.
### Chain Dependencies

If tool B uses an ID returned by tool A, mock data must be consistent across tools. Design the full data graph before configuring anything:

```
get_user_info(phone) → {id: "B001", ...}
get_account(user_id: "B001") → {account_id: "ACC-4421", balance: 1250.00}
get_transactions(account_id: "ACC-4421") → [{...}, {...}]
```

All cross-tool references (user IDs, account numbers, booking references) must be identical across tools for the same test user.

### Append-Not-Replace

When adding entries to an existing tool, always GET first → merge → PATCH the full combined array. A PATCH with only new entries **replaces all existing mappings**.

```bash
# Wrong — wipes existing mappings:
PATCH /test_framework/v1/mock-tools/{id}/ -d '{"information": [<new entries only>]}'

# Right:
GET /test_framework/v1/aiagents/{agent_id}/tools/  # get current information array
# append new entries to existing array, then:
PATCH /test_framework/v1/mock-tools/{id}/ -d '{"information": [<full merged array>]}'
```

### Large Payload Workaround

For tools with large `information` arrays (many mappings or large output objects), use curl with a file — MCP URL-encodes parameters and can hit nginx's URI limit:

```bash
curl -X POST https://api.cekura.ai/test_framework/v1/aiagents/{agent_id}/tools/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @tool.json
```

---

## Step 3 — Create or Reuse Test Profiles

### Profile Structure

```json
{
  "name": "John Carter — Loan Payoff",
  "project": 2998,
  "information": {
    "customer_name": "John Carter",
    "date_of_birth": "03/14/1982",
    "customer_phone_number": "8645239892",
    "backup_phone_number": "5551234567",
    "account_id": "B001",
    "loan_balance": "12,450.00"
  }
}
```

Profiles are project-level — always set `project`, not `agent`.

### Template Variable Syntax

- `{{test_profile.field_name}}` — standard dot access
- `{{test_profile['key with spaces']}}` — bracket notation for keys containing spaces
- `{{test_profile.address.city}}` — nested access

In voice scenarios, the simulated caller reads from the instruction text. The profile data is there for the caller to reference — it is not injected as hidden context.

### When to Create New vs. Reuse

**For Approach B — check mock data first:**

| Mock data situation | Profile action |
|--------------------|---------------|
| Existing mock entries fit this scenario | Find the test profile derived from those entries and reuse it |
| Existing entries fit but corresponding profile has only a SUBSET of required fields | Reuse the existing mock entries; create a new profile with all required fields |
| No existing mock entries fit the scenario | Create new mock entries (sufficiently distinct from existing), derive a new profile from those outputs |

**For Approach A — check profiles directly:**

| Situation | Action |
|-----------|--------|
| Existing profile has all required fields in the correct format | Reuse |
| Existing profile has only a SUBSET of required fields | Create new — never use a partial profile |
| Existing profile has all fields but in wrong format (e.g., date format mismatch vs staging) | Create new with correct format |
| Need a different test persona for coverage breadth | Create new with distinct identity |
| Existing profile is tied to another scenario's inbound phone | Create new to avoid mock data collisions |

**The partial-match rule:** If a profile has fields A and B but the scenario needs A, B, and C — the testing agent will improvise C. This breaks authentication and verification flows silently. Always use a complete profile.

### Deriving Profile Values from Mock Outputs (Approach B)

All profile fields that the testing agent uses for verification must come from mock tool outputs — same value, same format. If `get_user_info` returns `{"dob": "03/14/1982"}`, the profile must have `"date_of_birth": "03/14/1982"`. Never create them separately.

The profile must contain:
- All **lookup keys** the agent will call tools with (phone number, account ID, etc.)
- All **verification fields** the agent will ask the caller to confirm (DOB, SSN last 4, name)
- Any **contextual data** the testing agent needs to respond naturally (appointment type, loan balance, preferred time)

### Building from Real Call Transcripts

For Approach A or when you need realistic data:
1. Pull recent production transcripts from the observability endpoint
2. Identify what data the agent requested and what the caller provided
3. Extract exact values — formats, IDs, phone numbers as they appear in real calls
4. Build the profile from those values to ensure compatibility with the production backend

---

## Step 4 — Dynamic Variables

Dynamic variables are values the main agent reads at the start of each call — caller identity, account context, or per-run configuration.

### Generating Values for Dynamic Variables

List all registered variables before generating data:

```
GET /test_framework/v1/aiagents/{agent_id}/dynamic-variables/
```

For each variable, read its description — this specifies the expected format, type, and structure. Then:

- **If the variable maps to a fact in the mock tool output** (e.g., `account_id` corresponds to `id` in `get_user_info`): use the exact same value from the mock output.
- **If the variable is not exercised by this scenario**: use a sensible default (`null`, `false`, `[]`) — never omit a variable.
- **Format must match the description exactly**: if the description says "MM/DD/YYYY", the value must be in that format — not "YYYY-MM-DD". If existing mock data uses a specific format, match it.

Every registered variable must have a value — never skip a key.

### Generating the Data Trio

For each evaluator, generate mock tool entries, test profile, and dynamic variable values as one synchronized unit. Follow this process:

**Step 1 — Try to reuse existing mock data (all-or-nothing)**
Scan existing mock tool entries. If a single identity can satisfy **every** step of the scenario across all tools, reuse those entries. You cannot mix identities — if identity A covers tool 1 but not tool 2, skip to Step 2.

Exception: if the scenario instructions explicitly name a person or identifier, only reuse existing data if it matches those exact values.

**Step 2 — Generate a new identity if needed**
If no existing identity fulfills the full scenario, generate a completely new identity (ID, name, phone, etc.) that does not appear anywhere in the existing mock data. Follow the variation rules from "Generating Sufficient Variation" to ensure it is distinct enough for fuzzy matching.

**Scope rule:** Only generate entries for tools the scenario actually calls. If the agent has 4 tools but the scenario exercises 2, output entries for those 2 only.

**Pattern recognition — identify which patterns apply before generating outputs:**

| Pattern | When | Required behavior |
|---------|------|-------------------|
| Cardinality | Scenario needs the caller to choose between options | Tool output must return ≥2 distinct items; the chosen ID must be in the test profile |
| Branching | Scenario follows "new user" or "not found" path | Tool output must return a NotFound/Empty/failure status |
| Validation failure | Scenario requires a verification check to fail, triggering a fallback | **Deliberately mismatch**: test profile value ≠ mock tool "stored" value for that field |
| Logic-first PII | Agent description requires data the scenario instructions don't mention | Include it in the test profile and variables anyway |

### Consistency: Same Fact in Profile and Variables

Test profile value == variable value == tool input value — they must be identical strings for the same fact across all three. The only exception is the validation failure pattern, where the mismatch is intentional.

---

## API Reference

### Mock Tool Endpoints

```
PATCH /test_framework/v1/mock-tools/{tool_id}/
```

Append a new entry to the tool's `information` array (GET first → merge → PATCH full array).

```json
{
  "information": [
    {"input": {"phone": "8645239892"}, "output": {"id": "B001", "name": "John Carter", "dob": "03/14/1982"}}
  ]
}
```

### Test Profile Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/test-profiles/` | Create profile |
| GET | `/test_framework/v1/test-profiles/` | List profiles (`?project_id=<id>`) |
| GET | `/test_framework/v1/test-profiles/{id}/` | Get profile |
| PATCH | `/test_framework/v1/test-profiles/{id}/` | Update profile |
| DELETE | `/test_framework/v1/test-profiles/{id}/` | Delete profile |

### Phone Number Pool (Approach B Inbound)

Each inbound scenario needs a unique phone to avoid mock data collisions.

```
GET /test_framework/v1/phone-numbers/?project=<id>
```

Filter for unassigned (`scenario_name: null`), US format (`+1` prefix, 12 chars). Assign via `PATCH /scenarios/{id}/` with `inbound_phone_number: <phone_id>`.

### Dynamic Variable Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/aiagents/{agent_id}/dynamic-variables/` | Upsert variables (full array) |
| GET | `/test_framework/v1/aiagents/{agent_id}/dynamic-variables/` | List registered variables |

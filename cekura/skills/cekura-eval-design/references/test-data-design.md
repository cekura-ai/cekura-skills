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

### Per-Input Branching

A single input/output mapping per tool is not enough. Each distinct input the agent might send needs its own entry.

```json
"information": [
  {"input": {"phone": "8645239892"}, "output": {"id": "B001", "name": "John Carter", "dob": "03/14/1982"}},
  {"input": {"phone": "18645239892"}, "output": {"id": "B001", "name": "John Carter", "dob": "03/14/1982"}},
  {"input": {"phone": "+18645239892"}, "output": {"id": "B001", "name": "John Carter", "dob": "03/14/1982"}},
  {"input": {"phone": "5559274103"}, "output": {"id": "B109", "name": "Priya Mehta", "dob": "11/07/1995"}},
  {"input": {"phone": "0000000000"}, "output": {"error": "not_found"}}
]
```

### Generating Sufficient Variation for Precise Fuzzy Matching

Cekura finds the **closest** input in the `information` array. If entries are too similar, the wrong one gets returned. When creating new mock data:

- **Phone numbers:** aim for 3+ digits of difference between distinct users. Never share a phone prefix across different users.
- **IDs:** use non-overlapping ranges (B001–B009 for one user cluster, B100–B109 for another) or different prefixes entirely.
- **Names:** avoid near-matches like "John Doe" and "Jane Doe" — the fuzzy matcher sees these as close.
- **Dates of birth:** span different decades to prevent partial collisions.
### Phone Format Variants (same user)

The agent receives the caller's phone number and passes it to a lookup tool — but it may reformat the number before the call (strip the country code, add `+1`, etc.). If the mock only has one format and the agent sends another, the lookup silently fails even though the number is correct.

Add all three variants pointing to the same output for every user:

```json
{"input": {"phone": "8645239892"}, "output": {"id": "B001", "name": "John Carter", "dob": "03/14/1982"}},
{"input": {"phone": "18645239892"}, "output": {"id": "B001", "name": "John Carter", "dob": "03/14/1982"}},
{"input": {"phone": "+18645239892"}, "output": {"id": "B001", "name": "John Carter", "dob": "03/14/1982"}}
```

Phone format mismatches are the most common cause of "account not found" failures during testing.

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

## Step 4 — Dynamic Variables (Outbound/WebSocket)

In **outbound voice** and **WebSocket** runs, test profile fields are forwarded to the main agent as dynamic caller variables at call start. The main agent receives them as runtime context without additional setup.

In **inbound voice** and **text/chat** runs, the main agent does not automatically receive test profile data — it arrives via the caller (testing agent) during the conversation.

Register variables via the API so Cekura's eval generator knows what values to produce for each scenario:

```bash
curl -X POST https://api.cekura.ai/test_framework/v1/aiagents/{agent_id}/dynamic-variables/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '[
    {"name": "customer_name", "description": "Full name of the caller. String. Example: \"John Carter\"."},
    {"name": "account_id", "description": "Customer account ID. Alphanumeric, prefixed with B. Example: \"B001\"."}
  ]'
```

This is an upsert — POST the full array each time. Returns 201 with the complete variable list.

---

## Data Flow by Mode

| Mode | Testing agent gets profile via | Main agent gets profile data via |
|------|-------------------------------|----------------------------------|
| Voice inbound | `{{test_profile.*}}` in instructions (reads at call time) | Inbound phone lookup → mock tool response |
| Voice outbound | `{{test_profile.*}}` in instructions | Dynamic variables forwarded at call start |
| Text/chat | `{{test_profile.*}}` in instructions | Not automatically received |
| WebSocket | `{{test_profile.*}}` in instructions | Dynamic variables forwarded at connection start |

---

## API Reference

### Mock Tool Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/aiagents/{agent_id}/tools/` | Create mock tool |
| GET | `/test_framework/v1/aiagents/{agent_id}/tools/` | List mock tools on agent |
| PATCH | `/test_framework/v1/mock-tools/{tool_id}/` | Update mock tool (append-not-replace) |
| DELETE | `/test_framework/v1/mock-tools/{tool_id}/` | Delete mock tool |

Mock tool schema:
```json
{
  "name": "get_user_info",
  "description": "Retrieves user data by phone number",
  "information": [
    {"input": {"phone": "8645239892"}, "output": {"id": "B001", "name": "John Carter", "dob": "03/14/1982"}}
  ],
  "freetext_params": ["notes"]
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

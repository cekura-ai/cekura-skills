# Test Profiles

## What They Are

Test profiles are identity containers that pass personal/contextual data to both the **testing agent** and the **main agent** (in chat/websocket runs). They enable realistic verification flows, tool call testing with known data, and consistent scenario execution.

**Key insight:** Test profiles are passed to both sides of the conversation — the simulated caller uses the data to answer verification questions, and the main agent (in text/websocket mode) receives the data to perform lookups and verify identity. This dual-flow is what makes test profiles essential for end-to-end testing.

## Always Use Test Profiles

**Never hardcode identity data in scenario instructions.** Names, DOBs, account IDs, addresses, phone numbers — all belong in test profiles, not instructions.

**Bad — hardcoded in instructions:**
```
State that your name is John Smith and your date of birth is January 1, 1990.
Provide account number ACC-12345 when asked.
```

**Good — uses test profile:**
```
Provide your name and date of birth when asked for verification.
Give your account number when the agent requests it for lookup.
```

The actual values come from the test profile's `information` object, injected via template variables.

## Template Variable Syntax

Reference test profile data in scenario instructions using double-brace notation:

| Syntax | Use Case | Example |
|--------|----------|---------|
| `{{test_profile.field_name}}` | Simple field | `{{test_profile.name}}` → "Sarah Johnson" |
| `{{test_profile.nested.field}}` | Nested data | `{{test_profile.address.city}}` → "New York" |
| `{{test_profile['key with spaces']}}` | Keys with spaces | `{{test_profile['customer name']}}` |

**Example instruction with template variables:**
```
Your date of birth is {{test_profile.date_of_birth}}. Provide it when the agent
asks for verification. Your appointment ID is {{test_profile.appointment_id}}.
```

## Test Profile Structure

```json
{
  "name": "Sarah Johnson - Scheduling Happy Path",
  "agent": 12345,
  "information": {
    "name": "Sarah Johnson",
    "date_of_birth": "01/01/1990",
    "phone": "+1-555-0123",
    "email": "sarah.j@email.com",
    "patient_id": "PT-12345",
    "insurance_provider": "Blue Cross",
    "address": {
      "street": "123 Main St",
      "city": "New York",
      "state": "NY",
      "zip": "10001"
    },
    "appointment_id": "APT-67890",
    "provider_name": "Dr. Smith"
  }
}
```

**Field requirements:**
- `name` (string, required): Descriptive profile name (max 255 chars)
- `agent` or `project` (integer, required): One must be provided
- `information` (object): Arbitrary key-value pairs — structure this to match what the agent's tools expect

## Check Existing Profiles First

**Always list existing test profiles before creating new ones.** Clients often pre-build profiles that are already tested against their mock backend or production tools. Reuse these rather than building from scratch.

List test profiles via `GET /test_framework/v1/test-profiles/?agent=<agent_id>`.

Profiles like `sarah_smith_one_upcoming` or `joseph_carter_failed_cancellation` may already exist and be specifically calibrated to trigger certain backend behaviors.

## Building Test Profiles from Real Data

The most effective approach: **pull call history from observability, analyze toolcall inputs/outputs, and build profiles from data that is known to work.**

### Data Extraction Workflow

1. **Fetch recent call transcripts:**
   List call logs via `GET /observability/v1/call-logs-external/?agent=<agent_id>`.

2. **Analyze toolcall inputs and outputs** from real calls:
   - What names/IDs did callers provide?
   - What data did tools return?
   - Which combinations led to successful flows?

3. **Build a memory document** mapping existing data:
   ```
   Known working data:
   - Patient "Sarah Johnson" (PT-12345) → has appointments, valid insurance
   - Patient "Mike Chen" (PT-67890) → no upcoming appointments (good for edge case)
   - Appointment APT-11111 → cancelable, with Dr. Smith
   - Appointment APT-22222 → already past, cannot reschedule
   ```

4. **Create test profiles** using this verified data — each profile maps to a specific scenario type (happy path, edge case, error condition).

### Why Real Data Matters

- **Production tools accept it:** No "test data not found" errors
- **Exercises real code paths:** Tools return actual response structures
- **Covers real edge cases:** Data naturally includes variations

## Profile Categories

Create profiles for different testing needs:

| Category | Purpose | Example |
|----------|---------|---------|
| Happy path | Standard successful flow | Valid patient, has appointments, good insurance |
| Verification failure | Identity mismatch | Wrong DOB, name spelling different from records |
| Edge case | Boundary conditions | No appointments, expired insurance, multiple matches |
| Error condition | System failures | Non-existent patient ID, invalid format data |
| Multi-workflow | Cross-workflow testing | Patient who needs to cancel and immediately rebook |

## Data Flow in Different Execution Modes

### Voice Mode (Inbound)
- Testing agent receives profile data via template substitution
- Main agent does NOT receive profile data directly — it queries its own backend
- Tests real verification: caller provides data → agent looks it up → agent confirms

### Voice Mode (Outbound)
- Testing agent receives profile data via template substitution
- **Test profile fields are sent to the main agent as dynamic caller variables** — mimicking what production systems provide when initiating outbound calls
- This lets you test the full end-to-end flow: agent receives caller context → agent uses it to personalize the conversation → testing agent validates

### Text/Chat Mode
- Testing agent receives profile data via template substitution
- Main agent ALSO receives profile data (simulating what a CRM/backend would provide)
- Enables tool verification without voice calls — fast, cheap iteration

### WebSocket Mode
- Same as text/chat and outbound: **test profile fields are sent as dynamic variables to the main agent**
- Enables full end-to-end testing with known data, including tool call verification

### Why This Matters for Outbound/WebSocket

For outbound callers and websocket agents, test profiles aren't just about the testing agent — they're the mechanism for passing caller context to the main agent. Without test profiles:
- The main agent has no context about who it's calling
- Tool calls that depend on caller data will fail or return unexpected results
- You can't test the production flow where the agent receives pre-populated caller info

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test_framework/v1/test-profiles/` | Create test profile |
| GET | `/test_framework/v1/test-profiles/` | List profiles (filter by `agent_id` or `project_id`) |
| GET | `/test_framework/v1/test-profiles/{id}/` | Get profile |
| PATCH | `/test_framework/v1/test-profiles/{id}/` | Update profile |
| DELETE | `/test_framework/v1/test-profiles/{id}/` | Delete profile |

## Profile Data Determines Backend Behavior

Test profile data often controls what the backend/mock returns. The profile itself doesn't have a "new patient" or "established patient" flag — that's determined by whether the mock backend recognizes the name.

**Examples:**
- Using a name the mock recognizes → `profile_found: True` → established patient flow
- Using a name the mock doesn't recognize → `profile_found: False` → new patient flow
- Using a patient ID with appointments → rescheduling/cancellation flows available
- Using a patient ID with no appointments → edge case where agent says "no upcoming appointments"

Choose profile data strategically to exercise the specific flow you need.

## Best Practices

- **Check existing profiles first** — clients often pre-build and test profiles against their backend
- **One profile per scenario type** — don't reuse the same profile across wildly different scenarios
- **Match data formats exactly** — if the backend expects DOB as "MM/DD/YYYY", use that in the profile
- **Include all fields the agent asks for** — if verification asks for name, DOB, and last 4 of SSN, profile needs all three
- **Profile data must align with mock/backend behavior** — if the mock only recognizes "Sarah" and "John" for insurance lookup, don't use "Xavier" in a profile that needs valid insurance
- **Document data provenance** — note which real calls the data came from
- **Keep profiles updated** — when backend data structures change, update profiles to match
- **Use descriptive names** — "sarah_smith_one_upcoming" or "joseph_carter_failed_cancellation" not "Test Profile 1"

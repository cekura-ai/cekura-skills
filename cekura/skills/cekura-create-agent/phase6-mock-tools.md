# Phase 6 — Main Agent Mock Tools

Set up mock responses for any external APIs or tools the main agent calls during conversations.

---

> **Auto-import providers (VAPI / Retell / ElevenLabs / Synthflow):** If you used `configure_from_provider: true` in Phase 5, skip this phase entirely — tools were auto-fetched during import. Go directly to [Phase 7](phase7-knowledge-base.md).

> **Start:** Announce "Starting Phase 6 — Main Agent Mock Tools" before doing anything in this phase.

## 6a. Determine from code and description first

**If code or description is available**, determine whether the main agent calls any external tools by reading:

- Tool/function definitions in the code (OpenAI tools array, function schemas, tool registrations)
- Tool call invocations in the main agent logic (any call to external APIs during a conversation)
- The main agent description from Phase 4 — any tools documented there
- The provider's tool list (if auto-fetched earlier)

Then state your finding and confirm:

> "I [found / did not find] any tool calls in the main agent code. [Brief reason — e.g. 'The agent calls `get_account_info` and `book_appointment`' or 'No tool definitions or external API calls are present'.] Should I [set up mock tools / skip this phase]?"

**If no code access**, ask:

> "Does your main agent call any external APIs or tools during conversations? (e.g. booking systems, CRMs, payment APIs)"

If no tools → skip to [Phase 7](phase7-knowledge-base.md).

---

## 6b. Option A — Auto-Fetch (VAPI, Retell, ElevenLabs, Pipecat)

If the provider API key and assistant ID are already set:

1. Go to **Agent Settings → Mock Tools → click Auto-Fetch**
2. Cekura fetches all tool definitions from the provider and generates sample I/O data
3. Review and toggle mock mode per tool

**Via API — new agents:** set `provider.configure_from_provider: true` inside the `provider` block when calling `POST /v2/aiagents/`. Requires `provider.agent_id` (the assistant ID on the provider) and `provider.credentials.api_key`. The create response includes a `progress_id` to poll `GET /v2/aiagents/{id}/auto-fetch-progress/?progress_id=...`.

```json
{
  "name": "My Agent",
  "project": 123,
  "provider": {
    "type": "retell",
    "agent_id": "agent_abc123",
    "credentials": { "api_key": "..." },
    "configure_from_provider": true
  }
}
```

**Via API — existing agents:** use `POST /v2/aiagents/{id}/auto-fetch/` which returns a `progress_id`; poll `GET /v2/aiagents/{id}/auto-fetch-progress/?progress_id=...` until completed.

---

## 6c. Option B — Manual setup (all providers)

Read the main agent description to find every tool name. For each tool, create a mock.

Mock tools are managed via the `mock_tools` field on the agent. **Always pass the full list** — a PATCH replaces the entire set. To add tools without losing existing ones, fetch current tools first then include them.

```bash
# Fetch current tools first
curl https://api.cekura.ai/test_framework/v2/aiagents/{agent_id}/?ql={mock_tools} \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY"

# PATCH with full list (existing + new)
curl -X PATCH https://api.cekura.ai/test_framework/v2/aiagents/{agent_id}/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "mock_tools": [
      {
        "name": "get_user_info",
        "description": "Retrieves user data based on phone number",
        "mock_data": [
          {
            "input": {"phone_number": "8645239892"},
            "output": {"borrower_id": "B001", "first_name": "John", "last_name": "Doe"}
          },
          {
            "input": {"phone_number": "18645239892"},
            "output": {"borrower_id": "B001", "first_name": "John", "last_name": "Doe"}
          }
        ],
        "freetext_params": ["notes", "reason"]
      }
    ]
  }'
```

---

## 6d. Mock tool design rules

- **`name`** must exactly match the tool name in the main agent config (max 64 chars, `[a-z0-9_-]`)
- **Multiple mappings per tool** — one entry per distinct input (different users, topics, error cases)
- **`freetext_params`** — fields to skip during match (free-text like "notes", "reason" that vary per call)
- **Phone format variants** — for phone lookups, add 10-digit, 11-digit-with-1, and E.164 forms
- **Chain dependencies** — if tool B uses output from tool A, mock data must be consistent across tools
- **Append-not-replace** — when adding entries, GET first → merge → PATCH full array; partial PATCH replaces all existing mappings

Full design guide with examples: `references/mock-tool-design.md`

---

## Phase 6 Gate

**Confirm all tools referenced in the main agent description have mock entries with at least one input/output mapping.**

Announce: "Phase 6 complete." Then immediately begin [Phase 7 — Knowledge Base](phase7-knowledge-base.md) without waiting for the user.

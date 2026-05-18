# Phase 7 — Mock Tools

Set up mock responses for any external APIs or tools the agent calls during conversations.

---

## 7a. Does the agent use tools?

Ask: "Does your agent call external APIs or tools during calls? (e.g. booking systems, CRMs, payment APIs)"

If no → skip to [Phase 8](phase8-knowledge-base.md).

---

## 7b. Option A — Auto-Fetch (VAPI, Retell, ElevenLabs, Pipecat)

If the provider API key and assistant ID are already set:

1. Go to **Agent Settings → Mock Tools → click Auto-Fetch**
2. Cekura fetches all tool definitions from the provider and generates sample I/O data
3. Review and toggle mock mode per tool

Auto-fetch is UI-only — no direct API equivalent. Manage individual tools via API afterward.

---

## 7c. Option B — Manual setup (all providers)

Read the agent description to find every tool name. For each tool, create a mock.

**Important:** `mcp__cekura__aiagents_tools_create` is not exposed by MCP — always use curl:

```bash
curl -X POST https://api.cekura.ai/test_framework/v1/aiagents/{agent_id}/tools/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_user_info",
    "description": "Retrieves user data based on phone number",
    "information": [
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
  }'
```

---

## 7d. Mock tool design rules

- **`name`** must exactly match the tool name in the agent config (max 64 chars, `[a-z0-9_-]`)
- **Multiple mappings per tool** — one entry per distinct input (different users, topics, error cases)
- **`freetext_params`** — fields to skip during match (free-text like "notes", "reason" that vary per call)
- **Phone format variants** — for phone lookups, add 10-digit, 11-digit-with-1, and E.164 forms
- **Chain dependencies** — if tool B uses output from tool A, mock data must be consistent across tools
- **Append-not-replace** — when adding entries, GET first → merge → PATCH full array; partial PATCH replaces all existing mappings

Full design guide with examples: `references/mock-tool-design.md`

---

## Phase 7 Gate

**Confirm all tools referenced in the agent description have mock entries with at least one input/output mapping.**

Move to [Phase 8 — Knowledge Base](phase8-knowledge-base.md).

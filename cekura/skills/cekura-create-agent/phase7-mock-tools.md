# Phase 7 — Main Agent Mock Tools

Set up mock responses for any external APIs or tools the main agent calls during conversations.

---

> **Auto-import providers (VAPI / Retell / ElevenLabs / Synthflow):** If you used `configure_from_provider: true` in Phase 5, skip this phase entirely — tools were auto-fetched during import. Go directly to [Phase 8](phase8-knowledge-base.md).

> **LiveKit with the Cekura SDK (Phase 6):** Mocks defined here are auto-injected by the SDK at runtime — no agent-side wiring needed. Skip 7e.

> **Start:** Announce "Starting Phase 7 — Main Agent Mock Tools" before doing anything in this phase.

## 7a. Determine from code and description first

**If code or description is available**, determine whether the main agent calls any external tools by reading:

- Tool/function definitions in the code (OpenAI tools array, function schemas, tool registrations)
- Tool call invocations in the main agent logic (any call to external APIs during a conversation)
- The main agent description from Phase 4 — any tools documented there
- The provider's tool list (if auto-fetched earlier)

Then state your finding and confirm:

> "I [found / did not find] any tool calls in the main agent code. [Brief reason — e.g. 'The agent calls `get_account_info` and `book_appointment`' or 'No tool definitions or external API calls are present'.] Should I [set up mock tools / skip this phase]?"

**If no code access**, ask:

> "Does your main agent call any external APIs or tools during conversations? (e.g. booking systems, CRMs, payment APIs)"

If no tools → skip to [Phase 8](phase8-knowledge-base.md).

---

## 7b. Option A — Auto-Fetch (VAPI, Retell, ElevenLabs, Pipecat)

If the provider API key and assistant ID are already set:

1. Go to **Agent Settings → Mock Tools → click Auto-Fetch**
2. Cekura fetches all tool definitions from the provider and generates sample I/O data
3. Review the mock data per tool — mock tools are activated per-run by passing `mock_tool_names` when running scenarios

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

## 7b-2. Option A (custom) — Auto-Fetch from a self-hosted MCP server

For **self-hosted / custom agents** that expose their own [MCP](https://modelcontextprotocol.io) server (JSON-RPC 2.0), auto-fetch works directly via the API/MCP — no managed provider needed. Cekura reads the server's tool list, generates mock data, then hosts a drop-in mock MCP endpoint you point the agent at (so 7e wiring is a single endpoint swap, not per-tool). Drive it yourself with the Cekura MCP tools:

1. **Auto-fetch** — `aiagents_tools_auto_fetch_create` with `provider="custom"`, `mcp_server_url`, optional `mcp_server_headers` (auth). Reads `tools/list` and LLM-generates mock I/O. Returns a `progress_id`.
   - URL is SSRF-validated (http/https only; private/loopback/metadata IPs blocked; `Host`/`Cookie`/`X-Forwarded-*` headers rejected). Headers stored encrypted. One MCP server per agent.
2. **Poll** — `aiagents_tools_auto_fetch_progress_retrieve` until `status="completed"`. Saves mock tools; does **not** activate mocking.
3. **Review/edit** the generated mock data (7d design rules).
4. **Enable mock** — `aiagents_tools_enable_mock_create` (`provider="custom"`), then poll `aiagents_tools_enable_mock_progress_retrieve`. The completed response returns `mcp_endpoints[]` (`{mock_index, url, tool_names}`) — the Cekura-hosted mock MCP endpoint.
5. **Point the agent at it for test runs** — set the agent's MCP client to the returned `url`. Read the URL from `aiagents_tools_mock_status_retrieve`; never hand-build it.
6. **Disable** later with `aiagents_tools_disable_mock_create` (`provider="custom"`); the stored `mcp_server_url` is preserved for re-enable.

Full flow and JSON-RPC examples: https://docs.cekura.ai/documentation/integrations/custom-integration#mock-an-mcp-server

> **If the `aiagents_tools_*` MCP tools aren't available**, the Cekura MCP server hasn't regenerated from the latest spec yet. Fall back to raw REST against the same paths (see `references/api-reference.md` → "Auto-fetch & mock-mode endpoints") with the `X-CEKURA-API-KEY` header until the tools appear.

> The mock endpoint makes tools *respond*, but tool-based metrics score the **transcript** — the self-hosted agent must still emit `function_call` messages in the transcript it posts.

---

## 7c. Option B — Manual setup (all providers)

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

## 7d. Mock tool design rules

- **`name`** must exactly match the tool name in the main agent config (max 64 chars, `[a-z0-9_-]`)
- **Multiple mappings per tool** — one entry per distinct input (different users, topics, error cases)
- **`freetext_params`** — fields to skip during match (free-text like "notes", "reason" that vary per call)
- **Phone format variants** — for phone lookups, add 10-digit, 11-digit-with-1, and E.164 forms
- **Chain dependencies** — if tool B uses output from tool A, mock data must be consistent across tools
- **Append-not-replace** — when adding entries, GET first → merge → PATCH full array; partial PATCH replaces all existing mappings

Full design guide with examples: `references/mock-tool-design.md`

---

## 7e. Wire the mocks into the running agent (when auto-injection is not available)

For providers without auto-injection (everything except LiveKit + Cekura SDK), the mocks defined above are not used unless the agent itself routes tool calls to Cekura's mock endpoints. For every place the real tool is invoked, replace the call with the Cekura mock-tool endpoint during testing. This can be done in two ways:

- **In agent code** — wrap the tool call so that when running in test mode it hits `POST /test_framework/v1/mock-tools/<tool_name>/invoke/` instead of the real API. Branch on an env var (e.g. `CEKURA_USE_MOCK_TOOLS=1`) so production traffic still uses real tools.
- **In the provider configuration** — some providers (e.g. VAPI, Retell, ElevenLabs) let you point a tool's URL at an external endpoint. Set that URL to Cekura's mock endpoint for the tool. Tools auto-fetched in 7b are already wired this way.
- **Via a mock MCP endpoint (custom/self-hosted)** — if you used 7b-2, point the agent's MCP client at the single `mcp_endpoints[].url` from enable-mock instead of rewriting each tool. It speaks standard MCP JSON-RPC 2.0 and serves all the agent's mocked tools.

If the agent has no path to hit Cekura's mock endpoint, the mocks defined here will sit unused during test runs and tool calls will hit real APIs.

---

## Phase 7 Gate

**Confirm all tools referenced in the main agent description have mock entries with at least one input/output mapping, and (for non-auto-injection setups) that the agent is wired to call Cekura's mock endpoints during testing.**

Announce: "Phase 7 complete." Then immediately begin [Phase 8 — Knowledge Base](phase8-knowledge-base.md) without waiting for the user.

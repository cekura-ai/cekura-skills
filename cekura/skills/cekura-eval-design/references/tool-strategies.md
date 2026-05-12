# Tool Strategies — Full Detail

Three approaches to handling the agent's external tool calls during testing. Pick one with the user up front; it shapes the entire test infrastructure setup.

## Approach A: Client-Side Mock Data

The client manages their own mock backend (staging API, test database, etc.). Cekura doesn't mock the tools — the agent calls the real (staging) endpoints. Your job is to **align test profiles with the client's mock data** so the agent gets expected responses.

**When to use:** Client already has a staging/test environment, doesn't want to replicate their data in Cekura, or their tool behavior is too complex to mock (multi-step state machines, database transactions).

**Workflow:**
1. Ask the user for their mock/staging data — what inputs produce what outputs in their system
2. Create test profiles that match those inputs exactly (names, IDs, phone numbers, dates — all must match what the staging system expects)
3. Verify data formats align: if the client's system expects `MM/DD/YYYY` for DOB, the test profile must use that format, not `YYYY-MM-DD`
4. Scenarios reference test profile data generically ("provide your date of birth when asked") — the testing agent reads from the profile, the agent sends it to the real staging backend
5. No Cekura mock tools needed — leave them disabled

**Key questions to ask the user:**
- "What test data exists in your staging environment? (test users, accounts, etc.)"
- "What format does your system expect for dates, phone numbers, IDs?"
- "Are there specific test accounts I should use, or can we create new ones?"

**Validation:** Run a scenario and check transcript — if the agent says "I couldn't find your account" or gets authentication errors, the test profile data doesn't match the staging system.

## Approach B: Cekura Mock Tools

Cekura intercepts the agent's tool calls and returns pre-configured mock responses. The agent never hits a real backend. Your job is to **set up mock tool mappings and ensure test profiles match the mock outputs**.

**When to use:** No staging environment, want fully isolated tests, need predictable responses for every scenario, or the agent's tools are simple enough to mock (lookups, bookings, CRUD operations).

**Workflow:**
1. **Auto-fetch tools** (recommended for VAPI/Retell/ElevenLabs): In Cekura UI, go to Agent Settings → Mock Tools → Auto-Fetch. Cekura pulls all tool definitions from the provider and generates sample I/O data. Then enable mock mode per tool.
2. **Review auto-fetched mappings** — List the agent's tools to see what was created. Each tool has an `information` array of input/output pairs.
3. **Add per-scenario mappings** — Auto-fetch creates illustrative examples, not exhaustive data. For each scenario you'll test, add the specific input/output pairs that scenario needs. If a tool accepts different parameters (different users, topics, actions), each variant needs its own mapping. See `mock-tool-design.md`.
4. **Create test profiles FROM the mock data** — Derive all profile fields from mock tool outputs. If `get_user_info` returns `{"first_name": "John", "dob": "01/15/1990"}`, the test profile must have those exact values. Never create profile data independently.
5. **Use auto-gen with mock awareness** — When mock tools are enabled on the agent, the generate endpoint creates tool-aware scenarios automatically. Scenarios will reference the mocked tools in their instructions.
6. **Validate runs** — After running, check transcripts for: tool calls returning expected data, agent using the mock data correctly, no "tool not found" or format mismatch errors.

**Key questions to ask the user:**
- "Can I auto-fetch your tools from the provider, or do we need to set them up manually?"
- "For each tool, what are the different inputs the agent might send?" (per-input branching)
- "Do any tools depend on data from other tools?" (chain dependencies)

**Handling large mock-tool payloads:** if a tool's `information` array is large (many input/output mappings, or large output objects), create or update the tool by POSTing a direct JSON body via the API rather than passing parameters through tools that may URL-encode them:

```bash
curl -X POST https://api.cekura.ai/test_framework/v1/aiagents/{agent_id}/tools/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @tool.json
```

## Approach C: No Mock Data

The agent either doesn't use external tools, or the tools aren't relevant to what you're testing. Use test profiles for caller identity but don't worry about tool responses.

**When to use:** Agent is conversational only (no tool calls), testing soft skills/tone/adherence rather than tool-dependent workflows, or tools are optional and the scenario focuses on the dialog path.

**Workflow:**
1. Create test profiles with caller identity data (name, DOB, etc.)
2. Write scenarios focused on conversational behavior, not tool outcomes
3. Expected outcomes should not reference tool results — focus on what the agent says and does
4. If the agent attempts tool calls, they'll hit the real backend (or fail if there's no backend). Decide with the user whether that's acceptable.

**Key questions to ask the user:**
- "Does your agent use any external tools during calls?"
- "Are we testing the tool-dependent workflows, or just the conversational quality?"

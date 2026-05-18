# Phase 4 — Create the Agent

Create the agent record on Cekura using the data collected in Phases 1–3.

---

## 4a. Create via MCP (description ≤ 4 KB)

For short descriptions, use the MCP tool:

```
mcp__cekura__aiagents_create with:
  agent_name: "Customer Support Bot"
  project: <project_id>
  language: "en"
  description: "<full system prompt>"
  contact_number: "+14155551234"
  inbound: true
```

---

## 4b. Create via curl (description > 4 KB)

MCP tools URL-encode parameters and hit nginx's URI length limit on large payloads (multi-state agents, full exported configs). Use curl instead:

```bash
curl -X POST https://api.cekura.ai/test_framework/v1/aiagents/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @agent.json
```

Or use the included helper script:

```bash
scripts/upload-agent.sh agent.json          # create new
scripts/upload-agent.sh agent.json <id>     # update existing
```

Where `agent.json` contains the full payload:

```json
{
  "agent_name": "Customer Support Bot",
  "project": 123,
  "language": "en",
  "description": "<full system prompt or exported config>",
  "contact_number": "+14155551234",
  "inbound": true
}
```

---

## 4c. Save the agent ID

The response includes an `id` field. **Record it — every subsequent step requires it.**

---

## Phase 4 Gate

**Do not proceed until the agent is created and you have its `id`.**

Move to [Phase 5 — Provider Integration](phase5-provider.md).

# Phase 10 — Verify Setup

Confirm the agent is fully configured and ready for testing before handing off to the next skill.

---

> **Start:** Announce "Starting Phase 10 — Verify Setup" before doing anything in this phase.

## 10a. Verification checklist

Run through each item:

1. **Agent exists** — retrieve the agent via the API → confirm `name`, `description`, `telephony.phone_number`
2. **Provider connected** — `provider.type`, `provider.credentials.api_key`, and `provider.agent_id` (where applicable) are all set
3. **Connection mode confirmed** — `telephony.phone_number` present, OR `provider.chat_agent_details` set, OR WebRTC credentials configured
4. **Mock tools configured** — list mock tools via the API → every tool in the agent description has at least one mapping
5. **Knowledge base** — `knowledge_base_files` on the agent object matches what was uploaded (or confirmed empty)
6. **Dynamic variables** — all runtime-injected variables are registered via the API (or confirmed none needed)
7. **End-to-end test** — see 10b below

---

## 10b. End-to-end verification run

Ask the user:

> "Would you like me to generate a single test scenario and run it now to verify the agent is working end-to-end?"

If yes, proceed. If no, skip to 10c.

**Step 1 — Generate one scenario**

Use the Cekura API to auto-generate a single scenario for the agent:

```bash
# Start scenario generation
curl -X POST https://api.cekura.ai/test_framework/v1/scenarios-external/generate/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent": <agent_id>, "count": 1}'
```

Poll the progress endpoint until `status` is `completed`, then use the returned scenario ID.

**Step 2 — Run the scenario**

Run it using the appropriate connection mode for this agent (websocket, voice, text, etc.):

```bash
# Example for WebSocket/text mode
curl -X POST https://api.cekura.ai/test_framework/v1/scenarios-external/run-text/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scenarios": [{"scenario": <scenario_id>}]}'
```

Wait for the run to complete (poll the result).

**Step 3 — Check the transcript**

Retrieve the run result and inspect the transcript. **Success criteria:**

- The transcript contains at least 2 turns
- Both the simulated caller AND the agent have spoken (both sides have messages)
- Neither side is silent or shows only an error message

If the transcript shows a real back-and-forth conversation → **setup is confirmed working**.

If the transcript is empty, one-sided, or contains an error → diagnose and fix before proceeding:
- Empty transcript: connection failed — check WebSocket URL, credentials, or phone number
- Only caller messages: agent is not responding — check agent is running and reachable
- Error in result: check the error message and fix the underlying issue

---

## 10c. Summary for the user

Present a summary before handing off:

```
Agent: [name] (ID: [id])
Project: [project_id]
Provider: [provider.type] (agent_id: [provider.agent_id])
Connection mode: [phone / WebRTC / chat / WebSocket]
Mock tools: [count] configured
Knowledge base: [count] files
Dynamic variables: [list or "none"]
```

---

## 10d. Next steps

The agent is ready. Point the user to what comes next:

| Goal | Skill |
|------|-------|
| Generate test evaluators | **cekura-eval-design** |
| Create quality metrics | **cekura-metric-design** |
| Full platform walkthrough | **cekura-onboarding** |
| Run a quality report | **cekura-report** |

---

## Phase 10 Gate

**All phases complete. The skill ends here.**

Announce: "Phase 10 complete. Agent setup is done — the agent is ready for testing."

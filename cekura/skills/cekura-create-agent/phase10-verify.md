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
7. **Run one test** — suggest running a single simple evaluator to confirm end-to-end connectivity

---

## 10b. Summary for the user

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

## 10c. Next steps

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

# Phase 11 — Verify Setup

Confirm the agent is fully configured and ready for testing before handing off to the next skill.

---

## 11a. Verification checklist

Run through each item:

1. **Agent exists** — `mcp__cekura__aiagents_retrieve` → confirm `agent_name`, `description`, `contact_number`
2. **Provider connected** — `assistant_provider`, API key field, and `assistant_id` are all set
3. **Connection mode confirmed** — phone number present, OR chat/WebRTC credentials set, OR `websocket_url` set
4. **Mock tools configured** — `mcp__cekura__aiagents_tools_list` → every tool in the agent description has at least one mapping
5. **Knowledge base** — `knowledge_base_files` on the agent object matches what was uploaded (or confirmed empty)
6. **Dynamic variables** — detected variables match the `{{placeholders}}` in the description (or confirmed none)
7. **Run one test** — suggest running a single simple evaluator to confirm end-to-end connectivity

---

## 11b. Summary for the user

Present a summary before handing off:

```
Agent: [name] (ID: [id])
Project: [project_id]
Provider: [provider] (assistant: [assistant_id])
Connection mode: [phone / WebRTC / chat / WebSocket]
Mock tools: [count] configured
Knowledge base: [count] files
Dynamic variables: [list or "none detected"]
Advanced: [LLM model / topic nodes / etc. — or "defaults"]
```

---

## 11c. Next steps

The agent is ready. Point the user to what comes next:

| Goal | Skill |
|------|-------|
| Generate test evaluators | **cekura-eval-design** |
| Create quality metrics | **cekura-metric-design** |
| Full platform walkthrough | **cekura-onboarding** |
| Run a quality report | **cekura-report** |

# Phase 10 — Verify Main Agent Setup

Confirm the main agent is fully configured and verify it works end-to-end with a real test run. **This phase does not end until the run succeeds.**

---

> **Start:** Announce "Starting Phase 10 — Verify Main Agent Setup" before doing anything in this phase.

## 10a. Verification checklist

Run through each item:

1. **Main agent exists** — retrieve the main agent via the API → confirm `name`, `description`, `telephony.phone_number`
2. **Provider connected** — `provider.type`, `provider.credentials.api_key`, and `provider.agent_id` (where applicable) are all set
3. **Connection mode confirmed** — `telephony.phone_number` present, OR `provider.chat_agent_details` set, OR WebRTC credentials configured
4. **Mock tools configured** — list mock tools via the API → every tool in the main agent description has at least one mapping
5. **Knowledge base** — `knowledge_base_files` on the main agent object matches what was uploaded (or confirmed empty)
6. **Dynamic variables** — all runtime-injected variables are registered via the API (or confirmed none needed)

---

## 10b. End-to-end verification run (mandatory)

**Do not ask permission. Run this automatically using MCP tools.**

**This step is not complete until the transcript shows a real conversation — both the testing agent and the agent must have exchanged messages.**

**Step 1 — Generate one scenario using the MCP generate tool**

Use `mcp__cekura__scenarios_generate_bg` to auto-generate a single scenario for the agent. Do not write or create a scenario manually. Pass `agent_id` and `count: 1`. Poll `mcp__cekura__scenarios_generate_progress` until `status` is `completed`, then use the returned scenario ID.

**Step 2 — Run the scenario using the MCP run tool**

Use the appropriate MCP tool based on the main agent's connection mode. Do not construct API calls manually — call the MCP tool directly:

| Connection mode | MCP tool |
|----------------|----------|
| WebSocket / text | `mcp__cekura__scenarios_run_text` |
| Voice / phone | `mcp__cekura__scenarios_run_voice` |
| SIP | `mcp__cekura__scenarios_run_sip` |
| WebRTC (VAPI) | `mcp__cekura__scenarios_run_vapi_webrtc` |
| WebRTC (Retell) | `mcp__cekura__scenarios_run_retell_webrtc` |
| WebRTC (LiveKit) | `mcp__cekura__scenarios_run_livekit_v2` |
| WebRTC (Pipecat) | `mcp__cekura__scenarios_run_pipecat_v2` |
| WebRTC (ElevenLabs) | `mcp__cekura__scenarios_run_elevenlabs` |

Poll the result using `mcp__cekura__results_retrieve` until the run is complete, then inspect the transcript.

**Step 3 — Check the transcript**

Inspect `transcript_object` in the result — **not** just the run status or `connected_runs`.

**Success requires ALL of:**
- `transcript_object` is non-empty and contains real message text
- At least 2 turns present
- Both the testing agent AND the agent have messages in the transcript
- The main agent's messages are non-empty actual responses

**A run that is "connected" or "completed" with an empty `transcript_object` is a FAILURE.** Connection alone proves nothing about the main agent working — messages must have actually been exchanged.

**Failure — diagnose and fix, then retry:**

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| `transcript_object` empty, run shows as connected | Main agent connected but sent no messages — responses not in Cekura's expected format `{"content": "..."}`, or agent code isn't sending | Fix agent response format and retry |
| Empty transcript, not connected | Server not reachable — go back to Phase 3, fix URL, retry | — |
| Only testing agent messages, agent silent | Agent not responding | Check agent is running and sending responses |
| Only main agent messages, no testing agent | Scenario runner issue | Check dynamic variables, scenario instructions |
| Tool call errors | Missing mock tools | Go back to Phase 6, add/fix mock tools |
| Variable substitution errors | Missing dynamic variables | Go back to Phase 8, register the variables |
| Agent gives empty/wrong responses | Description too vague | Go back to Phase 4, improve the description |

**After fixing any issue, re-run from Step 1.** Do not move to the summary until the run produces a real back-and-forth conversation in the transcript.

---

## 10c. Summary for the user

Only present this after the verification run succeeds:

```
Agent: [name] (ID: [id])
Project: [project_id]
Provider: [provider.type] (agent_id: [provider.agent_id])
Connection mode: [phone / WebRTC / chat / WebSocket]
Mock tools: [count] configured
Knowledge base: [count] files
Dynamic variables: [list or "none"]
Verification: ✓ Run confirmed — testing agent and main agent exchanged messages
```

---

## 10d. Next steps

The main agent is ready. Point you to what comes next:

| Goal | Skill |
|------|-------|
| Generate test evaluators | **cekura-eval-design** |
| Create quality metrics | **cekura-metric-design** |
| Full platform walkthrough | **cekura-onboarding** |
| Run a quality report | **cekura-report** |

---

## Phase 10 Gate

**The skill does not end until the verification run succeeds.** If the run fails, fix the issue and retry. Do not announce completion until the transcript confirms a real conversation happened.

Announce: "Phase 10 complete. Verification confirmed — the main agent is working end-to-end."

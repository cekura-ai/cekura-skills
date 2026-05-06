# Phase 1 — Debug the Issue

Understand exactly what went wrong before touching any code or building any evaluator.

---

## 1a. Fetch the production call

If a call ID was not provided, **ask the user for it** — do not browse recent calls. The user knows which call had the issue.

Fetch the full call:

```bash
get_call "CALL_ID"
```

Extract and record:

| Field | Path |
|---|---|
| Real agent ID | `metadata.agent_id` (not top-level `agent_id`) |
| Personality ID | `metadata.personality_id` |
| Project ID | `project` field on the agent |
| Customer data | `dynamic_variables` |
| Ended reason | `metadata.ended_reason` |
| Transcript | `transcript_object` (array of turns with role + content) |
| Failing metrics | `runs[].evaluation.metrics[]` — note which ones failed and their names |

Fetch agent config:

```
cekura:aiagents_retrieve  →  id = metadata.agent_id
```

Extract: `description` (system prompt).

---

## 1b. Check logs and traces

Use all available observability tools to build a complete picture of what happened during the call. Search using `call_id`, `session_id`, agent ID, or the call's timestamp range.

### Datadog — logs and APM traces
Use Datadog MCP tools to search logs and traces:
- `search_datadog_logs` — search application logs around the call timestamp
- `search_datadog_spans` / `get_datadog_trace` — find the trace for this call and inspect individual spans
- `search_datadog_events` — check for errors or anomalies flagged during the call
- `analyze_datadog_logs` — summarise log patterns around the failure window

### LLM observability — LLMObs / Langfuse / similar
If the agent uses LLM observability (Datadog LLMObs, Langfuse, etc.), search for the LLM spans tied to this call:
- Look up the session or trace by `call_id` or `session_id`
- Inspect individual LLM call inputs, outputs, latency, and token counts
- Check for timeout signals, empty responses, or unexpected completions
- Datadog LLMObs tools: `get_llmobs_trace`, `get_llmobs_span_details`, `search_llmobs_spans`

### What to look for across all tools
- Errors or exceptions in the call handler
- Unexpected tool call inputs or outputs
- Timeouts or slow spans (STT, LLM, TTS, tool calls)
- Any upstream service returning unexpected or empty responses
- Gaps between transcript turns that suggest a silent failure

Cross-reference findings with `transcript_object` turn-by-turn to pinpoint exactly where and why the call diverged from expected behaviour.

---

## 1c. Identify the root cause

Summarise:
- What the caller said (from transcript)
- What the agent did wrong
- What the root cause is in code
- Which function / code path is responsible
- Which metrics were failing in the prod call (from `runs[].evaluation.metrics[]`)

---

## Phase 1 Gate

**Do not proceed to Phase 2 until the root cause is confirmed with the user.**

Present your analysis and ask the user to confirm:
- Is this the correct root cause?
- Are the failing metrics identified correctly?
- Is there anything else they observed in the prod call that should be captured?

Only after explicit user confirmation move to [Phase 2](phase2-reproduce.md).

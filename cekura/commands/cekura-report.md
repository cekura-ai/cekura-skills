---
name: cekura-report
description: Run a full end-to-end agent quality report — generates 10 evals, runs them, and produces a structured markdown report
argument-hint: "[agent ID] [mode: voice/text/websocket/pipecat/retell/vapi/livekit/elevenlabs/sip]"
allowed-tools:
  [
    "AskUserQuestion",
    "Read",
    "Write",
    "mcp__cekura__aiagents_retrieve",
    "mcp__cekura__aiagents_list",
    "mcp__cekura__scenarios_generate_bg",
    "mcp__cekura__scenarios_generate_progress",
    "mcp__cekura__scenarios_list",
    "mcp__cekura__scenarios_partial_update",
    "mcp__cekura__scenarios_folder_create",
    "mcp__cekura__scenarios_folders_list",
    "mcp__cekura__metrics_list",
    "mcp__cekura__scenarios_run_voice",
    "mcp__cekura__scenarios_run_text",
    "mcp__cekura__scenarios_run_websocket",
    "mcp__cekura__scenarios_run_pipecat_v1",
    "mcp__cekura__scenarios_run_pipecat_v2",
    "mcp__cekura__scenarios_run_retell_webrtc",
    "mcp__cekura__scenarios_run_vapi_webrtc",
    "mcp__cekura__scenarios_run_livekit_v2",
    "mcp__cekura__scenarios_run_elevenlabs",
    "mcp__cekura__scenarios_run_sip",
    "mcp__cekura__results_list",
    "mcp__cekura__results_retrieve",
    "mcp__cekura__results_rerun_create",
    "mcp__cekura__end_call",
  ]
---

# /cekura-report

Build a full agent quality report from scratch: confirm target → validate config → generate evals → run → analyze → write report.

---

## Step 1 — Confirm what to test

Use `AskUserQuestion` to collect (do NOT guess):

1. **Agent ID** on Cekura (numeric, e.g. `16937`). If unknown, use `mcp__cekura__aiagents_list` to help find it.
2. **Connection mode** for running the evals:
   - `voice` — generic voice call (VAPI, Retell, etc.)
   - `text` — text-only chat (fastest, cheapest)
   - `websocket` — custom websocket endpoint
   - `pipecat` — Pipecat v1 client
   - `pipecat-v2` — Pipecat v2 client
   - `retell` — Retell WebRTC
   - `vapi` — VAPI WebRTC
   - `livekit` — LiveKit v2
   - `elevenlabs` — ElevenLabs
   - `sip` — SIP
3. (Optional) Project ID, if the user manages multiple projects.
4. (Optional) Domain / product context — useful for generating realistic evaluators.

Do not proceed until agent ID + mode are confirmed.

---

## Step 2 — Validate the agent

Call `mcp__cekura__aiagents_retrieve` with the supplied `id`. Check:

- **`agent_description`** is present and substantive — at least 2 sentences covering what the agent does, who it serves, and key capabilities. Empty or placeholder descriptions produce generic, low-quality evaluators.
- **The chosen connection mode is configured**:
  - `voice` → voice provider wired up (VAPI, Retell, LiveKit, ElevenLabs, etc.)
  - `text` → text mode supported
  - `websocket` → `websocket_url` present (and `websocket_headers` if needed)
  - `pipecat` / `pipecat-v2` → Pipecat integration configured
  - `retell` → Retell WebRTC configured
  - `vapi` → VAPI WebRTC configured
  - `livekit` → LiveKit v2 configured
  - `elevenlabs` → ElevenLabs configured
  - `sip` → SIP endpoint configured
- **Knowledge base / dynamic variables**, if present, match the user's stated domain.

**If anything is missing, STOP and surface it.** Examples:

> ⚠️ The agent's `agent_description` is empty. Auto-generated evaluators will be generic. Please add a description before continuing — or confirm you want to proceed anyway.

> ⚠️ You asked for `websocket` mode but the agent has no `websocket_url`. Either configure it or choose a different mode.

Only continue once issues are resolved or the user explicitly opts to proceed.

---

## Step 3 — Generate 10 evaluators

### 3a. Create a folder

Always create a dedicated folder — never dump scenarios into root.

Check existing folders with `mcp__cekura__scenarios_folders_list`, then create:
```
mcp__cekura__scenarios_folder_create:
  name: "Report — [agent name] [date]"
  project_id: <project_id>
```

### 3b. Trigger generation

Call `mcp__cekura__scenarios_generate_bg` with:

| Field | Value |
|-------|-------|
| `agent_id` | Agent ID |
| `num_scenarios` | `10` |
| `generate_expected_outcomes` | `true` |
| `folder_path` | Folder from 3a |
| `personalities` | `[693]` (Normal Male, en/American) — adjust for non-English agents |
| `tool_ids` | `["TOOL_END_CALL"]` — add `TOOL_END_CALL_ON_TRANSFER` if agent has transfer flows |
| `extra_instructions` | Aim for: 5–6 core workflow, 2–3 edge cases, 1–2 adversarial/red-team |

Returns `{"progress_id": "<uuid>"}`.

### 3c. Poll for completion

Poll `mcp__cekura__scenarios_generate_progress` every 10 seconds until `status` is `completed` or `failed`. Generation takes 30–90 seconds for 10 scenarios — do not give up after one check.

If output looks wrong (scenarios don't match the agent's domain), pause and ask the user before continuing.

### 3d. Post-generation fixups

Fetch the generated scenarios and apply:

1. **Metrics** — `mcp__cekura__metrics_list` to find baseline metric IDs (Expected Outcome, Infrastructure Issues, Tool Call Success, Latency), then PATCH each scenario:
   ```
   mcp__cekura__scenarios_partial_update:
     id: <scenario_id>
     metrics: [<expected_outcome_id>, <infra_id>, <tool_call_id>, <latency_id>]
   ```
   Without metrics, runs report pass/fail based on call completion only — not correctness.

2. **Language** — If non-English, PATCH each scenario: `scenario_language: "es"` (or `ru`, `hi`, `zh`, etc.)

3. **First message** — If auto-gen added a greeting where you wanted an exact opener, PATCH `first_message`.

### 3e. Pre-run checklist

Confirm before running:
- [ ] All 10 scenarios have metrics attached
- [ ] `TOOL_END_CALL` is in `tool_ids` (prevents hung calls)
- [ ] `TOOL_END_CALL_ON_TRANSFER` added if agent has transfer flows
- [ ] Test profiles assigned where scenarios involve identity/booking/account lookup

---

## Step 4 — Run the evaluators

Trigger the run using the mode from Step 1:

| Mode | Tool |
|------|------|
| voice | `mcp__cekura__scenarios_run_voice` |
| text | `mcp__cekura__scenarios_run_text` |
| websocket | `mcp__cekura__scenarios_run_websocket` |
| pipecat | `mcp__cekura__scenarios_run_pipecat_v1` |
| pipecat-v2 | `mcp__cekura__scenarios_run_pipecat_v2` |
| retell | `mcp__cekura__scenarios_run_retell_webrtc` |
| vapi | `mcp__cekura__scenarios_run_vapi_webrtc` |
| livekit | `mcp__cekura__scenarios_run_livekit_v2` |
| elevenlabs | `mcp__cekura__scenarios_run_elevenlabs` |
| sip | `mcp__cekura__scenarios_run_sip` |

Pass `agent_id` and `scenarios` (array of IDs). Capture the returned `result_id`.

Poll `mcp__cekura__results_retrieve(id=result_id)` until `status` is `completed` or `failed`. Use `mcp__cekura__results_list` to monitor overall progress. If a run hangs, use `mcp__cekura__end_call` to terminate it.

If `status=failed`, inspect `failed_reasons` and surface infra issues (connection errors, websocket handshake failures) before writing the report.

---

## Step 5 — Write the report

Pull the result with `mcp__cekura__results_retrieve` and synthesize a markdown report. **Follow this structure exactly:**

### 1. Header

Result name + ID, agent name + ID, status, success rate, met / total expected outcomes.

### 2. Quick Summary of Issues

One paragraph identifying the root-cause pattern across failures (persona drift? missing tool? hallucinated facts? flow break?).

A compact table:

| Scenario | Result | Issue |
|----------|--------|-------|
| ... | ✅/❌ | one-line reason |

Be explicit about whether failures are tool/integration problems vs. config/persona/knowledge problems.

### 3. Detailed Breakdown

One subsection per run, **failures first, then passes**. Title each as a clickable link:

```
### ❌ [Run <run_id> — <scenario name>](https://dashboard.cekura.ai/<project_id>/results/<result_id>?call_id=<run_id>)
```

Use ❌ for failures, ✅ for passes.

For each: state the expected outcome, quote the most damning (or most positive) transcript line verbatim, and explain why it failed/passed. Group passes that share a reason into a single subsection with bullet-linked runs.

### 4. What Works Well

3–6 bullets of genuine strengths from the transcripts. Be specific — name the run.

### 5. Next Steps

Order by likely impact. Always include a mock-tools section with two options:

- **Option A — Configure mock tools yourself**: when the user knows which backend tools the agent calls.
- **Option B — Let Cekura surface what's needed**: re-run and inspect the tool-call trace; unmocked tools surface as failures.

If failures are clearly not tool failures (persona/knowledge/prompt drift), say so first.

Also mention: **re-run individual scenarios** that failed using `mcp__cekura__results_rerun_create` once fixes are applied — no need to re-run the full suite.

### Style rules

- Dashboard links: `https://dashboard.cekura.ai/{project_id}/results/{result_id}?call_id={run_id}`
- Quote transcript lines verbatim (with quotes)
- Don't invent metrics — only cite what's in the payload
- Tone: direct and analytical, not cheerleading

Save as `result_<result_id>_report.md` in the working directory and return the path.

---

## Failure modes to watch for

- **Empty `transcript` field but populated `transcript_object`** — render from `transcript_object` (list of `{role, content}` turns).
- **`success=true` with `error_message` set** — infra issue; don't treat as a real pass.
- **All passes on generic scenarios, all fails on specific-fact scenarios** — strong signal of persona/KB misconfiguration; call it out explicitly.
- **Auto-generated evaluators that don't match the agent's domain** — pause and re-generate with better `extra_instructions` rather than running junk.

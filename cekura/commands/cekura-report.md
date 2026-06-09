---
name: cekura-report
description: Run a full end-to-end agent quality report — generates 10–20 evals, runs them, and produces a structured markdown report
argument-hint: "[agent ID]"
allowed-tools:
  [
    "AskUserQuestion",
    "Read",
    "Write",
    "Skill",
    "mcp__cekura__aiagents_retrieve",
    "mcp__cekura__aiagents_list",
    "mcp__cekura__scenarios_generate_bg",
    "mcp__cekura__scenarios_generate_progress",
    "mcp__cekura__scenarios_list",
    "mcp__cekura__scenarios_partial_update",
    "mcp__cekura__scenarios_folder_create",
    "mcp__cekura__scenarios_folders_list",
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
  , "mcp__cekura__cekura_skill_started", "mcp__cekura__cekura_report_issue"]
---
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="cekura-report"`. If a conversation/session ID is available (e.g. you
were invoked from Cekura sandbox), also pass it as `conversation_id`. The call
returns immediately; it lets us understand which skills are actually being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, call `mcp__cekura__cekura_report_issue` to flag it. Use this
LIBERALLY — even `severity="low"` reports are valuable feedback.

# /cekura-report

Build a full agent quality report from scratch: confirm target → validate config → generate evals → configure mock data → run → analyze → write report.

---

## Step 1 — Confirm what to test

Use `AskUserQuestion` to collect:

1. **Agent ID** on Cekura (numeric, e.g. `16937`). If unknown, use `mcp__cekura__aiagents_list` to help find it.
2. (Optional) Project ID, if the user manages multiple projects.
3. (Optional) Domain / product context — useful for generating realistic evaluators.

**Do NOT ask for connection mode here.** Connection mode is collected later, right before the run (Step 4).

### If the user wants to create an agent first

If the user's intent is "I want to create an agent" / "set up a new agent" / "I don't have an agent yet" — do **not** proceed with this report flow. Delegate to the `cekura:cekura-create-agent` skill via `Skill` and resume here once they have an agent ID.

Do not proceed until the agent ID is confirmed.

---

## Step 2 — Validate the agent

Call `mcp__cekura__aiagents_retrieve` with the supplied `id`. Check:

- **`agent_description`** is present and substantive — at least 2 sentences covering what the agent does, who it serves, and the workflows it supports. Empty or placeholder descriptions produce generic, low-quality evaluators.
- **Knowledge base / dynamic variables**, if present, match the user's stated domain.
- **Provider** — note which provider the agent is configured with (VAPI, Retell, ElevenLabs, LiveKit, Pipecat, websocket, SIP, text). You'll need this in Step 3 to decide the mock-data options and in Step 4 to pick the run tool.

**If `agent_description` is missing or weak, STOP and surface it:**

> ⚠️ The agent's `agent_description` is empty / very short. Auto-generated evaluators will be generic. Please add a description (workflows, audience, key capabilities) before continuing — or confirm you want to proceed anyway.

Do **not** validate the connection mode here — that happens in Step 4 once the user has chosen the mode.

Only continue once description issues are resolved or the user explicitly opts to proceed.

---

## Step 3 — Generate evaluators (10–20, sized to agent complexity)

### 3a. Decide how many scenarios to generate

Read the `agent_description` and count distinct workflows / capabilities.

| Description signal | Suggested count |
|---|---|
| Basic — 1–2 workflows, narrow scope (e.g. "answers FAQs about hours and location") | **10** |
| Moderate — 3–5 workflows (e.g. clinic receptionist that books, cancels, reschedules, answers hours) | **12–15** |
| Complex — 6+ workflows, multiple personas served, branching flows, KB-grounded answers, transfer logic, post-call actions | **17–20** |

Pick a number in `[10, 20]` and tell the user the count + reasoning before generating. They can override.

### 3b. Configure mock data for tool-dependent scenarios

Some scenarios need pre-existing state in the user's backend (e.g. cancelling an appointment assumes one exists; checking an order assumes the order ID is in their system). For those, decide upfront how to handle the mocks.

**Always ask the user via `AskUserQuestion`. Options depend on the agent's provider:**

**If provider is `retell`, `vapi`, or `elevenlabs` — offer 3 options:**

1. **Use Cekura's mock tool functionality** — Cekura intercepts the tool call and returns a mock response. No changes needed in the user's backend. Best for fast iteration.
2. **Get a list of mock data to add to your system** — Cekura tells you the exact records (IDs, names, statuses) it will reference; you seed them in your backend before the run.
3. **Skip scenarios that require mock state** — only generate/keep scenarios that don't depend on backend state (e.g. greetings, FAQs, booking-new-appointment flows, off-topic deflection).

**For all other providers (websocket, pipecat, pipecat-v2, livekit, sip, text) — offer only 2 options:**

1. **Get a list of mock data to add to your system**
2. **Skip scenarios that require mock state**

(Cekura's hosted mock-tool layer isn't wired up for those providers.)

**Example — clinic receptionist that books and cancels appointments:**
- *Booking new appointment* — no mock state needed; can run as-is.
- *Cancelling an existing appointment* — requires an appointment record in the backend (or a Cekura mock for the cancel tool). This is what the user is choosing the option for.

After the user picks an option, record it. You'll apply it after generation:
- **Cekura mock tools** (only offered for Retell/VAPI/ElevenLabs):
  1. Check the agent record for whether mock tools are already configured.
  2. If **not configured**, ask the user: *"Mock tools aren't enabled on this agent. Want me to configure them now, or skip the scenarios that need backend state?"*
     - If they want to configure → enable mock tools on the agent and auto-fetch all tools so each one has a mock entry.
     - If they want to skip → fall back to the *Skip* option below.
  3. Right before running the scenarios in Step 4, ensure mock tools are enabled on the agent.
- **List for user's system** → produce a markdown table of `{tool name, parameters the scenario will pass, record the user must seed}` and share it with the user.
- **Skip** → after generation, identify scenarios that depend on backend state and either delete them or replace them with backend-stateless variants.

### 3c. Create a folder

Always create a dedicated folder — never dump scenarios into root.

Check existing folders with `mcp__cekura__scenarios_folders_list`, then create:
```
mcp__cekura__scenarios_folder_create:
  name: "Report — [agent name] [date]"
  project_id: <project_id>
```

### 3d. Trigger generation

Call `mcp__cekura__scenarios_generate_bg` with:

| Field | Value |
|-------|-------|
| `agent_id` | Agent ID |
| `num_scenarios` | Count from 3a (10–20) |
| `generate_expected_outcomes` | `true` |
| `folder_path` | Folder from 3c |
| `personalities` | `[693]` (Normal Male, en/American) — adjust for non-English agents |
| `tool_ids` | `["TOOL_END_CALL"]` — add `TOOL_END_CALL_ONLY_ON_TRANSFER` if the agent has transfer flows |
| `extra_instructions` | Coverage mix scaled to the count: ~60% core workflow, ~25% edge cases, ~15% adversarial/red-team. Tell the generator about the mock-data choice from 3b so it doesn't generate scenarios that will be skipped. |

Returns `{"progress_id": "<uuid>"}`.

### 3e. Poll for completion

Poll `mcp__cekura__scenarios_generate_progress` every 10 seconds until `status` is `completed` or `failed`. Generation takes 30–120 seconds depending on count — do not give up after one check.

If output looks wrong (scenarios don't match the agent's domain), pause and ask the user before continuing.

### 3f. Apply the mock-data choice from 3b

Now execute whichever option the user picked in 3b:
- **Cekura mock tools** → ensure mock tools are enabled on the agent before running.
- **List for user's system** → emit the markdown seed-data table and wait for the user to confirm records are seeded before running.
- **Skip** → delete or disable any generated scenarios that depend on backend state.

---

## Step 4 — Pick the connection mode and run

### 4a. Derive candidate modes from the agent record

Use the agent record from Step 2 (`provider.type`, `telephony.phone_number`, `telephony.websocket_url`, `provider.chat_agent_details`, `telephony.sip_uri`, `telephony.inbound`) to compute the set of **valid** modes. **Do not** present modes the agent isn't configured for.

The three telephony-style modes are distinct:
- **`voice`** = generic PSTN call to a `telephony.phone_number`. Works with any provider that publishes a phone number.
- **`sip`** = only when `telephony.sip_uri` is present (e.g., `sip:agent@yourdomain.com`). Not PSTN — a bare phone number is `voice`, never `sip`.
- **WebRTC modes** (`vapi`, `retell`, `elevenlabs`, `livekit`) = provider-specific browser/SDK connection, not phone.

Mapping:

| Agent config signal | Candidate modes |
|---|---|
| `provider.type: vapi` + `telephony.phone_number` | `vapi`, `voice`; add `text` if `provider.chat_agent_details` set |
| `provider.type: vapi`, no phone | `vapi`; add `text` if `provider.chat_agent_details` set |
| `provider.type: retell` (analogous) | `retell`; add `voice` if `telephony.phone_number`; add `text` if `provider.chat_agent_details` |
| `provider.type: elevenlabs` (analogous) | `elevenlabs`; add `voice` if `telephony.phone_number`; add `text` if `provider.chat_agent_details` |
| `provider.type: livekit` | `livekit`; add `voice` if `telephony.phone_number` |
| `provider.type: pipecat` | `pipecat-v2` (preferred), `pipecat`; add `voice` if `telephony.phone_number` |
| `provider.type: self_hosted` + `telephony.sip_uri` | `sip` |
| `provider.type: self_hosted` + `telephony.websocket_url` (no sip) | `websocket` |
| `provider.type: self_hosted` + only `telephony.phone_number` | `voice` |
| No provider, only `telephony.phone_number` | `voice` |
| `telephony.websocket_url` set, no provider | `websocket` |
| `provider.chat_agent_details` set, nothing else | `text` |

### 4b. Auto-pick or ask — only when there's genuine choice

**Principle:** auto-pick when obvious; ask only when ambiguous; never list modes the agent isn't configured for.

- **Zero candidates** — STOP and surface the gap:
  > ⚠️ Agent has no provider, phone number, SIP endpoint, or websocket URL configured. Can't run evals. Configure a connection on the agent first.
- **Exactly one candidate** — **auto-pick** it. Announce:
  > Auto-selected `<mode>` — only configured connection on this agent.
  Skip `AskUserQuestion`.
- **Two or more candidates** — use `AskUserQuestion` with **only the configured options** (never the full 10-way list). Include a one-line speed/cost hint: text fastest/cheapest, WebRTC moderate, PSTN voice realistic but slowest.

The user can still override by passing a mode explicitly in their initial command.

### 4c. Trigger the run

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

Pull the result with `mcp__cekura__results_retrieve` and synthesize a markdown report. **Follow this structure exactly.** Every run reference is a clickable link of the form:

```
https://dashboard.cekura.ai/<project_id>/results/<result_id>?call_id=<run_id>
```

**Wrap the entire report (from "1. Header" through "5. Next Steps") in HTML-comment sentinels so the product-chat PDF export can pick it out cleanly:**

```
<!-- CEKURA-REPORT-START -->
# Cekura Quality Report — <agent name>
…the full report sections below…
<!-- CEKURA-REPORT-END -->
```

The sentinels are invisible in the rendered chat (markdown ignores HTML comments). Pre-report narration ("Pulling the result…", "Analyzing failures…") MUST stay outside the sentinels.

### 1. Header

Result name + ID, agent name + ID, status, success rate, met / total expected outcomes, connection mode used, scenario count.

### 2. Quick Summary of Issues

One paragraph identifying the root-cause pattern across failures (persona drift? missing tool? hallucinated facts? flow break? auth/lookup failure?).

Then a table grouped **by issue category, not by scenario**:

| Issue category | Result | What's going wrong | Affected runs |
|---|---|---|---|
| Auth blocked at account lookup | ❌ (6 runs) | Test profile (Jessica Miller / 9876543 / PIN 2468) doesn't resolve in the prod backend, so every authenticated workflow exits before PIN, address-confirm, or post-auth steps run. | [3056761](https://dashboard.cekura.ai/<project_id>/results/<result_id>?call_id=3056761) Data Balance Full-Auth · [3056762](https://dashboard.cekura.ai/<project_id>/results/<result_id>?call_id=3056762) Secondary Auth after PIN Fail · [3056763](https://dashboard.cekura.ai/<project_id>/results/<result_id>?call_id=3056763) Update Contact Info · [3056765](https://dashboard.cekura.ai/<project_id>/results/<result_id>?call_id=3056765) Device Internet Troubleshooting · [3056766](https://dashboard.cekura.ai/<project_id>/results/<result_id>?call_id=3056766) PIN Authentication · [3056767](https://dashboard.cekura.ai/<project_id>/results/<result_id>?call_id=3056767) Authenticated Plan Name Retrieval |

Each row groups together every run that failed for the same underlying reason. Be explicit about whether the cause is config/data, tool/integration, or persona/knowledge/prompt.

### 3. Detailed Breakdown

Organize **by issue, not by run.** For each issue category from the summary table, write a subsection. Inside, list every affected run with a brief proof from the transcript.

Format:

```
### ❌ <Issue category> (<N> runs)

<One paragraph explaining the issue, root cause, and which step of the flow breaks. State whether it's a config/data, tool/integration, or model/persona issue.>

#### Run [<run_id>](https://dashboard.cekura.ai/<project_id>/results/<result_id>?call_id=<run_id>) — <scenario name>
- ❌ "<verbatim transcript quote that proves this category's failure>" (<timestamp>)

#### Run [<run_id>](https://dashboard.cekura.ai/<project_id>/results/<result_id>?call_id=<run_id>) — <scenario name>
- ❌ "<verbatim transcript quote>" (<timestamp>)
```

For each affected run, the issue paragraph already explains what's going wrong category-wide — do **not** re-list every step that worked or every downstream skip. Just one transcript quote per run that's the cleanest proof of *this specific category's* failure.

Concrete example:

> ### ❌ Auth blocked at account lookup (6 runs)
>
> The test profile's identity (Jessica Miller, phone 3105551234, account 9876543, PIN 2468) does not resolve in TruConnect's production backend. The agent reaches the lookup step and exits early — every downstream check (PIN, address confirms, balance, troubleshooting) is skipped. Configuration issue, not a model issue.
>
> #### Run [3056766](https://dashboard.cekura.ai/<project_id>/results/<result_id>?call_id=3056766) — PIN Authentication Test
> - ❌ "The main agent repeatedly stated the account could not be found, not that it was found." (01:16)
>
> #### Run [3056767](https://dashboard.cekura.ai/<project_id>/results/<result_id>?call_id=3056767) — Authenticated Plan Name Retrieval
> - ❌ "Agent stated locating account but did not ask for PIN or confirm authentication." (01:17)

After all failure issues, add a **Passes** subsection grouping passing runs by what they validated:

```
### ✅ <What this group validated> (<N> runs)
- [<run_id>](dashboard link) — <scenario name>
- [<run_id>](dashboard link) — <scenario name>
```

### 4. Performance

Pull non-binary metrics from the result payload (latency, interruption rate, talk-time ratio, time-to-first-token, etc.) and present them. Skip any metric not present in the payload — do not invent values.

| Metric | Value | Notes |
|---|---|---|
| Avg agent latency (p50 / p95) | e.g. 820ms / 1.9s | flag if p95 > 2s |
| Interruption count (avg per call) | e.g. 0.4 | flag if > 1 |
| Talk-time ratio (agent : user) | e.g. 1.3 : 1 | flag if > 2:1 |
| Time-to-first-token | e.g. 480ms | |
| Tool-call success rate | e.g. 92% | from Tool Call Success metric |

Call out runs that are outliers and link them.

### 5. What Works Well

3–6 bullets of genuine strengths from the transcripts (flow execution, tone, recovery, voice quality, etc.). Be specific — name the run with a dashboard link.

### 6. Next Steps

Order by likely impact. Always include a mock-tools section reflecting the option chosen in Step 3b:

- **Option A — Configure mock tools**: when the user knows which backend tools the agent calls. (For Retell/VAPI/ElevenLabs agents, suggest Cekura's hosted mock tools.)
- **Option B — Let Cekura surface what's needed**: re-run and inspect the tool-call trace; unmocked tools surface as failures.
- **Option C — Skip backend-state scenarios**: keep only stateless scenarios for now.

If failures are clearly not tool failures (persona/knowledge/prompt/data drift), say so first and recommend fixing those before investing in mocks.

Mention: **re-run individual scenarios** that failed using `mcp__cekura__results_rerun_create` once fixes are applied — no need to re-run the full suite.

### Style rules

- Every `<run_id>` reference is a markdown link to `https://dashboard.cekura.ai/{project_id}/results/{result_id}?call_id={run_id}`.
- Quote transcript lines verbatim (with quotes) and timestamps where available.
- Don't invent metrics — only cite what's in the payload.
- Tone: direct and analytical, not cheerleading.

Save as `result_<result_id>_report.md` in the working directory and return the path.

---

## Failure modes to watch for

- **Empty `transcript` field but populated `transcript_object`** — render from `transcript_object` (list of `{role, content}` turns).
- **`success=true` with `error_message` set** — infra issue; don't treat as a real pass.
- **All passes on generic scenarios, all fails on specific-fact scenarios** — strong signal of persona/KB misconfiguration or missing test data; call it out explicitly and group those failures under one issue category in the summary.
- **Auto-generated evaluators that don't match the agent's domain** — pause and re-generate with better `extra_instructions` rather than running junk.

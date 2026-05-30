---
name: cekura-onboarding
description: >
  Use when the user says "get started with Cekura", "set up Cekura", "onboard to Cekura",
  "I'm new to Cekura", "help me set up my agent", "how do I use Cekura",
  "walk me through Cekura", "configure my project", "first time using Cekura",
  or needs guidance on initial platform setup. Covers two onboarding paths:
  **testing** (default — build evaluators and run simulated calls) and
  **observability** (ingest production call logs and evaluate them).
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Platform Onboarding

## Purpose

Walk a new user through the complete Cekura setup — from account creation to their first useful artifact.

Two onboarding paths share the same Phases 1–2 (account, project, agent) and diverge after that:

- **Testing** *(default)* — build evaluators (test scenarios), run them against the agent in simulation, review results. Use this for pre-deploy regression testing and "is my prompt change safe to ship?".
- **Observability** — ingest production call logs into Cekura, attach metrics, run evaluation, and review/vote on results. Use this for "what's actually happening on live calls?".

This is an interactive, step-by-step walkthrough. At each phase, confirm with the user before proceeding and help them with the actual API calls or UI steps.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

Each phase below names the primary tool for that step. **Actually call the tool** rather than telling the user to do it in the dashboard — that's what makes the onboarding hands-on instead of a tutorial. If a call fails (validation error, missing field, auth), fix the cause or ask the user for the missing input, then retry; don't claim a step is done until the call succeeds.

### Never invent IDs

Every agent ID, scenario ID, call log ID, metric ID, and run ID comes from a real tool response. If you don't have an ID you need, call the relevant list/retrieve tool and pull it from the response — do not fabricate one to keep the flow moving. This holds even when the user gives you a name ("the Booking Bot agent"): look it up and use the returned `id`. Provider-side identifiers the user must supply (VAPI assistant IDs, Retell agent IDs, API keys, webhook URLs) follow the same rule — ask the user, never guess.

## How to Use This Skill

This is an **interactive walkthrough**, not a reference doc. Guide the user through each phase conversationally:

1. Confirm which **path** applies (Phase 0 — usually already known from how you were invoked).
2. Survey what already exists, so you skip completed work (State Assessment).
3. Use platform tools to perform actions on the user's behalf.
4. Validate each step before moving to the next.
5. Hand off to specialized skills (`cekura-create-agent`, `cekura-metric-design`, `cekura-eval-design`, `cekura-metric-improvement`) when appropriate.

## Phase 0: Choose the Path

If the caller already specified a path — via the `/cekura-onboarding` command argument or the invoking context — honour it without asking.

Otherwise, ask once:

> Two onboarding paths — which fits your goal?
> - **Testing** *(default)* — build evaluators and run simulated calls against your agent.
> - **Observability** — ingest your production call logs and evaluate them.

Default to **testing** when ambiguous. Phases 1–2 are identical for both; the flow forks at Phase 3.

---

## State Assessment *(do this once, before Phase 1)*

Survey what already exists in the user's project before walking them through any phase. This prevents asking "Resume where?" on an empty project (redundant) and prevents skipping past existing work (risky).

**Gathering state:**
- If you were handed an inventory (e.g. the `/cekura-onboarding` command pre-detected project state and passed it in context), trust it — don't re-run the same lookups.
- Otherwise, list the path-relevant resources yourself: agents and metrics for both paths; plus scenarios and results for **testing**; plus call logs for **observability**.

**Decision:**

| State of the path's relevant resources | Action |
|---|---|
| **Clean slate** — none exist (testing: 0 agents + 0 scenarios + 0 results; observability: 0 agents + 0 call logs + 0 metrics) | Proceed straight to Phase 1 (or Phase 2 if account/project already set up). Don't ask "Resume where?" / "Ready to continue?" — there's nothing to resume. |
| **Mid-onboarding** — some relevant resources exist but the flow is incomplete | Surface ONE concrete clarification: e.g. "Found existing agent **Booking Bot** with 12 scenarios and 1 result. Continue with it, or create a new agent?" — never a generic "Ready to continue?". |
| **Obvious from the user's message** — they said "create a new agent" / "start fresh" / named a specific agent | Honour that intent without an extra confirm. |

After deciding, move into the appropriate phase. Confirm at phase boundaries and before destructive operations, but never re-ask the state you just surveyed.

---

## Phase 1: Account & Project Setup *(shared)*

**Skip this phase entirely if the user is already signed in with a project selected** (or state was handed to you showing an existing project) — go straight to Phase 2. Phase 1 is only for users starting from nothing; don't re-ask account or project facts you already have.

### 1.1 Verify Account Access

Ask the user:
- "Do you already have a Cekura account?"
- "Do you have an API key, or do you sign in via OAuth?"

If they have an API key, verify it works by listing metrics. A successful response (even empty) confirms the key is valid.

If they don't have an account, direct them to sign up at https://dashboard.cekura.ai/sign-up and create a project.

**For Claude Code plugin users:** If platform operations aren't working, run `/setup-mcp` to configure API access.

### 1.2 Project Setup

Ask: "Do you already have a project, or do we need to create one?"

**If creating:** Create the project (`projects_create`) or point them to the dashboard.

**Project organization guidance:**
- Small teams: single project for multiple agents.
- Enterprises: separate projects by team and environment (staging vs production).
- Each project gets its own metrics, evaluators, and observability data.

---

## Phase 2: Agent Configuration *(shared, framing differs by path)*

Both paths register the agent with `aiagents_create`. What differs is the framing:

- **Testing**: "Let's create your test agent — pick the provider you'll simulate against."
- **Observability**: "Let's connect your production agent — Cekura needs to know about it so we can attribute uploaded calls to it."

### 2.1 Create or Connect an Agent

Ask:
- "Do you already have a voice AI agent deployed?"
- "What provider — VAPI, Retell, LiveKit, ElevenLabs, Pipecat, or custom?"

Create the agent on Cekura with `aiagents_create` — agent name, project ID, and description. For detailed agent setup (provider integration, mock tools, KB, dynamic variables), hand off to the **cekura-create-agent** skill.

**Critical: agent description is essential.** It enables automatic evaluator generation (testing) and powers metrics that reference `{{agent.description}}` (both paths). Ask the user to paste their agent's full system prompt — it's the single most leverage-rich field on the agent record.

### 2.2 Provider Integration

Based on their provider, guide them through connecting:

**VAPI:**
- Need: VAPI API Key + Assistant ID.
- In Cekura: Agent Settings → Provider → VAPI → enter credentials.
- *Observability tip:* If you only need call-log ingestion, provider creds are optional — ingestion works with the external `assistant_id` alone.

**Retell:**
- Need: Retell API Key + Assistant ID.
- In Cekura: Agent Settings → Provider → Retell → enter credentials.
- Optionally enable auto-sync of prompts.

**LiveKit:**
- Need: LiveKit agent deployment details.
- Calls include `metadata.raw_metrics` for latency tracking.

**ElevenLabs:**
- Need: ElevenLabs API Key + Agent ID.

**Pipecat:**
- Pipecat agents use `assistant_provider: "self_hosted"` + `transcript_provider: "pipecat"` + a `pipecat_api_key` (`contact_number` = the agent name). `pipecat` is **not** a valid `assistant_provider` value.
- Run tests over WebRTC with `scenarios_run_pipecat_v2`.
- See https://docs.cekura.ai/documentation/integrations/pipecat for the webhook contract.

**Self-hosted / Custom (reached via SIP, WebSocket, or chat):**
- These are `assistant_provider: "self_hosted"` agents — SIP / WebSocket / chat are *connection modes*, not providers.
- Guide based on their specific setup.
- Refer to https://docs.cekura.ai/documentation/integrations/ for provider-specific docs.

### 2.3 Dynamic Variables (if applicable)

Ask: "Does your agent use dynamic variables — per-call data like customer names, account IDs, or configuration flags?"

If yes:
- Cekura auto-detects `{{variableName}}` patterns in the agent description.
- These become available in metrics as `{{dynamic_variables.keyName}}`.
- Useful for multi-agent flows where each node has its own system prompt.
- *Observability path:* `dynamic_variables` is also a field on ingestion payloads — values appear alongside the transcript in the UI.

### 2.4 Mock Tools (testing) / Real Tool Calls (observability)

**Testing path** — ask: "Does your agent call external APIs or tools during calls?" If yes:
- Auto-fetch from provider (recommended): Cekura pulls tool definitions automatically.
- Manual setup: Add tool names, descriptions, and input/output mappings.
- Mock tools let you test without hitting real backends.
- See the **cekura-eval-design** skill for detailed mock tool configuration.

**Observability path** — tool calls in production are real. They surface in the call log as `tool_calls` (alongside the transcript) and the Tool Call Success metric scores them automatically once enabled.

After Phase 2, the flow diverges. Follow ONLY your path's Phase 3+ sections below.

---

# ──────── Testing path (Phases 3–6) ────────

*Use this branch when the path is **testing** (default).*

## Phase 3 (testing): Metrics Setup

### 3.1 Enable Pre-defined Metrics

**Always recommend selecting ALL pre-defined metrics** for comprehensive analysis:

| Category | Metrics |
|----------|---------|
| Accuracy | Expected Outcome, Hallucination, Relevancy, Response Consistency, Tool Call Success, Transcription Accuracy, Voicemail Detection |
| Quality | Interruption counts, Response latency, Silence detection, Call termination appropriateness |
| Customer Experience | CSAT, Sentiment, Dropoff nodes, Topic categorization |
| Speech Quality | Pitch, Speaking rate, Gibberish detection, Pronunciation verification |

Guide: "Go to your project's Metrics section and enable all pre-defined metrics. This gives you a comprehensive baseline."

**Two-step activation:** Metrics must be (1) toggled on at the project level AND (2) attached to individual evaluators.

### 3.2 Custom Metrics (optional, defer to later)

For first-time users, skip custom metrics initially. Once they have test results, they can use the **cekura-metric-design** skill to create targeted custom metrics.

## Phase 4 (testing): First Evaluators

### 4.1 Auto-Generate Evaluators (Recommended)

The fastest path to first tests — generate scenarios with `scenarios_agent_create`:

```json
{
  "agent_id": <agent_id>,
  "num_scenarios": 10,
  "personalities": [<personality_id>],
  "generate_expected_outcomes": true,
  "tool_ids": ["TOOL_END_CALL", "TOOL_END_CALL_ONLY_ON_TRANSFER"]
}
```

Generation runs in the background — poll `scenarios_generate_progress` until it completes, then review the generated scenarios.

**After generation, check:**
- Are instructions specific and behavioral?
- Are expected outcomes concise and achievable?
- Are the right tools enabled?
- For non-English agents: PATCH `scenario_language` to correct code.

### 4.2 Review and Supplement

Common gaps in auto-generated evals:
- Red-team / adversarial scenarios.
- Edge cases specific to the client's domain.
- Multi-language coverage.
- Tool failure scenarios.

Hand off to the **cekura-eval-design** skill for designing more targeted evaluators.

### 4.3 Attach Metrics

Every evaluator needs metrics attached. At minimum:
- **Expected Outcome** — Did the agent achieve the scenario's goal?
- **Infrastructure Issues** — Connection drops, silence, non-response.

Use bulk-add via `actions → modify scenarios` in the UI.

## Phase 5 (testing): First Test Run

Run the scenarios with one of the `scenarios_run_*` tools. The exact tool depends on the agent's provider/transport:
- `scenarios_run_pipecat_v2` — Pipecat Cloud, **WebRTC** (uses the agent's `pipecat_api_key`)
- `scenarios_run_livekit_v2` — LiveKit, WebRTC
- `scenarios_run_vapi_webrtc` / `scenarios_run_retell_webrtc` — VAPI / Retell WebRTC
- `scenarios_run_elevenlabs` — ElevenLabs
- `scenarios_run_websocket` — custom/self-hosted WebSocket agents
- `scenarios_run_sip` — SIP endpoints
- `scenarios_run_voice` / `scenarios_run_text` — phone (PSTN) / text

### 5.1 Execute

```json
{
  "agent_id": <agent_id>,
  "scenarios": [<scenario_ids>],
  "frequency": 1
}
```

**Start with 5–10 scenarios** for the first run. Voice calls take 1–3 minutes each.

### 5.2 Monitor

Check results via the results endpoint. Each run includes:
- Full transcript.
- Audio recording.
- Metric scores.
- Expected outcome pass/fail.

### 5.3 Review Results

Guide the user through interpreting results:
- **70–80% pass rate** is realistic for a first iteration.
- Review failures to identify: misunderstandings, missing info, technical issues.
- **90–95%** after refinement is the target.
- Don't aim for 100% — real conversations are unpredictable.

## Phase 6 (testing): What's Next

| Need | Next step | Description |
|------|-----------|-------------|
| Better metrics | **cekura-metric-design** | Design custom metrics for specific workflows. |
| More evaluators | **cekura-eval-design** | Design targeted test scenarios. |
| Improve metric quality | **cekura-metric-improvement** | Iterate metric quality through feedback. |
| Monitor production | Re-run onboarding on the **observability** path | Ingest live calls and score them. |
| CI/CD integration | GitHub Actions | Auto-test on code changes. |
| Scheduled tests | Cron jobs | Recurring test suites. |

---

# ──────── Observability path (Phases 3–7) ────────

*Use this branch when the path is **observability**.*

The observability path does not generate scenarios or run simulations. Instead, you ingest the user's actual production calls, attach metrics, evaluate, and review. The agent registered in Phase 2 is the production agent that owns those calls.

## Phase 3 (observability): Ingest Call Logs

Get the user's production calls into Cekura with `observe_create`.

### 3.1 Pick an ingestion mode

Ask: "Do you want to (a) upload a sample call to see how Cekura processes it, or (b) configure continuous webhook ingestion from your provider?"

#### (a) One-shot upload — fastest start

Call `observe_create` with the user's transcript. Identify the agent by either:
- `agent`: the Cekura agent ID from Phase 2 (preferred), or
- `assistant_id`: the external provider-side ID (Cekura resolves it to your agent).

Minimum payload:
```json
{
  "call_id": "<unique call id>",
  "agent": <agent_id>,
  "transcript_type": "cekura",
  "transcript_json": [
    {"role": "Testing Agent", "content": "Hi, can I book a room?", "start_time": 0.0, "end_time": 2.1},
    {"role": "Main Agent", "content": "Of course — for what date?", "start_time": 2.3, "end_time": 4.0}
  ],
  "call_ended_reason": "completed"
}
```

For `transcript_type: "cekura"`, the only valid roles are `"Testing Agent"` (caller) and `"Main Agent"` (the agent under test). `"agent"` / `"user"` are NOT valid for this format.

If the user has a provider-native transcript (VAPI, Retell, ElevenLabs, Bland, LiveKit, Pipecat, KoreAI, Trillet), set `transcript_type` to that provider and pass `transcript_json` exactly as the provider emits it — Cekura normalises it internally.

Useful optional fields:
- `voice_recording_url` — enables audio-based metrics (pitch, speaking rate, gibberish detection).
- `metadata` — freeform tags for Observability filtering (`{"customer_id": "...", "campaign_id": "..."}`).
- `dynamic_variables` — values injected into the agent at runtime; shown alongside the transcript.
- `customer_number` — caller's number in E.164.
- `metric_ids` — comma-separated metric IDs to evaluate immediately (skips Phase 5's separate kickoff).

#### (b) Continuous webhook ingestion

Cekura ships provider-specific webhook endpoints that accept the provider's raw post-call shape — no transformation on the user's side:

| Provider | Webhook URL |
|---|---|
| VAPI | `POST /observability/v1/vapi/observe/` |
| Retell | `POST /observability/v1/retell/observe/` |
| ElevenLabs | `POST /observability/v1/elevenlabs/observe/` |
| LiveKit | `POST /observability/v1/livekit/observe/` |
| Pipecat | `POST /observability/v1/pipecat/observe/` |
| Other | Use generic `observe_create` |

Guide the user to configure their provider's webhook to POST every completed call to the relevant URL with their Cekura API key in the `Authorization: Bearer ...` header. Then trigger one test call so a real ingestion lands.

### 3.2 Verify ingestion

After the first call lands:

1. List call logs (`call_logs_list`) to confirm it's visible.
2. Show the user the resulting call log id and explain that metric evaluation is async — initial `status` is `evaluating`; full results appear shortly after.

### 3.3 Iterate (optional)

If the user has more than one provider, repeat with a sample from each to build the call inventory for Phase 5 evaluation.

## Phase 4 (observability): Configure Metrics

Metrics in observability mode score real calls. The starter set should cover correctness, customer experience, and safety.

### 4.1 Survey existing metrics

List metrics (`metrics_list`) to see what's already configured. If the project already has metrics from a prior testing onboarding, reuse them — they apply to call logs as well as test runs.

### 4.2 Recommend a starter set

For first-time observability onboarding, recommend three metrics that cover the high-value bases:

| Metric | Why it matters in observability |
|---|---|
| **Hallucination** | Catches the agent inventing facts on live calls — highest blast-radius failure mode. |
| **Expected Outcome adherence** | Did the agent accomplish the call's purpose (booking, transfer, info-gathering)? |
| **Sentiment** | Surfaces customer frustration trends; a leading indicator for churn. |

List the full catalog with `predefined_metrics_list`. For each chosen metric, create it with `metrics_create` (single) or `metrics_bulk_create` (multiple), passing the project_id and metric specifics.

### 4.3 LLM-generated metrics from agent description (optional)

If the user wants metrics auto-tailored to their agent (e.g. workflow-specific outcome metrics), use `metrics_generate` — Cekura generates metric definitions from the agent's description. Defer to the **cekura-metric-design** skill for designing custom metrics carefully.

## Phase 5 (observability): Run Metric Evaluation

If you passed `metric_ids` during ingestion, auto-evaluation already started. This phase evaluates *additional* metrics on *existing* call logs.

### 5.1 Kick off evaluation

Call `call_logs_evaluate_metrics_create`:

```json
{
  "call_log_ids": [<id1>, <id2>],
  "metric_ids": [<metric_id1>, <metric_id2>]
}
```

Evaluation runs async — the response shows `status: "evaluating"` and the call log's `metrics` array is initially empty. Re-retrieve the call log shortly after to see scores.

### 5.2 Rerun (when needed)

If a metric prompt was updated and the user wants existing call logs re-scored, use `call_logs_rerun_evaluation_create`.

## Phase 6 (observability): Review Results & Vote

The point of observability is closing the loop: humans review scores, mark ones that disagree with their judgment, and that feedback improves future metric quality.

### 6.1 Show results

Retrieve the call log (`call_logs_retrieve`) with metric results. Walk the user through:
- The transcript.
- Each metric's score + reasoning.
- Any flagged segments (low-confidence, edge cases).

If results still show `status: "evaluating"`, wait a moment and re-retrieve.

### 6.2 Collect votes

Ask the user to pick at least one metric result they disagree with and explain why. Then record it with `call_logs_mark_metric_vote_create`:

```json
{
  "call_log_id": <id>,
  "metric_id": <id>,
  "vote": "incorrect",
  "reasoning": "<user's reason>"
}
```

Encourage 3–5 votes for a meaningful feedback signal.

### 6.3 Iterate

Hand off to **cekura-metric-improvement** to use the collected votes to actually refine metric prompts. That skill loops: rebuild prompt → preview on the voted call logs → ship.

## Phase 7 (observability): What's Next

| Need | Next step | Description |
|------|-----------|-------------|
| Improve metrics with votes | **cekura-metric-improvement** | Use Phase 6's votes to refine metric prompts. |
| Design custom metrics | **cekura-metric-design** | New metrics for workflow-specific behaviour. |
| Add pre-deploy tests | Re-run onboarding on the **testing** path | Use real production calls as the basis for new scenarios. |
| Scheduled re-evaluation | Cron jobs | Re-score live calls as metrics evolve. |
| Multi-project rollups | Observability dashboards | Aggregate metric scores across agents/projects. |

---

## Documentation

- Public docs: https://docs.cekura.ai
- LLM-friendly docs: https://docs.cekura.ai/llms.txt
- Concepts: https://docs.cekura.ai/documentation/key-concepts/
- Integrations: https://docs.cekura.ai/documentation/integrations/
- Observability webhook setup: https://docs.cekura.ai/documentation/observability/

See `references/api-quickstart.md` for the essential endpoints used during onboarding.

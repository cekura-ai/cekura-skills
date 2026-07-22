# Collect — Gather Failures and Inspect Provider Call State

Runs first (before Debug) and again on every loop re-entry from Eval. Reads the current failure set, turns it into a **kept failure set**, and inspects call state for every kept failure (Signals 1–5, incl. who hung up). Produces no edits. Output feeds **Debug** on the first pass and **Fix** on loop re-entry.

**Input by pass:** first pass → the raw signal (the prod `call_ids` / `result_id` / `run_ids`, or supplied failures); loop re-entry → the latest Eval runs of the harness. Treat all as ordinary failure records (Step COLLECT.1). On loop re-entry the harness's mocks + dynamic variables are already set — don't re-derive; the recorded **failure class** and **full set** travel on run state and are read by Eval, so don't widen the full set here.

**First pass also extracts the replay artifacts** (merged from old REPRO.1) that Reproduce consumes to build the harness — see COLLECT.6.

## Pre-flight check (fail closed)

Before any COLLECT.x work, verify Setup is complete. If any is unresolved, ask the specific question and wait:

- Mode resolved (`vapi` / `elevenlabs` / `self_hosted`)?
- Live target: simulation runner resolved? (N/A render-only.)
- Source-of-truth editable surface loaded? (VAPI: `/assistant/{id}` + tools; ElevenLabs: `/v1/convai/agents/{id}` + referenced tools; self_hosted: the surface the run-setup points to — source file / DB row / Cekura mock tools / pasted text.)
- **Self-hosted live target**: `redeploy_command` resolved to a shell command or `"manual"`? If not, return to [`../setup.md`](setup.md) § Step 1.4. (N/A for VAPI / ElevenLabs and for render-only.)

## Step COLLECT.1 — If input is `scenario_ids`: execute, then wait

Skip for other input types. Use Setup's saved simulation runner. Trigger, capture `result_id`, poll to terminal (~30s cadence; cap 15 min voice / 5 min text), then treat as a `result_id` input.

Self-hosted scenario execution runs against the live agent the run-setup points to. In auto mode the skill triggers validation without pausing to confirm a redeploy/restart; unchanged results across iterations surface the no-change hypothesis after the fact (Eval EVAL.4). When there's no reachable live target (render-only), there are no scenarios to execute — only pasted failures.

## Step COLLECT.2 — Fetch the runs or call logs (or trust pasted failures)

**For `result_id` inputs (common case): run the bundled helper** [`agents/fetch_failures.py`](../agents/fetch_failures.py). It does the result scan AND the per-run bulk retrieve in one process, guaranteeing `metadata.ended_reason` (Signal 5) is captured for every kept failure. Do NOT hand-call `results_retrieve` + `runs_bulk_retrieve` for the same `result_id` — dropping the second step was the dominant cause of phantom early-end diagnoses.

```
CEKURA_API_KEY=<key> python3 <skill_root>/agents/fetch_failures.py <result_id> --out /tmp/r<result_id>.md
```

The report contains: a funnel line citing per-run `evaluation_status`; one block per kept failure with run id, scenario name, `evaluation_status`, **`metadata.ended_reason` (Signal 5)**, duration, `error_message`, `scenario_instructions`, expected-outcome bullets, failed alignments (`aligned: no` only), and the flattened transcript.

Exit codes: `0` = kept failures present (→ COLLECT.3); `3` = zero kept (stop early — see "kept = 0 but total > 0" at bottom + Eval EVAL.4); `1` = fetch error; `2` = missing `CEKURA_API_KEY`. Read the emitted file directly into COLLECT.5.

For shapes the script doesn't cover, fall back to direct MCP:

| Input | Tool path |
|-------|-----------|
| `run_ids` | `runs_bulk_retrieve(run_ids="1,2,3")` — bare comma-separated string. Same per-run shape (transcript, expected_outcome, scenario_instructions, **`metadata.ended_reason`**, `error_message`, metric evaluations). |
| `call_ids` | Fetch each call log individually — transcripts + metric evaluations, no expected outcome. |
| Pasted failures (render-only, no live target) | Trust `{transcript, expected_outcome, verdict, verdict_explanation}` blocks. No fetch. One failing run each, no metric evals beyond what's pasted. |

**Two-step fetch rationale (fallback paths only).** `metadata.ended_reason` (Signal 5) is carried ONLY on the `runs_bulk_retrieve` per-run shape — NOT on the per-run subtree nested inside `results_retrieve`. The trap: calling `results_retrieve` manually and diagnosing off its `runs[*]` subtree — reading `ended_reason` from there returns `null`/missing for every run (a wrong-source signature, not "field absent for this provider"). If you find yourself doing this, stop and use the helper (or `runs_bulk_retrieve` on the failing IDs). Secondary benefit: payload size stays small (a raw `results_retrieve` for 20 runs is 250–300 KB, mostly passed-run transcripts).

**Authoritative failure view is per-run, not result-level.** A `results_retrieve` payload holds two conflicting views:

- **Authoritative (use):** each `runs[*].evaluation_status` — the post-human-review verdict, the only field COLLECT.3 reads.
- **Misleading (do NOT use):** result-level aggregates `failed_workflow_runs`, `failed_reasons.issues`, `failed_runs_count`, `success_runs_count`, `success_rate` — computed from raw machine scores **before** human-review overrides. A run with machine `score == 0` but `evaluation_status == "reviewed_success"` still appears in those aggregates; feeding them in smuggles `reviewed_success` items into the kept set and produces edits that contradict the reviewer.

Always iterate `runs` and read each run's own `evaluation_status`. Same rule for `run_ids` (bulk returns the same shape) and call-log inputs (per-item verdict, never a batch aggregate).

## Step COLLECT.3 — Pre-filter, accumulate, and discard voice failures

**Pre-filter by run-level verdict** (`evaluation_status`, or equivalent), four states:

- **`failure`** → **keep** (machine-judged failure — primary improvement candidate).
- **`reviewed_failure`** → **keep**, high-confidence (human confirmed the fail or overrode a success to fail). Strongest signal — never drop.
- **`reviewed_success`** → **drop** (human review supersedes machine; feeding these pushes edits that contradict the reviewer). Recognize equivalents: `review_status == "reviewed_success"`, `reviewed_success: true`, `human_review.outcome == "success"`.
- **`success`** → **drop** (nothing to improve).

Kept set = `failure` ∪ `reviewed_failure` — flows straight to fix, no "which to include" gate. Track dropped counts (`reviewed_success`, `success`) on separate summary lines for the funnel. For inputs where the verdict field isn't `evaluation_status` (call logs: `verdict`/`result`; pasted: whatever the user wrote), map to the same four buckets; when a non-standard status is ambiguous, **keep it** (false keeps recover in fix; false drops lose signal). If skipped items cluster on one or two metric judges, hint at `cekura-metric-improvement`.

**Accumulate failures from survivors:**

1. **Expected-outcome failures** *(runs only)* — verdict fail / not-met / false. Capture scenario id + name, transcript excerpt, expected-outcome text, verdict explanation.
2. **Metric failures** *(runs and call logs)* — any attached metric verdict `FAIL` (skip `PASS` / `N/A` / `VALID_SKIP`). Capture metric id + name, FAIL explanation, offending snippet.

A run can contribute to both — track separately (expected-outcome → usually prompt logic; metric → agent or metric).

**Voice/channel filter.** This skill optimizes only prompt + tool config + owned code, so discard failures rooted in the voice channel: audio quality, ASR errors, TTS issues, latency / dead air / talk-over, dropped connections, errored runs, voice-quality metrics. **Keep** failures where the agent had the input it needed and still behaved wrong (skipped a step, asked wrong info, hallucinated, missed a handoff, missed an end-of-call requirement). When in doubt, **keep**. For text-mode runs and chat call logs the filter is a no-op — track the discarded count separately from `reviewed_success`.

## Step COLLECT.4 — Inspect provider call state (default, every iteration)

Run for **every kept failure**. Output feeds Fix. Skipping this is the most common way the loop produces phantom prompt fixes for upstream-rooted issues — AND the only way the FIX.1 early-end triage gets its candidates (it relies on Signal 5).

Fetch the provider call object and record:

- **Signal 1 (intent):** `assistantOverrides.variableValues` — what Cekura passed at call start.
- **Signal 2 (runtime):** `artifact.variableValues` — what the provider saw after merging overrides + defaults.
- **Signal 3 (substitution failure):** rendered system message (`artifact.messages[0].content`, or per-activation for squads) — search literal `{{...}}` substrings.
- **Signal 4 (LLM output):** tool-call args (`artifact.messages[*].toolCalls[*].function.arguments`) — flag literal placeholders, empty arrays where data was expected, hallucinated values.
- VAPI squads: `artifact.assistantActivations` — which member was active per activation.
- **Signal 5 (end-of-call attribution: who hung up).** Record for every kept failure — the load-bearing signal for the next sub-phase; do NOT skip. Field varies; check in order: (a) **`metadata.ended_reason` on the bulk-retrieved run** (helper's per-failure block; canonical for self-hosted + VAPI-via-Cekura; values `main-agent-ended-call`, `testing-agent-ended-call`, `timeout`, `client-disconnect`…); (b) provider `endedReason` via direct-VAPI fallback `GET https://api.vapi.ai/call/{id}` (`assistant-said-end-call-phrase`, `assistant-ended-call`, `customer-ended-call`, `silence-timed-out`…); (c) last transcript turns — main-agent farewell before the testing-agent completed required actions = premature end. Also record (d) transcript turn count vs the scenario's required-step count (premature end vs proper end). If `metadata.ended_reason` is missing, you went off the helper path — re-run [`agents/fetch_failures.py`](../agents/fetch_failures.py) (or `runs_bulk_retrieve` on the failing IDs) before inferring from the transcript tail.

Bulk-fetch runs (NOT result-fetch — call details aren't there) or fetch call logs individually. Payloads are large (250–500 KB/run); use `jq`/python, not full re-reads. Direct-VAPI fallback available when `provider_call_details` is missing/stale.

**Signal availability by mode.** The full VAPI signal surface (1–5 + rendered system message) isn't reproduced elsewhere:

- **Self-hosted** — the user's agent controls what Cekura sees. Typically available: Signal 1 (test-profile/scenario variable values on the run record), Signals 3/4-partial (transcript + any `{"role":"Function Call","data":{…}}` tool records the agent forwards; many agents don't echo variable values), Signal 5 (`metadata.ended_reason`). Treat substitution as not-observable unless the transcript literally shows `{{varName}}`. With no live target (render-only), only Signals 3, 4-partial, 5 (from transcript tail).
- **ElevenLabs** — no rich `artifact.variableValues` / rendered-message surface. Typically: Signal 1 (dynamic-var values on the run record), Signals 3/4-partial (transcript + tool records), Signal 5 (`metadata.ended_reason`, and the agent's built-in `end_call`/`transfer_to_agent` firing before required steps = early-end). Rendered system message generally NOT observable; confirm surviving `{{var}}` only from the transcript. Richer call object: `GET https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}` (`xi-api-key`).

In every mode: if a failure looks variable-injection-shaped but you can't confirm runtime state, mark "suspected upstream — runtime state not observable" and surface the gap rather than proposing a phantom prompt edit.

### Adjacent provider & telephony logs (VAPI & ElevenLabs — required for tool-shaped / telephony-shaped failures)

The call artifact alone isn't always enough. For two failure classes it looks ambiguous but adjacent logs nail the diagnosis; skipping is the dominant source of phantom prompt edits against issues rooted below the prompt layer.

**Triggers:**

- **Tool-shaped** — a tool fired but the next agent turn ignores its documented result (re-asks what the tool answered, uses a stale value, calls the tool "unavailable"); long silence after a tool call; transcript references a tool that never fired. The artifact shows only final state; provider logs show the request/response trace, retries, error codes, webhook timing.
- **Telephony-shaped** — very short duration (< 5s) with no transcript; call-not-connected verdicts; `ended_reason` ∈ {`silence-timeout`, `customer-no-input`, `error`, `pipeline-error`} on turn 1; one-sided audio; ringing-only durations; SIP rejection. Usually carrier-level (no prompt/tool edit fixes them) — pull the logs to confirm Upstream/data and stop the loop early for that failure.

**Where to pull:**

- **VAPI `/logs`** — `GET https://api.vapi.ai/logs?callId={call_id}` (`Authorization: Bearer $VAPI_KEY`). Per-turn LLM request/response, tool attempts (incl. ones that errored pre-transcript), webhook delivery status + bodies, timing. Tool-shaped: (a) webhook HTTP status — 4xx/5xx = tool-config issue (URL/auth/schema), not prompt; (b) response body — empty/malformed = tool impl; (c) latency around the tool turn — extremes explain "agent gave up and improvised." Telephony-shaped: `endedReasonDetail`, `transport.callSid` (Twilio SID, next bullet), error events.
- **ElevenLabs conversation detail** — `GET https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}` (`xi-api-key`). Full tool-call records (incl. `voicemail_detection`, `transfer_to_agent`, `end_call` that terminated server-side without a clean transcript line), per-message timing, authoritative `status` / `termination_reason`. Built-in system-tool firings look like "the call just ended" in the transcript — confirm here. Key for voicemail (`voicemail_detection` terminates server-side), transfer (`transfer_to_agent` routed away), agent-ended-early (`end_call` vs server-side).
- **Twilio call logs** *(VAPI & ElevenLabs, Twilio only)* — `GET https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls/{CallSid}.json` (Basic auth `$TWILIO_ACCOUNT_SID`/`$TWILIO_AUTH_TOKEN`). `CallSid` = VAPI `transport.callSid` or ElevenLabs `conversation_initiation_client_data.dynamic_variables.system__caller_id` (varies — grep the payload for SID prefix `CA`). Inspect `status`, `duration`, `price`, especially `SipResponseCode` (`486 Busy`, `480`, `503`, `603` — each a distinct carrier failure). Also `GET .../Calls/{CallSid}/Events.json` for codec/RTP issues. `SipResponseCode` ≥ 400 is upstream by definition — surface as Upstream/data with the code and stop the loop for that failure. Skip the Twilio branch if the outbound number isn't Twilio (presence of a `CA…` SID is the trigger; absence → provider logs only).

**Auth.** Read from shell/`.env`: `VAPI_KEY`, `ELEVENLABS_API_KEY` (some setups `CEKURA_ELEVEN_LABS_API_KEY`), `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN`. If a key is unavailable, do NOT block — record `adjacent_logs: not fetched (auth unavailable for <provider>)` per affected failure and proceed on call-artifact signals (fix stays conservative about Upstream/data without confirmation). Ask the user once whether to set the missing key.

**Self-hosted skips this section** — no managed-provider log surface; the user's infra logs are out of band. Telephony-shaped self-hosted failures route directly to Upstream/data.

Group repeating patterns ("all 3 share the same variable-injection failure"). Full per-signal decision tree, squad per-member-message caveat, and the bare-comma bulk-retrieve gotcha: [`../../references/dynamic-variables-debugging.md`](../references/dynamic-variables-debugging.md).

## Step COLLECT.5 — Build the failure summary

Group by **scenario** (runs) or **metric** (call logs). Feeds fix + shown to the user. Report on separate lines and **cite the source field explicitly** so the skip is auditable: items inspected (per-run `evaluation_status`), `reviewed_success` skipped (human override), `success` skipped, voice-related discarded, prompt-following kept. Example: `5 runs inspected (per-run evaluation_status) — 1 reviewed_failure kept, 1 reviewed_success dropped (human override), 3 success dropped.` Include COLLECT.4 observations inline, with Signal 5 called out per kept failure.

**`metadata.ended_reason` is a required column per kept failure.** Each summary line must carry run ID, scenario name, verdict (`failure`/`reviewed_failure`), the FAIL bullet from `expected_outcome.explanation` (or metric explanation), AND `ended_reason` (from the bulk retrieve). A line without `ended_reason` is incomplete — the FIX.1 early-end triage can't triage it. If genuinely missing on the record (rare; pasted-failures variant), write `ended_reason: unavailable`.

**Collect does not pause for approval** — the user gate is at fix (FIX.6). One exception: if failures are dominated by one or two thin-signal metrics, stop and suggest `cekura-metric-improvement` (metric-quality, not agent-quality).

**Do not surface small-sample / overfitting caveats.** Even for a single-run input, no "N runs risks overfitting" / "5–10+ would be healthier" lines — internal confidence calibration is fine; user-facing hedging reads as a stall. Mechanical overfitting in the edits is the Overfitting Gate's job, not Collect's.

Full template, edge cases (zero failures / all-errored / mixed inputs), and metric-quality hand-off wording: [`../../references/phase-2-failure-collection.md`](../references/phase-2-failure-collection.md).

## Step COLLECT.6 — Extract the replay artifacts (first pass only)

Merged from old REPRO.1. On the **first pass** (raw signal), reuse the fetched call and record the trace fields Reproduce replays into the harness. Skip on loop re-entry (the harness already exists).

| Field | Path | Used by |
|---|---|---|
| Agent under test | call record's agent reference | every reproduction artifact is created under this agent |
| Personality ID | `metadata.personality_id` | testing-agent persona (REPRO.3d) |
| Project ID | `project` on the agent record | result URLs in PR / summary |
| Main-agent dynamic vars | `dynamic_variables` (call metadata) | REPRO.3c |
| Tool-call trace | `transcript_object` + provider call object (`artifact.messages[*].toolCalls`, or provider `/logs` req/resp pairs) | REPRO.3a/b |
| Ended reason | `metadata.ended_reason` | early-end signal |
| Transcript | `transcript_object` (turns: role + content) | REPRO.3d |
| Failing metrics | `runs[].evaluation.metrics[]` | fallback evaluator (REPRO.4) |

## Hand-off

After COLLECT.5 (+ COLLECT.6 on the first pass), hand off with:

- The kept failure set + per-failure call-state observations (all five signals, especially Signal 5).
- The voice-discard count + `reviewed_success` / `success` drop counts.
- Dropped metric-failure clusters (if any), for the eventual proposal's hand-offs.
- **First pass:** the replay artifacts (COLLECT.6) → to [`debug.md`](debug.md), then Reproduce.
- **Loop re-entry:** the kept set → straight to [`optimization/fix.md`](optimization/fix.md) (Debug + Reproduce are once-only, already done).

If Collect produced zero kept failures (all `success` / `reviewed_success` / voice-discarded), DO NOT hand off — report success or surface the voice-only situation and stop the loop early. See the orchestrator's "kept = 0 but total > 0" handling jointly with Eval EVAL.4.

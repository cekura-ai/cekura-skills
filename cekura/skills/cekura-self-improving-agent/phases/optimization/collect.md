# Optimization · Collect — Gather Failures and Inspect Provider Call State

First sub-phase of optimization. Reads the iteration's input (raw input on iteration 1; the re-collected failure set handed back from Eval on iteration 2+), turns it into a kept failure set, and inspects provider call state for every kept failure (including who hung up — needed by the next sub-phase to triage early-end-call failures).

This sub-phase produces no edits. Its output is the kept failure summary + provider call state observations, both consumed by the next sub-phase ([`early-end-call-diagnose.md`](early-end-call-diagnose.md)).

**Prod-call inputs arrive here as reproduction scenario IDs.** When the original input was a production call (`call_ids` / prod `result_id`), the [Reproduce phase](../reproduce.md) has already replaced the raw input with the reproduction scenario IDs (the N-scenario dataset for LLM-based failures, or the single repro scenario for infra) and proven they fail the must-fail-first gate. From Collect's perspective these are ordinary `scenario_ids` — execute them per Step COLLECT.1. The mock tools and dynamic variables the replay needs are already set on the agent (Reproduce REPRO.3); do not re-derive them. The recorded **failure class** (LLM-based / infra) and **full set** travel on the run state and are read by Eval for its must-pass re-run policy — do not widen the full set here.

## Pre-flight check (fail closed)

Before any Step COLLECT.x work, verify that the Setup phase is complete:

- Mode and sub-flavor resolved? (`vapi` / `elevenlabs` / `pipecat` / `websocket-file` / `websocket-offline`)
- Source-of-truth artifacts loaded? (VAPI: `/assistant/{id}` + tools; ElevenLabs: `/v1/convai/agents/{id}` + referenced `/v1/convai/tools/{id}`; pipecat: Cekura mock tools, prompt per run setup; websocket-file: the correct live source file, confirmed when ambiguous)
- **Self-hosted live target**: `redeploy_command` resolved to a shell command or `"manual"`? If not, return to [`../setup.md`](../setup.md) § Step 1.4 — do NOT begin Optimization. (N/A for VAPI / ElevenLabs — both land edits live.)

If any of the above is unresolved, ask the user the specific clarifying question and wait for an answer. Skipping this pre-flight is the foot-gun documented in the orchestrator's Common Pitfalls; the rest of the loop assumes all three are settled.

## Step COLLECT.1 — If input is `scenario_ids`: execute, then wait

Skip for the other input types. Pick voice mode for VAPI and ElevenLabs (default — both are voice agents). Trigger the run, capture the `result_id`, then poll until terminal (every ~30s, capped at 15 min for voice / 5 min for text). Once complete, treat as a `result_id` input.

For self-hosted agents, scenario execution still runs against the live agent (pipecat agent on Pipecat Cloud; websocket server at the configured URL). In auto mode the skill triggers validation without pausing to ask if the user has redeployed / restarted; if results look unchanged across iterations, the no-change hypothesis is surfaced after the fact (see Eval phase Step EVAL.4).

For the offline variant, there are no scenarios to execute — only pasted failures.

## Step COLLECT.2 — Fetch the runs or call logs (or trust pasted failures)

Branch on input type to populate a list of items to inspect.

**For `result_id` inputs (the common case): run the bundled helper script** at [`agents/fetch_failures.py`](../../agents/fetch_failures.py). It performs the result scan AND the per-run bulk retrieve in a single process, guaranteeing `metadata.ended_reason` (Signal 5) is captured for every kept failure. Manual invocation of the underlying MCP tools (`results_retrieve` + `runs_bulk_retrieve`) for the same `result_id` is discouraged — the helper exists specifically because the two-step rule is easy to drop on the floor under context pressure, and that drop was the dominant cause of phantom early-end diagnoses in earlier iterations.

Canonical usage (run from any working directory; `<skill_root>` resolves to this skill's folder):

```
CEKURA_API_KEY=<your_key> python3 \
  <skill_root>/agents/fetch_failures.py <result_id> --out /tmp/r<result_id>.md
```

The script writes a markdown report with:

- a funnel summary line citing per-run `evaluation_status` as the source (matches Step COLLECT.3's authoritative-view rule);
- one block per kept failure containing run id, scenario name, `evaluation_status`, **`metadata.ended_reason` (Signal 5)**, duration, `error_message`, `scenario_instructions`, expected-outcome explanation bullets, failed alignments (`aligned: no` only), and the flattened transcript.

Exit codes: `0` = kept failures present (proceed to Step COLLECT.3), `3` = zero kept (orchestrator should stop the loop early — see Eval phase Step EVAL.4 and the "kept = 0 but total > 0" handling at the bottom of this file), `1` = fetch error, `2` = missing `CEKURA_API_KEY`. Read the emitted file directly into Step COLLECT.5 — do not separately call `results_retrieve` or `runs_bulk_retrieve` for the same `result_id`.

For input shapes the script does not cover, fall back to direct MCP tool invocation:

| Input | Tool path |
|-------|-----------|
| `run_ids` | `runs_bulk_retrieve(run_ids="1,2,3")` — bare comma-separated string. Returns the same per-run shape the helper above produces internally (transcript, expected_outcome, scenario_instructions, **`metadata.ended_reason`**, `error_message`, metric evaluations). |
| `call_ids` | Fetch each call log individually — transcripts and metric evaluations, no expected outcome. |
| Pasted failures (offline variant only) | Trust the user's `{transcript, expected_outcome, verdict, verdict_explanation}` blocks. No fetch. Treat each block as a single failing run with no metric evaluations beyond what's pasted. |

**Why the two-step fetch (rationale, applies to fallback paths only).** `metadata.ended_reason` — Signal 5, end-of-call attribution — is only carried on the per-run shape returned by `runs_bulk_retrieve`. It is NOT present on the per-run subtree nested inside a `results_retrieve` payload. The helper script collapses both calls into one process so this cannot be missed; the manual fallback for `run_ids` already starts from the bulk endpoint, so it is also safe. The trap is the discouraged path: calling `results_retrieve` manually and then diagnosing off its nested `runs[*]` subtree. Mining the saved result blob with `jq` and reading `metadata.ended_reason` from there will return `null` / missing for every run — that is a wrong-source signature, not a "field absent for this provider" signature. If you ever find yourself doing this, stop and invoke the helper script (or, at minimum, `runs_bulk_retrieve` on the failing IDs) before continuing.

A secondary benefit of routing through the helper / bulk endpoint is payload size: a raw `results_retrieve` for a 20-run batch runs 250–300 KB and a 100-run batch is multi-megabyte, most of which is transcripts for runs that already passed. Keeping each call small mirrors the four-bucket pre-filter in Step COLLECT.3 and guarantees the diagnose sub-phases only see failing-run material — but this is a nice-to-have, not the reason the rule exists.

**Authoritative failure view is per-run, not result-level.** A `results_retrieve` payload contains two conflicting views of "what failed":

- **Authoritative (use this):** each item under `runs[*]` carries its own `evaluation_status` — this is the post-human-review verdict and the only field Step COLLECT.3 should read.
- **Misleading (do NOT use):** the result-level summary fields — `failed_workflow_runs`, `failed_reasons.issues`, `failed_runs_count`, `success_runs_count`, `success_rate` — are computed from raw machine scores **before** any human review override. A run with `evaluation.metrics[0].score == 0` but `evaluation_status == "reviewed_success"` (human overrode the machine fail) shows up in `failed_workflow_runs` and inflates `failed_runs_count`. Feeding those aggregates into Step COLLECT.3 silently smuggles `reviewed_success` items into the kept set, producing edits that contradict the reviewer.

Always iterate `runs` and read each run's own `evaluation_status`. The same rule applies to `run_ids` input (bulk fetch returns the same per-run shape) and to call-log inputs (per-item verdict, not any batch-level aggregate).

## Step COLLECT.3 — Pre-filter, accumulate, and discard voice failures

**Pre-filter by run-level verdict.** Each run / call log carries a top-level terminal verdict (`evaluation_status` on Cekura runs, or equivalent) with four possible states: `success`, `failure`, `reviewed_success`, `reviewed_failure`. Default behavior:

- **`failure`** → **keep** (machine-judged failure — the primary candidate for improvement).
- **`reviewed_failure`** → **keep**, treated as **high-confidence** failure (a human either confirmed the machine's fail verdict OR overrode a machine success to mark it failed). These are the strongest signal in the batch — never drop.
- **`reviewed_success`** → **drop**. The human review supersedes machine verdicts, so feeding these into later sub-phases would push edits that contradict the reviewer. Also recognize equivalent overrides (`review_status == "reviewed_success"`, `reviewed_success: true`, `human_review.outcome == "success"`).
- **`success`** → **drop** (nothing to improve).

The kept set (`failure` ∪ `reviewed_failure`) is what flows to the diagnose sub-phases — there is no separate "ask the user which ones to include" gate. Track the dropped counts (`reviewed_success` and `success`) on separate lines in the summary so the user can see the full funnel.

For inputs where the verdict field isn't named exactly `evaluation_status` (call logs use `verdict` or `result`; pasted failures use whatever the user wrote), apply the same four-bucket logic by mapping equivalent statuses. When a non-standard status is ambiguous, **keep the item** — false keeps are recoverable in the diagnose sub-phases; false drops silently lose signal.

If skipped metric failures cluster on one or two metrics (e.g., many `reviewed_success` items all flagged FAIL on the same metric judge), hint to the user that those metrics may need `cekura-metric-improvement`.

**Accumulate failures from the survivors:**

1. **Expected-outcome failures** *(runs only, not call logs)* — verdict `fail` / not-met / false. Capture scenario id + name, transcript excerpt, expected-outcome text, verdict explanation.
2. **Metric failures** *(both runs and call logs)* — any attached metric verdict `FAIL` (skip `PASS`, `N/A`, `VALID_SKIP`). Capture metric id + name, FAIL explanation, and offending transcript snippet.

A single run can contribute to both classes. Track them separately — the diagnose sub-phases treat them differently (expected-outcome failures usually point at agent prompt logic; metric failures may point at either the agent or the metric).

**Voice/channel filter.** This skill only optimizes prompt + tool config, so discard failures whose root cause is the voice channel: audio quality, ASR errors, TTS issues, latency / dead air / talk-over, dropped connections, errored runs, or failures from metrics that explicitly score voice quality. **Keep** failures where the agent had the input it needed and still behaved wrong (skipped a step, asked wrong info, hallucinated, missed a handoff, missed an end-of-call requirement). When in doubt, **keep the failure** — false keeps are recoverable in the diagnose sub-phases; false discards silently lose signal.

For text-mode runs and chat call logs the filter is a no-op — every collected failure passes through. Track the discarded count separately from the `reviewed_success` count.

## Step COLLECT.4 — Inspect provider call state (default, every iteration)

Run this for **every kept failure**. The output feeds the next two sub-phases (early-end-call-diagnose AND diagnose). Skipping this step is the most common way the loop produces phantom prompt fixes for issues actually rooted upstream — AND the only way the early-end-call diagnose sub-phase can identify its candidates (it relies on Signal 5 below).

For each kept failing run / call log, fetch the provider call object and record:

- `assistantOverrides.variableValues` — what Cekura passed to the provider at call start (Signal 1: intent).
- `artifact.variableValues` — what the provider saw after merging overrides + defaults (Signal 2: runtime).
- The rendered system message (`artifact.messages[0].content`, or per-activation messages for squads) — search for literal `{{...}}` substrings (Signal 3: substitution failure).
- Tool-call arguments (`artifact.messages[*].toolCalls[*].function.arguments`) — flag literal placeholders, empty arrays where data was expected, hallucinated values (Signal 4: what the LLM produced).
- For VAPI squads: `artifact.assistantActivations` — which member was active per activation.
- **End-of-call attribution (Signal 5: who hung up).** For every kept failure, record who terminated the call. This is the load-bearing signal the next sub-phase uses to identify early-end-call failures, so do NOT skip it. The field name varies by provider — check, in order: (a) **`metadata.ended_reason` on the bulk-retrieved run record** (emitted in the helper script's per-failure block in Step COLLECT.2; the canonical source for self-hosted + VAPI runs reached via Cekura — common values include `main-agent-ended-call`, `testing-agent-ended-call`, `timeout`, `client-disconnect`); (b) the provider call's `endedReason` field via direct-VAPI fallback (`GET https://api.vapi.ai/call/{id}` — values like `assistant-said-end-call-phrase`, `assistant-ended-call`, `customer-ended-call`, `silence-timed-out`); (c) the last few transcript turns — if the final turn is the main agent saying a farewell (e.g., "Thank you for calling..., bye!") and the testing-agent script hadn't completed its required actions yet, the agent ended the call prematurely. Also record (d) transcript length (turn count) relative to the scenario's required-step count, since the next sub-phase needs this to decide "premature end" vs "agent followed the script and ended properly." If `metadata.ended_reason` is missing from the data you have on hand, you went off the helper path — re-run [`agents/fetch_failures.py`](../../agents/fetch_failures.py) (or call `runs_bulk_retrieve` directly on the failing IDs) before proceeding. Do not infer Signal 5 from the transcript tail when the authoritative field is one bulk-fetch away.

Bulk-fetch runs (NOT result-fetch — provider call details aren't included there) or fetch call logs individually. Payloads are large (250–500 KB per run); use `jq` or python rather than re-reading the whole blob. Direct-VAPI fallback (`GET https://api.vapi.ai/call/{id}`) is available when `provider_call_details` is missing or stale.

**Self-hosted / pipecat caveats.** The pipecat transcript_provider does not expose `assistantOverrides.variableValues` or a fully-rendered `artifact.messages[0].content` the way VAPI does. The signals available are typically: (1) the test-profile / scenario variable values that Cekura passed at run start (Signal 1, intent — visible on the run record), (2) the transcript and any tool-call records that Cekura captured (Signals 3 and 4 partial), (5) `metadata.ended_reason` on the run record. Substitution failures usually surface as the agent literally speaking `{{variableName}}` or as a tool call with placeholder arguments. If a failure looks variable-injection-shaped but you cannot confirm runtime state, mark the diagnosis "suspected upstream — runtime state not observable" and surface the gap rather than blindly proposing a prompt edit in later sub-phases.

**Self-hosted / websocket caveats.** The user's websocket server controls what Cekura sees. The convention for `main.py`-style agents is to forward tool-call records to Cekura via `{"role": "Function Call", "data": {...}}` messages; when present, Signal 4 is recoverable. `assistantOverrides.variableValues` is typically NOT observable — most websocket agents don't echo it back. Treat substitution as not-observable unless the transcript literally shows `{{varName}}`. With the `offline` variant, only Signals 3, 4-partial, and 5 (inferred from transcript tail) are available.

**ElevenLabs caveats.** ElevenLabs does not expose VAPI's rich `artifact.variableValues` / rendered-system-message surface. The signals available are typically: (1) the dynamic-variable values Cekura passed at conversation start (Signal 1, intent — visible on the run record where Cekura records them), (3/4 partial) the transcript and any tool-call records Cekura captured, and (5) `metadata.ended_reason` on the run record. ElevenLabs end-of-call attribution also surfaces in the agent's built-in `end_call` / `transfer_to_agent` tool firing — if the transcript shows the agent invoking `end_call` before the scenario's required steps completed, that is the early-end signal. The fully-rendered system message is generally NOT observable, so treat "literal `{{var}}` survived substitution" as confirmed only when the transcript literally shows the placeholder. The direct-provider fallback for a richer call object is `GET https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}` (header `xi-api-key`) when `metadata.ended_reason` or tool-call records are missing from the Cekura run record. If a failure looks variable-injection-shaped but runtime state can't be confirmed, mark the diagnosis "suspected upstream — runtime state not observable" rather than proposing a phantom prompt edit.

### Adjacent provider & telephony logs (VAPI & ElevenLabs modes — required for tool-shaped and telephony-shaped failures)

The call artifact / conversation object alone is not always sufficient. For two classes of failure, the call-artifact looks ambiguous but the adjacent logs nail the diagnosis. Skipping this step is the dominant way the loop produces phantom prompt edits against issues rooted upstream of the prompt layer.

**When to pull adjacent logs (trigger conditions):**

- **Tool-shaped failures.** Transcript shows a tool was invoked but the agent's next-turn behavior makes no sense given the tool's documented result (agent re-asks something the tool just answered, agent uses a stale value, agent describes the tool as "unavailable" or "broken"); long silence between a tool call and the next agent turn; the transcript references a tool that never fired. The call artifact often shows only the *final* state — provider logs show the request/response trace, retries, error codes, and webhook timing that the transcript omits.
- **Telephony-shaped failures.** Very short duration (< 5s) with no transcript content; call-not-connected verdicts; `metadata.ended_reason` ∈ {`silence-timeout`, `customer-no-input`, `error`, `pipeline-error`} on the first turn; one-sided audio (agent spoke but customer turns are empty / vice versa); ringing-only durations; SIP-level rejection symptoms. These are typically carrier-level issues that no prompt or tool edit fixes — the goal of pulling the telephony logs is to confirm Upstream/data and stop the loop early for those failures rather than burning iterations on phantom edits.

**Where to pull from:**

- **VAPI `/logs`** *(VAPI mode)* — `GET https://api.vapi.ai/logs?callId={call_id}` (header `Authorization: Bearer $VAPI_KEY`). Returns per-turn LLM request/response, tool-call attempts (including ones that errored before reaching the transcript), webhook delivery status + response bodies, and timing. Use the same `call_id` Cekura records on the run record. For tool-shaped failures, look at: (a) tool webhook HTTP status — 4xx/5xx is a tool-config issue (URL, auth, schema mismatch), not a prompt issue; (b) tool response body — empty/malformed responses point at the tool implementation; (c) `firstByteLatency` / total latency around the tool turn — extreme values often explain "agent gave up and improvised." For telephony-shaped failures, look at: VAPI's `endedReasonDetail` (richer than `endedReason`), `transport.callSid` (the Twilio SID — needed for the next bullet), and any error events.
- **ElevenLabs conversation detail** *(ElevenLabs mode)* — `GET https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}` (header `xi-api-key`). The `conversation_id` is the ElevenLabs identifier Cekura records alongside the run (or surface it via direct lookup if absent). Returns full tool-call records (including `voicemail_detection`, `transfer_to_agent`, `end_call` invocations that may have terminated the call server-side without leaving a clean transcript line), per-message timing, and the authoritative `status` / `termination_reason`. Built-in system-tool firings often look like "the call just ended" in the transcript — the conversation endpoint is where you confirm which system tool fired and why. Particularly important for: voicemail scenarios (`voicemail_detection` terminates server-side), transfer scenarios (`transfer_to_agent` may have routed away), agent-ended-early diagnoses (was it `end_call` or a server-side termination?).
- **Twilio call logs** *(VAPI & ElevenLabs — when telephony provider is Twilio)* — `GET https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls/{CallSid}.json` (HTTP Basic with `$TWILIO_ACCOUNT_SID` / `$TWILIO_AUTH_TOKEN`). The `CallSid` is exposed on the VAPI call as `transport.callSid` and on the ElevenLabs conversation as `conversation_initiation_client_data.dynamic_variables.system__caller_id` or similar (varies — grep the conversation payload for the Twilio SID prefix `CA`). Inspect: `status` (`completed` / `busy` / `no-answer` / `canceled` / `failed`), `duration`, `price`, and especially `SipResponseCode` (`486 Busy`, `480 Temporarily Unavailable`, `503 Service Unavailable`, `603 Decline` — each maps to a different carrier-side failure mode). Also pull `GET .../Calls/{CallSid}/Events.json` if available — surfaces SIP-level events including codec negotiation failures and RTP / audio-path issues. A `SipResponseCode` ≥ 400 on the call is upstream by definition; surface as Upstream/data hand-off with the response code and stop the loop for that failure.

  Skip the Twilio branch if the agent's outbound number is not a Twilio number — VAPI / ElevenLabs both support non-Twilio carriers (SIP trunks to other providers, ElevenLabs-native numbers, etc.). The presence of a Twilio `CA…` SID on the run / conversation is the trigger; absence means use the provider's own logs only.

**Reading auth.** Required env vars (read from the user's shell or `.env`): `VAPI_KEY` (VAPI logs), `ELEVENLABS_API_KEY` (ElevenLabs conversation detail; some setups use `CEKURA_ELEVEN_LABS_API_KEY`), `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` (Twilio). If a key is unavailable, do NOT block the iteration — record `adjacent_logs: not fetched (auth unavailable for <provider>)` on each affected failure, then proceed with the call-artifact signals alone. The diagnose sub-phases will see the gap and be more conservative about classifying as Upstream/data without confirmation. Ask the user once whether to set the missing key for future iterations.

**Self-hosted modes (pipecat / websocket) skip this section entirely** — there's no managed-provider log surface to consult, and the user's own infrastructure logs are out of band for this skill. Telephony-shaped failures in self-hosted modes route directly to Upstream/data hand-off without an adjacent-log confirmation step.

Group observations when patterns repeat — "all 3 failed runs share the same variable-injection failure" is more actionable than per-run repetition. For the full per-signal decision tree (key absent vs. wrong-name vs. literal-placeholder-survives), the squad per-member-message caveat, and the bare-comma-separated-string gotcha for bulk-retrieve, see [`../../references/dynamic-variables-debugging.md`](../../references/dynamic-variables-debugging.md).

## Step COLLECT.5 — Build the failure summary

Group failures by **scenario** (for runs) or by **metric** (for call logs). The summary feeds the diagnose sub-phases and is also shown to the user for transparency. Report on separate lines and **cite the source field explicitly** so the skip is auditable: items inspected (per-run `evaluation_status`), `reviewed_success` skipped (human override), `success` skipped, voice-related discarded, prompt-following kept. Example: `5 runs inspected (per-run evaluation_status) — 1 reviewed_failure kept, 1 reviewed_success dropped (human override), 3 success dropped.` Include the provider-call-state observations from Step COLLECT.4 inline, with Signal 5 (end-of-call attribution) called out per kept failure since the next sub-phase will branch on it.

**`metadata.ended_reason` is a required column in the per-failure summary.** For every kept failure, the rendered summary line must include the run ID, scenario name, verdict (`failure` / `reviewed_failure`), the FAIL-bullet from `expected_outcome.explanation` (or metric explanation for metric failures), AND `metadata.ended_reason` (sourced from the Step B bulk-retrieve — see Step COLLECT.2). A failure summary line that omits `ended_reason` is incomplete because the next sub-phase cannot triage it without the early-end signal. If the field is genuinely missing on the run record (extremely rare; pasted-failures variant is the usual cause), write `ended_reason: unavailable` so the gap is visible rather than silently dropped.

**Collect does not pause for approval** — the user-facing gate is at the end of the diagnose sub-phase (Step DIAGNOSE.5), where the combined proposal is presented. The one exception: if failures are dominated by one or two metrics with thin signal, stop and suggest hand-off to `cekura-metric-improvement` — those are metric-quality issues, not agent-quality issues, and the diagnose sub-phases won't fix them.

**Do not surface small-sample / overfitting caveats to the user.** Even when the input is a single run, do not include lines like "with N runs any fix risks overfitting" or "5–10+ items would be a healthier signal" — internal calibration of confidence is fine; user-facing hedging reads as a stall. The user has already chosen to act on the input they have. Mechanical overfitting in the proposed edits (verbatim transcript quotes, scenario IDs in the prompt) is the Overfitting Gate's job, not Collect's.

For the full summary template, edge cases (zero failures / all-errored / mixed inputs), and the exact wording around the metric-quality hand-off, see [`../../references/phase-2-failure-collection.md`](../../references/phase-2-failure-collection.md).

## Hand-off to the early-end-call diagnose sub-phase

After Step COLLECT.5, the Collect sub-phase is complete. Hand off to [`early-end-call-diagnose.md`](early-end-call-diagnose.md) with:

- The kept failure set, with per-failure provider call state observations (all five signals, especially Signal 5).
- The voice-discard count + `reviewed_success` / `success` drop counts for the user-facing summary.
- The dropped metric-failure clusters (if any), for inclusion in the eventual proposal as hand-offs.

If Collect produced zero kept failures (everything was `success` / `reviewed_success` / voice-discarded), DO NOT hand off — report success or surface the voice-only situation back to the orchestrator and stop the loop early. See the orchestrator's "kept = 0 but total > 0" handling jointly with Eval Step EVAL.4.

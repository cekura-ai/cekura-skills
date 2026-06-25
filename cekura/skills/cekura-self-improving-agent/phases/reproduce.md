# Reproduce Phase — Build a Faithful Replay of the Prod Call, Then Gate on a Definitive FAIL

This phase runs **once per invocation**, after Setup (and Clone, for VAPI / ElevenLabs) and before the Optimization loop. It exists for one reason: the loop is only as trustworthy as the failure it iterates against. Before any edit is proposed, the skill stands up a controlled reproduction of the production failure on Cekura and **proves the bug reproduces** — otherwise every later iteration is chasing a failure it can't measure.

**When this phase does real work vs. passes through:**

- **Prod-call inputs (`call_ids`, or a `result_id` / `run_ids` that point at production call logs rather than simulation runs)** → full procedure below. The skill auto-builds the reproduction harness from the prod call's own trace (mock tools, expected tool returns, main-agent dynamic variables, testing-agent variables), constructs the evaluator, branches the harness shape on the failure class, and runs the must-fail-first gate.
- **Simulation-run inputs (`scenario_ids`, or a `result_id` / `run_ids` from a Cekura simulation)** → the reproduction artifacts already exist as scenarios. Skip harness construction (REPRO.3) and evaluator construction (REPRO.4); still run REPRO.1 (debug / root-cause) lightly, REPRO.2 (LLM-vs-infra classification, which drives the dataset-vs-single branch and the stochastic re-run policy), and REPRO.6 (must-fail-first gate against the existing scenarios). A scenario that doesn't fail on re-run is not a reproduction — surface and stop, same as the prod-call path.
- **Offline variant (pasted prompt + pasted failures)** → no live target to replay against. Skip this phase entirely; the pasted `{transcript, expected_outcome, verdict}` blocks are the only available failure signal. The must-fail-first and must-pass gates degrade to "the user re-pastes failures each iteration" (handled in Eval).

> ## ⚠️ SAME CONNECTION MEDIUM AS THE PROD CALL — NO EXCEPTIONS
>
> Every reproduction, verification, and regression run MUST be a full end-to-end simulation on Cekura over the **same transport the agent is configured for**. Read the agent record (already fetched in Setup) to confirm transport — telephony / SIP (most common) → `run_voice`; WebRTC → the provider's WebRTC run endpoint. **Text mode is never a valid substitute, and you must not switch transports between phases.** The bug lives in the real call path; only a simulation over the same medium confirms it.

---

## Step REPRO.1 — Debug the prod call and confirm the root cause

Fetch the full production call and build a complete picture of what went wrong **before** touching any harness or evaluator.

```bash
get_call "CALL_ID"
```

Extract and record:

| Field | Path | Why it matters downstream |
|---|---|---|
| Real agent ID | `metadata.agent_id` (NOT top-level `agent_id`, which may be a monitoring agent) | every reproduction artifact is created under this agent |
| Personality ID | `metadata.personality_id` | testing-agent persona for the replay |
| Project ID | `project` on the agent record | result URLs in the PR / summary |
| Main-agent dynamic variables | `dynamic_variables` (call metadata) | REPRO.3 copies these onto the agent |
| Tool-call trace | `transcript_object` + provider call object (`artifact.messages[*].toolCalls`, or the provider `/logs` request/response pairs) | REPRO.3 derives mock-tool entries + expected returns |
| Ended reason | `metadata.ended_reason` | early-end signal |
| Transcript | `transcript_object` (turns with role + content) | testing-agent turns for the replay |
| Failing metrics | `runs[].evaluation.metrics[]` | fallback evaluator construction (REPRO.4) |

Then pull logs and traces around the call timestamp using whatever observability is configured (Datadog, Grafana, CloudWatch, Langfuse, LLMObs, etc.) — search by `call_id` / `session_id` / agent ID / timestamp. Look for: exceptions in the call handler, unexpected tool inputs/outputs, timeouts or slow spans (STT / LLM / TTS / tool), upstream services returning empty or malformed responses, and gaps between transcript turns that suggest a silent failure. Cross-reference findings turn-by-turn with `transcript_object` to pinpoint exactly where the call diverged.

**Root-cause summary** — write down: what the caller said, what the agent did wrong, the suspected root cause, which code path / artifact is responsible, and which metrics were failing.

**Gate:** present the root-cause summary and confirm with the user before building anything. *(In `auto_mode: true`, render the summary and proceed unless the root cause is genuinely ambiguous or low-confidence — then pause and ask, per the orchestrator's "when to ask" rules. A wrong root cause here wastes the whole loop.)*

---

## Step REPRO.2 — Classify the failure: LLM-based vs. infra

This classification drives two later decisions — the harness shape (REPRO.5) and the stochastic re-run policy (REPRO.6, Eval) — so it is not optional. It falls directly out of the existing Diagnose taxonomy (see [`optimization/diagnose.md`](optimization/diagnose.md) Step DIAGNOSE.3):

| Class | Diagnose buckets | Nature | Harness shape | Re-run policy |
|---|---|---|---|---|
| **LLM-based** | Gap / Conflict / Ambiguity (and over-eager-transfer / premature-exit prompt patterns) | Probabilistic agent behavior — the model *sometimes* gets it wrong | **dataset** of N scenarios (REPRO.5) | auto re-run 5–10× (REPRO.6) |
| **Infra** | CodeBug (websocket history truncation, broken state, missing tool-result forwarding) / Upstream-infra (mock-tool wiring, idle timer, DTMF parsing, telephony) | Deterministic — fails the same way every time | **single** evaluator (REPRO.5) | single run is enough |

This is a *preview* classification from the prod call's evidence, not the authoritative Diagnose verdict (that's still produced inside the loop, per failure). It only needs to be good enough to pick the harness shape and re-run count. When the prod call shows symptoms of both (e.g., a prompt gap that only triggers when a mock returns a specific shape), default to **LLM-based + dataset** — the larger sample is the safe error.

---

## Step REPRO.3 — Auto-build the reproduction harness (prod-call inputs only)

The whole point of this phase: **replay the prod call faithfully with zero manual mock/variable setup by the user.** Derive every artifact below from the prod call's own trace — never from prompt-guessing.

### REPRO.3a — Mock tool entries

Every tool the prod call invoked must appear in the Cekura agent's mock-tool JSON. Walk the tool-call trace from REPRO.1 and, for each distinct tool the agent called, ensure a mock-tool entry exists (name + parameter schema matching what the agent actually sent).

For self-hosted / pipecat and websocket agents, mock tools are the Cekura testing contract — set them on the agent record (the full desired `mock_tools` list: fetch current → merge → write back). For VAPI / ElevenLabs, the referenced tools already exist on the cloned agent (Clone phase copied them); here you set their *mock return values* (next step) so the replay is deterministic.

### REPRO.3b — Expected mock tool return values

For each tool invocation in the prod trace, set the mock's return value to the **actual response the tool produced in production** — read it from the request → response pairs in the call object / provider `/logs`, not from what the prompt says the tool "should" return. If the same tool was called multiple times with different arguments → different responses, encode the per-invocation mapping (`freetext_params` / argument-keyed mock data) so each call in the replay returns what it returned in prod. A mock that returns a plausible-but-different value will not reproduce the bug.

### REPRO.3c — Main-agent dynamic variables

Copy `dynamic_variables` from the prod call's metadata onto the agent (assistant-level / squad-level dynamic variables, per provider). These are the values the live agent had at call time — the bug may depend on them. Do **not** invent or normalize them; copy verbatim. (Leave `{{...}}` placeholders in the prompt untouched — you're setting the *values* they resolve to, not editing the placeholders.)

### REPRO.3d — Testing-agent variables

Wherever the testing-agent / scenario layer accepts variables — caller persona, context payload, scripted fields, test-profile variables — populate them from the prod call so the simulated caller mirrors the real one. Use the prod `personality_id` for the persona, and extract the testing-agent (caller) turns from `transcript_object` **verbatim** — garbled text, truncated words, STT artifacts are exactly what the main agent's LLM received in production and are often the bug trigger. Do not clean them up.

---

## Step REPRO.4 — Construct the evaluator (prefer `expected_outcome`, fall back to the prod metric)

**Default: derive the evaluator's pass/fail bullets from the scenario's `expected_outcome` field.** Express the behavior that should have happened as expected-outcome bullets. These are higher-signal, easier to reason about, and align with how Diagnose classifies failures (it keys off expected-outcome bullets). Defaulting to the prod metric instead drags metric-judge noise in as a confounder.

**Fallback — use the prod metric directly — only when the failure mode is genuinely out of scope for `expected_outcome`:** i.e., the failure is a latency / sentiment / interruption-score / infrastructure metric that doesn't map to behavioral bullets. In that case attach the exact metric(s) that were failing in the prod call (from REPRO.1's `runs[].evaluation.metrics[]`) rather than inventing behavioral bullets a behavioral judge can't score.

If you're unsure whether `expected_outcome` can express the failure, prefer `expected_outcome` and add the prod metric as a secondary check — but do not silently drop to metric-only. When the choice is genuinely ambiguous, ask the user.

Create the scenario(s) under `metadata.agent_id` (the agent that handled the failing call) so the replay runs against the correct configuration:

```bash
create_scenario '{
  "agent": METADATA_AGENT_ID,
  "personality": PERSONALITY_ID,
  "name": "Bug repro: <brief issue description>",
  "instructions": "Replay the production call that caused <issue>.",
  "expected_outcome": "<behavioral bullets derived from the prod failure>",
  "conditional_actions": { "role": "caller", "conditions": [ /* verbatim testing-agent turns from REPRO.3d */ ] }
}'
```

(For the fallback path, omit `expected_outcome` bullets that can't express the failure and attach `"metrics": [METRIC_ID_1, ...]` instead.) Save the `scenario_id`(s).

---

## Step REPRO.5 — Branch the harness shape on the failure class

From REPRO.2:

- **LLM-based → build a dataset of N scenarios.** One reproduction scenario alone gives the loop too little signal to tell a real fix from a lucky sample. Build `N` scenarios (default `N = 8`, configurable via `dataset_size`, range 5–10) that all exercise the *same* failure mode with light variation — vary the caller's phrasing / order / incidental details while keeping the trigger condition (the thing that broke) constant. The prod replay is scenario 1; the rest are near-variants. This dataset is the **full set** for the rest of the loop (Eval, regression).
- **Infra → a single evaluator is enough.** Deterministic failures don't need a sample — one faithful replay reproduces them every time. The single repro scenario is the full set.

---

## Step REPRO.6 — Must-fail-first gate (the hardest gate in the skill)

> ## ⛔ ABSOLUTE HARD STOP — DO NOT ENTER THE OPTIMIZATION LOOP WITHOUT A DEFINITIVE FAIL.

Run the reproduction evaluator(s) on Cekura over the agent's transport and **require a definitive FAIL before any edit is proposed or applied.**

### Re-run policy (from REPRO.2)

- **LLM-based (dataset):** the skill **auto-triggers the runs itself** — do NOT ask the user to trigger each one. Run the evaluator(s) **5–10 times** (default `N = 8`, configurable via `stochastic_runs`). Because agent behavior is probabilistic, a single failing run is not proof the bug is real and reproducible. **The bug counts as reproduced only if it fails in ≥ M of N runs** (default `M = ⌈N/2⌉`, e.g. ≥4/8 or ≥5/10 or ≥3/5 — tune via `repro_threshold`). Fewer than M fails → the bug is not reliably reproducible from this harness; surface and stop (see "If it passes" below).
- **Infra (single):** one run is sufficient. A deterministic failure that shows up once will show up every time.

```bash
# LLM-based: the skill fires N runs without prompting the user between them
run_voice "SCENARIO_ID" '{"agent_number": "<caller_id>"}'   # ×N
get_result "RESULT_ID"                                        # poll each to terminal
```

**Self-hosted live targets:** launch the main agent and pass it the per-run Cekura connection details using the steps saved in the `## Cekura Agent Run Setup` block (Setup Step 1.4a, in `memory.md` / `CLAUDE.md`). If those launch steps weren't captured at Setup, ask the user now and persist them to that block before the first run — don't guess how to start the agent.

### What "fails" means

Failure means the **Cekura metric / expected-outcome scores** show failure — not that the call merely ended, errored, or the transcript "looks wrong." Read `runs[].evaluation.metrics[]` (or expected-outcome verdict) on each result. The same failure mode the prod call showed must be present in the replay transcript **and** reflected in the scores. Compare the replay transcript turn-by-turn with the prod transcript.

### Errors are NOT a reproduction

If a run errored, the call didn't connect, or the bot crashed → **fix it and retry that run.** An error is not a FAIL and does not count toward the M-of-N threshold. If you can't get the simulation to run at all, stop and ask the user.

### If it PASSES (below the fail threshold) — STOP and surface

If the evaluator passes (or fails fewer than M of N times), the bug is **not reproduced** — do not enter the loop. The most likely causes, in order:

1. **Mock/variable mismatch** — a mock tool returns a different value than prod (REPRO.3b), a dynamic variable wasn't copied (REPRO.3c/d), or the testing-agent turns were cleaned up instead of replayed verbatim (REPRO.3d). Re-check the harness against the prod trace.
2. **Stale fix** — the bug was already fixed on the live agent since the prod call. Confirm with the user; if so, there's nothing to do.
3. **Wrong evaluator** — the bullets / metric don't actually detect this failure (REPRO.4).

Show the user the replay transcript + scores side-by-side with prod and ask: "this didn't reproduce the prod failure — is the harness wrong, or was this already fixed?" Do not guess, and do not proceed into the loop on an unreproduced bug.

---

## Hand-off to the Optimization loop

When the must-fail gate is satisfied (definitive FAIL ≥ M of N for LLM-based, or a single FAIL for infra), hand off to [`optimization/collect.md`](optimization/collect.md) with:

- The **reproduction scenario IDs** as the loop's input (replacing the raw `call_ids` — from here on the loop iterates against the controlled replay, not the raw prod log).
- The recorded **full set** (the N-scenario dataset for LLM-based; the single scenario for infra) and the **failure class** (LLM-based / infra), which Eval reads for its must-pass re-run policy.
- The root-cause summary, the harness inventory (mocks + variables set), and the failing fail-run result URLs (these go in the eventual PR / summary as the reproduction evidence).
- The prod call ID + project ID (for the final PR / summary).

The Optimization loop, Overfitting Gate, and Eval then run exactly as documented — now anchored to a reproduction the skill has proven fails.

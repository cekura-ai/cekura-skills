---
name: cekura-self-improving-agent
description: >
  Use when the user asks to "improve my agent", "self-improving agent",
  "auto-tune my agent", "iterate on my agent prompt", "fix my agent based
  on test results", "close the loop on agent quality", "auto-improve agent
  prompt", "use eval results to improve agent", "optimize my prompt based
  on failures", "rewrite my prompt", or describes agent self-improvement,
  prompt iteration from run results, or automated agent quality loops.
  Covers the full diagnose → propose → apply → re-validate loop for VAPI
  agents (squads + tool definitions) and for self-hosted agents (custom
  websocket servers, including the offline / pasted-prompt degenerate
  variant).
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.19.0"
---

# Cekura Self-Improving Agent

## Purpose

Close the loop on agent prompt and tool-config quality. Ingest evaluation signal (scenario IDs to run, completed runs, a result batch, or production call logs), classify failures, diagnose where the prompt or tool config has gaps / conflicts / ambiguities, propose targeted edits, apply them, and re-run validation — iterating until the agent reaches **100% pass rate on the validation set** or the iteration cap is reached.

**Two data streams, one diagnosis.** Every iteration reads two artifacts in parallel: (1) the agent's prompt + tool definitions, and (2) the provider-side call state for each failing run (variable injection, rendered system messages, tool-call arguments where observable). A failure that *looks* like a prompt bug is often a missing dynamic variable; a failure that *looks* upstream is sometimes a prompt/tool conflict that survives correct injection. Mapping failures only to prompt sections produces phantom fixes.

**Two top-level modes, three variants.** The skill organizes providers under `providers/`:

- **`vapi`** — VAPI agents. Both system prompts and tool definitions are editable directly via the VAPI API. Tool config covers function declarations, referenced tool definitions (`name`, `description`, `parameters`, spoken `messages` like `request-start` / `request-complete` / `request-failed`, and handoff `destinations`), and which tools each squad member references via its `toolIds` array. Edits land on VAPI; the live agent picks them up immediately. See [`providers/vapi/overview.md`](providers/vapi/overview.md).
- **`self_hosted` (websocket)** — custom websocket servers (e.g., Python / Node / Go) whose system prompt, tool definitions, **and conversation-orchestration code** live in the user's source code. Editable surface is the user's source file via the `Edit` tool — covering the system prompt, tool schemas, AND orchestration code (conversation-history management, message wiring, state-preservation logic, keepalive / retry plumbing) when a failure's root cause is in code rather than prompt wording. Business logic (what a tool *computes* or what an external service returns) and security-sensitive code (API keys, auth, signing) remain out of scope. **The Cekura agent record's `llm_system_prompt` field is NOT the source of truth in this mode — do not read it, and never ask the user to paste their prompt while a workspace is reachable.** Always source the prompt from the workspace: start with the file currently open in the IDE (`ide_opened_file`), then grep project files for the system-prompt string constant. The user restarts their websocket server before re-validation; in auto mode the gate is skipped. A degenerate `offline` variant covers the "no live websocket reachable" case — the skill renders the rewritten prompt for manual application and asks for pasted failures each iteration (offline variant supports prompt edits only, never code edits). See [`providers/self-hosted/websocket.md`](providers/self-hosted/websocket.md) and [`providers/self-hosted/overview.md`](providers/self-hosted/overview.md).

**Exit gate.** The voice/channel/infra filter informs *what to fix* (Phase 3 only proposes edits for prompt-following failures), not *when to stop*. Any remaining failure of any class keeps the loop alive. Only the iteration cap or a genuine 100% pass ends the loop.

Currently supported for **VAPI** and **self-hosted** (websocket). Retell and pipecat support are intentionally disabled and will be re-enabled in a future revision.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

- VAPI mode: VAPI write operations (assistant PATCH, tool create / PATCH / delete) are not exposed through Cekura platform tools — they go directly to the VAPI API with `VAPI_KEY`. Full curl bodies in [`providers/vapi/phase-4-apply.md`](providers/vapi/phase-4-apply.md).
- Self-hosted / websocket: file edits land via the `Edit` tool on the user's source code — system prompt, tool schemas, and conversation-orchestration code (history management, message wiring, state) are all in scope; optional `mcp__cekura__aiagents_partial_update` to sync the Cekura description as a mirror. Full flow in [`providers/self-hosted/websocket.md`](providers/self-hosted/websocket.md).

## How to Use This Skill

This is an **interactive, multi-iteration workflow**. The user supplies one of:

- **VAPI / self-hosted modes (any live target)** — an `agent_id` plus exactly one of: `scenario_ids`, `result_id`, `run_ids`, or `call_ids`.
- **Self-hosted / websocket / offline variant** — a `prompt` (pasted text or read-only file path) plus pasted `{transcript, expected_outcome, verdict}` blocks. No live agent required.

Optionally:

- `max_iterations` (default 10) — caps the Phase 4 loop.
- `mode` (`vapi` / `self_hosted`) — explicit override if the resolution would otherwise be ambiguous.
- `redeploy_command` (self-hosted only) — shell command(s) the skill should run after each apply step to restart the live agent before re-validation. If provided, Phase 4 runs this automatically and the user-side restart gate is skipped entirely. If set to the literal string `"manual"` (or not provided in `auto_mode: false`), the skill falls back to the canonical "pause and ask the user to restart" gate. Collected at the end of Phase 1.3 for self-hosted modes — see step 1.4 below. VAPI mode ignores this field (VAPI edits land live; nothing to redeploy).
- `auto_mode` (default **true**) — when true, skip the Phase 3 → Phase 4 approval gate on every iteration. With `redeploy_command` configured, the skill is fully end-to-end autonomous for self-hosted modes (auto-apply → auto-redeploy → auto-validate). Without `redeploy_command`, auto_mode skips the routine user-side deployment pauses too and trusts the user to keep their live system in sync (the no-change detector at Step 4.5 catches stale-state cases after the fact). The iteration cap, oscillation detection, validation-set stability, and the user's ability to interrupt mid-loop all still apply. Set `auto_mode: false` only when you want a per-iteration diff-approval pause AND (if `redeploy_command` is unset) explicit user-side deployment gates before validation.

**Ask for feedback or clarification wherever required, even in auto mode.** Auto mode skips *routine* gates; it does NOT make the skill silent on genuinely ambiguous inputs or risky decisions. Pause and ask when:

- The user's input is ambiguous or incomplete (e.g., `agent_id` + `prompt` supplied without a mode; structured-config file where the prompt field can't be identified safely; empty / one-line / clearly-non-production prompt).
- Self-hosted / websocket / offline variant — there is no automated path to re-collect failures, so the skill must ask for pasted failures after each iteration.
- The skill needs to widen the validation set, switch input types mid-loop, or change the validation comparison set in any way — never silent in either mode.
- Oscillation is detected (same scenario flipping pass/fail across iterations) or a no-change signature appears (identical post-edit failures two iterations in a row). Surface and pause; do not burn the iteration cap.
- Most kept failures cluster on one or two metrics whose explanations look subjective — hand off to `cekura-metric-improvement` instead of iterating blindly.
- All kept failures classify as Upstream/data — surface the hand-off and stop the loop early; do not propose phantom prompt edits.
- A diagnosis is low-confidence ("could be Conflict or Ambiguity, depending on intent") — ask the user to disambiguate rather than guessing.

When in doubt, ask. A short clarifying question costs less than a wrong PATCH against a live agent or a wasted iteration. But do NOT pre-emptively ask the user to redeploy their server, restart their pipeline, or re-apply a prompt before triggering evals — auto mode runs validation directly and surfaces stale-state hypotheses only if results come back suspiciously unchanged.

The four phases run in order, with the last looping until the agent passes:

1. **Phase 1 — Verify Agent and Provider Support.** Resolve mode and variant. For `agent_id` inputs, fetch the agent and gate on `assistant_provider`. Route to one of: `providers/vapi/` or `providers/self-hosted/websocket.md`. Each loads the source-of-truth artifacts the rest of the loop edits against.
2. **Phase 2 — Collect Failures and Inspect Provider Call State.** Branch on input type. For `scenario_ids`, run them first and wait for completion; for `result_id` / `run_ids` / `call_ids`, fetch the supplied runs / call logs; for pasted failures (offline variant only), trust the user's transcripts + verdicts directly. Pre-filter human-reviewed successes. Accumulate expected-outcome and metric failures, **discard voice/channel failures**, and **for every kept failure also pull the provider call state** when available (variable injection, rendered system message, tool-call arguments). Both streams flow into Phase 3.
3. **Phase 3 — Diagnose and Propose Changes.** Synthesize the prompt/tool artifacts AND the variable-state findings to attribute each failure to its actual root cause: prompt Gap / Conflict / Ambiguity, tool-config issue, or **Upstream/data** (missing or malformed dynamic variables that no prompt edit can fix). Produce minimal scoped edits for the prompt-and-tool roots; surface upstream-rooted failures with a clear hand-off. In the offline variant, only prompt edits are produced — tool findings become hand-offs.
4. **Phase 4 — Apply, Validate, and Iterate.** Apply the prompt and/or tool-definition edits to the right surface for the resolved mode and variant:
   - VAPI → direct API PATCH (see `providers/vapi/phase-4-apply.md`).
   - Self-hosted / websocket / `file` variant → `Edit` calls on the user's source file; user restarts the server (see `providers/self-hosted/websocket.md`).
   - Self-hosted / websocket / `offline` variant → render the rewritten prompt; user applies and re-runs externally.

   In auto mode, validation runs immediately after apply — no pre-emptive pause to ask the user to redeploy / restart / re-apply. In `auto_mode: false`, Phase 4 pauses on the appropriate gate. Confirm sync (skipped in offline variant), run validation against the relevant scenarios, re-collect failures with the same Phase 2 classification. Exit only on **100% pass rate**; otherwise feed the new failure summary back into Phase 3. Loop up to `max_iterations` times.

By default (`auto_mode: true`), routine gates are skipped and the skill runs end-to-end. For VAPI agents this is fully autonomous. For self-hosted agents, Cekura-side / file-system edits land but the live agent only picks them up after the user's redeploy / restart — the skill surfaces a no-change hypothesis if results look unchanged across iterations. For the websocket / offline variant, the skill must ask for new pasted failures after each iteration. The skill must still pause and ask wherever required — see the bulleted list above. The user can interrupt at any time.

When `auto_mode: false`, the user gates every Phase 3 → Phase 4 boundary. Phase 1 → Phase 2 → Phase 3 runs straight through. Every apply step is preceded by an explicit user OK on that iteration's diff.

## Phase 1: Verify Agent and Provider Support

### Step 1.1 — Resolve the run mode

Branch on the user's input shape:

- The user supplied a `prompt` (pasted text or file path) **and** no `agent_id`, OR they supplied a `prompt` plus an explicit `mode: self_hosted, self_hosted_flavor: websocket, websocket_variant: offline` → resolve to **self-hosted / websocket / offline** and skip to Step 1.3 (per the websocket sub-flavor doc).
- The user supplied an `agent_id` only → continue with Step 1.2.
- The user supplied both an `agent_id` and a `prompt` without specifying a mode → ask once which they want: provider mode (skill PATCHes the live agent / edits the source file) or offline variant (skill outputs a rewritten prompt only). Default to provider mode if they accept the default.
- The user supplied neither → ask for one. If they don't know an agent ID, list their agents so they can pick one.

### Step 1.2 — Fetch agent details and gate on provider (skipped in offline variant)

Retrieve the agent and read `assistant_provider`:

- **`vapi`** → continue down the VAPI branch (Step 1.3a; see [`providers/vapi/overview.md`](providers/vapi/overview.md)).
- **`self_hosted`, `custom`, `agentforce`, or any other non-VAPI tag** → route to the self-hosted / websocket branch (Step 1.3b; see [`providers/self-hosted/websocket.md`](providers/self-hosted/websocket.md)). If the user can't point at a source file, fall back to the `offline` variant.
- **`retell`, `pipecat`, `elevenlabs`, `livekit`, `sip`, or missing/empty** → offer the self-hosted / websocket / `offline` variant ("This skill can't PATCH a `<provider>` agent directly, but it can run in offline mode if you paste your system prompt — want to do that instead?"). Halt only if the user declines.

`retell` and `pipecat` are in the unsupported list on purpose — their direct handling is temporarily disabled. Do not bypass the gate for direct PATCHing. If `assistant_provider` is empty, point the user at `cekura-create-agent` (Phase 3: Configure Provider Integration), or offer the offline variant if they have a draft prompt. Compare lowercased — be defensive against mixed-case input.

Track the resolved mode and variant on the run; every later phase branches on them.

For the exact VAPI error-message shape, the Retell-specific note, and 404 handling, see [`providers/vapi/phase-1-fetch.md`](providers/vapi/phase-1-fetch.md). For the self-hosted overview, see [`providers/self-hosted/overview.md`](providers/self-hosted/overview.md).

### Step 1.3 — Fetch the source-of-truth artifacts (branch by mode)

Each branch's full procedure lives in its provider doc:

- **VAPI** — [`providers/vapi/overview.md`](providers/vapi/overview.md) (with [`providers/vapi/phase-1-fetch.md`](providers/vapi/phase-1-fetch.md) for curl bodies + edge cases). VAPI is the source of truth; the Cekura `description` is informational only. Pulls the live `/assistant/{id}` (or squad) plus every referenced `/tool/{id}` using `VAPI_KEY`.
- **Self-hosted / websocket** — [`providers/self-hosted/websocket.md`](providers/self-hosted/websocket.md). `file` variant: the user's source file (the system prompt is a string constant; tool definitions usually live in the same file); `offline` variant: pasted prompt text, read-only.

Each branch ends by surfacing a compact summary to the user before moving on to Step 1.4 (self-hosted) or Phase 2 (VAPI).

### Step 1.4 — Collect the redeploy command (self-hosted modes only)

Skipped for VAPI (edits land live; nothing to redeploy) and for the websocket `offline` variant (no live agent at all).

For self-hosted mode with a live target (websocket / `file` variant), the live agent does not pick up prompt or tool-config changes until the user restarts. The skill can either run that step automatically each iteration (preferred, fully autonomous) or pause on a manual restart gate (the legacy behavior).

If `redeploy_command` is already provided in the run inputs, use it. Otherwise, ask the user exactly once:

```
For end-to-end automation, I can run your redeployment automatically after each
prompt edit so the live agent is ready before re-validation. What shell command
(or commands) restarts your live agent?

Examples:
  Local Python websocket server:    pkill -f main.py; nohup python main.py &
  Docker compose:                   docker compose restart agent
  systemd:                          sudo systemctl restart my-agent
  SSH'd remote host:                ssh user@host 'systemctl restart agent'
  Fly.io:                           fly deploy --strategy immediate

Reply with the shell command, OR reply "manual" if you'd rather restart the
agent yourself between iterations (I'll pause and ask "done" before each
re-validation).
```

Record the resolved `redeploy_command` on the run. Treat the literal `"manual"` (case-insensitive) as a sentinel meaning "user-driven restart gate every iteration" — that branch is the iter-pause behavior documented in the websocket doc's Phase 4.1.

When the user provides a real command, treat it as a contract: the skill will execute it after every iteration's apply step (Phase 4.1, before validation in Phase 4.4). The user is responsible for the command being correct and idempotent; the skill is responsible for running it, capturing exit code + stderr, and failing loudly if it errors. Backgrounded servers (`nohup ... &`, `disown`) are fine — the Bash tool returns once the foreground portion completes.

For the full collection-prompt wording, sentinel handling, command-execution semantics, and how to handle "the command is multi-step or interactive" edge cases, see [`providers/self-hosted/overview.md`](providers/self-hosted/overview.md) § "Redeploy command flow".

## Phase 2: Collect Failures and Inspect Provider Call State

### Step 2.1 — If input is `scenario_ids`: execute, then wait

Skip for the other input types. Pick voice mode for VAPI (default). Trigger the run, capture the `result_id`, then poll until terminal (every ~30s, capped at 15 min for voice / 5 min for text). Once complete, treat as a `result_id` input.

For self-hosted agents, scenario execution still runs against the live websocket server at the configured URL. In auto mode the skill triggers validation without pausing to ask if the user has restarted; if results look unchanged across iterations, the no-change hypothesis is surfaced after the fact (see Phase 4.5). In `auto_mode: false`, Phase 4.1 gates this with the appropriate apply pause.

For the offline variant, there are no scenarios to execute — only pasted failures.

### Step 2.2 — Fetch the runs or call logs (or trust pasted failures)

Branch on input type to populate a list of items to inspect:

| Input | Tool path |
|-------|-----------|
| `result_id` | Fetch the result batch — every run inside has scenario info, status, transcript, expected-outcome verdict, and metric evaluations. |
| `run_ids` | Bulk fetch — same per-run shape as above. |
| `call_ids` | Fetch each call log individually — transcripts and metric evaluations, no expected outcome. |
| Pasted failures (offline variant only) | Trust the user's `{transcript, expected_outcome, verdict, verdict_explanation}` blocks. No fetch. Treat each block as a single failing run with no metric evaluations beyond what's pasted. |

**Authoritative failure view is per-run, not result-level.** A `results_retrieve` payload contains two conflicting views of "what failed":

- **Authoritative (use this):** each item under `runs[*]` carries its own `evaluation_status` — this is the post-human-review verdict and the only field Step 2.3 should read.
- **Misleading (do NOT use):** the result-level summary fields — `failed_workflow_runs`, `failed_reasons.issues`, `failed_runs_count`, `success_runs_count`, `success_rate` — are computed from raw machine scores **before** any human review override. A run with `evaluation.metrics[0].score == 0` but `evaluation_status == "reviewed_success"` (human overrode the machine fail) shows up in `failed_workflow_runs` and inflates `failed_runs_count`. Feeding those aggregates into Step 2.3 silently smuggles `reviewed_success` items into the kept set, producing edits that contradict the reviewer.

Always iterate `runs` and read each run's own `evaluation_status`. The same rule applies to `run_ids` input (bulk fetch returns the same per-run shape) and to call-log inputs (per-item verdict, not any batch-level aggregate).

### Step 2.3 — Pre-filter, accumulate, and discard voice failures

**Pre-filter by run-level verdict.** Each run / call log carries a top-level terminal verdict (`evaluation_status` on Cekura runs, or equivalent) with four possible states: `success`, `failure`, `reviewed_success`, `reviewed_failure`. Default behavior:

- **`failure`** → **keep** (machine-judged failure — the primary candidate for improvement).
- **`reviewed_failure`** → **keep**, treated as **high-confidence** failure (a human either confirmed the machine's fail verdict OR overrode a machine success to mark it failed). These are the strongest signal in the batch — never drop.
- **`reviewed_success`** → **drop**. The human review supersedes machine verdicts, so feeding these into Phase 3 would push edits that contradict the reviewer. Also recognize equivalent overrides (`review_status == "reviewed_success"`, `reviewed_success: true`, `human_review.outcome == "success"`).
- **`success`** → **drop** (nothing to improve).

The kept set (`failure` ∪ `reviewed_failure`) is what feeds the rest of Phase 2 — there is no separate "ask the user which ones to include" gate. Track the dropped counts (`reviewed_success` and `success`) on separate lines in the summary so the user can see the full funnel.

For inputs where the verdict field isn't named exactly `evaluation_status` (call logs use `verdict` or `result`; pasted failures use whatever the user wrote), apply the same four-bucket logic by mapping equivalent statuses. When a non-standard status is ambiguous, **keep the item** — false keeps are recoverable in Phase 3; false drops silently lose signal.

If skipped metric failures cluster on one or two metrics (e.g., many `reviewed_success` items all flagged FAIL on the same metric judge), hint to the user that those metrics may need `cekura-metric-improvement`.

**Accumulate failures from the survivors:**

1. **Expected-outcome failures** *(runs only, not call logs)* — verdict `fail` / not-met / false. Capture scenario id + name, transcript excerpt, expected-outcome text, verdict explanation.
2. **Metric failures** *(both runs and call logs)* — any attached metric verdict `FAIL` (skip `PASS`, `N/A`, `VALID_SKIP`). Capture metric id + name, FAIL explanation, and offending transcript snippet.

A single run can contribute to both classes. Track them separately — Phase 3 treats them differently (expected-outcome failures usually point at agent prompt logic; metric failures may point at either the agent or the metric).

**Voice/channel filter.** This skill only optimizes prompt + tool config, so discard failures whose root cause is the voice channel: audio quality, ASR errors, TTS issues, latency / dead air / talk-over, dropped connections, errored runs, or failures from metrics that explicitly score voice quality. **Keep** failures where the agent had the input it needed and still behaved wrong (skipped a step, asked wrong info, hallucinated, missed a handoff, went off-topic, missed an end-of-call requirement). When in doubt, **keep the failure** — false keeps are recoverable in Phase 3; false discards silently lose signal.

For text-mode runs and chat call logs the filter is a no-op — every collected failure passes through. Track the discarded count separately from the `reviewed_success` count.

### Step 2.4 — Inspect provider call state (default, every iteration)

Run this for **every kept failure**. The output feeds Phase 3 alongside the failure verdicts. Skipping this step is the most common way the loop produces phantom prompt fixes for issues actually rooted upstream.

For each kept failing run / call log, fetch the provider call object and record:

- `assistantOverrides.variableValues` — what Cekura passed to the provider at call start (Signal 1: intent).
- `artifact.variableValues` — what the provider saw after merging overrides + defaults (Signal 2: runtime).
- The rendered system message (`artifact.messages[0].content`, or per-activation messages for squads) — search for literal `{{...}}` substrings (Signal 3: substitution failure).
- Tool-call arguments (`artifact.messages[*].toolCalls[*].function.arguments`) — flag literal placeholders, empty arrays where data was expected, hallucinated values (Signal 4: what the LLM produced).
- For VAPI squads: `artifact.assistantActivations` — which member was active per activation.

Bulk-fetch runs (NOT result-fetch — provider call details aren't included there) or fetch call logs individually. Payloads are large (250–500 KB per run); use `jq` or python rather than re-reading the whole blob. Direct-VAPI fallback (`GET https://api.vapi.ai/call/{id}`) is available when `provider_call_details` is missing or stale.

**Self-hosted / websocket caveats.** The user's websocket server controls what Cekura sees. The convention for `main.py`-style agents is to forward tool-call records to Cekura via `{"role": "Function Call", "data": {...}}` messages; when present, Signal 4 is recoverable. `assistantOverrides.variableValues` is typically NOT observable — most websocket agents don't echo it back. Treat substitution as not-observable unless the transcript literally shows `{{varName}}`. With the `offline` variant, only Signals 3 and 4-partial are available — what the pasted transcript shows.

Group observations when patterns repeat — "all 3 failed runs share the same variable-injection failure" is more actionable than per-run repetition. For the full per-signal decision tree (key absent vs. wrong-name vs. literal-placeholder-survives), the squad per-member-message caveat, and the bare-comma-separated-string gotcha for bulk-retrieve, see [`references/dynamic-variables-debugging.md`](references/dynamic-variables-debugging.md).

### Step 2.5 — Build the failure summary

Group failures by **scenario** (for runs) or by **metric** (for call logs). The summary feeds Phase 3 and is also shown to the user for transparency. Report on separate lines and **cite the source field explicitly** so the skip is auditable: items inspected (per-run `evaluation_status`), `reviewed_success` skipped (human override), `success` skipped, voice-related discarded, prompt-following kept. Example: `5 runs inspected (per-run evaluation_status) — 1 reviewed_failure kept, 1 reviewed_success dropped (human override), 3 success dropped.` Include the provider-call-state observations from Step 2.4 inline.

**Phase 2 does not pause for approval** — the user-facing gate is at every Phase 3 → Phase 4 transition. The one exception: if failures are dominated by one or two metrics with thin signal, stop and suggest hand-off to `cekura-metric-improvement` — those are metric-quality issues, not agent-quality issues, and Phase 3 won't fix them.

**Do not surface small-sample / overfitting caveats to the user.** Even when the input is a single run, do not include lines like "with N runs any fix risks overfitting" or "5–10+ items would be a healthier signal" — internal calibration of confidence is fine; user-facing hedging reads as a stall. The user has already chosen to act on the input they have.

For the full summary template, edge cases (zero failures / all-errored / mixed inputs), and the exact wording around the metric-quality hand-off, see [`references/phase-2-failure-collection.md`](references/phase-2-failure-collection.md).

## Phase 3: Diagnose and Propose Changes

Take the **kept** failure summary from Phase 2 — including both verdicts (Step 2.3) AND provider call state (Step 2.4) — and the **current agent prompt and tool definitions**. Synthesize all three into a root-cause attribution per failure, then produce a concrete, reviewable set of edits (or, for upstream-rooted failures, a hand-off recommendation).

Outputs split into four streams; any may be empty for a given iteration:

- **Prompt edits** —
  - *VAPI:* change the system message of one or more squad members (or the lone assistant for non-squad agents).
  - *Self-hosted / websocket / `file`:* change the system prompt string in the user's source file via `Edit`.
  - *Self-hosted / websocket / `offline`:* render a rewritten prompt for the user to copy.
- **Tool-config edits** —
  - *VAPI:* change a tool's name / description / parameter schema / spoken messages / handoff destinations, OR change which tools a member references via `toolIds` (add a new tool, remove a reference, create a new tool).
  - *Self-hosted / websocket / `file`:* change tool-definition blocks in the user's source file via `Edit`. These are *live* edits.
  - *Self-hosted / websocket / `offline`:* always empty. Tool findings become upstream hand-offs.
- **Orchestration-code edits** — *self-hosted / websocket / `file` only.* When the root cause is in the user's conversation-orchestration code rather than prompt wording — e.g., aggressive history truncation that drops earlier qualification answers, missing tool-result forwarding back to the LLM, keepalive / retry logic that silently loses turns, state slicing that breaks mid-conversation — propose a minimal `Edit` to the relevant function. Scope is limited to plumbing/orchestration: how messages flow, how conversation state is preserved, how the loop is structured. **Out of scope**: business logic (what a tool computes, what an external service returns), security-sensitive code (API keys, auth, signing, secrets), dependency / requirements changes, framework upgrades. VAPI and the websocket `offline` variant never produce this stream — code-rooted findings in those modes become upstream hand-offs.
- **Upstream hand-off recommendations** — for failures rooted in missing / wrong dynamic variables, no prompt or tool edit fixes the issue. Surface the variable mismatch with a concrete pointer to where it should be set (test profile, scenario config, squad / project defaults, upstream caller). In the websocket `offline` variant, also surface tool-shaped findings here. In VAPI / websocket `offline`, also surface code-shaped findings here.

### Step 3.1 — Read both data streams

Re-fetch the source-of-truth artifacts if more than a few minutes have passed since Phase 1.3:

- *VAPI:* `/assistant/{id}` and every referenced `/tool/{id}` — VAPI dashboard edits don't notify Cekura, and a stale local copy will produce a wrong PATCH body.
- *Self-hosted / websocket / `file`:* re-read the source file with the Read tool. The user may have edited the file between iterations (manually, in their IDE).
- *Self-hosted / websocket / `offline`:* re-read the prompt only if its source was a file path; pasted prompts don't change between iterations unless the user explicitly pastes a new one.

Note dynamic-variable placeholders (`{{variableName}}`) in both prompts and tool messages / parameter schemas — they're injected per call and must not be touched by edits unless the user explicitly asks.

Variable-state observations from Step 2.4 are co-equal input. Compare each `{{...}}` placeholder in the prompt or tool definitions against what actually appeared in the failing runs' variable values. A placeholder the prompt depends on but the runtime never received is the most common root cause of "agent stalled / improvised / hallucinated" failure shapes — and it's invisible if you only read the prompt.

If the prompt is empty or clearly not the production prompt (one-line summary, etc.), **stop and ask** — the agent isn't fully configured, or the user is running prod somewhere the skill can't see. In websocket mode this also catches the "user pointed at the wrong file" case.

### Step 3.2 — Map each kept failure to its governing artifacts AND variable state

For each kept failure, locate every artifact that *should* have governed that behavior, AND record the variable state at the moment of failure:

- **Prompt sections** — quote the exact lines from the responsible assistant's system message (the speaker in the relevant transcript turn, for squads).
- **Tool definitions** — if the failure involves a tool call, pull the relevant tool's definition. Quote `function.description`, the relevant property in `function.parameters`, the offending `messages[*].content`, or the suspect `destinations` entry.
- **Orchestration code** *(self-hosted / websocket / `file` only)* — for failures whose shape suggests a code-level bug rather than a prompt issue (agent "forgets" earlier turns, tool result never reaches the LLM, conversation drops mid-flow, keepalive loses messages, history is sliced too aggressively), open the source file and locate the relevant function — typically the conversation loop, history-management block, or message-forwarding logic. Quote the exact lines and note window sizes, slice indices, or branching conditions that match the failure shape.
- **Variable state** — for every `{{...}}` placeholder referenced by the relevant prompt section or tool definition, record what actually appeared in the runtime variable values: `null`, empty arrays, missing keys, name mismatches, or literal placeholder strings that survived into rendered messages or tool-call arguments.

If no prompt or tool artifact governs the failure AND variable state looks healthy, mark it "uncovered" — that's a strong gap signal *and* a cue to check orchestration code in websocket mode. If variable state is malformed, the failure is likely upstream regardless of how clean the prompt looks. Most failures have signal in more than one dimension; track all matches.

### Step 3.3 — Classify each failure

| Bucket | What it looks like |
|--------|--------------------|
| **Gap** | No section addresses this situation, AND variable state is healthy. The agent improvised and got it wrong. |
| **Conflict** | Two clauses contradict, OR a clause contradicts a tool definition, OR a clause contradicts the desired behavior implied by the failure. |
| **Ambiguity** | One section addresses it but the wording is vague enough the agent could read it either way, AND variable state is healthy. |
| **CodeBug** *(websocket / `file` only)* | The prompt clearly instructs the right behavior but the agent demonstrably can't follow it because the orchestration code prevents it — e.g., earlier qualification answers are no longer in the LLM's context window (history truncation), tool results aren't forwarded back, conversation state is sliced in a way that drops required information, oscillating verdicts on the same scenario suggest stochastic context loss. The prompt is fine; the plumbing is broken. |
| **Upstream/data** | Variable state shows the runtime didn't have what the prompt or tool requires: `null` / absent / empty, key-name mismatch, or literal `{{...}}` survived into rendered messages or tool-call arguments. |

If you can't tell, default to **Ambiguity** and flag for the user. A failure can have both an Upstream/data root AND a Gap/Conflict/Ambiguity/CodeBug component; pick the bucket that, if fixed, would produce the largest behavior change — usually Upstream/data, because phantom prompt fixes against broken variable state will fail re-validation the same way and obscure whether the prompt edit helped. Surface the secondary component as "deferred — re-evaluate after upstream fix".

**CodeBug signals worth watching for** (in websocket / `file` mode only):
- The same scenario flips pass/fail across iterations on prompt-only changes (oscillation) and the failure mode involves "agent forgot earlier info" or "agent re-asked despite an explicit don't-re-ask clause" → suspect history truncation or context-window slicing.
- The agent literally repeats `{{varName}}` AND the runtime variable was provided → the rendering / substitution code in the user's file is broken, not Cekura's injection.
- A tool call fires but the LLM never sees its result on the next turn (transcript shows tool call → silence → user prompt re-asked) → tool-result forwarding back to the LLM is broken.
- Conversations drop mid-flow with no error and no end-of-call message → keepalive / connection-management code.
- Repeated prompt-wording iterations on the same failure produce no behavior change (no-change signature) → root cause is below the prompt layer.

### Step 3.4 — Propose a change for each diagnosis

Use the smallest change that fixes the failure — don't rewrite paragraphs to fix one missed step.

- **Upstream/data → no edit, hand off.** This skill cannot fix upstream root causes. Surface a hand-off naming each missing/wrong variable, what the prompt expected, what the runtime saw, and where to inject (test profile, squad / assistant-level dynamic variables, upstream caller). In the websocket `offline` variant, runtime state may not be fully observable. If a prompt edit could *also* harden the agent against the missing variable, note it as a secondary candidate but do not include it in the iteration's edit set unless the user asks. If **all** kept failures are Upstream/data, this iteration produces zero edits — surface and stop the loop early.
- **Prompt edits.** Gap → **add** a clause next to the closest related section, matching existing voice/format. Conflict → **edit** or **remove** the contradictory clause; if both have legitimate use cases, **scope** them with explicit conditions. Ambiguity → **edit for specificity**; replace vague verbs with concrete steps; add a checklist if there are >2 required actions.
- **Tool-config edits — VAPI mode.** Four sub-types: (a) **edit** an existing tool's `function.description` / parameters / spoken `messages` / handoff `destinations`; (b) **add** a new tool when a flow step requires data the agent doesn't have (POST `/tool` then PATCH the assistant's `toolIds`); (c) **remove a tool reference** from a specific member when squad inheritance is exposing a tool that member shouldn't use (PATCH `model.toolIds`, leave the tool definition); (d) **delete a tool** — rare, only after cross-referencing every squad member's `toolIds` and confirming no references remain.
- **Tool-config edits — self-hosted / websocket / `file`.** Two sub-types: (a) **edit** a tool-definition block in the user's source file via `Edit` (the schema flows into the live agent on restart); (b) **add** a new tool-definition entry to the `TOOLS` list (or equivalent). Tool *implementations* (the function body that computes a result or calls an external service) remain out of scope — surface those as hand-offs.
- **Tool-config edits — self-hosted / websocket / `offline`.** None. Surface tool-shaped findings as upstream hand-offs.
- **Orchestration-code edits — self-hosted / websocket / `file` only.** When the diagnosis is **CodeBug**, propose the smallest `Edit` that fixes the plumbing. Common shapes:
  - *History truncation too aggressive* — bump the window size, switch from raw last-N to "system + last-N user/assistant turns", or summarize-and-prepend collected state before truncation. Example: a `if len(history) > 12: tail = history[-10:]` slice that drops earlier qualification answers — raise to 24 or higher, and ensure the resulting list still starts at a `user` message to avoid orphaned `tool` messages.
  - *Tool result not forwarded* — add the missing append to `history` after the tool call returns, OR fix a broken message-role mapping (`"role": "tool"` with the right `tool_call_id`).
  - *Keepalive / connection drops* — adjust the ping interval, fix a coroutine that's cancelled prematurely, ensure `await websocket.send(...)` isn't dropped during a long tool call.
  - *State sliced incorrectly* — fix the index math, the role-filtering condition, or the dedup logic.

  **Rules**: One `Edit` per logical change; use 5–10 lines of surrounding context per anchor. Show the user the diff before applying (auto mode renders for transparency, then proceeds). Do NOT touch business logic, tool-implementation bodies, security/auth code, secrets, dependency lists, or framework imports. Do NOT rewrite whole functions — change the minimum needed. If the fix requires non-trivial refactor (new helper functions, multi-file changes, dependency additions), surface as a hand-off instead of attempting it.

**Cluster related diagnoses.** If 5 failures all stem from the same missing clause OR the same noisy `request-start` message, propose one edit that covers all 5. Prompt and tool edits can also cluster across artifacts: e.g., "remove tool reference from member X **and** add a clause to its prompt explaining what to do at that decision point instead" is one logical change, surfaced as a paired edit.

For the full classification table with examples, the tool-edit anti-patterns (do-not-rename, do-not-tighten-schema, do-not-mass-delete), the manual-vs-automated-improver guidance, and the Phase 3 anti-patterns, see [`references/phase-3-diagnosis.md`](references/phase-3-diagnosis.md).

### Step 3.5 — Present the proposal to the user

Show every proposed change as a **before/after** block grouped by bucket and edit surface (prompt vs. tool), with the failures it addresses. End with a summary line: `4 changes proposed and 1 upstream hand-off across 12 prompt-following failures (2 prompt edits, 2 tool edits; 1 gap, 2 conflicts, 1 ambiguity, 1 upstream).`

**Default (`auto_mode: true`): skip the routine approval prompt.** Still render the before/after blocks and the summary line for transparency, then proceed straight to Phase 4.1 with **all** proposed edits accepted. Do not silently downgrade or filter the proposal. Upstream hand-offs are still surfaced. If the iteration produced **zero** prompt/tool edits (all failures were Upstream/data), there is nothing to apply — surface the hand-offs and stop the loop the same way the non-auto path would. **Even in auto mode, pause and ask if the proposal is low-confidence, the edit set is unusually large for the failure count, or any of the "ask for feedback" triggers from the How to Use section apply.**

**When `auto_mode: false`: this gate fires on every iteration, not just the first.** Ask the user to accept all, accept a subset, or push back; do not move to Phase 4 until they explicitly confirm.

For the exact before/after templates (prompt edit, tool-definition edit, `toolIds` reference removal, upstream hand-off), see [`references/phase-3-diagnosis.md`](references/phase-3-diagnosis.md).

## Phase 4: Apply, Validate, and Iterate

This phase is a **loop**. Each iteration: apply the approved edits → run validation → diagnose new failures → propose more changes → apply again. Exit only on **100% pass rate** (zero failures of any class) or when the iteration cap is hit. Do not exit just because the latest failures look like voice/infra rather than prompt issues — first re-attribute squad failures to whichever member is now responsible and consider mitigation edits.

**Early-exit shortcut.** If Phase 2 collected zero failures of any class from the initial input, Phase 3 was skipped — report success and stop. If Phase 2 found failures but they are *all* voice/infra/tool, do not auto-exit; run the same logic as the "kept = 0 but total > 0" branch in Step 4.6 first.

### Step 4.1 — Apply the edits (branch by mode + variant)

Apply-order details, gate wording, and edge cases live in each provider's doc:

- **VAPI** — [`providers/vapi/phase-4-apply.md`](providers/vapi/phase-4-apply.md): tool PATCH → new-tool POST → assistant PATCH (prompt + `toolIds` bundled). No redeploy step (edits land live).
- **Self-hosted / websocket / `file`** — [`providers/self-hosted/websocket.md`](providers/self-hosted/websocket.md) § "Phase 4.1d — Apply" (variant `file`): tool-definition `Edit`s → new-tool `Edit` → system-prompt `Edit` → optional Cekura description sync → **restart step** (see below).
- **Self-hosted / websocket / `offline`** — [`providers/self-hosted/websocket.md`](providers/self-hosted/websocket.md) § "Phase 4.1d — Apply" (variant `offline`): render the rewritten prompt; auto-mode asks once for new pasted failures concisely; non-auto fires the full manual-apply gate. No restart step (no live agent).

**Restart step (self-hosted with live target).** After apply lands and before Step 4.2 sync verification, branch on `redeploy_command` (collected in Step 1.4):

- **Command provided** → run it via the Bash tool. Capture exit code and stderr. On non-zero exit, surface the failure to the user, do NOT proceed to validation, and ask whether to retry the restart or abort. On success (or success-with-warnings), proceed to Step 4.2.
- **`redeploy_command == "manual"` (or unset and `auto_mode: false`)** → fire the websocket restart gate. Wait for explicit user confirmation (`done` / `restarted` / `yes`).
- **Unset and `auto_mode: true`** → proceed straight to validation without pausing. The Step 4.5 no-change detector surfaces stale-state hypotheses after the fact.

Treat the restart step as a critical path: a failed restart means validation will reflect the pre-edit live state. Never silently swallow a non-zero exit code and proceed to validation — that produces results indistinguishable from "the prompt edit didn't help" and burns iteration cap.

### Step 4.2 — Confirm sync (branch by mode + variant)

- **VAPI** — re-fetch `/assistant/{id}` and every edited / created `/tool/{id}` and verify the changed fields landed. Don't skip the tool re-fetch — VAPI's tool PATCH semantics replace nested objects wholesale.
- **Self-hosted / websocket / `file`** — re-read the source file (Read tool, not cached) and verify the changed regions match the intended `Edit` output. If a tool-definition edit was supposed to extend `TOOLS` but the post-edit file shows the old length, the edit landed in the wrong place or matched a partial-but-ambiguous `old_string` — roll back and retry.
- **Self-hosted / websocket / `offline`** — skip; nothing to sync. The user's reply to the apply gate is the only confirmation.

### Step 4.3 — Build the validation set

Pick the validation set based on the **original input type**:

| Original input | Validation set (full) |
|----------------|----------------|
| `scenario_ids` | Reuse the same scenario IDs. |
| `result_id` / `run_ids` | Extract `scenario_id` from every run (already fetched in Phase 2.2). De-duplicate. |
| `call_ids` | Synthesize one scenario per call from its transcript. Cache new scenario IDs on the first iteration so subsequent iterations reuse them. |
| Pasted failures (offline variant) | The validation set is whatever the user re-runs after applying the prompt — Phase 4.5 collects new pasted failures (or zero, if everything passed). Record on iteration 1 which scenarios the user is testing against and ask before letting them silently widen the set. |

The skill tracks **two distinct sets** derived from the table above:

- **Full set** — every scenario in the original input batch (the table column above). Recorded on iteration 1; never changes mid-loop.
- **Failure set** — the subset of the full set that failed in Phase 2 (initial failure analysis) or in the most recent iteration's Step 4.5 re-collection.

**Iteration cadence:** Per iteration (Steps 4.4 → 4.5), run the **failure set only**. This is the cleanest signal that the edit fixed *those specific failures* and keeps iteration latency / cost down. If the failure set is exactly equal to the full set (every scenario failed initially), the two are the same and the distinction is moot until Step 4.6's regression sweep.

**Final regression sweep (Step 4.6):** Once an iteration achieves 100% on the failure set, the skill does NOT exit immediately. Instead it runs the **full set** as a one-shot confirmation pass to catch any regression in scenarios that had been passing all along (e.g., a prompt edit that fixes scenario A but breaks scenario B). The sweep only happens once, on the iteration that hits 100% on the failure set; see Step 4.6 for the exit logic. Skip the sweep when failure set ≡ full set on iteration 1 (no scenarios were previously passing, so there's nothing to regress).

Never widen the failure set or the full set mid-loop without telling the user — the stopping criterion depends on stable comparison sets.

### Step 4.4 — Run validation

Execute the validation set in voice mode for VAPI. Capture `result_id`, poll until terminal (same 30s cadence and 15-min cap as Phase 2.1). For self-hosted / websocket / `file`, the same Cekura-driven execution applies — the validation runs hit the live agent the user just (hopefully) restarted.

In **self-hosted / websocket / `offline` variant**, the skill does not run validation itself. Step 4.4 collapses into "ask the user for the new failure set" — a fresh batch of pasted `{transcript, expected_outcome, verdict}` blocks. Treat zero new failures as a 100% pass.

### Step 4.5 — Re-collect failures with the same Phase 2 logic

Run the new result through Phase 2 end to end — verdict pre-filter (keep `failure` + `reviewed_failure`, drop `success` + `reviewed_success`), accumulate, voice filter, **and re-run Step 2.4 provider-call-state inspection** against the new runs. Re-running Step 2.4 each iteration matters: a Phase 4.1 edit only changes prompts and tool definitions; it cannot change variable injection. If iteration N-1's failures were rooted upstream, iteration N's variable state should look identical — that's the signal the upstream issue is unresolved (and the loop should stop and surface, not iterate further).

In **self-hosted mode**, also watch for the "no-change" signature: if the new failures look identical to the prior iteration's (same scenarios fail with same transcript shapes), the most likely cause is that the live agent didn't pick up the new state — the websocket server wasn't restarted, or (offline variant) the rewritten prompt didn't land in the user's system. Surface this hypothesis explicitly in Step 4.6 before iterating further. Self-hosted / websocket / `offline` is the most prone to this — the user has to apply the rewritten prompt to *their* system manually.

### Step 4.6 — Decide: exit, sweep, or loop

The final exit criterion is **100% pass rate on the full set** (not just the failure set) — zero failures of any class on every scenario the user originally provided. Reaching 100% on the failure set is a necessary but not sufficient milestone; the regression sweep is what closes the loop.

Decision tree, in order:

1. **Failure set < 100%** → loop normally. Feed the new failure summary and the **current (post-edit) prompt** back into Phase 3, surface a fresh proposal, and **wait for explicit approval** before Step 4.1 (in `auto_mode: false`; in auto mode, render and proceed). The failure set may shrink across iterations (some failing scenarios start passing) — track that as progress but stay on the same set; don't drop now-passing scenarios from the in-loop failure set until the sweep, or you lose the ability to detect oscillation.

2. **Failure set = 100% AND a sweep has not yet been run this loop** → **trigger the final regression sweep.**
   - Build the **full set** (every scenario in the original input batch, per the Step 4.3 table).
   - If the full set equals the failure set (no scenarios were initially passing), skip the sweep and treat as case 3 (100% on full).
   - Otherwise: announce the sweep to the user ("All N originally-failing scenarios now pass — running the full M-scenario set as a regression check"), then execute Steps 4.4 → 4.5 once against the full set.
   - On the result:
     - **Full set = 100%** → case 3 (success).
     - **Full set < 100%, the new failures are scenarios that *had* been passing** → case 4 (regression detected). Loop back into Phase 3 with the regression failures as the new failure set; previously-failing-now-fixed scenarios stay in the validation set so the loop catches re-regressions.
     - **Full set < 100%, but the new failures are the same scenarios that just passed in the failure-set-only run** → this is **stochastic flake**. Surface to the user, do not silently re-iterate. Suggest either: (a) re-running the sweep once more to see if it's transient, (b) accepting the flake and exiting if the failing scenarios are known-flaky from prior iterations, or (c) treating as a new failure set and continuing.

3. **Full set = 100%** → success. Report final pass rate, cumulative diff, total iterations used, and which scenarios changed verdict during the loop. Stop.

4. **Regression detected during sweep** → do NOT exit. The new failure set = the scenarios that regressed. Loop back to Phase 3 with the regression failures. Mention explicitly that this iteration's edit broke a previously-passing scenario, so Phase 3 can consider scoping the fix more narrowly (e.g., conditional clauses for the specific failing scenario type rather than blanket prompt-wide changes).

5. **Failure set 100% but every full-set sweep within this loop has already happened and the same scenarios keep flaking** → oscillation territory. Surface and pause; do not burn the iteration cap chasing a flake.

6. **Kept = 0 but total > 0** (failures exist but the voice/channel filter discarded them all) → do **not** exit yet. Work in order: (1) **re-classify with fresh eyes** — a tool error *handled badly* by the agent is a prompt issue; for squads, re-attribute by speaker. (2) **Consider mitigation edits** — both prompt (better retries / fallback / escalation) and tool config (noisy `request-start`, misleading `request-failed`, over-broad `function.description`, wrong handoff destination, self-referencing destination). Surface both as Phase 3 candidates next iteration. (3) Only after both above are exhausted → surface a clear stop with residual failures, hand off to the appropriate skill (`cekura-create-agent` for tool/config issues; backend team for upstream service errors).

**Iteration cap.** Default 10. The user can override with `max_iterations` or stop / extend mid-loop ("keep going" / "stop"). The regression sweep counts as part of the iteration that triggered it (not a separate iteration). Don't loop silently past the cap. After hitting the cap, surface what's been fixed, what's still failing, and a recommended next skill.

For the full PATCH curl bodies, the tool-backup pattern, the loop guardrails (oscillation detection, validation-set stability, cumulative-diff tracking), and the per-iteration scope rules, see [`providers/vapi/phase-4-apply.md`](providers/vapi/phase-4-apply.md) (VAPI specifics; the loop guardrails apply across modes).

## Common Pitfalls

- **Asking the user to redeploy / restart / re-apply before triggering evals in auto mode.** `auto_mode` is on by default and skips BOTH the diff-approval gate AND the user-side deployment pauses. The skill proceeds straight to validation. Don't render "before continuing, redeploy your server" instruction blocks in the default path. If results come back unchanged, surface the no-change hypothesis *after the fact* (Step 4.5 already does this).
- **Exiting on failure-set 100% without running the regression sweep.** A 2/2 pass on the originally-failing subset is a milestone, not the finish line. The exit gate is 100% on the **full set** (every scenario the user originally provided), and the only way to confirm that is to actually run the full set after the failure subset hits 100%. Skipping the sweep masks regressions where an edit fixed scenarios A & B but broke scenario C. Step 4.6's decision tree enforces this — never declare success on failure-set 100% alone.
- **Treating auto mode as fully silent.** Auto mode skips *routine* gates, NOT the skill's responsibility to ask for clarification on genuinely ambiguous inputs or risky decisions. Ambiguous mode resolution (vapi vs. self-hosted), prompt-source ambiguity (which file? which variable?), low-confidence diagnoses, oscillation, no-change signatures, all-upstream failure sets, and metric-quality clusters all require an explicit pause-and-ask.
- **Auto mode masking diagnosis quality.** Without the per-iteration human read on the diff, a bad diagnosis lands silently and shows up only as a failed re-validation. Treat oscillation and no-change signatures as harder stops in auto mode — surface and pause rather than burn the iteration cap.
- **Forcing `auto_mode: false` for routine work.** The diff-approval + deployment-gate pauses are useful when calibrating the skill against a new agent. For repeat use against an agent whose diagnosis quality you've already validated, the default `auto_mode: true` is correct.
- **Proposing tool-config edits in the offline variant.** Only prompt edits are valid there — tool findings must be surfaced as upstream hand-offs, not edits.
- **Proposing VAPI-shaped edits in self-hosted mode.** Spoken `messages` (`request-start`, `request-complete`, `request-failed`), handoff `destinations`, squad `model.toolIds` — none of these exist outside VAPI. Phase 3 must filter these edit candidates out for self-hosted.
- **Treating Cekura's `description` as the source of truth in websocket mode.** It is at best a mirror; the live prompt is in the user's source code. Editing the description does nothing to the live agent unless the user's code reads from it.
- **Reading `llm_system_prompt` from the Cekura agent record in self-hosted mode, or asking the user to paste their prompt.** For `assistant_provider == "self_hosted"`, `llm_system_prompt` is almost always empty — the live prompt lives in the user's workspace (the source file). Do NOT pull `llm_system_prompt` and do NOT ask "paste your current system prompt so I can run improve-prompt against it." Instead, locate the prompt in the workspace: first the IDE-opened file (`ide_opened_file` context), then grep project files for the prompt string constant, and edit it directly via the `Edit` tool. Asking the user to paste is only acceptable in the explicit `offline` variant where no workspace is reachable.
- **Applying `Edit` with a non-unique `old_string` in websocket / `file` variant.** The Edit tool fails on ambiguous matches. Use enough surrounding context (5–10 lines on either side) for every anchor.
- **Hallucinating variable-injection findings without runtime state.** Especially common in the websocket / `offline` variant. Don't claim "the runtime didn't receive `{{accountId}}`" unless the transcript itself shows the placeholder leaking.
- **Shortcutting Step 2.3 by reading result-level summary fields instead of per-run `evaluation_status`.** A `results_retrieve` payload exposes both: per-run `evaluation_status` (post-review, authoritative) AND result-level aggregates (`failed_workflow_runs`, `failed_reasons.issues`, `failed_runs_count`, `success_rate`) computed from raw machine scores **before** human review. The aggregates lump `failure` and `reviewed_success` into the same buckets — using them silently smuggles human-overridden passes into the kept set and produces edits that contradict the reviewer. The four-bucket filter only works when applied to each run's own `evaluation_status`. Same rule for `run_ids` (use per-item verdict) and `call_ids` (use per-log verdict). The Step 2.5 funnel line must cite `per-run evaluation_status` as the source so the skip is auditable.
- **Skipping the variable-state inspection (Step 2.4) and mapping failures only to prompt sections.** Produces phantom prompt fixes for failures actually rooted upstream.
- **Quitting the loop the moment failures look non-prompt.** The exit gate is 100% pass rate or the iteration cap — not "first sight of an infra-shaped failure." Re-classify with fresh eyes before declaring upstream. In websocket / `file` mode, also check whether the failure is a **CodeBug** (history truncation, missing forwarding, broken state) — those are in-scope for editing, not hand-offs.
- **Iterating prompt-wording when the diagnosis is CodeBug.** If oscillation or a no-change signature surfaces and the failure shape matches a CodeBug signal (agent forgets earlier turns, agent ignores explicit don't-re-ask rules despite the prompt being clear, etc.) — stop iterating the prompt. Move to the orchestration-code stream. Repeated prompt-only edits will not converge if the plumbing prevents the agent from following the instructions.
- **Touching business logic, auth code, or dependencies in websocket-mode code edits.** Orchestration-code edits are scoped to plumbing: history management, message wiring, state preservation, keepalive. Tool implementation bodies, API keys / auth code, secrets handling, dependency lists, and framework imports remain out of scope. When in doubt, hand off rather than edit.
- **Proposing code edits in VAPI or websocket `offline`.** The orchestration-code stream exists only for websocket / `file`. In other modes, code-shaped findings become upstream hand-offs — the skill cannot reach VAPI infrastructure code, and the offline variant has no live file to edit.
- **Skipping the per-iteration user gate in `auto_mode: false`.** The skill applies edits to a live agent. Every PATCH / Edit must be preceded by explicit approval of *that iteration's* proposed diff.
- **Skipping the Phase 4.2 sync re-fetch.** VAPI's PATCH semantics replace nested objects wholesale; a malformed body can silently wipe `messages` or `destinations` while returning 200. For websocket / `file`, an `Edit` call with an ambiguous anchor can land in the wrong spot. Always re-read and verify.
- **Editing dynamic-variable placeholders (`{{...}}`).** They're owned by the calling system. Touch them only if the user explicitly asks.
- **Patching a tool's spoken `messages` to mask a prompt issue.** If the agent says the wrong thing, fix the prompt — unless the tool's `request-start` message is itself the offending utterance.
- **Iterating with a noisy metric.** If most kept failures come from one metric whose explanations look subjective, the metric is probably miscalibrated — hand off to `cekura-metric-improvement` first.
- **Surfacing small-sample / overfitting caveats.** Internal calibration of confidence is fine; user-facing hedging reads as a stall.
- **Treating expected-outcome failures and metric failures the same.** Expected-outcome failures are first-class signal about agent behavior; metric failures may reflect either the agent or the metric.
- **Mass-deleting "unused"-looking tools.** A tool with no references in this agent's squad members may still be referenced elsewhere. Prefer reference removal over delete.

## Next Steps

After this skill, the user typically needs:

- For tool / KB / provider-integration issues surfaced in Phase 4.6 → invoke **cekura-create-agent**
- For metric-quality issues (noisy or miscalibrated metric judges) → invoke **cekura-metric-improvement**
- For test-suite gaps (the eval set itself is too narrow) → invoke **cekura-eval-design**
- For metric definition / design questions → invoke **cekura-metric-design**

## Documentation

- Public docs: https://docs.cekura.ai
- Concepts: https://docs.cekura.ai/documentation/key-concepts/
- Integrations: https://docs.cekura.ai/documentation/integrations/
- VAPI assistant API: https://docs.vapi.ai/api-reference/assistants
- VAPI tool API: https://docs.vapi.ai/api-reference/tools

## Directory Layout

```
cekura-self-improving-agent/
├── SKILL.md                                  # this file — top-level flow, mode routing
├── agents/                                   # MCP-agnostic helpers
└── providers/
    ├── vapi/
    │   ├── overview.md                       # VAPI-mode editable surfaces, anti-patterns
    │   ├── phase-1-fetch.md                  # assistant/squad/tool fetch curl bodies, edge cases
    │   └── phase-4-apply.md                  # PATCH/POST/DELETE curl bodies, loop guardrails
    └── self-hosted/
        ├── overview.md                       # self-hosted overview, shared characteristics
        └── websocket.md                      # websocket flavor — file Edit + restart gate; offline variant
└── references/                               # cross-cutting (shared by every mode)
    ├── phase-2-failure-collection.md         # failure summary template, metric hand-off
    ├── phase-3-diagnosis.md                  # classification table, before/after templates
    └── dynamic-variables-debugging.md        # variable-state per-signal decision tree
```

### Reference Files (loaded on demand)

- **[`providers/vapi/overview.md`](providers/vapi/overview.md)** — VAPI editable surfaces, what's PATCHable directly, anti-patterns.
- **[`providers/vapi/phase-1-fetch.md`](providers/vapi/phase-1-fetch.md)** — Provider-gate error message shapes, VAPI assistant + squad + tool fetch curl bodies, member summary template, Phase 1 edge cases.
- **[`providers/vapi/phase-4-apply.md`](providers/vapi/phase-4-apply.md)** — VAPI PATCH / POST / DELETE curl bodies, tool-backup pattern, validation-set construction, loop guardrails, iteration-cap exit messaging.
- **[`providers/self-hosted/overview.md`](providers/self-hosted/overview.md)** — Self-hosted overview, shared characteristics, redeploy command flow.
- **[`providers/self-hosted/websocket.md`](providers/self-hosted/websocket.md)** — Websocket flavor gate, source-file discovery, `Edit`-based apply path, restart-server gate, pasted-prompt / pasted-failures degenerate `offline` variant, websocket-specific edge cases.
- **[`references/phase-2-failure-collection.md`](references/phase-2-failure-collection.md)** — Full failure-summary template, the metric-improvement hand-off wording, edge cases (no failures / all-errored / mixed inputs), and the no-overfitting-caveats rule.
- **[`references/phase-3-diagnosis.md`](references/phase-3-diagnosis.md)** — Full classification table with examples, before/after templates per edit surface, tool-edit anti-patterns, the manual-vs-automated-improver guidance, Phase 3 anti-patterns.
- **[`references/dynamic-variables-debugging.md`](references/dynamic-variables-debugging.md)** — Per-signal decision tree for variable state, where each signal lives in the Cekura payload, the direct-VAPI fallback, the `runs_bulk_retrieve` bare-string gotcha, squad per-member-message caveats.

---
name: cekura-flag-call-logs
description: |
  Triage the last N production call logs for a Cekura agent and flag the
  ones that match specified issues or goals — then report just the flagged
  calls with verbatim evidence. Use when the user says "flag call logs",
  "analyze the last N calls for issues", "which recent calls had <problem>",
  "find calls where the agent <did X>", "triage prod calls", "go through
  recent call logs and tell me which ones broke", "find failing calls", or
  pastes an agent ID / project ID and lists the problems to look for. Pulls
  recent call logs, evaluates each against the user's issues/goals (or, if
  none given, against the agent's intended behavior), applies attribution
  rules so caller-side endings and recovered calls are NOT flagged, and
  emits a flagged-calls list. This is the upstream triage step that feeds
  `cekura-internal:generate-scenarios` — it does NOT create scenarios.
argument-hint: "<agent_id | project_id | dashboard URL> [issues/goals to flag]"
allowed-tools:
  - AskUserQuestion
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Skill
version: 0.1.0
---

# flag-call-logs

Go through an agent's recent **production call logs** and surface the ones that hit a specified issue or miss a specified goal. The output is a short, evidence-backed list of **flagged call log IDs** — nothing more. It is the triage front-end: once you have the flagged set, hand it to `cekura-internal:generate-scenarios` to build evaluators, or to the user for review.

This skill is **strictly read-only** — it never creates, updates, or deletes anything. It only reads call logs.

The single most important job here is **attribution**: flag a call only when the *agent under test* is responsible for the issue. Caller-side endings, simulated-caller disconnects, and calls the agent recovered from are noise in an agent-quality report — they must NOT be flagged.

---

## Step 0 — Prerequisites

Reads through the Cekura MCP. Confirm these are present:

- `mcp__cekura__aiagents_retrieve` — agent description + intended behavior (defines what counts as a failure when the user gives no explicit issue list)
- `mcp__cekura__call_logs_list` — paginated production call list filtered to the agent
- `mcp__cekura__call_logs_retrieve` — transcript, metric evaluations, `ended_reason` per call
- (optional) `mcp__cekura__metrics_list` — to see which metrics already grade the behaviors in question

If the `mcp__cekura__*` tools aren't connected, stop and tell the user to connect the Cekura MCP — don't fall back to DB queries.

---

## Step 1 — Inputs

Use `AskUserQuestion` for anything not already supplied:

1. **Agent ID** (numeric, e.g. `15290`). If unknown, `mcp__cekura__aiagents_list` helps find it.
2. (Optional) **Project ID**, if the user manages multiple projects.
3. **Window** — how many recent calls (default: last **50**) or a date/incident range.
4. **Issues / goals to flag against** — the heart of the request. One of:
   - **Explicit issues** the user names — e.g. *"calls that ended before all vetting questions were asked"*, *"the agent looped on an unclear answer"*, *"background noise stopped the agent from responding"*. Treat each as a separate flag bucket.
   - **A goal** stated positively — e.g. *"every call should fully vet the candidate"* — which you invert into "flag calls that fail this goal."
   - **Nothing specific** → fall back to *"any genuine agent failure,"* grounded in the agent's `agent_description` (Step 2). In this mode, classify against the **failure-mode taxonomy** below.

Echo the issue list back so the user can confirm the flag criteria before you grind through 50 transcripts.

---

## Step 2 — Fetch agent context + call logs

Run in parallel.

**Agent context** — `mcp__cekura__aiagents_retrieve(id=<agent_id>)`. Capture `agent_description` (intended behavior — the yardstick for "is this a failure"), `agent_name`, `project_id`, and any dynamic-variable names referenced as `{{var}}` (some issues, like "all vetting questions asked", are defined by per-call dynamic variables such as `questionsToVet`).

> ⚠️ If `agent_description` is empty/placeholder AND the user gave no explicit issue list, STOP — "failure" is ungrounded. Ask the user to either name the issues to flag or flesh out the description.

**Call logs** — `mcp__cekura__call_logs_list` filtered to the agent, sorted descending by `created_at`, page size = the window. Per row capture `id`, `created_at`, `duration`, `ended_reason`/`call_ended_reason`, any rolled-up metric pass/fail, and `transcript`/`transcript_object`. If the list view lacks transcripts or metric detail, fetch `mcp__cekura__call_logs_retrieve(id=...)` **in parallel for the candidates only** — don't pull every transcript if the list already tells you which calls are clean.

If `call_logs_list` returns 0, stop and tell the user (pre-production agent — no prod signal to triage).

---

## Step 3 — Evaluate each call against the issues/goals

For each call, decide **flag** or **no-flag**. When flagged, record:

```
{ call_log_id, issue, severity, evidence_quote, ended_reason, expected_behavior }
```

- `issue` — which user-specified issue (or failure mode) it hit.
- `evidence_quote` — **verbatim** transcript slice (or the failing metric justification). No paraphrasing. If you can't quote it, it isn't a flag.
- `expected_behavior` — one sentence on what the agent should have done, grounded in `agent_description` / the stated goal. (Carries downstream into a scenario's `expected_outcome_prompt`.)

When the issue list is explicit, match against exactly those. When in "any genuine failure" mode, classify against this taxonomy:

| Code | Mode | Detection signals |
|---|---|---|
| 🛑 `drop` | Call dropped / ended early **by the agent** | agent ended/transferred mid-workflow; `ended_reason` shows an agent-side disconnect; transcript ends mid-step with the agent at fault |
| 🌀 `drift` | Agent went off-task / off-persona | content unrelated to `agent_description`; answered outside declared scope |
| 👻 `hallucination` | Agent stated facts not in KB/description | numbers, policies, products absent from the description/KB |
| 🔧 `tool_error` | Tool selection / args / post-tool handling broke | tool error response; agent re-asks something a successful tool already answered; wrong tool fired |
| 🎯 `workflow_miss` | Required step skipped or wrong | quoted a balance without verifying; skipped consent; **concluded before asking all required questions** |
| 🤔 `comprehension` | Agent misunderstood the caller | agent re-asks the same clarifying question 3+ times; loops on an unclear answer with no recovery |
| 🔁 `loop` | Agent stuck repeating without converging | same question/confirmation repeated many times; runaway invented questions; never progresses |
| 🚪 `refusal` | Agent refused a legitimate, in-scope ask | "I can't help with that" for something inside its description |
| ⚡ `latency`/`responsiveness` | Long response gaps / didn't respond promptly | long inter-turn gaps in timestamps; agent slow/unresponsive after the caller finished |
| 🧨 `safety` | PII leak / unsafe content | repeated back SSN/card unprompted; disallowed content |

A call can hit multiple issues — record each separately.

---

## Step 3.5 — Attribution & recovery rules (the part that prevents false flags)

**Flag a call ONLY when the agent under test caused the issue.** Apply these filters before flagging — they are the difference between a useful report and noise:

1. **Caller-side / simulated-caller endings are NOT a flag.** If the candidate/caller/testing agent hung up or disconnected (`ended_reason` ∈ {`testing-agent-ended-call`, `customer-ended-call`, `Client disconnected: 1005/1012`, caller-ended}) before the agent could finish, the agent did nothing wrong. This is the most common false positive on "call ended before all X" issues — the caller bailed, not the agent. Exclude it.
2. **Recovery = no flag.** If the agent hit a rough patch but **eventually got what it needed and continued the workflow**, don't flag it. Examples to exclude: the caller's answer came through as "…" / garbled a couple of times but the agent re-prompted and the caller eventually answered and it moved on; the agent re-asked one question once after a non-answer, got the answer, and proceeded. Only flag when the agent **stays stuck / cannot recover / the call derails** — the same question many times with no escape, the call ends inside the loop, or it never progresses.
3. **Legitimate early exits are NOT a flag.** The agent correctly stopping because the caller declined, failed a hard requirement / disqualifying answer, or asked for a callback — and following its workflow for that branch — is correct behavior. A graceful end after completing the required steps is also fine.
4. **Agent interrupting / cutting off the user is NOT flagged by default.** Talking over a caller's late "actually, I have a question" and wrapping up is generally not a defect — only flag it if the user explicitly lists "agent interrupting the user" as an issue to look for.

These are general agent-quality triage rules; if the user's explicit issue list contradicts a default (e.g. they *do* want caller-ended drops flagged), follow the user.

---

## Step 4 — Report (flagged calls only)

**Report ONLY the flagged calls. Do NOT list the clean / excluded / complete calls.** Listing every reviewed call buries the signal — the user asked which calls have the problem, not a roster of all calls.

```markdown
# Flagged call logs — <agent_name> (`<agent_id>`)

**Window:** last <N> calls (<start> → <end>) · **Reviewed:** <N> · **Flagged:** <K>
**Flag criteria:** <the confirmed issue/goal list>

| Call | Issue | Evidence (verbatim) | ended_reason | Sev |
|---|---|---|---|---|
| [<id>](https://dashboard.cekura.ai/<project>/observe/<id>) | concluded before all vetting questions | "Thanks for your time, we'll be in touch" — asked 7 of 11 | main-agent-ended-call | high |
| [<id>](https://dashboard.cekura.ai/<project>/observe/<id>) | loop on unclear answer | re-asked "which shift?" ×6, never converged | — | high |

## Excluded (counts only, with reason)
- 12 caller/testing-agent ended before the agent could finish
- 5 recovered (agent re-prompted and proceeded)
- 3 legitimate early exit (declined / failed hard requirement)
```

Rules:
- Every call reference is a markdown link to `https://dashboard.cekura.ai/<project>/observe/<id>`.
- Evidence is a **verbatim** quote — never paraphrase the agent/caller words (a short annotation like "asked 7 of 11" alongside the quote is fine).
- The **Excluded** section is counts + reason buckets only — never an enumerated list of clean call IDs. It exists so the user trusts the triage was thorough, not to dump data.
- Direct, evidence-led tone. No hedging.

---

## Step 5 — Handoff

After the report, offer the next step:

> Flagged <K> calls. Want me to turn these into regression scenarios? I can hand this flagged set to `cekura-internal:generate-scenarios`, which clusters them and builds one evaluator per failure pattern.

If the user says yes, invoke `cekura-internal:generate-scenarios` and pass the flagged set as input — each entry carries `{call_log_id, issue/mode, severity, evidence_quote, expected_behavior}`, which is exactly the per-call failure record that skill expects (it skips its own mining and goes straight to clustering + construction). Do not re-triage in that skill.

---

## When to stop / redirect

- **Single call, already known.** If the user points at one specific call ID and wants a scenario from it, this triage step is unnecessary — go straight to `cekura-internal:generate-scenarios` (single-call fast path).
- **Debugging why one run failed** (telephony, didn't connect, SIP, empty transcript) → `cekura-internal:debug-run`, not this skill.
- **No prod call logs** (pre-production agent) → stop; there's nothing to triage.

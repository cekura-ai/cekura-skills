---
name: cekura-flag-call-log-failures
description: |
  Triage the last N production call logs for a Cekura agent against a set of
  KPIs / issues / goals, report the call IDs that hit each failure WITH the
  percentage of overall call logs affected, and distribute the remaining
  calls into a mutually-exclusive outcome taxonomy (e.g. not-answered /
  vetted / non-vetted caller-side / non-vetted agent-issue) with per-bucket
  percentages. Use when the user says "flag call log failures", "analyze the
  last N calls for issues", "what % of calls have <problem>", "which calls
  broke and how often", "find failing calls", "give me the breakdown of call
  outcomes", "what % of answered calls can be improved", or pastes an agent /
  project ID and lists the problems or KPIs to measure. Applies attribution
  rules so caller-side endings and recovered calls are NOT counted as agent
  failures. This is the upstream triage step that feeds
  `cekura-generate-scenarios` — it does NOT create scenarios.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
allowed-tools: AskUserQuestion Bash Read Write Edit Grep Glob Skill
metadata:
  author: cekura
  version: "0.3.0"
---

# flag-call-log-failures

Go through an agent's recent **production call logs** and produce three things:

1. **Flagged calls** — the call IDs that hit each specified KPI/issue/goal failure, with verbatim evidence.
2. **Failure rates** — what **percentage of all reviewed call logs** each failure represents.
3. **Outcome distribution** — every remaining call bucketed into a **mutually-exclusive outcome taxonomy** (e.g. *not-answered / vetted / non-vetted caller-side / non-vetted agent-issue*), with per-bucket percentages, so the flagged failures are framed against the whole population.

It is the triage front-end: hand the flagged set to `cekura-generate-scenarios` to build evaluators, or give the user the distribution for a customer-facing quality report.

This skill is **strictly read-only** — it never creates, updates, or deletes anything.

The single most important job is **attribution**: a call is an *agent* failure only when the agent under test caused it. Caller-side endings, simulated-caller disconnects, and recovered calls must NOT be counted as agent failures — they belong in their own buckets.

---

## Step 0 — Prerequisites

Reads through the Cekura MCP. Confirm these are present:

- `mcp__cekura__aiagents_retrieve` — agent description + intended behavior (the yardstick for "failure")
- `mcp__cekura__call_logs_list` — paginated production call list (lightweight: usually has `id`, `duration`, `call_ended_reason`, `success`, rolled-up metric scores — but often **no transcript**)
- `mcp__cekura__call_logs_retrieve` — full transcript + metric evaluations for a single call
- `mcp__cekura__metrics_list` — to find metrics that already grade the KPIs/issues (reuse these as the classification basis when they exist)

If the `mcp__cekura__*` tools aren't connected, stop and tell the user to connect the Cekura MCP (see `/setup-mcp` or https://docs.cekura.ai/mcp/overview).

---

## Step 1 — Inputs

Use `AskUserQuestion` for anything not supplied:

1. **Agent ID** (numeric). If unknown, `mcp__cekura__aiagents_list` helps find it.
2. (Optional) **Project ID**.
3. **Window** — how many recent calls (default **100**) or a date range. Process in **batches** (see Step 2).
4. **KPIs / issues / goals to measure** — the heart of the request:
   - **Explicit issues** — e.g. *"calls that ended before all vetting questions"*, *"agent looped on an unclear answer"*, *"background noise stalled the agent"*. Each becomes a flag bucket + a failure-rate number.
   - **A KPI / goal** — e.g. *"every call should fully vet the candidate"*, *"what % of answered calls can we improve"* — which you invert into the failure(s) that break it.
   - **Nothing specific** → *"any genuine agent failure,"* grounded in `agent_description`, classified against the **failure-mode taxonomy** in Step 3.
5. **Outcome taxonomy** — the mutually-exclusive buckets to distribute ALL calls into. Derive these from the agent's job. For a candidate-vetting agent the natural set is:
   - `not answered` · `vetted` · `non-vetted — caller-side` · `non-vetted — agent/system issue`

   For other agents, adapt (e.g. `resolved / escalated / abandoned / agent-error`). Confirm the bucket set with the user before reporting.

Echo the issue list **and** the bucket set back so the user confirms before you grind through the window.

---

## Step 2 — Fetch in batches, classify cheap-first

**Agent context** — `mcp__cekura__aiagents_retrieve(id=...)`: capture `agent_description`, `agent_name`, `project_id`, and any `{{dynamic_variable}}` names that define a KPI (e.g. `requiredScreeningQuestions`).

> ⚠️ If `agent_description` is empty/placeholder AND no explicit issue list was given, STOP — "failure" is ungrounded. Ask the user to name the issues or flesh out the description.

**Call logs — loop in batches.** `mcp__cekura__call_logs_list` with `page_size=20`, walking `page=1..K` until you've covered the window. The list view is lightweight, so collect the cheap signal for **every** call first:

| Field | Used for |
|---|---|
| `id`, `duration` | identity, length-based heuristics |
| `call_ended_reason` | who/what ended the call (the strongest first-pass signal) |
| `success` / `status` | rolled-up pass/fail |
| `metrics[]` scores | if your KPI metrics already ran (see below), read the score directly |

**Cheap first pass (heuristic) → then verify only the candidates.** Pulling every transcript is wasteful and can blow the token budget. Instead:

1. **Bucket by `call_ended_reason` + `duration` first.** Strong proxies:
   - very short (e.g. `< 25s`) → **not answered / no engagement**
   - agent-ended (`Main agent-ended-call`) at normal length → agent **completed its flow** (provisionally *vetted*)
   - caller/testing-agent-ended (`testing-agent-ended-call`, `customer-ended-call`, `Client disconnected`) → **caller-side** (provisionally)
   - silence/timeout (`Ending conversation after N seconds of silence`) → **agent/system candidate** (verify)
2. **Transcript-verify ONLY the agent-issue candidates** — silence-timeouts, abnormally long calls, and anything the heuristic can't place. Pull these with `call_logs_retrieve` (they overflow to a file when large — parse with a script for loop/repeat detection rather than reading inline).
3. **`long call ≠ loop`.** A long call is NOT automatically an agent failure — verify before counting it. Check for an actually-repeated question (same normalized agent line ≥4×) or a runaway invented-question pattern. Many long calls are just thorough vetting (≈1:1 agent/candidate turns, no repeat).

**Prefer the metrics we already built** as the classification basis when they're attached to the agent/project — they encode the exact attribution rules:
- `Call not answered (no pickup / voicemail)` → defines the **not-answered** bucket (TRUE = not answered).
- `All vetting questions asked (perf)` → vetting **completion** on eligible calls (PASS = vetted).
- `Testing agent ended call before hard vetting started` → caller-side **early drop** (TRUE).
- `All vetting questions asked` (failure-flag) → agent **skipped** questions.

If those metrics haven't been evaluated on the window yet, you can either trigger them (`call_logs_evaluate_metrics_create` — costs eval credits, async) for an audited number, or classify by transcript/heuristic and report the result as an **estimate** (state which).

If `call_logs_list` returns 0, stop — pre-production agent, nothing to triage.

---

## Step 3 — Classify each call

For each call, decide its **outcome bucket** (mutually exclusive) and, if it's an agent failure, **which issue/mode**. When flagged as a failure, record:

```
{ call_log_id, issue/mode, severity, evidence_quote, ended_reason, expected_behavior }
```

- `evidence_quote` — **verbatim** transcript slice (or failing metric justification). No paraphrasing; if you can't quote it, it isn't a flag.
- `expected_behavior` — one sentence on what the agent should have done (carries into a scenario's `expected_outcome_prompt`).

"Any genuine failure" taxonomy (when no explicit issue list):

| Code | Mode | Detection signals |
|---|---|---|
| 🛑 `drop` | Ended early **by the agent** | agent ended/transferred mid-workflow; agent-side disconnect |
| 🌀 `drift` | Off-task / off-persona | content unrelated to `agent_description` |
| 👻 `hallucination` | Facts not in KB/description | numbers/policies/products absent from the description/KB |
| 🔧 `tool_error` | Tool selection/args/post-tool broke | tool error; re-asks something a tool already answered; wrong tool |
| 🎯 `workflow_miss` | Required step skipped/wrong | concluded before asking all required questions; skipped consent |
| 🤔 `comprehension` | Misunderstood caller | re-asks same clarifying question 3+ times; loops with no recovery |
| 🔁 `loop` | Stuck repeating, never converges | same question/confirmation many times; runaway invented questions |
| 🚪 `refusal` | Refused a legitimate, in-scope ask | "I can't help with that" inside its description |
| ⚡ `latency` | Long gaps / slow / unresponsive | long inter-turn gaps; no response after caller finished |
| 🧨 `safety` | PII leak / unsafe content | repeated back SSN/card unprompted; disallowed content |
| 📻 `asr_capture` | Candidate spoke but wasn't captured | candidate turns register as "…"; agent re-prompts "are you still there?" → silence-timeout (system/ASR class, improvable but not a prompt bug — call it out distinctly) |

A call can hit multiple issues — record each. But it lands in exactly **one** outcome bucket.

---

## Step 3.5 — Attribution & recovery rules (prevents false failures)

**Count a call as an agent failure ONLY when the agent under test caused it.** Otherwise it goes in a non-agent bucket.

1. **Caller-side / simulated-caller endings are NOT an agent failure.** `call_ended_reason` ∈ {`testing-agent-ended-call`, `customer-ended-call`, `Client disconnected: 1005/1012`} before the agent could finish → **non-vetted caller-side**, not agent.
2. **Recovery = not a failure.** If the agent hit a rough patch but **got what it needed and continued**, don't flag it. Only flag when it **stays stuck / cannot recover / the call derails**.
3. **Legitimate early exits are NOT a failure.** Correctly stopping because the candidate declined, failed a hard requirement, or asked for a callback is correct behavior → counts as a clean / legitimate outcome, not an agent failure.
4. **Agent interrupting / cutting off the user is NOT flagged by default** — only if the user explicitly lists it.

If the user's explicit issue list contradicts a default (e.g. they *do* want caller drops counted), follow the user.

---

## Step 4 — Quantify + distribute

Two computations over the full reviewed set (let `N` = total reviewed):

**A. Failure rates.** For each flagged issue: `count / N` = % of overall call logs with that failure. If the user framed it as "% of *answered* calls," compute against the answered denominator instead (answered = `N − not_answered`, where not-answered is the `Call not answered` bucket). State the denominator explicitly.

**B. Outcome distribution.** Assign every call to exactly one bucket and report counts + %:

```
not answered            : a/N
vetted                  : b/N   (= b/answered)
non-vetted caller-side  : c/N   (= c/answered)
non-vetted agent/system : d/N   (= d/answered)   ← the improvable slice
```

Sub-split a bucket when it's useful (the agent/system slice often splits into e.g. `ASR-capture` vs `true agent loop`; the caller-side slice into `dropped before vetting began` vs `dropped mid-vetting` — the latter maps to the `Testing agent ended before hard vetting started` metric).

**Headline the improvable number:** *"X% of answered calls are improvable on our side"* (the agent/system bucket), and note how much of the non-vetted total is caller-side (not an agent defect).

---

## Step 5 — Report

```markdown
# Call-log failure analysis — <agent_name> (`<agent_id>`)

**Window:** last <N> calls (<start> → <end>) · **Answered:** <A>
**Criteria:** <the confirmed KPI/issue list>

## Outcome distribution
| Bucket | Count | % of all | % of answered |
|---|---|---|---|
| Not answered | a | a/N | — |
| Vetted | b | b/N | b/A |
| Non-vetted — caller-side | c | c/N | c/A |
| Non-vetted — agent/system (improvable) | d | d/N | d/A |

→ **~d/A% of answered calls are improvable on our side.** (Caller-side = c/A%, not an agent defect.)

## Flagged failures (agent/system) — call IDs + rate
| Issue | Rate (of all) | Calls (evidence) |
|---|---|---|
| ASR capture → silence drop | 6/N | [<id>](…) "are you still there?" ×N → timeout; … |
| Loop | 1/N | [<id>](…) re-asked "which shift?" ×6 |

## Methodology & confidence
- Which calls were transcript-verified vs. heuristic-bucketed (ended_reason + duration).
- If the agent/system count is a lower bound (issues hidden inside agent-ended/caller-ended calls weren't all read), say so.
- Whether numbers are audited (metrics evaluated) or estimated (heuristic).
```

Rules:
- Every call reference is a markdown link to `https://dashboard.cekura.ai/<project>/observe/<id>`.
- Evidence is a **verbatim** quote (a short annotation like "asked 7 of 11" alongside is fine).
- List the flagged agent/system calls explicitly; for the large clean buckets, give **counts only**, never an enumerated roster of clean IDs.
- Direct, evidence-led tone. State the denominator behind every percentage.

---

## Step 6 — Handoff

> Flagged <d> agent/system calls (<d/A>% of answered). Want me to turn these into regression scenarios? I can hand the flagged set to `cekura-generate-scenarios`, which clusters them and builds one evaluator per failure pattern.

If yes, invoke `cekura-generate-scenarios` and pass the flagged set — each entry already carries `{call_log_id, issue/mode, severity, evidence_quote, expected_behavior}`, exactly the per-call record it expects (it skips its own mining and goes straight to clustering). Don't re-triage there.

---

## When to stop / redirect

- **Single known call → a scenario:** skip triage, go straight to `cekura-generate-scenarios` (single-call fast path).
- **Why did one run fail** (telephony, didn't connect, SIP, empty transcript) → that's run debugging, not call-log triage; investigate the run's telephony/agent configuration or contact Cekura support.
- **No prod call logs** (pre-production agent) → stop; nothing to triage.

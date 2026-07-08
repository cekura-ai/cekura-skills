---
name: cekura-metric-builder
description: >
  Use when the user asks to "build a metric by testing it on real calls",
  "run my draft metric and find edge cases", "figure out what my metric should do
  in edge cases", "help me nail down a metric against real data", "turn my metric
  idea into a tested definition", or wants to refine a metric conversationally
  from an intent rather than hand-writing the whole prompt. Covers the
  grounded build loop: draft → run on real calls/runs → surface edge cases →
  resolve the clear ones automatically → ask only on genuine ambiguity → create.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Metric Builder (grounded, conversational)

## Purpose

Turn a plain-language metric intent into a tested, edge-case-aware metric by
**running it on real calls and runs first**, then resolving what's ambiguous —
instead of hand-writing a long prompt up front and discovering the gaps later.
Most edge cases you resolve automatically from the data; you only ask the user
when the correct verdict depends on a policy they haven't stated.

Use this when the user has a rough idea ("did the agent resolve the issue?") and
wants it turned into a solid definition. For metric-writing *principles* and
prompt structures, see **cekura-metric-design**; for the labs feedback loop on an
already-deployed metric, see **cekura-metric-improvement**.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## Core Terminology

- **Main agent**: the client's AI voice agent being evaluated.
- **Testing agent**: Cekura's simulated caller (in runs) — the "user" side.
- **Call**: a production call log (observability). **Run**: a simulation run.
- **Metric**: a post-call evaluation that scores a transcript (LLM-judge prompt
  or custom Python code).

## The Build Loop

Follow these steps in order. The whole point is that steps 2–4 are driven by
**real data**, not guesswork.

### 0. Pick the scope

Ask once (default **both**, so this is usually just a confirmation):

> Should this metric apply to **calls** (production), **runs** (simulations), or **both**?

A metric meant only for production calls or only for simulation runs should
sample just that source — it changes which transcripts drive the edge cases.

### 1. Draft and clean the definition

Take the user's intent and write a first draft that:
- refers to the agent under test as the **main agent** and the caller as the
  **testing agent**;
- **preserves every `{{variable}}`** the user included (never drop them);
- states explicitly what **success** and **failure** look like.

Keep it tight — this is a starting point, not the final artifact.

### 2. Run the draft on a sample of real calls + runs

Pull ~25 recent calls and ~25 recent runs for the agent (respecting the scope)
that have transcripts, and evaluate the draft metric against each to get a
**prediction + explanation per item**. There are no ground-truth labels yet —
you are looking at what the metric *currently* decides so you can spot where it's
wrong, uncertain, or silent.

Prefer the platform's preview/evaluate tooling so the predictions match how the
metric will behave once deployed. Evaluate every sampled item (no relevance
gate) so nothing is filtered out.

### 3. Read the results and find edge cases

Scan the predictions for **edge cases** — items where the verdict is wrong,
borderline, or where the transcript hit a situation the definition never
addressed:

- caller hangs up early / voicemail / transfer
- partial completion (agent did most of it, missed one sub-step)
- off-topic or wrong-agent transcripts (a different bot answered)
- garbled / broken agent output
- promise-to-pay / "I'll call back" / scheduled follow-up
- the metric's own assumptions being violated

### 4. Resolve — automatically where you can, ask only where you can't

For each edge case:

- **Resolve it yourself** when the correct verdict is objectively clear from the
  agent's purpose. Tighten the definition to handle it and note the rule. **Most
  edge cases should be resolved this way.**
- **Ask the user** only when the correct verdict depends on a **policy they
  haven't stated** and you cannot infer — or when two defensible readings of the
  intent disagree. "Hard but decidable" is not ambiguous; decide it.

When you do ask, keep it scannable (this is the difference between a helpful
assistant and a tedious form):

- Ask **at most ~3** questions; each is **one short sentence** stating only the
  decision — no evidence dump.
- Offer **2–4 concrete options**, and mark the one you'd **recommend**.
- Point at **1–3 specific example calls/runs** from the sample so the user can
  open the actual transcript and decide.
- Let the user pick an option **or** type their own answer.

### 5. Fold answers in and converge

Apply the user's answers as explicit rules in the definition, re-check the
affected items, and repeat only if a genuinely new ambiguity appears. Stop as
soon as nothing ambiguous remains — don't chase 100%.

### 6. Create the metric (user reviews first)

Present the final definition (a diff against the draft reads best) plus a short
summary of the edge cases you handled. The user reviews and creates it — don't
auto-create. On create, wire the scope you chose in step 0 (calls / runs / both).

## LLM-judge vs custom code

- **LLM-judge (default):** the whole loop operates on the natural-language
  `description`. Express the rules in prose; an LLM reading the transcript handles
  messy timing and phrasing better than brittle code. This is the well-trodden path.
- **Custom code (Python):** edit the code with **minimal, surgical changes** that
  fix the specific edge case — keep it valid, runnable code in the same style;
  do not rewrite it as an LLM-judge description. Note that testing a code change
  means re-running it on the sample, so plan an extra pass.

## Common Pitfalls

- **Writing the whole prompt before looking at data.** The point of this skill is
  the opposite — draft small, run it, let real edge cases drive the detail.
- **Asking the user about everything.** If it's decidable from the agent's
  purpose, decide it. Over-asking recreates the tedious manual loop.
- **Long, narrated questions.** One sentence + options + an example link. Not a paragraph.
- **Dropping `{{variables}}`** during cleanup. Always preserve them.
- **All-PASS or all-FAIL sample.** If every sampled item lands the same way, the
  signal is weak — widen the sample or revisit the definition before trusting it.
- **Auto-creating.** Always let the user review the final definition first.

## Next Steps

- For metric-writing principles, prompt structures, and VALID_SKIP patterns → **cekura-metric-design**
- To refine an already-deployed metric from result feedback (labs) → **cekura-metric-improvement**
- To build the evaluators/scenarios that generate runs → **cekura-eval-design**

## Documentation

- Public docs: https://docs.cekura.ai
- Metrics concepts: https://docs.cekura.ai/documentation/key-concepts/metrics/overview

## Additional Resources

### Example Files (illustrative, read only when relevant)

- **`examples/resolve-issue-metric.md`** — a worked build of "did the agent
  resolve the caller's issue?" showing which edge cases were auto-resolved vs
  surfaced as questions.

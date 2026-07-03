# Overfitting Gate Phase — Scrub the Just-Applied Edits

Sits between Optimization ([`optimization/apply.md`](optimization/apply.md) + [`optimization/sync.md`](optimization/sync.md) just landed and verified the edit set) and [`eval.md`](eval.md). Re-reads those edits, scores them against five overfitting signatures, and emits cleanup edits that generalize or strip the overfit material before validation.

The gate exists because the fix sub-phases read failing transcripts, and that exposure leaks into proposals — an LLM often writes the failing utterance verbatim into the prompt as the trigger, turning a generic instruction into a string-match against one transcript. That fixes the seen failure but won't generalize. Early-end-call fix is especially prone (it inspects farewell phrasing). The gate is a **no-op pass-through when nothing is detected** — the typical case after a few iterations. Cost: one re-read + a short judgment pass; no extra apply round-trip unless cleanup is needed.

## Pre-flight check

Confirm Optimization completed cleanly this iteration:

- Edits applied (APPLY.1) AND sync confirmed (SYNC.1), OR — render-only (no live target) — the rewrite was rendered and the user asked for new pasted failures.
- The iteration's edit set is known (fields/files/sections changed + old/new text), handed up from [`optimization/sync.md`](optimization/sync.md). Includes both the FIX.1 early-end edits and the FIX.5 fix edits ([`optimization/fix.md`](optimization/fix.md)).
- The iteration's failure summary is available (source failures + failing transcripts from [`collect.md`](collect.md)) — needed to score "did this edit copy the failing utterance verbatim?".

If any is missing, return to the orchestrator — Optimization did not complete cleanly. **Skip the gate entirely** when the iteration produced zero edits (all-Upstream / kept = 0).

## The five overfitting signatures

Score each Optimization edit against these; any match makes the edit a cleanup candidate.

| Signature | What it looks like | Why it overfits |
|-----------|--------------------|-----------------|
| **Verbatim transcript quote** | A phrase added to the prompt that appears word-for-word in a failing transcript ("If the user says 'I need a refund right now', then…"). **Also flag paraphrases where only proper nouns were genericized but the syntactic frame is lifted** — e.g. transcript "I said *Delhi* earlier but we are actually in *Gurugram*" → edit example "I said *one city* earlier but we are actually in *a different city*": nouns generalized, but "earlier but we are actually" is verbatim. Check: replace every proper noun / number / date in the edit's example with a placeholder, then search failing transcripts for any ≥4-word contiguous substring of the remaining frame. A hit = flag. | Future calls phrase the same intent differently ("want my money back"); a string-match rule won't fire. Replacing only identifiers doesn't defuse it — the frame is the leak. |
| **Scenario-specific identifier** | A scenario name/ID, test-profile name, or run ID in the prompt or tool description ("For scenario `test_billing_v2`, do X"). | Test artifacts. The agent can't know which scenario it's in at runtime — dead text at best, confusing at worst. |
| **Test-data value hardcoded** | A concrete value from the failing run baked in as a literal (account #, customer name, dollar amount, date: "if the customer mentions account #4827361…"). | Real users won't say "account #4827361" — a fingerprint of the test data, not a behavioral rule. |
| **Hyper-narrow case clause** | A clause so specific it matches one transcript shape — many `AND`s, exact step counts, exact wordings ("If refund policy AND order > 6 months old AND they say 'pre-paid' THEN…"). | Won't generalize across the cluster; production traffic won't hit the exact conjunction. |
| **Transcript-cloned few-shot example** | A "for example, …" block whose dialog is a recognizable paraphrase (or copy) of a failing transcript. | Steers the model to memorize one trajectory. Fine if the example is *constructed* to illustrate the rule; harmful if it leaks the test set. |

**NOT flagged:**
- **General rule + LLM-constructed example** — e.g. "When the user mentions a billing issue, verify the account is active first." Leave only when BOTH: (a) the example reads as a plausible LLM-constructed illustration, AND (b) it passes the verbatim-quote check above (placeholder-swap, then no ≥4-word frame substring in any failing transcript). If (a) but not (b), it's still a transcript clone — flag it.
- **Tool-schema specificity** — narrowing a param `enum`, tightening a `description` with concrete units. Desirable, not overfitting.
- **A missing step added** — Gap fix "ask for the order date before quoting return policy" is general even if the failing scenario was about order dates.
- **Orchestration-code edits** (self-hosted owned source, incl. forked/vendored SDK in the tree) — scored by code correctness, not this lens. Note: the FIX.1 early-end triage may emit BOTH a prompt edit AND a code edit for one cluster — score the prompt edit, skip the code one. **But embedded prompt string literals inside source ARE scored** (a system-prompt string in a `.py`/`.ts` file is a prompt surface, not control flow).

When in doubt, **flag but propose REVISE, not STRIP** — generalizing a borderline edit is cheap; stripping a useful fix is expensive.

## Step GATE.1 — Inventory the iteration's edits

Pull this iteration's diff (generic surfaces; provider detail differs only in where the field lives):

- **Prompt / tool config (VAPI · ElevenLabs · self-hosted DB row / Cekura mock tools)** — diff the system prompt(s), tool `description` / `parameters` / schema, and (VAPI) spoken `messages` + handoff `destinations`, tool-id deltas.
- **Owned source (self-hosted)** — diff the source regions APPLY.1 touched: system-prompt string literals and tool-definition blocks (score these), orchestration control-flow (do NOT score).
- **Render-only** — diff the previously-rendered prompt vs the just-rendered rewrite.

Each inventoried edit is one row to score. Cluster edits touching the same logical section (one row per `Edit` call, not per line) so the verdict aligns with the diff the user reviewed at FIX.6.

## Step GATE.2 — Score each edit against the five signatures

For each match record:

- **Signature name** (e.g. `verbatim_transcript_quote`).
- **Evidence** — the offending sub-string AND the failing transcript / scenario it came from (the user-facing receipt: "you added '`refund right now`'; it appears verbatim in `run_abc123`").
- **Severity** —
  - *high* (STRIP candidate) — scenario identifier, hardcoded test-data value, or a verbatim quote > ~5 words used as a trigger.
  - *medium* (REVISE candidate) — hyper-narrow case clause, transcript-paraphrasing few-shot.
  - *low* (KEEP, note in summary) — a single short word/phrase also in the transcript but plausible general language ("refund").

**Skip scoring** an edit that is: an orchestration-code edit (different regime); a pure deletion (removing a contradictory clause / stale tool reference — nothing added); or a tool-schema narrowing (precision, not overfit).

If the whole edit set scores no-flags, surface `No overfitting detected in N edits — passing straight to Eval.` and skip to GATE.7 (SYNC.1 is still valid; re-running it is wasteful).

## Step GATE.3 — Decide REVISE / STRIP / KEEP per flagged edit

- **REVISE** — replace the overfit fragment with generalized phrasing. Default for *medium*, and for *high* where the behavioral intent is still load-bearing.
  - `If the user says "I need a refund right now", escalate.` → `If the user explicitly asks for a refund, escalate.`
  - `For scenario test_billing_v2, gather order ID first.` → `For billing queries spanning multiple orders, gather the order ID first.`
  - `Example: "my charge of $42.91 on 03/14 is wrong" → "Let me look up that charge…"` → `Example: if the customer reports an incorrect charge, look up the transaction before disputing.`
- **STRIP** — revert the fragment entirely. Default for *high* where the fragment is purely overfit (scenario IDs, hardcoded values with no general form) and the surrounding edit stands without it (e.g. remove a transcript-clone example block, keep the rule).
- **KEEP** — leave as-is, record the finding for transparency. Use for *low* severity, or when REVISE would over-generalize and re-open the failure Optimization just fixed. Always note WHY.

**When REVISE would invalidate the fix** — sometimes the edit fixes the failure *because* it's specific; STRIP/REVISE would re-open it on Eval, Eval re-emits the same failure, Optimization re-writes the same overfit edit → a no-change loop the gate causes. If this looks likely, **surface the tension; don't pick a side**: "Optimization added a clause matching one transcript verbatim. The gate would normally REVISE to a general intent rule, but the diagnosis (Ambiguity, not Gap) suggests the specificity is load-bearing. Two paths: (a) accept the overfit edit, let Eval validate; (b) REVISE to a general rule and accept the failure may re-surface — in which case the right fix is architectural (model swap / flow restructure)." **Pause for a decision even in auto mode**, unless the user already directed a path this run.

## Step GATE.4 — Produce cleanup edits

Convert each REVISE / STRIP into a concrete edit via the same apply path Optimization used (bundle into one write per artifact to minimize round-trips):

- **Prompt / tool config** — a follow-up PATCH (provider API) or DB-row / mock-tool update overwriting the just-changed field.
- **Owned source** — `Edit` calls on the source file (`old_string` = the overfit fragment that just landed, `new_string` = cleaned-up; 3–5 lines of surrounding context to keep `old_string` unique).
- **Render-only** — render a SECOND revised prompt replacing the just-shown one: "The previous rendering quoted the failing transcript verbatim; apply this generalized version instead."

If every flagged row was KEEP, no cleanup is needed — skip GATE.5–6 and hand to Eval after surfacing the summary.

## Step GATE.5 — Present the cleanup proposal

Show each cleanup edit as a **before / after** block (Optimization edit on "before", gate-revised on "after"), grouped by signature. End with a summary line: `Gate cleanup: 3 revises, 1 strip, 2 keeps across 6 flagged edits (2 verbatim quotes, 2 scenario-IDs, 1 narrow-case, 1 few-shot).`

**Default (`auto_mode: true`): skip the routine approval prompt** — render the before/after + summary for transparency, then proceed to GATE.6 with all cleanup accepted. **Pause and ask (fires even in auto mode) only when:**

- A REVISE would invalidate the fix (the tension case in GATE.3) — never silent.
- The gate would STRIP more than half of the iteration's edits — a large strip-set signals Optimization produced mostly overfit material; the right move is often "go back to Optimization with a hint to generalize" rather than ship a heavily-scrubbed proposal. Surface it; do not silently apply.
- The evidence is itself low-confidence — a flagged phrase both appears in the transcript AND is generic enough to appear in production traffic. Confirm before stripping.

**When `auto_mode: false`: this gate fires every iteration.** Present the cleanup alongside the FIX.6 proposal so the user reviews both together. Do not proceed until confirmed.

## Step GATE.6 — Apply the cleanup edits

Apply via the same machinery APPLY.1 uses (provider PATCH ordering, `Edit`+redeploy, or DB/mock update — see the provider apply docs). Live-immediate paths (provider API) need no redeploy.

**Redeploy (self-hosted live target)** — cleanup changes live state again, so the `redeploy_command` flow runs a second time:
- **Command provided** → run via Bash; same exit-code handling as APPLY.2.
- **`"manual"`** → fire the manual restart gate; wait for user confirmation.
- **Unset + `auto_mode: true`** → proceed to GATE.7 without pausing.

**Skip redeploy entirely** if the gate produced zero cleanup edits (the Optimization apply is still the live state).

## Step GATE.7 — Confirm sync

Re-fetch / re-read the cleaned-up artifacts; verify the overfit fragments are gone AND the surrounding rules intact. Same per-surface re-fetch as SYNC.1:

- **Prompt / tool config** — re-fetch the agent + every edited tool (provider API) or re-run the DB fetch / `aiagents_retrieve`.
- **Owned source** — re-`Read` the source file (not cached), verify cleanup `Edit`s landed.
- **Render-only** — skip; nothing to sync server-side.

**Skip the re-fetch** if the gate produced zero cleanup edits (SYNC.1 is still valid).

## Hand-off to Eval

After GATE.7 hand to [`eval.md`](eval.md) with:

- The cumulative edit set (Optimization + gate cleanup) so the iteration diff is tracked correctly.
- The gate summary line (flag/revise/strip/keep counts) for the iteration log.
- The same failure set + full set + iteration number Optimization handed up (unchanged).

If the gate ended at "all KEEP" or "no flags", it's a transparent pass-through — Eval sees the exact post-Optimization state.

## Anti-patterns

- **Stripping every flagged edit on auto-pilot.** REVISE is the default; STRIP only when no general form exists. Aggressive stripping re-opens fixes and burns iteration cap.
- **Generalizing past the diagnosis.** If Optimization diagnosed Ambiguity and added specificity, don't REVISE that specificity back to vagueness. Ambiguity fixes legitimately add narrowness; the gate cleans transcript-specific narrowness, not all narrowness.
- **Flagging short common words.** "Refund", "order", "account" appear in transcripts AND production. Reserve the verbatim signature for ≥4–5-word phrases OR unmistakably test-derived tokens (account numbers, names).
- **Scoring only identifiers, not the frame.** Genericizing nouns while keeping the transcript's frame ("I said `<city>` earlier but we are actually in `<city>`") is still a verbatim quote. Placeholder-swap the example, grep failing transcripts for any ≥4-word frame substring; a hit means it's structurally cloned. Fix = drop the example or rewrite from scratch, not swap nouns.
- **Re-flagging the same edit across iterations.** If iteration N's edit was flagged then KEPT, don't re-flag the applied state in N+1. Track KEEP'd flags so they stay out of later inventories.
- **Running the gate on orchestration-code or pure-deletion edits.** Code edits are scored by correctness (skip control flow; DO score embedded prompt string literals). Pure deletions add nothing — no overfit risk.
- **Triggering double-redeploy with no cleanup edits.** Short-circuit GATE.5/6/7 when the decision is "no cleanup needed".
- **Surfacing the verdict as a worry caveat.** Report a clean transition ("Gate scrub: 2 revises applied, sync confirmed, moving to validation"), not hedging ("the edits might generalize poorly").

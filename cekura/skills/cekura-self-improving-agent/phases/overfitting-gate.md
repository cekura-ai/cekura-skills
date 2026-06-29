# Overfitting Gate Phase — Scrub the Just-Applied Edits

The Overfitting Gate phase sits between the Optimization phase (whose final sub-phases [`optimization/apply.md`](optimization/apply.md) and [`optimization/sync.md`](optimization/sync.md) just landed and verified the edit set) and Eval. It re-reads those edits, detects overfitting signatures (verbatim transcript quotes, specific scenario IDs / names, hyper-narrow case clauses, hardcoded test data), and emits cleanup edits that generalize or strip the overfit material before validation runs.

The gate exists because the Optimization diagnose sub-phases read failing transcripts, and that exposure leaks into proposals: an LLM diagnosing "the agent said 'sorry I cannot help with that' when it should have escalated" will often *write the failing utterance directly into the prompt* as the trigger — turning a generic instruction into a verbatim match against one transcript. That edit fixes the seen failure but won't generalize. The early-end-call diagnose sub-phase is especially prone to this since it inspects farewell phrasing directly. The gate catches both before validation and prevents the loop from celebrating a memorized fix.

The gate is a no-op pass-through on iterations where no overfitting is detected — the typical case after a few iterations once the LLM has settled into generalized phrasing. Cost is one extra re-read + a short LLM judgment pass; no extra apply round-trip unless cleanup edits are actually needed.

## Pre-flight check

Before any Step GATE.x work, verify that the Optimization phase completed cleanly this iteration:

- Edits were applied (Optimization · Apply Step APPLY.1) AND sync was confirmed (Optimization · Sync Step SYNC.1), OR — for a render-only run (no live target) — the rewritten prompt was rendered and the user has been asked for new pasted failures.
- The iteration's edit set is known (which fields/files/sections changed, and what the old + new text was) — handed up from [`optimization/sync.md`](optimization/sync.md). This includes both early-end-call edits (from [`optimization/early-end-call-diagnose.md`](optimization/early-end-call-diagnose.md)) and diagnose edits (from [`optimization/diagnose.md`](optimization/diagnose.md)).
- The iteration's failure summary is available (the source failures the edits were meant to address — needed to score "did this edit just copy the failing utterance verbatim?"). This includes the failing transcripts handed up from [`optimization/collect.md`](optimization/collect.md).

If any of the above is missing, return control to the orchestrator — the Optimization phase did not complete cleanly. **Skip the gate entirely** when the iteration produced zero prompt/tool/orchestration edits (all-Upstream / kept = 0); there is nothing to scrub.

## What counts as overfitting

The gate looks for five concrete signatures. Score each Optimization edit against these; an edit that triggers any signature is a candidate for cleanup.

| Signature | What it looks like | Why it overfits |
|-----------|--------------------|-----------------|
| **Verbatim transcript quote** | A phrase added to the prompt that appears word-for-word in one of the failing transcripts ("If the user says 'I need a refund right now', then…"). **Also flag paraphrases where only the proper nouns were genericized but the syntactic frame around them is lifted verbatim.** Example: failing transcript says "I said *Delhi* earlier but we are actually based in *Gurugram*"; the proposed edit adds the example "I said *one city* earlier but we are actually in *a different city*" — the city names are generalized, but the 5-word substring "earlier but we are actually" is verbatim. That counts. Concrete check: after mentally replacing every proper noun / number / date in the edit's example with a placeholder, search the failing transcripts for any ≥4-word contiguous substring of the remaining frame. A hit = flag. | Future calls will phrase the same intent differently ("refund please", "want my money back"); the rule won't match. The agent now follows a string-match heuristic instead of an intent. Replacing only the identifiers does not defuse the signature — the frame itself is the leak. |
| **Scenario-specific identifier** | A scenario name, scenario ID, test-profile name, or run ID appears in the prompt or tool description ("For scenario `test_complex_billing_query_v2`, do X"). | Scenario identifiers are test artifacts. The agent has no way to know which scenario it's in at runtime, so the clause is at best dead text and at worst confuses the model. |
| **Test-data value hardcoded** | A specific account number, customer name, dollar amount, date, or other concrete value from the failing run is baked into the prompt as a literal ("if the customer mentions account #4827361 …"). | Real users won't say "account #4827361". The clause is a fingerprint of the test data, not a behavioral rule. |
| **Hyper-narrow case clause** | A new clause whose condition is so specific it matches only one transcript shape — many `AND`s, exact-step counts, exact-question wordings ("If the user asks about refund policy AND the order is over 6 months old AND they mention 'pre-paid' THEN respond …"). | The condition won't generalize across the failure cluster. Production traffic won't match the exact conjunction; the edit fixes one transcript and nothing else. |
| **Few-shot example pulled from failing run** | A "for example, …" block added to the prompt whose example dialog is recognizably a paraphrase (or worse, a verbatim copy) of one of the failing transcripts. | Steers the model to memorize one trajectory. Fine if the example is *constructed* to illustrate the rule; harmful if it leaks the test set into the prompt. |

**What the gate does NOT flag:**
- **General behavioral rules with concrete examples constructed by the LLM** — e.g., "When the user mentions a billing issue, first verify the account is active. Example: if the user reports an incorrect charge, look up the transaction before discussing the dispute." Leave it only when BOTH conditions hold: (a) the example reads as a plausible LLM-constructed illustration, AND (b) the example's sentence frame does not match any failing transcript by the procedure in the **Verbatim transcript quote** signature row above (replace nouns/numbers/dates with placeholders, then grep failing transcripts for any ≥4-word contiguous substring of the remaining frame). If (a) but not (b), it's still a transcript clone — flag it.
- **Tool-schema specificity** — narrowing a parameter `enum` to a closed set, tightening a `description` with concrete units, etc., is desirable, not overfitting.
- **Adding a step that was missing** — if the diagnosis was Gap and the fix adds "ask for the order date before quoting return policy", that is general and not overfitting even if the failing scenario was about order dates.
- **Edits to orchestration code** (self-hosted source-file edits only) — code edits are evaluated by their own correctness, not by the overfitting lens. Skip code-stream edits in the gate.

When in doubt, **flag it but propose REVISE rather than STRIP** — generalizing a borderline edit is cheap; stripping a useful fix is expensive.

## Step GATE.1 — Inventory the iteration's edits

Pull the diff for this iteration:

- **VAPI** — diff of `/assistant/{id}` (system message changes per squad member, `toolIds` deltas) and every edited `/tool/{id}` (`function.description`, `function.parameters`, `messages[*].content`, `destinations`).
- **ElevenLabs** — diff of the agent's `conversation_config.agent.prompt.prompt` (system prompt) and `prompt.tool_ids` deltas, plus every edited `/v1/convai/tools/{id}` (`tool_config.description`, `api_schema`, `parameters`).
- **Self-hosted** — diff of whatever was edited per the run-setup: the source file regions Optimization · Apply Step APPLY.1 touched (system prompt string, tool-definition blocks — orchestration-code edits are NOT scored here), the database-row prompt, the mock-tool `description` / `mock_data` changes, OR (render-only) the diff between the previously-rendered prompt and the just-rendered rewrite.

Each inventoried edit becomes one row to score. Cluster edits that touch the same logical section (one row per `Edit` call, not per added line) so the gate's verdict aligns with how the user reviewed the diff in Optimization · Diagnose Step DIAGNOSE.5.

## Step GATE.2 — Score each edit against the five signatures

For every inventoried edit, walk the five signatures in the table above. For each match, record:

- **Signature name** (e.g., `verbatim_transcript_quote`).
- **Evidence** — the offending sub-string from the edit AND the failing transcript / scenario where it came from. The evidence is the user-facing receipt: "you added '`refund right now`' to the prompt; this phrase appears verbatim in failing run `run_abc123`."
- **Severity** —
  - *high* (STRIP candidate) — scenario identifier, hardcoded test-data value, or a verbatim transcript quote longer than ~5 words used as a trigger condition.
  - *medium* (REVISE candidate) — hyper-narrow case clause, few-shot example that paraphrases the failing transcript.
  - *low* (KEEP, flag in summary) — a single short word/phrase that also happens to be in the transcript but is plausible general language (e.g., "refund" — common term, not unique to the failing run).

Skip the scoring entirely for an edit if:
- It is an orchestration-code edit (self-hosted source-file edits only) — different evaluation regime.
- It is a pure deletion (removing a contradictory clause, removing a stale tool reference) — nothing was added; nothing to overfit.
- It is a tool-schema narrowing (param `enum`, `description` typing) — those are precision improvements, not overfitting.

If an iteration's entire edit set scores as no-flags, surface a one-line `No overfitting detected in N edits — passing straight to Eval.` and skip to Step GATE.7 (sync check is unchanged from Optimization · Sync Step SYNC.1 and re-running it is wasteful — go straight to Eval).

## Step GATE.3 — Decide REVISE / STRIP / KEEP per flagged edit

Walk the flagged rows from Step GATE.2 and choose one outcome per row:

- **REVISE** — replace the overfit fragment with a generalized phrasing. Default for *medium*-severity findings and for *high*-severity findings where the underlying behavioral intent is still load-bearing. Examples:
  - `If the user says "I need a refund right now", then escalate.` → `If the user explicitly asks for a refund, then escalate.`
  - `For scenario test_complex_billing_query_v2, gather order ID first.` → *strip the scenario reference, keep the behavioral rule:* `For billing queries that span multiple orders, gather the order ID first.`
  - `Example: "Customer: my charge of $42.91 on 03/14 is wrong" → respond: "Let me look up that charge…"` → `Example: if the customer reports an incorrect charge, acknowledge and look up the transaction before disputing.`
- **STRIP** — revert the offending fragment entirely. Default for *high*-severity findings where the fragment is purely overfit (scenario IDs, hardcoded values that have no general-form) and where the surrounding edit can stand without it. Example: a few-shot example block that's a transcript clone — remove the example block, keep the surrounding rule.
- **KEEP** — leave the edit as-is and record the finding in the gate's summary for transparency. Use for *low*-severity findings or when REVISE would over-generalize and re-introduce the failure that Optimization just fixed. Always note WHY KEEP was chosen ("generalizing this would lose the specificity the failure needed; left as-is").

**When REVISE would invalidate the fix** — sometimes the only way the Optimization edit fixes the failure is *because* it's specific. In that case STRIP / REVISE would re-open the failure on Eval, and Eval would re-emit the same failure to Optimization, which would re-write the same overfit edit, creating a no-change loop the gate causes. If this case looks likely, **surface the tension to the user explicitly** rather than picking a side: "Optimization added a specific clause that matches one transcript verbatim. The gate would normally REVISE this to a general intent rule, but the underlying diagnosis (Ambiguity, not Gap) suggests the specificity is load-bearing. Two paths: (a) accept the overfit edit and let Eval validate; (b) REVISE to a general rule and accept that the same failure may re-surface, in which case the right fix is probably architectural (model swap / flow restructure) rather than prompt wording." Pause for a decision unless the user has already directed a path in this run.

## Step GATE.4 — Produce cleanup edits

Convert each REVISE / STRIP decision into a concrete edit:

- **VAPI** — a follow-up assistant PATCH or tool PATCH that overwrites the just-changed field with the cleaned-up version. Bundle all cleanup edits into a single PATCH per artifact (one for the assistant, one per tool) to minimize round-trips.
- **ElevenLabs** — a follow-up agent PATCH (`conversation_config.agent.prompt.prompt`) or tool PATCH (`/v1/convai/tools/{id}`) overwriting the just-changed field with the cleaned-up version. One PATCH per artifact.
- **Self-hosted** — apply the cleanup via whatever the run-setup edits: `Edit` calls on the source file (each with `old_string` = the overfit fragment that just landed and `new_string` = the cleaned-up version; include 3–5 lines of surrounding context per anchor to keep `old_string` unique), the database-row write query, or a follow-up `mcp__cekura__aiagents_partial_update` with the updated `mock_tools` list. For render-only, render a SECOND revised prompt and replace the just-shown one, telling the user explicitly: "I noticed the previous rendering quoted the failing transcript verbatim; here's a generalized version — apply this instead of the previous one."

If KEEP was the decision for every flagged row, no cleanup edits are needed — skip Steps GATE.5 and GATE.6 and hand off straight to Eval after surfacing the gate's summary.

## Step GATE.5 — Present the cleanup proposal to the user

Show every cleanup edit as a **before / after** block, with the original Optimization edit on the "before" side and the gate-revised version on the "after" side. Group by signature. End with a summary line: `Gate cleanup: 3 revises, 1 strip, 2 keeps across 6 flagged edits (2 verbatim quotes, 2 scenario-IDs, 1 narrow-case clause, 1 few-shot example).`

**Default (`auto_mode: true`): skip the routine approval prompt.** Render the before/after blocks and summary line for transparency, then proceed straight to Step GATE.6 with all cleanup edits accepted. Pause and ask only when:

- A REVISE would invalidate the fix (the "tension" case in Step GATE.3) — never silent.
- The gate would STRIP more than half of an iteration's edits — large strip-set is a signal that the Optimization phase produced mostly overfit material; the right answer is often "go back to Optimization with a hint to generalize" rather than ship a heavily-scrubbed proposal. Surface the situation; do not silently apply.
- The gate's evidence is itself low-confidence — e.g., a flagged phrase appears in the transcript AND is also generic enough that it'd appear in production traffic. Ask the user to confirm before stripping.

**When `auto_mode: false`: this gate fires every iteration.** Present the cleanup proposal alongside (or just after) the Optimization · Diagnose Step DIAGNOSE.5 proposal so the user reviews both together. Do not proceed to Step GATE.6 until the user confirms.

## Step GATE.6 — Apply the cleanup edits

Apply via the same provider-specific apply machinery the Optimization · Apply sub-phase uses in Step APPLY.1. The full apply-order details live in each provider's doc:

- **VAPI** — [`../providers/vapi/phase-4-apply.md`](../providers/vapi/phase-4-apply.md) (tool PATCH → assistant PATCH).
- **ElevenLabs** — [`../providers/elevenlabs/phase-4-apply.md`](../providers/elevenlabs/phase-4-apply.md) (tool PATCH → agent PATCH). No redeploy step (edits land live).
- **Self-hosted** — [`../providers/self-hosted/overview.md`](../providers/self-hosted/overview.md) § "Apply order, Sync, and exit framing" + "Edit mechanisms". For render-only, render the revised prompt and tell the user to apply this version instead of the previous one.

**Redeploy step (self-hosted with live target).** The cleanup apply changes the live agent's state again, so the same `redeploy_command` flow runs a second time this iteration:

- **Command provided** → run it via the Bash tool. Same exit-code handling as Optimization · Apply Step APPLY.2.
- **`redeploy_command == "manual"`** → fire the manual restart gate. Wait for explicit user confirmation.
- **Unset and `auto_mode: true`** → proceed straight to Step GATE.7 without pausing.

**Skip the redeploy entirely** if the gate produced zero cleanup edits (the original Optimization apply is still the live state; no new redeploy needed).

## Step GATE.7 — Confirm sync

Re-fetch / re-read the just-cleaned-up artifacts and verify the overfit fragments are gone AND the surrounding rules are intact. Use the same per-mode re-fetch as Optimization · Sync Step SYNC.1:

- **VAPI** — re-fetch `/assistant/{id}` and every edited `/tool/{id}`.
- **ElevenLabs** — re-fetch `GET /v1/convai/agents/{id}` (confirm `conversation_config.agent.prompt.prompt` shows the cleaned-up text) and every edited `GET /v1/convai/tools/{id}`.
- **Self-hosted** — re-read whatever was edited: re-`Read` the source file (not cached) and verify the cleanup `Edit`s landed; re-run the DB fetch query; or re-fetch via `mcp__cekura__aiagents_retrieve`. For render-only, skip — nothing to sync server-side.

**Skip the re-fetch** if the gate produced zero cleanup edits — the Optimization · Sync Step SYNC.1 from a few moments ago is still valid.

## Hand-off to the Eval phase

After Step GATE.7, the Overfitting Gate phase is complete for this iteration. Hand off to [`eval.md`](eval.md) with:

- The cumulative edit set (Optimization edits PLUS gate cleanup edits) so the iteration's diff is tracked correctly by the orchestrator.
- The gate's summary line (count of flags, count of revises/strips/keeps) so it appears in the iteration log alongside the Optimization diff.
- The same failure set + full set + iteration number Optimization handed up — the gate does not change these.

If the gate's decision tree ended at "all flags resolved as KEEP" or "no flags found", the gate is a transparent pass-through — Eval sees exactly the post-Optimization state.

## Gate-specific anti-patterns

- **Stripping every flagged edit on auto-pilot.** REVISE is the default; STRIP is for the cases where no general form exists for the fragment. Aggressive stripping re-opens failures Optimization just fixed and burns iteration cap.
- **Generalizing past the diagnosis.** If Optimization diagnosed Ambiguity ("the wording is vague enough the agent could read it either way") and the fix added specificity, the gate must not REVISE that specificity back to vagueness in the name of generalization. Ambiguity fixes legitimately add narrowness; the gate cleans up overfitting (transcript-specific narrowness), not all narrowness.
- **Flagging short common words.** "Refund", "order", "account" appear in failing transcripts AND in production traffic. A short common word in the edit is not a verbatim transcript quote. Reserve the signature for phrases ≥ 4–5 words OR shorter phrases that are unmistakably test-derived (account numbers, customer names).
- **Scoring only the identifiers, not the surrounding frame.** When an edit adds an example dialog, the gate must check both the proper nouns AND the surrounding sentence frame. Genericizing the nouns while keeping the transcript's syntactic frame ("I said `<city>` earlier but we are actually in `<city>`") is still a verbatim quote — the 5-word substring "earlier but we are actually" was lifted whole. The fix is to drop the example entirely or rewrite it from scratch using a frame the model would plausibly generate on its own, not just swap the nouns. Procedure when scoring: mentally replace every proper noun / number / date in the edit's example with `<X>`, then grep the failing transcripts for any ≥4-word contiguous substring of the remaining frame. A hit means the example is structurally cloned from the transcript even if the surface tokens look generic.
- **Re-flagging the same edit across iterations.** If iteration N's edit was flagged and KEPT (because revising would invalidate the fix), iteration N+1 should not re-flag the now-applied state. Track the KEEP'd flags so they don't enter the gate inventory on subsequent iterations.
- **Running the gate on orchestration-code edits.** Code edits (self-hosted source-file edits only) are scored by code correctness, not by overfitting signatures. The same five-signature lens doesn't apply to history-window sizes or message-role mappings. Skip code-stream edits entirely. Note that early-end-call-diagnose may emit BOTH a prompt edit AND an orchestration-code edit for the same failure cluster — score the prompt edit, skip the code one.
- **Running the gate on pure-deletion edits.** If Optimization removed a contradictory clause and added nothing, there is no overfitting risk. Score only edits that introduced new text.
- **Triggering double-redeploy when there are no cleanup edits.** The gate must short-circuit (skip GATE.5 / GATE.6 / GATE.7 redeploy) when its decision is "no cleanup needed". Otherwise it inflates per-iteration cost for zero benefit.
- **Surfacing the gate's verdict as a worry caveat.** Internal calibration is fine; user-facing wording should report a clean transition: "Gate scrub: 2 revises applied, sync confirmed, moving to validation." Avoid hedging language like "the edits *might* generalize poorly" — the gate either revised the issue or it didn't.

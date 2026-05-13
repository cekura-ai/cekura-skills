# Optimization · Early-End-Call Diagnose — Triage the "agent hung up too soon" Failures

Second sub-phase of optimization. Specialized diagnosis for failures where the **main agent ended the call before the scenario's required steps completed**. These failures look identical to "agent skipped a field" from the verdict alone, but the fix surface is qualitatively different: prompt edits that target later behavior (after the farewell) are wasted work because the call literally cut off before they could fire.

This sub-phase runs BEFORE the general diagnose sub-phase ([`diagnose.md`](diagnose.md)) because the early-end pattern dominates any other diagnosis on the same scenario — if the call ended at turn 4 and the scenario required 8 steps, no amount of step-4-onward prompt wording will help. Catching this first prevents wasted edits in the diagnose sub-phase.

This sub-phase produces only proposed edits — it does NOT apply them. Proposed edits flow into diagnose, which combines them with its own proposals and presents the full set to the user in Step DIAGNOSE.5. Apply happens in [`apply.md`](apply.md).

## Pre-flight check

Before any Step EARLY.x work, verify Collect is complete:

- The kept failure set is populated (`failure` ∪ `reviewed_failure` from Collect Step COLLECT.3).
- Provider call state observations are recorded for every kept failure (Collect Step COLLECT.4 ran in full). Specifically, **Signal 5 (end-of-call attribution) MUST be present** — `metadata.ended_reason` or `endedReason`, plus transcript-tail data and turn-count vs. required-step-count. Without Signal 5 this sub-phase has nothing to operate on.
- Failure summary built (Collect Step COLLECT.5).

If Signal 5 is missing for any failure, return to Collect Step COLLECT.4 — the inspection skipped end-of-call recording.

## Step EARLY.1 — Identify early-end-call failures

For each kept failure, fill **exactly** this — no rationale, no narrative, no analysis paragraph:

```
Run <id>:
  [ ] main agent ended the call?       (metadata.ended_reason == "main-agent-ended-call" for self-hosted;
                                        endedReason ∈ {assistant-ended-call, assistant-said-end-call-phrase} for VAPI;
                                        customer-ended / timeout / silence-timed-out / client-disconnect → NO)
  [ ] scenario-incomplete in bullets?  (failed / 🟡 expected-outcome bullets describe steps the call never
                                        reached — e.g. "appointment was not booked", "did not get to ask",
                                        "no [final-step] occurred"; NOT "the agent did step X wrong" — that's
                                        wrong-behavior-during-call, not scenario-incomplete)
  → VERDICT: both YES → FLAGGED · any NO → PASS
```

If you wrote anything other than `VERDICT: FLAGGED` or `VERDICT: PASS` on the verdict line above, delete it and start over with just the two boxes. There is no third option, no borderline, no "suspected." The two checks are exhaustive — together they encode the full early-end-call pattern. Anything that doesn't fit becomes PASS and flows to [`diagnose.md`](diagnose.md) for normal classification.

**Pass-through case.** If every kept failure is PASS, this sub-phase is a one-line no-op: surface `Early-end-call triage: 0 failures match the pattern — handing off all N kept failures to diagnose.` and skip to the hand-off section. No edits are proposed.

## Step EARLY.2 — Diagnose the root cause for each flagged failure

For each flagged failure, locate the layer that allowed the premature end. Investigate in this order:

1. **System prompt — "End Conversation" / "Closure" rules.** Quote the relevant lines from the responsible assistant's system message (the speaker in the final transcript turn, for squads). Look for: rules that treat "okay" / "thanks" / generic closure phrases as a signal to end; missing explicit gates requiring all required fields to be collected before farewell; closure logic that triggers on the agent's own farewell intent rather than the caller's. **Common shape**: the prompt has a "wrap up the call" section that fires on any natural conversational pause, with no required-fields checklist.
2. **Orchestration code's end-of-call detection** *(self-hosted / websocket / `file` only)*. Open the source file and locate the end-of-call detection logic — typically a function or branch that scans agent / user messages for keywords ("goodbye", "bye", "thanks") and closes the websocket. **Common shape**: the loop ends on any agent message containing a closure keyword, regardless of conversation state.
3. **Tool / handoff destinations** *(VAPI only)*. If a tool has a `destinations[]` entry that hands off to an end-call assistant prematurely, or a tool message ("request-complete") that implies the call is done, that can also produce an early end.

Pick the layer that, if fixed, would produce the largest behavior change. For VAPI / websocket / offline modes, the prompt layer is almost always the right surface (orchestration code is out of reach for VAPI / offline; tool-handoff edits apply only to VAPI and are rare causes). For websocket / `file` mode, prefer the prompt edit when the prompt's closure rules are clearly too permissive; reach for the orchestration-code edit when the prompt is fine and the code-level keyword scan is what fires.

Surface the secondary layer ("also tighten the orchestration's end-of-call detection") as a follow-up note if appropriate, but do not include it in the primary edit set unless the user explicitly asks.

## Step EARLY.3 — Propose minimal early-end fixes

Use the smallest change that fixes the failure cluster. Cluster early-end failures that share a layer + diagnosis — if 4 failures all stem from the same too-permissive closure rule, propose one prompt edit covering all 4.

**Prompt-side edit (all modes).** Add or rewrite the closure / "End Conversation" rules so the agent must satisfy all required-field / required-step conditions before farewell. Match the prompt's existing voice. Example shapes:
- *Gap shape*: prompt has no closure rule at all → ADD: "Before ending the call, confirm that you have collected: [required field 1], [required field 2], [...]. If any required field is missing, ask for it explicitly before saying goodbye."
- *Ambiguity shape*: prompt says "wrap up when the conversation reaches a natural pause" → EDIT to: "Wrap up only after every required step has been completed. A natural pause from the caller is not a signal to end if required steps are pending."
- *Conflict shape*: one section says "be efficient and end quickly when possible" while another section requires multi-step collection → SCOPE the efficiency rule: "Be efficient AFTER all required steps are complete; do not shortcut the required-step collection."

**Orchestration-code edit (websocket / `file` only, optional).** When the diagnosis is "code-level keyword scan ends the loop too eagerly", propose a minimal `Edit` adding a `required_fields_collected` check before the loop accepts a closing turn. Keep it scoped: one `Edit`, 5–10 lines of surrounding context per anchor. Do not refactor the loop; do not touch business logic. If the orchestration-code edit would require non-trivial refactor (new helper functions, multi-file changes), surface as a hand-off instead of attempting it.

**Tool / handoff edit (VAPI only, rare).** When the diagnosis is a misconfigured `destinations[]` or a tool `messages[*].content` that pre-empts the call, PATCH the offending tool. See [`../../providers/vapi/phase-4-apply.md`](../../providers/vapi/phase-4-apply.md) for the curl body.

Each proposed edit gets a **before/after** block plus the failure-id list it addresses. The diff is rendered in DIAGNOSE.5 alongside the diagnose proposals.

## Anti-patterns specific to early-end-call diagnosis

- **Diagnosing early-end as Gap when it's Conflict.** "No rule prevents early end" sounds like Gap, but if the prompt also has an "be efficient and wrap up quickly" rule, the failure is a Conflict between efficiency and completeness. Diagnose accordingly; the fix shape is different (scope the efficiency rule rather than add a new gate).
- **Proposing prompt edits in modes that have a clearer code-level fix.** For websocket / `file`, if the orchestration code's keyword-scan closes the loop on any agent farewell regardless of conversation state, no prompt edit fully fixes it — the loop will close before the next agent turn even has a chance to ask the missed required question. Pick the orchestration-code surface for those.
- **Applying early-end edits before diagnose runs.** This sub-phase only PROPOSES; it does not apply. Applying here would re-fetch / re-classify the rest of the failures against a half-edited prompt and confuse the diagnosis. Apply is centralized in [`apply.md`](apply.md) after both diagnose sub-phases complete.

## Hand-off to diagnose

After Step EARLY.3 (or after the pass-through case in Step EARLY.1), hand off to [`diagnose.md`](diagnose.md) with:

- The full kept failure set (early-end-flagged + non-flagged failures). Rest-of-diagnose iterates only the non-flagged ones for primary diagnosis, but the flagged set is in scope for the combined proposal presentation in Step DIAGNOSE.5.
- The set of proposed early-end edits (may be empty in the pass-through case). Rest-of-diagnose will merge these with its own proposed edits when presenting to the user.
- A summary line for the user: `Early-end-call triage: M of N failures flagged (M early-end edits proposed across L layers).` On pass-through: `Early-end-call triage: 0 failures match the pattern — passing all N failures to diagnose.`

# Phase 3 — Diagnosis Reference

Full classification table with examples, before/after templates per edit surface, tool-edit anti-patterns, manual-vs-automated-improver guidance, and Optimization-phase anti-patterns.

## Classification table

| Bucket | What it looks like | Example |
|--------|--------------------|---------|
| **Gap** | No prompt section addresses this situation AND variable state is healthy. The agent improvised and got it wrong. | Prompt never says what to do if caller asks for a manager → agent makes up a transfer policy. |
| **Conflict** | Two clauses contradict each other, OR a clause contradicts the tool definition (e.g. tool description says "wait for X", prompt says "don't ask for X"), OR a clause contradicts the behavior the failure expects. | The scheduling-node prompt says "skip the question gate, fire handoff immediately"; handoff tool description says "wait for user confirms no questions" → agent stalls. |
| **Ambiguity** | One section addresses it but wording is vague enough the agent could read it either way AND variable state is healthy. | "Wrap up the call politely" — no concrete steps, agent skipped a legally required disclosure. |
| **CodeBug** | Owned source code (incl. any vendored/forked SDK inside the source tree the run-setup edits) has a verifiable bug causing the failure. Fix via Edit + redeploy, validated on Cekura (trigger forced in-sim per REPRO.3e), shipped as a PR. | Self-hosted agent: an SDK fork in the repo is double-encoding a payload, causing tool calls to fail. |
| **Upstream/data** | Variable state shows the runtime lacked what the prompt or tool requires: a placeholder is `null` / absent / empty, a key name mismatches, or literal `{{...}}` strings survived into rendered messages or tool-call arguments. No prompt or tool edit fixes the root cause. | The scheduling-node prompt depends on `{{customerId}}`, `{{schedulingRules}}`; runtime shows `schedulingRules=[]`, `customerId=null`; tool calls fire with literal `customerId="{{customerId}}"`. |

**When both Upstream/data AND a Gap/Conflict/Ambiguity are present**, pick the bucket that produces the larger behavior change if fixed — usually Upstream/data, because a phantom prompt fix against broken variable state will fail re-validation the same way. Surface the secondary component as "deferred — re-evaluate after upstream fix."

**CodeBug carve-out**: owned code (including a vendored/forked SDK in the self-hosted source tree) is CodeBug (in-scope), NOT Upstream. "Upstream" is only for code the user genuinely cannot edit. The Cekura-simulation infra/mock catalog below is about harness artifacts — those remain Upstream regardless; do not apply the CodeBug carve-out to simulation artifacts.

## Cekura-simulation infra / mock signatures → classify Upstream, never prompt-fix

> In Cekura-simulation runs the most common false "agent failure" is a harness, mock, or tool-contract artifact — not agent behavior. Classify these Upstream and never spend an iteration prompt-fixing them.

| # | Signature | Root cause | Verdict |
|---|-----------|------------|---------|
| 1 | `handoff-destination-request` → HTTP **400 `"Only in-progress status accepted"`**, OR a `handoff_to_*` tool with `destinations: [{type:"dynamic"}]` errors and control never transfers (agent stalls after "let me move you to the next step"). | Cekura sim harness does not implement VAPI's dynamic `handoff-destination-request`. | **Upstream (harness gap).** Don't edit the prompt. Test-env mitigation only: hardcode the handoff to a concrete member id — note it as a sim fix, not an agent-quality fix. |
| 2 | Agent repeatedly calls a generic fallback tool instead of the intended data tool; the intended MCP sub-tool name appears **zero times** in the call log. | VAPI failed to connect/list the MCP server's sub-tools at runtime; the needed function wasn't in the exposed tool set. | **Upstream (VAPI MCP load failure).** Do NOT write "use tool X" prompt edits. |
| 3 | `"Couldn't get tool for hook. toolId … does not exist"` at call creation / handoff. | Tool wiring / mock-clone churn left a dangling toolId reference. | **Upstream (tool wiring / call assembly).** |
| 4 | Tool results like `"No matching input found"`, `"No matching mock input found for tool: X"`, `{"success": false, "message": "recordId is required"}`, empty `availableSlots`, or stale dates (e.g. 2024 slots in a 2026 call). The agent made the right call; the mock returned an error/blank. | Mock/test-data gap: missing `freetext_params`, missing fields, stale dates, or stringified-arg extraction failing to match. | **Upstream (test/mock data).** Fix the mock, never the prompt. Fix via the mock tool's `freetext_params` / catch-all entry. |
| 6 | A tool fails because the backend requires a field that is neither in the tool schema nor a provided variable (e.g. `reschedule_intake_call` needs a `recordId` that exists nowhere) → guaranteed failure → transfer. | Tool/backend contract gap. | **Upstream (tool/backend contract).** Route to the backend/tool team; not promptable. |
| 7 | Caller asks for something the agent has no tool for (e.g. reschedule an appointment type it has no reschedule tool for) and the prompt's documented behavior is "transfer to human." | Missing capability — the transfer is the designed behavior. | **Upstream / working-as-designed.** Don't propose a prompt edit telling the agent to use a tool it doesn't have. |
| 8 | Run verdict reads `success: true` / `status: completed` but the call actually stalled into dead air / timeout. | Verdict flag doesn't always catch silence/stall. | Don't trust the flag alone — but equally **don't reclassify an infra stall (rows 1–4) as a prompt failure**. Confirm the failure shape against the transcript first. |
| 9 | `"Model request attempt #1 failed"` (category `model`) in the log. | Transient LLM-provider hiccup / retry. | **Ignore** — not an agent or harness defect. |

**Distinguishing rule:** Rows 1–6 and 9 are environmental — the agent could not have behaved differently. Row 7 is by design. None are fixed by editing a prompt or tool definition reachable from this skill. If a failure matches one of these signatures AND also shows a genuine prompt-following gap on a *different* turn, classify the prompt gap normally and note the infra signature as a separate Upstream hand-off — don't let the infra artifact suppress a real prompt finding, and don't let a real finding launder an infra artifact. (Row numbering matches the session catalog; rows 5 and 10–11 live elsewhere — variable-placeholder leakage is covered by the Upstream/data row above.)

## Prompt-edit rule of thumb

| Bucket | Change type | Rule |
|--------|-------------|------|
| Gap | **Add** a new clause | Place next to the closest related section. Match existing voice/format. |
| Conflict | **Edit** or **Remove** the contradictory clause | Resolve in favor of the behavior the failures expect. If both clauses have legitimate use cases, scope with explicit conditions. |
| Ambiguity | **Edit** for specificity | Replace vague verbs ("politely", "appropriately") with concrete steps. Add a checklist when >2 actions are required. |

## Recurring prompt-edit patterns

### DTMF / IVR navigation — same-turn digit-announcement

**Applies when** the agent has DTMF capability (`play_keypad_touch_tone` tool) AND any of:
- Agent fired the tool but the transcript at that turn is empty — no human-readable indication of which digit or why.
- IVR loops the same menu; the evaluator (reading transcript, not audio) can't confirm progress.
- Agent asked its conversational opener to the IVR menu instead of pressing a digit.
- Debugging a post-hoc IVR failure is impossible because the transcript shows `[tool: play_keypad_touch_tone]` with no readable context.

**Canonical prompt edit.** On the same turn the agent presses DTMF:

> When the IVR menu finishes playing, on the same turn you press the digit: (1) briefly announce the option you are selecting — e.g. "Pressing 1 for administrative staff" — keep it to that one phrase, do not ask any question — AND (2) call `play_keypad_touch_tone` with that digit. If the same menu plays again, immediately announce the option and call the tool again — never speak your conversational opener to an IVR.

**Why same-turn.** A separate "say first, press next turn" structure lets the IVR advance past the menu in the gap, making the announcement wrong by the time DTMF fires.

**Why the announcement matters:**
1. Transcript-based evaluators can confirm "agent intended digit 1" when DTMF doesn't render cleanly — without this the scenario looks indistinguishable from silence.
2. The "no question" clause prevents the most common IVR failure: agent asks its conversational opener to the menu, never reaches a human.
3. Production debug — the canonical signal for "did the agent press what we expected?" without listening to audio.

**Placement.** Pair with the existing "if you hear menu options, do X" / "Initial Audio Triage" guidance so the rules are read together.

**Apply path notes:**
- Managed-provider API/MCP update: prompt edit only, lands live.
- Self-hosted source code: verify the code allows agent text + DTMF tool invocation on the same turn; if the source routes DTMF before speech (split paths for tool vs. speech turns), add an orchestration-code edit in the same iteration. For non-source-edit targets (DB row / mock tools / render-only), surface a paired hand-off asking the user to enable speech + DTMF on the same turn.

### Over-eager transfer / premature-exit patterns (scheduling & support flows)

These recur on enrollment / appointment-scheduling squads. All are genuine prompt-following bugs (Gap or Ambiguity). Before classifying any transfer as a bug, confirm it is *over-eager* (fired on ambiguous or mid-task input) rather than a scripted, intended route or a missing-capability transfer (Upstream row 7).

- **Over-broad human-transfer trigger.** An `[IMMEDIATE HUMAN TRANSFER PROTOCOL]`-style clause fires on ambiguous utterances ("can I talk to somebody?", "hello?") that aren't actually requests for a human. → **Ambiguity.** Fix: scope the trigger to *explicit* requests for a human/agent/representative; add a disambiguation step before any transfer.
- **2-decline → premature transfer on scheduling.** Agent transfers after the caller declines an offered slot twice. → **Gap.** Fix: 3-strike rule — on the 2nd decline ask for caller's preferred day/time and re-query; only transfer on a 3rd strike.
- **Premature call-end on a mid-correction.** Agent ends the call while the caller is still correcting a value (address, ZIP, name). → Belongs to the **FIX.1 early-end triage**, not here. Fix: gate closure on an explicit confirmation turn; never close on a correction turn.
- **Phonetic name re-confirm loop.** Agent repeatedly re-confirms a name that is a near-homophone of `{{firstName}}`. → **Gap.** Fix: add phonetic-name tolerance — accept a close phonetic match as confirmation rather than re-spelling indefinitely.
- **Rejected-a-category, not availability.** Caller rejects a category ("no weekends") and the agent transfers instead of re-querying. → **Gap.** Fix: instruct the agent to re-query remaining days/slots before treating the request as unsatisfiable.

## Tool-config edit sub-types

The four sub-types apply regardless of provider. Managed providers use their live API/MCP; self-hosted edits owned source and redeploys. Preserve provider-specific routing and tool-reference semantics.

| Sub-type | When to propose | Mechanics |
|---|---|---|
| **Edit a tool definition** | A failure traces to a specific field: vague `function.description`, ambiguous parameter, a `destinations[].description` that misleads the LLM about when to use the handoff. | PATCH the tool by id. Show before/after of the changed field only. |
| **Add a tool** (new) | A flow step requires a tool call no current tool covers. | Create the tool, then PATCH the relevant assistant's `toolIds` to include the new id. Always pair with a prompt edit telling the agent when to call it. |
| **Remove a tool reference** | An assistant is hallucinating calls to a tool it shouldn't have (squad inheritance is a common cause), or a tool's destinations include the assistant itself (self-handoff). | PATCH that assistant's `toolIds` to drop the id. Do NOT delete the tool itself unless no other squad member references it. |
| **Delete a tool** | The tool is dead weight — referenced by no squad member after proposed `toolIds` updates land. | Rare. Cross-reference every squad member's `toolIds` first. Prefer leaving the tool dormant over deleting; deletes are irreversible from this skill. |

## Tool-edit anti-patterns

- **Renaming `function.name`** — forces every prompt, tool description, and metric config that mentions the name to update atomically. Avoid unless the name is actively misleading.
- **Tightening `function.parameters` to fix one bad call** — a single bad-args call is usually a prompt issue (the LLM didn't have / didn't use the right inputs). Fix the prompt first.
- **Mass-deleting "unused"-looking tools** — a tool with no references in this agent's squad may still be referenced by another squad or a rare branch. When in doubt, only remove the *reference*, never the tool.

## Before/after templates

### Prompt edit

```
Proposed Change 1 of 4 — Gap (prompt)
  Surface: <assistant / agent name and id>, system prompt
  Addresses: 3 failures (Run abc, Run def, Call xyz)
  Diagnosis: Prompt does not specify what to do when caller asks for a manager.

  Before:
    (no governing section — uncovered)

  After (insert after "Escalation rules:"):
    If the caller asks to speak with a manager, do not promise a transfer.
    Tell them you'll create a callback ticket and confirm their preferred
    time. Do not commit to a specific manager or response time.
```

### Tool-definition edit

```
Proposed Change 2 of 4 — Conflict (tool)
  Surface: tool handoff_to_specialist (id abc1...9999), messages[request-start].content
  Addresses: 8 failures (replays once per user turn after handoff)
  Diagnosis: request-start message fires on every chat-mode rerouting event,
             producing a repeated "Perfect, thank you..." utterance.

  Before:
    "Great, you're verified! Next let's go over your goals for the
     program..."

  After:
    "" (empty — squad transitions are handled by the destination's first
         message; no source-side spoken transition needed)
```

### `toolIds` reference removal

```
Proposed Change 3 of 4 — Conflict (tool reference)
  Surface: assistant <name> (<id>), model.toolIds
  Addresses: 12 failures (self-handoff loop)
  Diagnosis: handoff_to_self_member tool is exposed via squad inheritance;
             LLM calls it as a no-op routing affordance.

  Before:
    toolIds: [..., "abc12345-...", ...]

  After:
    toolIds: [..., (removed), ...]   # tool definition stays — other members may still use it
```

### Upstream hand-off

```
Upstream Finding 1 of 1 — Upstream/data (no edit, hand off)
  Surface: NOT EDITABLE FROM THIS SKILL — test profile / squad-level dynamic variables
  Affects: 3 of 3 failed runs
  Diagnosis: Prompt depends on {{customerId}}, {{zipcode}}, {{vendorList}},
             {{appointment_rules}}, {{currentDate}}. Runtime shows all null/empty.
             Tool calls fire with literal placeholders (e.g. customerId="{{customerId}}").

  Recommendation:
    Inject these variables in the test profile (preferred for test runs) or the
    squad/assistant-level dynamic variables. After upstream is fixed, re-run the
    same scenarios and return to this skill if any failures remain.

  Hand-off skill: cekura-create-agent (Phase: Add Dynamic Variables) or
                  scenario / test-profile config.

  Deferred (re-evaluate after upstream fix):
    - The scheduling-node prompt + handoff tool description conflict around the
      "no questions?" gate. Looks like a real prompt-following bug but cannot
      be confirmed against broken variable state.
```

End with a summary line: `4 changes proposed and 1 upstream hand-off across 12 prompt-following failures (2 prompt edits, 2 tool edits; 1 gap, 2 conflicts, 1 ambiguity, 1 upstream).`

## Manual analysis vs. the automated prompt-improver

This skill defaults to the **manual path** because it produces explainable, scoped diffs tied to specific failures, works across mixed inputs in one pass, and respects the voice-failure filter from Phase 2.

Use the automated improver as a **fallback** when manual analysis is inconclusive (failures don't cluster, or the user wants a second opinion). Treat its suggestions as input to Step 3.4, not as the final proposal — still surface them as before/after blocks for user review.

## Phase 3 anti-patterns

- **Rewriting the whole prompt** because several sections look weak — only edit what the failures justify.
- **Adding catch-all clauses** ("always be helpful and accurate") — they don't change behavior.
- **Stacking conditions indefinitely** on one failure: if a clause gets >3 nested conditions, the underlying flow needs restructuring — flag it for the user instead of patching.
- **Editing dynamic-variable placeholders** (`{{...}}`) in prompts or tool definitions — they're owned by the calling system. Touch them only if the user explicitly asks.
- **Silently dropping a failure** because no clean fix is obvious — surface it as "no change proposed — needs human review."
- **Patching a tool's spoken `messages` to mask a prompt issue** — fix the prompt driving the tool call. Exception: when the tool's request-start message is itself the offending utterance (e.g. a verbose message that fires repeatedly), the tool edit is correct.
- **Using tool edits to enforce flow** — adding a tool to "force" the agent to do something is usually a prompt-clarity problem in disguise. Try the prompt fix first; only add a tool when the failure genuinely requires data the agent doesn't have.

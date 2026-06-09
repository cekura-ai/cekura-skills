# Phase 3 — Diagnosis Reference

Full classification table with examples, before/after templates per edit surface, tool-edit anti-patterns, the manual-vs-automated-improver guidance, and Phase 3 anti-patterns.

## Full classification table (with examples)

| Bucket | What it looks like | Example |
|--------|--------------------|---------|
| **Gap** | No section of the prompt addresses this situation, AND variable state is healthy. The agent improvised and got it wrong. | Prompt never says what to do if the caller asks for a manager → agent makes up a transfer policy. |
| **Conflict** | The prompt has two clauses that contradict, OR a clause contradicts the tool definition (e.g. tool description says "wait for X", prompt says "don't ask for X"), OR a clause contradicts the desired behavior implied by the failure. | Lab Availability prompt says "skip the question gate, fire handoff immediately"; handoff tool's `function.description` says "wait for user confirms no questions". LLM has no firing trigger and stalls. |
| **Ambiguity** | One section addresses it but the wording is vague enough the agent could read it either way, AND variable state is healthy. | "Wrap up the call politely" — no concrete steps, agent skipped the legally required disclosure. |
| **Upstream/data** | Variable state shows the runtime didn't have what the prompt or tool requires: a placeholder is `null` / absent / empty, a key name mismatches, or literal `{{...}}` strings survived into rendered messages or tool-call arguments. The prompt may also be improvable, but no prompt or tool edit fixes the root cause. | Lab Availability prompt depends on `{{leadId}}`, `{{zipcode}}`, `{{appointment_rules}}`. Runtime shows `appointment_rules=[]`, `leadId=null`. Tool calls fire with literal `leadId="{{leadId}}"`. Mock tools return canned data, masking the problem in the transcript. |

A failure can have both an Upstream/data root AND a Gap/Conflict/Ambiguity component. When both are present, pick the bucket that, if fixed, would produce the largest behavior change — usually Upstream/data, because phantom prompt fixes against broken variable state will fail re-validation the same way and obscure whether the prompt edit helped. Surface the secondary component as a "deferred — re-evaluate after upstream fix" note rather than proposing it for this iteration.

## Cekura-simulation infra / mock signatures → classify Upstream, never prompt-fix

> **In Cekura-simulation runs, the most common false "agent failure" is actually a harness, mock, or tool-contract artifact — not agent behavior. Classify these Upstream and never spend an iteration prompt-fixing them.** The signatures below recur on VAPI-squad agents tested through Cekura's simulation harness; each is a hard Upstream classification regardless of how "prompt-shaped" the transcript looks. When you see one, surface it as an Upstream hand-off and move on — do not propose a prompt or tool-definition edit to "work around" it.

| # | Signature (what you see) | Root cause | Verdict / hand-off |
|---|--------------------------|------------|--------------------|
| 1 | Tool result / VAPI log shows `handoff-destination-request` → HTTP **400 `"Only in-progress status accepted"`**, OR a `handoff_to_*` tool with `destinations: [{type:"dynamic"}]` errors and control never transfers (agent stalls after "let me move you to the next step"). | Cekura's sim harness webhook does not implement VAPI's dynamic `handoff-destination-request`. | **Upstream (harness gap).** Don't edit the prompt. Test-env mitigation only: hardcode the handoff to a concrete member id — note it as a sim fix, not an agent-quality fix. |
| 2 | Agent repeatedly calls a generic fallback tool (FAQ / query tool) instead of the intended data tool; the intended MCP sub-tool name (e.g. `find_lab_locations`) appears **zero times** in the call log. | VAPI failed to connect/list the MCP server's sub-tools at runtime, so the needed function isn't in the exposed tool set. | **Upstream (VAPI MCP load failure).** Do NOT write "use tool X" prompt edits — the tool wasn't available to call. |
| 3 | `"Couldn't get tool for hook. toolId … does not exist"` at call creation / handoff. | Tool wiring / mock-clone churn left a dangling toolId reference. | **Upstream (tool wiring / call assembly).** |
| 4 | Tool results like `"No matching input found for the provided data"`, `"No matching mock input found for tool: X"`, `{"success": false, "message": "recordId is required"}`, empty `availableSlots`, or stale dates (e.g. 2024 slots in a 2026 call). The agent made the *right* call; the mock returned an error/blank. | Mock/test-data gap: missing `freetext_params`, missing fields (e.g. `appointment_rules`), stale dates, or stringified-arg extraction failing to match. | **Upstream (test/mock data).** Route to fix the mock, never the prompt. See [[reference-vapi-squad-mcp-tool-mocking]] for the freetext_params / catch-all fix. |
| 6 | A tool fails because the backend requires a field that is neither in the tool's input schema nor a provided variable (e.g. `reschedule_enrollment_call` needs a `recordId` that exists nowhere) → guaranteed failure → transfer. | Tool/backend contract gap. | **Upstream (tool/backend contract).** Route to the backend/tool team; not promptable. |
| 7 | Caller asks for something the agent has no tool for (e.g. reschedule a *twin* appointment when only lab / enrollment-call reschedule tools exist) and the prompt's documented behavior is "transfer to human." | Missing capability — the transfer is the designed behavior. | **Upstream / working-as-designed.** Don't propose a prompt edit telling the agent to use a tool it doesn't have. |
| 8 | Run verdict reads `success: true` / `status: completed` but the call actually stalled into dead air / timeout. | The verdict flag doesn't always catch silence/stall. | Don't trust the flag alone — but equally **don't reclassify an infra stall (rows 1–4) as a prompt failure**. Confirm the failure shape against the transcript before classifying. |
| 9 | `"Model request attempt #1 failed"` (category `model`) in the log. | Transient LLM-provider hiccup / retry. | **Ignore** — not an agent or harness defect. |

Distinguishing rule: rows 1–6 and 9 are *environmental* — the agent could not have behaved differently given what it was handed. Row 7 is *by design*. None of them are fixed by editing a prompt or a tool definition reachable from this skill. If a failure matches one of these signatures AND also shows a genuine prompt-following gap on a *different* turn, classify the prompt gap normally and note the infra signature as a separate Upstream hand-off — don't let the infra artifact suppress a real prompt finding, and don't let a real prompt finding launder an infra artifact into a phantom edit. (Row numbering matches the session catalog; rows 5 and 10–11 live elsewhere — variable-placeholder leakage is already covered by the Upstream/data row above and the placeholder anti-pattern below.)

## Prompt-edit rule of thumb

| Bucket | Change type | Rule of thumb |
|--------|-------------|---------------|
| Gap | **Add** a new clause | Place it next to the closest related section, not at the end. Match the existing voice/format. |
| Conflict | **Edit** or **Remove** the contradictory clause | Resolve in favor of the behavior the failures expect. If both clauses have legitimate use cases, **scope** them with explicit conditions ("if returning customer..." / "if first-time caller..."). |
| Ambiguity | **Edit** for specificity | Replace vague verbs ("politely", "appropriately") with concrete steps. Add a checklist if there are >2 required actions. |

## Recurring prompt-edit patterns

Failure shapes that recur often enough to standardize the proposed-edit wording. When a failure matches one of these, prefer the canonical shape below over re-inventing — the wording has been validated across multiple agents and modes.

### DTMF / IVR navigation — same-turn digit-announcement pattern

**When it applies.** The agent under test has DTMF capability (VAPI `play_keypad_touch_tone` tool, ElevenLabs `play_keypad_touch_tone` built-in system tool, self-hosted equivalent) AND the failure shape is one of:

- Agent fired `play_keypad_touch_tone` but the transcript at that turn is empty / silent — no human-readable indication of which digit or why.
- IVR loops the same menu repeatedly; evaluator (which reads transcript, not audio) can't tell what the agent pressed and so can't confirm progress.
- Agent asked its real conversational opener (e.g. "Hi, does Dr. X still work here?") to the IVR menu instead of pressing a digit — a "spoke to IVR" failure.
- Debugging an IVR-navigation failure post-hoc is impossible because the transcript shows `[tool: play_keypad_touch_tone]` with no readable context for which digit was intended.

**Canonical edit (prompt).** Require the agent, on the same turn it presses DTMF, to verbally announce the digit in a short standardized phrase carrying NO other content (no questions, no small talk, no opener). Suggested wording (adapt to the agent's existing voice):

> When the IVR menu finishes playing, on the same turn you press the digit: (1) briefly announce the option you are selecting in a short phrase such as "Pressing 1 for administrative staff" or "Selecting option 1" — keep it to that one phrase, do not ask any question — AND (2) call `play_keypad_touch_tone` with that digit. If the same menu plays again because the keypress did not register, immediately announce the option and call the tool again on the next turn — never speak your conversational opener to an IVR.

**Why same-turn (not separate turn).** A separate "first say it, then press it next turn" structure introduces a 1–2 second gap during which the IVR may advance past the menu, making the announcement wrong by the time the DTMF fires. Same-turn only.

**Why the announcement matters even though DTMF is the actual signal.** Three reasons, in order of impact:

1. **Transcript-based evaluators** (Cekura scenario metrics, anything reading the transcript) can confirm "agent intended digit 1" from the announcement when the DTMF tone doesn't render cleanly in the transcript — without this, the same scenario looks indistinguishable from "agent stayed silent."
2. **The "no question" clause** prevents the most common IVR failure shape: agent asks its real conversational opener to the menu, never reaches a human, scenario fails on "didn't connect to representative."
3. **Production debug** — the announcement is the canonical place to verify post-hoc "did the agent press what we expected?" without listening to call audio.

**Placement in the prompt.** Pair with the existing "if you hear menu options, do X" / "Initial Audio Triage" guidance so the agent reads them together as one rule. Don't put it in a generic "edge cases" section — that's how the rule gets ignored in practice.

**Per-mode notes:**

- **VAPI / ElevenLabs** — prompt edit only. Edits land live, no orchestration-code change needed.
- **Self-hosted / pipecat** — prompt edit on the Cekura `description`. If the pipecat code currently routes DTMF *before* the LLM speaks (split paths for tool turns vs. speech turns), surface a paired hand-off telling the user to allow speech + DTMF on the same turn.
- **Self-hosted / websocket / `file`** — prompt edit. Verify the websocket code allows agent text + DTMF tool invocation on the same turn (some implementations force one OR the other). If it doesn't, add an orchestration-code edit in the same iteration so the prompt-side change can actually take effect.
- **Self-hosted / websocket / `offline`** — prompt edit only; flag the orchestration-code caveat above as a hand-off the user should verify.

### Over-eager transfer / premature-exit patterns (scheduling & support flows)

These recur on enrollment / appointment-scheduling squads. Each is a genuine prompt-following bug (Gap or Ambiguity) — fix it in the prompt; do NOT confuse it with the by-design transfers and harness artifacts catalogued in the Upstream-signatures section above. Before classifying any transfer as a bug, first confirm it is *over-eager* (fired on ambiguous / irrelevant / mid-task input) rather than a scripted, intended route or a missing-capability transfer (Upstream row 7).

- **Over-broad human-transfer trigger.** An `[IMMEDIATE HUMAN TRANSFER PROTOCOL]`-style clause with "or similar" fires on ambiguous utterances ("can I talk to somebody?", "speak to me", "hello?") that aren't actually requests for a human. → **Ambiguity.** Fix: scope the trigger to *explicit* requests for a human/agent/representative, and add a disambiguation step ("I can help with that here — did you want me to connect you to a person, or shall we continue?") before any transfer.
- **2-decline → premature transfer on scheduling.** The agent transfers to a human after the caller declines an offered slot twice. → **Gap.** Fix: 3-strike rule — on the 2nd decline ask for the caller's preferred day/time and re-query; only transfer on a 3rd strike.
- **Premature call-end on a mid-correction.** The agent ends the call (or fires `<endcall />` / closure) while the caller is still correcting a value (address, ZIP, name). This belongs to the **Early-End-Call Diagnose** sub-phase, not here — flag it there. Fix: gate closure on an explicit confirmation turn; never close on a turn whose content is a correction.
- **Phonetic name re-confirm loop.** The agent repeatedly re-confirms a name that is a near-homophone of `{{firstName}}` (e.g. "Misha" vs "Michelle"). → **Gap.** Fix: add phonetic-name tolerance — accept a close phonetic match as confirmation rather than re-spelling indefinitely.
- **Rejected-a-category, not availability.** The caller rejects a *category* ("no weekends") and the agent transfers instead of re-querying other days. → **Gap.** Fix: instruct the agent to re-query the remaining days/slots before treating the request as unsatisfiable.

## Tool-config edit sub-types (VAPI)

> **ElevenLabs analog.** ElevenLabs has the same four sub-types with provider-specific mechanics: edit a standalone tool's `tool_config.description` / `api_schema` / `parameters` via `PATCH /v1/convai/tools/{id}` (or a legacy inline tool in the agent's `prompt.tools`); add a tool via `POST /v1/convai/tools` then PATCH the agent's `prompt.tool_ids`; remove a reference by dropping the id from `prompt.tool_ids` (leave the workspace-scoped definition); delete only after `usage_stats` confirms no other agent references it. ElevenLabs has **no** spoken `messages`, `destinations`, or per-member scoping. See [`../providers/elevenlabs/phase-4-apply.md`](../providers/elevenlabs/phase-4-apply.md). The table below is written for VAPI; read "assistant" as "the single agent" and ignore the squad/destinations rows for ElevenLabs.


| Sub-type | When to propose | Mechanics |
|---|---|---|
| **Edit a tool definition** | A failure traces to a specific field on an existing tool: vague `function.description`, ambiguous parameter, an outdated / verbose `request-start.content` that's spoken on every fire, a `destinations[].assistantId` that's wrong, a `destinations[].description` that misleads the LLM about when to use the handoff. | PATCH the tool by id (Phase 4.1). Show before/after of the changed field only; don't redisplay the whole tool. |
| **Add a tool** (new) | A flow step requires a tool call that no current tool covers (e.g., the prompt says "look up the customer's last order" but no `lookup_order` tool exists). | Phase 4.1 creates the tool via POST `/tool`, then PATCHes the relevant assistant's `model.toolIds` to include the new id. The new tool also needs a corresponding prompt edit telling the agent when to call it — usually one prompt edit + one tool create + one toolIds patch. |
| **Remove a tool reference** | A specific assistant is hallucinating calls to a tool it shouldn't have access to (squad inheritance is a common cause), or a tool's destinations include the assistant itself (self-handoff). The tool may be legitimate for *other* members; the issue is the reference, not the definition. | PATCH that assistant's `model.toolIds` to drop the id. Do NOT delete the tool itself unless no other squad member references it. |
| **Delete a tool** | The tool is dead weight — referenced by no squad member after the proposed `toolIds` updates land. | Rare. Only propose after cross-referencing every squad member's `toolIds` (already fetched in Phase 1) and confirming nothing points at it. Prefer leaving the tool dormant over deleting; deletes are irreversible from this skill. |

## Tool-edit anti-patterns

- **Editing a tool's `function.name`** — the LLM has been calling the tool by its current name; renaming forces every other place that mentions the name (prompts, other tools' descriptions, downstream metric configs) to be updated atomically. Avoid unless the name is actively misleading.
- **Tightening `function.parameters` schemas to fix one bad call** — a single bad-args call usually means a prompt issue (the LLM didn't have / didn't use the right inputs). Fix the prompt first.
- **Mass-deleting "unused"-looking tools** — a tool with no references in this agent's squad members may still be referenced by another squad or by a workflow that fires only on rare branches. When in doubt, only remove the *reference*, never the tool.

## Before/after templates

### Prompt edit example

```
Proposed Change 1 of 4 — Gap (prompt)
  Surface: VAPI assistant <member_name> (<member_id>), system prompt
  Addresses: 3 failures (Run abc, Run def, Call xyz)
  Diagnosis: Prompt does not specify what to do when caller asks for a manager.

  Before:
    (no governing section — uncovered)

  After (insert after "Escalation rules:"):
    If the caller asks to speak with a manager, do not promise a transfer.
    Tell them you'll create a callback ticket and confirm their preferred
    time. Do not commit to a specific manager or response time.
```

### Tool-definition edit example

```
Proposed Change 2 of 4 — Conflict (tool)
  Surface: VAPI tool handoff_to_screener (id 880d...3177), messages[request-start].content
  Addresses: 8 failures (replays once per user turn after handoff)
  Diagnosis: request-start message fires on every chat-mode rerouting event,
             producing a repeated "Perfect, thank you..." utterance.

  Before:
    "Perfect, thank you for that! Your identity is verified. Now let's get
     into the exciting part - understanding your health goals..."

  After:
    "" (empty — squad transitions are handled by the destination's first
         message; no source-side spoken transition needed)
```

### `toolIds` reference removal example

```
Proposed Change 3 of 4 — Conflict (tool reference)
  Surface: VAPI assistant <member_name> (<member_id>), model.toolIds
  Addresses: 12 failures (self-handoff loop)
  Diagnosis: handoff_to_self_member tool is exposed to this member via squad
             inheritance; LLM keeps calling it as a no-op routing affordance.

  Before:
    toolIds: [..., "880d2980-...-...", ...]

  After:
    toolIds: [..., (removed), ...]   # tool definition itself stays — other members may still legitimately use it
```

### Upstream hand-off example

```
Upstream Finding 1 of 1 — Upstream/data (no edit, hand off)
  Surface: NOT EDITABLE FROM THIS SKILL — test profile / squad-level dynamic variables
  Affects: 3 of 3 failed runs
  Diagnosis: Prompt depends on {{leadId}}, {{zipcode}}, {{labVendors}},
             {{appointment_rules}}, {{currentDate}}. Runtime shows all null/empty.
             Tool calls fire with literal placeholders (e.g. leadId="{{leadId}}").

  Recommendation:
    Inject these variables in the test profile (preferred for test runs) or the
    squad/assistant-level dynamic variables in VAPI. After upstream is fixed,
    re-run the same scenarios and return to this skill if any failures remain.

  Hand-off skill: cekura-create-agent (Phase: Add Dynamic Variables) or
                  scenario / test-profile config.

  Deferred (re-evaluate after upstream fix):
    - Lab Availability prompt + handoff tool description conflict around the
      "no questions?" gate. Looks like a real prompt-following bug, but cannot
      be confirmed against broken variable state.
```

End with a summary line: `4 changes proposed and 1 upstream hand-off across 12 prompt-following failures (2 prompt edits, 2 tool edits; 1 gap, 2 conflicts, 1 ambiguity, 1 upstream).`

## Manual analysis vs. the automated prompt-improver

Cekura also exposes an automated prompt-improver endpoint that takes a run and returns suggested edits. This skill defaults to the **manual analysis path above** because:

- It produces explainable, scoped diffs (each tied to specific failures)
- It works across mixed inputs (results, runs, call logs) in one pass
- It respects the voice-failure filter from Phase 2

Use the automated improver as a **fallback** when the manual analysis is inconclusive (e.g., failures don't cluster, or the user wants a second opinion). Treat its suggestions as input to Step 3.4, not as the final proposal — still surface them as before/after blocks for user review.

## Phase 3 anti-patterns

- **Rewriting the whole prompt** because several sections look weak. Only edit what the failures justify.
- **Adding catch-all clauses** like "always be helpful and accurate" — they don't change behavior.
- **Stacking conditions indefinitely** to handle one-off failures. If a clause is getting >3 nested conditions, the underlying flow probably needs restructuring; flag it for the user instead of patching.
- **Editing dynamic-variable placeholders** (`{{...}}`) in either prompts or tool definitions — they're owned by the calling system. Touch them only if the user explicitly asks.
- **Silently dropping a failure** because no clean fix is obvious. Surface it to the user as "no change proposed — needs human review" rather than hiding it.
- **Patching a tool's spoken `messages` to mask a prompt issue.** If the agent says the wrong thing, fix the prompt that drives the tool call, not the tool's request-start message. The exception is when the tool's message is itself the offending utterance (e.g., a verbose request-start that fires repeatedly) — then the tool edit is correct.
- **Using tool edits to enforce flow.** Adding a tool just to "force" the agent to do something is usually a prompt-clarity problem in disguise. Try the prompt fix first; only add a tool when the failure genuinely requires data the agent doesn't have.

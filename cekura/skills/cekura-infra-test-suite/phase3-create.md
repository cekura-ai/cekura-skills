# Phase 3 — Create Evaluators on Cekura

**All infra test scenarios must use `scenario_type: "conditional_actions"`** — always, without exception. Behavioral instructions are not deterministic enough to reliably trigger specific infra behaviors like idle timers, interruptions, or DTMF. Never use behavioral mode for this suite.

Create a folder, then create each confirmed scenario with a conditional_actions payload and the right metrics. Follow the authoring rules below — they prevent the most common failures.

---

## 3a. Create a folder

Always group infra scenarios in a dedicated folder. Never dump them in the root.

```
POST /test_framework/v1/scenarios/folder/
{
  "name": "Infrastructure Test Suite",
  "project_id": <project_id>
}
```

Use the returned `folder_path` on every scenario in this suite.

---

## 3b. Required fields on every scenario

Every scenario must include:

```json
{
  "scenario_type": "conditional_actions",
  "folder_path": "Infrastructure Test Suite"
}
```

**`personality`** — choose based on what the scenario needs to test: accent, language, background noise level, interruption tendency. Use `GET /test_framework/v1/personalities/` to list available options. Do not default to a fixed ID.

---

## 3c. Authoring rules — read before writing any conditions

### Rule: Condition 0 depends on who speaks first (Q8 answer)

**If the bot speaks first** (Q8: yes) — the testing agent must wait silently. Set `action: ""` so the testing agent stays quiet until the bot's greeting is complete. If both sides fire a first message simultaneously, the STT picks up both speakers and enters a confused state.

```json
{ "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "", "fixed_message": false }
```

**If the caller speaks first** (Q8: no) — the testing agent initiates. Give condition 0 a non-empty action with the caller's opening line.

```json
{ "id": 0, "type": "standard", "condition": "FIRST_MESSAGE", "action": "Hi, I need help with [domain-relevant request].", "fixed_message": false }
```

**Override for start-of-call interruption tests** — if the scenario is specifically testing whether the bot handles being interrupted immediately as it begins speaking, the testing agent should fire into the bot's first message intentionally, regardless of Q8. Use `<interruption>` in condition 0's action to cut in as soon as the bot starts.

### Rule: After condition 0, always use action_followup with fixed_message: true

Infra tests exercise specific technical behaviors — not the content of what the bot says. Every condition after condition 0 must be `type: "action_followup"` with `fixed_message: true`. This delivers a scripted sequence regardless of the bot's exact phrasing, making tests deterministic and independent of wording changes in the bot's responses.

```
Condition 0 → FIRST_MESSAGE (standard — always the entry point)
Condition 1 → action_followup of 0, fixed_message: true
Condition 2 → action_followup of 1, fixed_message: true
...
```

Never use `standard` conditions after condition 0. Standard conditions match on bot speech content — infra tests have no business depending on what the bot says, only on triggering and observing a specific pipeline behavior.

### Rule: Use `<hold>` for idle timer tests, not `<silence>`

Per the Cekura conditional actions docs, `<hold>` produces dead air (background noise stops) while `<silence>` keeps background noise running — which may register as caller activity on sensitive VAD configurations and prevent the idle timer from firing.

For all other tag constraints (`<interruption>` placement, `<voicemail>` usage, `<dtmf>` syntax, etc.) refer to the **cekura-eval-design** conditional actions reference.

---

## 3d. Create each scenario

For each scenario confirmed in Phase 2, construct the conditional_actions payload using the rules above and the Q answers from Phase 1. Use the timing values discovered (idle threshold, escalation count, DTMF terminator) and the bot's domain to write appropriate caller actions.

## 3e. Attach metrics to every scenario

Use the **cekura-predefined-metrics** skill to identify which metrics to attach to each scenario. It has the full catalog, cost, constraints, and configuration guidance.

Two activation steps are required — missing either means the metric never fires:
1. **Toggle on at the project level**
2. **Add to individual evaluators**

One rule specific to infra scenarios: the Expected Outcome metric evaluates transcript text only — it has no access to audio, silences, or interruptions. Write its prompt to describe only what is visible in the conversation, not internal pipeline state.

---

## Phase 3 Gate

All scenarios are created on Cekura with:
- ✓ `conditional_actions` payload
- ✓ Metrics attached (per cekura-predefined-metrics skill)
- ✓ Placed in the `Infrastructure Test Suite` folder

Move to [Phase 4](phase4-orchestrate.md).

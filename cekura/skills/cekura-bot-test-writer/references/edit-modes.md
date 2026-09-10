# Edit modes

Work down the ladder and stop at the first mode that closes the gap. Every example below edits the
v1 spec shape: `scenarios[]` of `type: "conditional_actions"`, each with a stable `key`, a
`conditional_actions.conditions[]` turn list, and an `expected_outcome` the judge reads line by
line.

---

## KEEP — no edit

The most common correct outcome. Write the row and move on:

```
| <where speech services are built>:88-140 | agent · websocket | none — provider args identical | interruption-gauntlet still valid | KEEP | diff shows extraction only |
```

Nothing goes in the spec file. The decision table is the deliverable.

---

## TIGHTEN — the case reaches the behavior but never asserted it

Cheapest real edit: the script already produces the moment, so only `expected_outcome` changes.
No new turn, no extra call, no risk to the existing coverage.

```diff
   "expected_outcome": "The main agent should answer the testing agent's question about opening hours.
   The main agent should keep speaking through the testing agent's single-word backchannel instead of abandoning its turn.
+  The main agent should state the callback number before the call ends."
```

Rules: one statement per line, each starting `The main agent should`. Only "main agent" and
"testing agent" as speaker labels. Every statement must be fired by a turn that already exists —
a statement whose trigger the script never produces returns `blocked` on every run forever, which
is worse than no statement because it looks like coverage. Full contract:
`cekura-eval-design/references/expected-outcomes.md`.

---

## EXTEND — a compatible case can carry more turns

The default when coverage is genuinely missing. A longer deterministic call is far cheaper than
another one.

**Compatibility checklist — all five must hold:**

1. Same seat and transport as the behavior you are adding.
2. Same `language`.
3. Same test profile — extending a case forces its `agent_variables` on your new turns too.
4. The existing case does **not** end in a terminal condition before your turns run. Nothing
   extends past a hangup, a transfer or a voicemail drop.
5. The caller `role` still reads as one coherent person. If the extension needs a different
   motive, it is a different case.

```diff
         {
           "id": 4,
           "condition": "The agent has stopped talking and is waiting for the caller",
           "action": "Sorry about that. Can I book the Friday ten o'clock slot?",
           "type": "standard",
           "fixed_message": true
+        },
+        {
+          "id": 5,
+          "condition": "The agent confirms the Friday booking",
+          "action": "One more thing — what's your cancellation policy?",
+          "type": "standard",
+          "fixed_message": true
         }
```

Then add the matching `expected_outcome` line. Ids ascend and never collide; an
`action_followup` condition holds the integer id of the earlier condition it follows.

### Extending can break the case it extends

This is the failure that looks like success. New turns change the transcript the judge reads for
the **whole** case, not just for your part of it:

- **A statement that was unambiguous stops being one.** "The main agent should confirm the Friday
  booking" scored cleanly when Friday came up once. Your added turns discuss a second date, and
  now the judge is reading two confirmations and one contradiction.
- **Terminal assertions drift.** "The call ends after the main agent's goodbye" described the last
  turn in the case. It no longer does. `max_duration`, end-call and hang-up assertions stay last.
- **The call gets longer, and `max_duration` is a hard cut.** Turns past the limit never run, and
  every statement they were supposed to fire comes back `blocked` — neither pass nor fail, so the
  case stops proving anything without ever going red.
- **Condition matching is order-sensitive.** A `standard` condition matches an observable main-agent
  turn. A new turn that produces a similar-looking one earlier can capture the match a later
  condition was written for, and the rest of the script runs against the wrong state.

So after extending, **re-read every pre-existing `expected_outcome` line against the new full turn
list** and confirm each still fires exactly where it did. If one does not, you have not extended
this case — you have replaced it, and the honest move is to say so and justify it as a REPLACE.

### What NOT to do when extending

- Do not weaken or delete an existing statement to make room for the new turns.
- Do not renumber or reorder existing condition ids. Append.
- Do not reword an existing action so your addition flows better. If an existing turn is in the
  way, that is a REPLACE and needs its own justification.
- Do not change the case's `language`, `test_profile` or personality to suit the new turns — those
  five fields are the compatibility check, not an obstacle to route around.
- Do not restructure or reformat the case while you are in there.
- Do not pad the terminal action with a trailing `<silence>` or `<hold>`.

---

## REPLACE — the behavior changed shape

Same key, same coverage intent, new mechanics. Use it when the PR moved a threshold, renamed a
required phrase, or restructured a flow the case walks through.

```diff
         {
           "id": 1,
           "condition": "The agent greets the caller and offers help",
-          "action": "I wanted to ask about a booking. <silence time=\"8s\" />",
+          "action": "I wanted to ask about a booking. <silence time=\"14s\" />",
           "type": "standard",
           "fixed_message": true
         },
```

The idle prompt moved from 10s to 6s, so the old 8s pause — chosen to sit *below* the old timer —
now straddles the new one and the case would pass for the wrong reason. Say the old and new
values in the pull-request comment; a reviewer cannot see a threshold from a JSON diff.

Never use REPLACE to make a red case green. If the assertion is false because the agent
regressed, that is step 6 of the skill: stop and report.

---

## RETIRE — the behavior is gone

A case whose code path was deleted goes red forever, and a permanently red case teaches reviewers
that red means nothing. Deleting it is a real contribution.

Delete the whole scenario object, then in the same edit:

- update the count in the coverage note and any workflow step that asserts it;
- state in the pull-request comment what coverage was lost and whether anything now covers it;
- if the case is being *repurposed* rather than dropped, that is not a retirement — it is a new
  key, because a key whose meaning changed silently corrupts its own history.

**When coverage is folded rather than dropped, record where it went.** A case that absorbs another
case's job says so in its own `name` or the coverage note — `folded in: idle-recovery (ordered idle
prompts, agent-driven end)`. Without that line a reviewer cannot tell merged coverage from lost
coverage, and neither can you in three months.

---

## ADD — nothing covers it and nothing can absorb it

One more live call on every run of the suite, forever. Justify it as that, not as a good idea.

An ADD is right for a distinct subsystem, seat, transport, provider, language, or terminal call
lifecycle. It is wrong for a variation of something already covered — a second interruption case
at a different offset, a provider swap, a rephrased prompt.

**Budget arithmetic — actually count it.** Before you commit, state the case count before and
after, and what that costs per run: six cases to seven is a 17% increase on every future run of
this gate, forever, and the increase compounds with each PR that reaches for ADD. If the coverage
note declares a count, name the new one and what paid for it — a case whose drop-if fired (see
`change-triage.md`), or two cases merged under the older key. If nothing can pay, say so and let
the user approve the growth. Do not grow the suite silently.

A new scenario copies the house shape of the file it joins:

```json
{
  "key": "spanish-booking-happy-path",
  "name": "Spanish booking happy path",
  "type": "conditional_actions",
  "language": "es",
  "tags": ["ci", "language"],
  "conditional_actions": {
    "role": "Eres Marta, llamas para reservar una cita el viernes.",
    "conditions": [
      { "id": 0, "condition": "FIRST_MESSAGE", "action": "", "type": "standard", "fixed_message": true },
      { "id": 1, "condition": "The agent greets the caller in Spanish", "action": "Hola, quiero reservar una cita para el viernes.", "type": "standard", "fixed_message": true }
    ]
  },
  "expected_outcome": "The main agent should conduct the entire call in Spanish.\nThe main agent should confirm a Friday appointment before the call ends."
}
```

Every condition carries all five fields. `id: 0` is always `FIRST_MESSAGE`, and its action is
empty only when the agent genuinely speaks first. Set `language` explicitly on the case — a
missing one silently runs English.

---

## After any edit — the checklist

Run all of it, in order. Items 3–8 are what a reviewer would catch, and catching them yourself is
the difference between a suite edit that gets merged and one that gets argued about.

1. `python3 <plugin>/skills/cekura-infra-test-suite/scripts/lint_suite.py <spec> --strict`.
2. Dry run against Cekura (`--dry-run`) — the only place an unenabled metric, an unreachable
   personality or a wrong channel shows up. It must return `valid: true`.
3. **No key changed.** Added keys are unique and descriptive; no existing key was renamed.
4. **Every pre-existing statement still fires where it did**, in every case you touched.
5. **Every new statement is fired by a written turn.** Nothing is permanently `blocked`.
6. **No assertion was loosened** — no dropped metric, no relaxed outcome, no removed turn.
7. **Counts.** Cases before and after, and the coverage note updated if it declares a number.
8. **The diff is only what you meant.** No reformatting, no reordering, no untouched case
   restyled, nothing outside the spec and its coverage note.

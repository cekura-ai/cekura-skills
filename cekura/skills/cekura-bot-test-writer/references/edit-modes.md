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

Watch the terminal ordering: `max_duration`, end-call and hang-up assertions stay last. Adding a
turn after the one that proves a clean ending destroys that proof.

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

---

## ADD — nothing covers it and nothing can absorb it

One more live call on every run of the suite, forever. Justify it as that, not as a good idea.

An ADD is right for a distinct subsystem, seat, transport, provider, language, or terminal call
lifecycle. It is wrong for a variation of something already covered — a second interruption case
at a different offset, a provider swap, a rephrased prompt.

**Budget arithmetic.** If the coverage note declares a count, name the new one and what paid for
it: a case whose drop-if fired (see `change-triage.md`), or two cases merged under the older key.
If nothing can pay, say so and let the user approve the growth — do not grow the suite silently.

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

## After any edit

1. `python3 <plugin>/skills/cekura-infra-test-suite/scripts/lint_suite.py <spec> --strict`
2. Dry run against Cekura (`--dry-run`), which is the only place an unenabled metric, an
   unreachable personality or a wrong channel shows up.
3. Re-read your own diff for the four things a generator gets wrong and a contributor does not:
   a changed key, a reformatted untouched case, a statement no turn fires, and a loosened
   assertion.

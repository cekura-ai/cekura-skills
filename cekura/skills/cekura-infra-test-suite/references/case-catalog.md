# Case catalog

Nine case templates for a voice-agent CI gate, in priority order. They are the distillation of a
suite that survived contact with a real pipeline: every one of them exists because a specific code
change broke something a transcript could see.

**Use them as starting shapes, not as a checklist.** Phase 1 discovery decides which apply. Each
carries a **drop-if** condition — when it fires, the case is a dead test and costs a call per run
while asserting nothing. Rule 2 (only test what's there) beats coverage anxiety every time.

A suite of 10–12 usually lands as: cases 1–5 nearly always, 6–9 where the codebase supports them,
plus one or two cases specific to what this repo actually gets wrong (see "Bug-history cases").

---

## How to read the "asserts" column

Two levels, and knowing which one you are on keeps a case honest:

- **Sequence and count** — what you can assert without knowing the configured value. "The reprompt
  fires, then a second one, then the agent ends the call." Correct regardless of whether the idle
  timer is 8s or 30s.
- **Threshold and exact value** — what you can assert once discovery has read the number and the
  string out of the code. "The first reprompt says *Are you still there?* and does not fire before
  8s."

Always reach for the second when Phase 1 found the value. Fall back to the first when it is set in
a provider dashboard the repo cannot see. Never guess a threshold and assert it.

---

## 1. Interruption gauntlet

Four assertions, one call. The single highest-yield case in the suite.

| | |
|---|---|
| **Shape** | barge during a deliberate pause (agent must ignore it) → one-word backchannel mid-sentence ("mhm") (must ignore) → decisive two-word interrupt ("stop — wait") (must stop speaking) → barge into a long silence (must respond) |
| **Sequence asserts** | the agent stops on the decisive interrupt and not on the backchannel; it answers the barge that follows the silence |
| **Threshold asserts** | the real `min_words` / interrupt gate: one word below it, exactly at it, one above |
| **Drop if** | never — every pipeline with a barge-in path needs this |

Each barge is `<interruption time="Xs" />` at the very start of an `action_followup` action. Use a
positive time that clears the lead-in; `0s` only where the agent is already mid-sentence.

## 2. Mid-sentence pause

| | |
|---|---|
| **Shape** | the caller pauses ~1.2s in the middle of one sentence, then finishes it |
| **Sequence asserts** | **exactly one** reply, to the complete utterance — the agent must not answer the fragment |
| **Threshold asserts** | probe at the endpointing window ±0.2s |
| **Drop if** | never |

1.2s is shorter than any plausible endpointing window, so the assertion holds without knowing the
configured value. Use `<silence>` (interruptible), not `<hold>`.

## 3. Idle escalation to hangup

| | |
|---|---|
| **Shape** | the caller goes silent and stays silent |
| **Sequence asserts** | the reprompt sequence fires in order, the configured number of times, then the agent ends the call |
| **Threshold asserts** | fires at the configured threshold; each prompt matches its exact string from the code |
| **Drop if** | the codebase has no idle timer |

Go silent for longer than any plausible timeout when the value is unknown. A condition whose action
is a long deliberate pause is the one place `type: "standard"` is correct — an `action_followup`
re-executes its action verbatim on interruption, restarting the pause and looping forever. **When
two conditions both hold pauses, their predicates must be tellable apart**, or the matcher re-picks
an already-executed condition and you have traded a replay loop for a re-match loop.

## 4. Full task, out of order

| | |
|---|---|
| **Shape** | the complete happy path, but the caller asks the questions in a different order than the prompt authors them, and repeats one question verbatim later |
| **Sequence asserts** | the task still completes; the repeated question is answered **both** times |
| **Drop if** | never |

The repeat is an echo-absorption tripwire: a pipeline that dedupes or swallows a repeated user turn
fails here and nowhere else.

## 5. Premature disengagement

| | |
|---|---|
| **Shape** | caller signals completion — "that's everything I needed" — **without** a goodbye → caller then asks one more real question → caller closes |
| **Sequence asserts** | the agent answers the extra question rather than treating the completion signal as the end; no agent turn repeats the previous agent turn |
| **Threshold asserts** | — |
| **Drop if** | never |

The gradeable behavior is **whether the agent keeps engaging**, and that holds whether or not the
agent can hang up. Do not grade the farewell wording, who ended the call, or the call-end reason:
those are structural, and the judge rules exclude them. An agent *with* an end-call tool can also
assert the agent-driven end here, because then termination is this case's declared point — but that
is the extra half, not the case.

The second assertion catches the filler loop: an LLM retry path that emits the same short line
("Okay.") on consecutive turns reads on a call as a hung agent.

Also catches the "Okay." loop — an agent repeating a filler line to itself.

## 6. IVR / voicemail navigation

| | |
|---|---|
| **Shape** | the agent dials out and meets a menu or a voicemail greeting with pauses inside it |
| **Sequence asserts** | the agent does not treat menu silence as its turn; it presses the right key, or leaves a coherent message after the beep |
| **Drop if** | the agent never places outbound calls |

`<ivr text="…" />` and `<voicemail text="…" />` must each occupy the **entire** action, self-closing.
Post-beep speech goes in a later `action_followup`. When `<ivr>` is in play, digits the agent presses
appear in the transcript, so a condition can match on which key it chose.

## 7. Degraded audio

| | |
|---|---|
| **Shape** | packet loss plus background noise while the caller states something that must survive — an order number, a date |
| **Sequence asserts** | the agent either transacts correctly **or** explicitly asks for a repeat. Both are passes; silently proceeding on a misheard value is the failure |
| **Threshold asserts** | the failure modes specific to the STT provider discovery found |
| **Drop if** | never |

Never assert that the impairment happened — a transcript cannot show it. Assert what the agent did
about it. Never assert a *spelled* value: STT normalises `"7 3 9 1"` to `"7391"`.

## 8. Tool call under pressure

| | |
|---|---|
| **Shape** | a turn that triggers a tool, and the caller barges during the "one moment" filler |
| **Sequence asserts** | the tool still fires and the agent recovers the thread rather than restarting it |
| **Drop if** | the agent has no tools, or no tool result is ever visible in the transcript |

## 9. Language switch

| | |
|---|---|
| **Shape** | the caller switches language mid-call, then switches back |
| **Sequence asserts** | the agent follows both switches and keeps the facts stated before the switch |
| **Drop if** | the agent is single-language, or a language is configured with no matching voice or STT model |

Set the case `language` to `multi` and pick a personality whose language matches the opening turns.

---

## Bug-history cases

The highest-signal input available, and nothing substitutes for it:

```bash
git log --oneline --since='6 months ago' -- <pipeline/turn-taking/tool paths>
git log --oneline --grep='fix' -i --since='6 months ago' -- <same paths>
```

A file that keeps getting fixed is a file that keeps breaking. Read the three or four most recent
fixes on the call path, ask "what would a transcript have shown when this was broken", and if the
answer is concrete, that is a case worth a slot — ahead of anything in this catalog that is only
theoretically relevant.

---

## What deliberately does not belong here

Cases that test the **testing framework** rather than the agent:

- tag-coverage matrices — proving `<speed>` / `<volume>` / `<spell>` render
- assertions that ambience played, a beep sounded, or volume changed
- anything asserting the simulator's own behavior

They belong to whoever maintains the simulator. In a customer's suite they assert someone else's
internals and fail for reasons the customer cannot fix.

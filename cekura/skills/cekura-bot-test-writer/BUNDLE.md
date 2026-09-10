---
name: cekura-bot-test-writer
description: >
  Use when a pull request changes a voice agent and the repository's committed Cekura
  test suite has to keep up: "update the tests for this PR", "extend test coverage for
  these changes", "does this PR need new voice tests", "keep cekura.tests.json in sync",
  "add a regression test for this bug fix", "review the suite against my diff", "run a
  test writer on every PR". Reads the PR diff against its merge base, decides per change
  whether existing cases already cover it, and makes the smallest edit that closes a real
  gap — most often no edit at all. This skill updates an existing suite; it never creates
  one from scratch (use cekura-infra-test-suite), never authors dashboard evaluators (use
  cekura-eval-design), and never places a live call.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

> **Condensed skill bundle** — loaded on the fly because the Cekura plugin is not installed in this session.
> Full reference files included at the end of this document: `change-triage.md`, `edit-modes.md`.
> Any other `references/…` file mentioned below ships only with the installed plugin — install it for the complete set: https://docs.cekura.ai/mcp/overview

Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="cekura-bot-test-writer"`, `verification_tag="ack:cekura-bot-test-writer:3d7k2m"`, and `plugin_version="0.15"`. It returns immediately and lets Cekura see which skills are in use.

# Cekura Bot Test Writer

## Purpose

Keep a repository's committed Cekura suite in step with the bot it tests, **one pull request at
a time**. The unit of work is a diff, not a repository: read what changed, decide whether the
existing cases already prove it, and make the smallest edit that closes a genuine gap.

The suite is source code with a history. Its value comes from cases whose keys and meanings hold
still across commits, so a red today is comparable to a green last month. An updater that
regenerates, renames, reflows, or grows the file every time it runs destroys exactly that.

## Where this skill sits

| Situation | Skill |
|---|---|
| The repository has no committed suite yet | **cekura-infra-test-suite** — creation, coverage matrix, CI wiring |
| A suite exists and a PR changed the agent | **this skill** |
| Dashboard evaluators, adaptive or exploratory scenarios | **cekura-eval-design** |
| Production calls are failing and need reproducing | **cekura-flag-call-log-failures** → **cekura-generate-scenarios** |
| A failure needs a fix, not just a test | **cekura-self-improving-agent** |

If Step 0 finds no suite, stop and hand over to `cekura-infra-test-suite`. Do not invent one
inside someone's pull request: a suite authored mid-review has no baseline, so its first run is
unreadable — nobody can tell a real regression from a case that was never right.

## The default answer is "no change"

Most pull requests do not change anything a caller can hear. Refactors, logging, type hints,
dependency bumps, internal renames, tests, docs and CI all normally end at **no change**, and
saying so with evidence is a complete, correct result — not a lazy one.

A suite that gains a case per pull request stops being a gate. Every case is a live call: it
costs credit on every run, adds wall-clock to every merge, and one more flake-prone red that
reviewers learn to wave through. **The cheapest edit that closes the gap is the right one, and
the cheapest edit is usually none.** Produce the decision table either way — the reasoning is the
deliverable when the file does not change.

## Workflow

### 0. Find the suite, then resolve the diff

```bash
grep -rl 'schemas/test-suite' --include='*.json' .          # definitive: a spec's $schema line
git ls-files | grep -Ei '(cekura|eval|suite|tests?).*\.json$'  # candidates
grep -rln 'cekura' .github/workflows .gitlab-ci.yml Jenkinsfile 2>/dev/null  # who runs them
```

A spec can live anywhere and be called anything — the `$schema` line is the only reliable
signal, and the workflow that posts it tells you which specs are live. Read every one you find
**in full**, along with whatever the repository uses as its coverage note (a README section, a
sibling markdown file), which records what each case is for and what was deliberately left
uncovered. Two suites — a fast PR tier and a broad pre-deploy tier — is a common shape; know
which one a change belongs in before editing either.

Then resolve an explicit base. Never diff the working tree, and never infer the change from a
branch name, a commit message, or a task summary:

```bash
BASE_REF="${PR_BASE_REF:-origin/main}"
git fetch origin "${BASE_REF#origin/}"
MERGE_BASE="$(git merge-base "$BASE_REF" HEAD)"
git diff --name-status -M "$MERGE_BASE" HEAD     # -M so renames read as renames
git diff --stat "$MERGE_BASE" HEAD
```

If the base or `HEAD` will not resolve, stop and say so. A diff against the wrong base either
hides the change or floods you with someone else's.

### 1. Translate each changed hunk into observable behavior

Read the hunks, not the filenames. For each one, answer a single question:

> Would the **transcript of an existing case** differ because of this change — or is there a new
> transcript-observable behavior that no current case produces?

If neither, the row is `none`. `references/change-triage.md` carries the per-layer table — prompt
text, providers, thresholds, tools, language, transport, lifecycle, error handling — with the
decision each class usually earns and the traps in the ones that look safe but are not.

**Reason from the layers, never from the framework.** Trace the runtime entrypoint and follow the
call path; do not decide anything from an import list or a framework's name. Every voice agent
has the same layers — something turns audio into text, something decides what to say, something
speaks it, something arbitrates whose turn it is, something calls tools, something ends the call
— whether they are Pipecat processors, LiveKit agent hooks, a vendor SDK's callbacks, or four
hundred lines of hand-rolled asyncio. A framework tells you *where* a layer lives, and nothing
about whether the change is observable. Two repositories doing the same thing differently earn
exactly the same triage, because the caller hears the same thing either way.

Two rules that decide most rows:

- **Observable means in the transcript.** Spoken content, turn order, digits recognised, a call
  that ends cleanly, a literal tag that must not leak. Not a waveform, not a log line, not which
  internal processor ran. If the only proof is a metric, say which metric — and check it is
  enabled on the agent before relying on it.
- **Record the seat and the transport.** Most repositories build only the agent under test, and
  then the seat is fixed and can go unsaid. Where one builds both it and the simulated caller,
  each seat runs different code and proving one proves nothing about the other. The same applies
  to a repository with more than one assembly — one entrypoint per transport is the usual shape —
  so a shared change reaching two of them is two rows, not one.

Quote a `file:line` for every threshold and every agent phrase you rely on. A sourced number
turns "the idle timer fires" into "it fires at 8s and says *Are you still there?*"; an unsourced
one writes a case that fails the suite instead of the bot.

### 2. Write the decision table before editing

This table is the deliverable. It goes in the handoff and in the pull-request comment, so a
reviewer sees the reasoning without the repository carrying a document that rots:

| Changed path / symbol | Seat + transport | Observable change | Existing case | Decision | Evidence |
|---|---|---|---|---|---|

One row per changed behavior, `none` included. Decisions come from the ladder in step 3. A row
whose decision is anything but `none` names the case key it touches.

### 3. Pick the cheapest edit on the ladder

Work down this list and stop at the first mode that closes the gap. `references/edit-modes.md`
has before/after JSON for each one, plus the compatibility checklist that decides whether a case
can absorb new turns at all.

| Mode | When | Cost |
|---|---|---|
| **KEEP** | An existing case already produces the changed behavior | none |
| **TIGHTEN** | The case triggers the behavior but never asserted it — add 1–2 `expected_outcome` lines | none |
| **EXTEND** | A compatible case can carry extra turns that trigger the new behavior | a longer call, no new one |
| **REPLACE** | The behavior changed shape — rewrite the turn in place, keep the key and the coverage | none |
| **RETIRE** | The behavior is gone — delete the case, or repurpose it deliberately | frees a call |
| **ADD** | A distinct subsystem, seat, transport, provider, or terminal call lifecycle that nothing covers | one more live call per run, forever |

**EXTEND is the default when coverage is genuinely missing.** A case can absorb new turns only
when the seat, transport, language, test profile and terminal condition all match, and the new
turns are reachable after the existing ones — nothing extends past a hangup. Merging aggressively
is right; a longer deterministic call is cheaper than a new one. An incoherent megatest is not.

**Extending can break the case it extends**, and that failure looks like success: a statement that
was unambiguous now reads against two similar turns, a terminal assertion describes a moment that
is no longer last, or the call outgrows `max_duration` and the tail comes back `blocked` — never
red, just no longer proving anything. After extending, re-read every pre-existing statement
against the new full turn list. `references/edit-modes.md` has the four failure modes and the
what-not-to-do list.

**ADD needs a budget, not just a reason.** If the suite's coverage note declares a case count,
adding means retiring something: a case whose drop-if condition has fired, or two cases that
merge. Never grow a suite silently — name the new count and what paid for it.

### 4. On a bug-fix PR, write the fix's own failure

If the pull request fixes a bug, the coverage you add or extend must be **the thing that was
broken**. A case that would have passed before the fix is decoration.

So name, in the pull-request comment, the transcript difference: what the pre-fix agent said or
did at that turn, and what it says now. If you cannot name one, the fix was not
transcript-observable — mark the row `uncovered`, say what would be needed (a metric, a
different transport, a fixture), and leave it. That is an honest gap; a case that passes either
way is a false one.

**Do not claim must-fail-first verification.** This skill places no calls, so it never observes
the old failure. Say what the case would catch and why; do not report it as proven.

### 5. Edit like a contributor, not a generator

- **Keys are permanent.** A key joins today's result to last month's. Renaming a case resets its
  history; quietly changing what a key means is worse, because the history stays continuous while
  the meaning moves. Retire a case explicitly or leave its key alone.
- **Match the file.** No reformatting, no reordering, no restyling to this skill's taste, no
  touching cases the diff did not implicate. A one-line semantic change is reviewable; the same
  change buried in a reflow is not.
- **Fix only what you touched.** Pre-existing lint warnings on untouched cases belong in their own
  pull request.
- **`expected_outcome` is the judge's prompt.** Read
  `cekura-eval-design/references/expected-outcomes.md` before writing a statement. When *editing*,
  three mistakes dominate: adding a statement no written turn fires (it returns `blocked` forever),
  naming a speaker anything but "main agent" / "testing agent", and slipping a subjective
  descriptor — "promptly", "clearly" — where an observable phrase belongs.
- **Tag syntax is executable.** `<interruption time="Xs" />` opens its action and its condition is
  `action_followup`; `<ivr …/>` and `<voicemail …/>` occupy the whole action; `<silence>` is
  interruptible and `<hold>` is not; `<audio>` cannot be referenced from a spec at all. The full
  rules live in `cekura-infra-test-suite`.

### 6. Never weaken an assertion to make the suite pass

When the pull request makes an existing assertion false, exactly one of two things is true:

1. **The product deliberately changed.** Update the case, and say in the pull-request comment
   which contract moved and where the change authorises it.
2. **It is a regression.** Stop. Report the case, the assertion, and the hunk that broke it.

Choosing between those two by editing the test is the failure this skill exists to prevent. When
the diff does not settle it, ask — do not soften the line, delete the metric, drop the turn, or
relax the outcome. A green suite bought that way costs more than a red one.

### 7. Lint, then dry run — never live

```bash
SPEC=<the spec you edited>      # whatever this repository calls it

python3 <plugin>/skills/cekura-infra-test-suite/scripts/lint_suite.py "$SPEC" --strict

CEKURA_API_KEY=… CEKURA_BASE_URL=… \
  python3 <plugin>/skills/cekura-infra-test-suite/scripts/run_suite.py \
  --spec "$SPEC" --dry-run --agent-id "$CEKURA_AGENT_ID"
```

The linter is offline and free; it mirrors the server's own tag validators. The dry run
(`POST …/run_scenarios_json/?dry_run=true`) is the only write-shaped request this skill may make,
and it is the only place that catches an unenabled metric slug, an unreachable personality, or a
channel the agent was never configured for. **An edited spec that has not returned `valid: true`
is not finished** — say that in those words rather than handing over a file that merely looks
complete.

This skill never starts a real run. A test writer that dials on every push bills on every push;
the suite's own workflow places calls on its own trigger, where someone chose the cost.

On a fork pull request there are no secrets by design. Stop at the lint, label the change
unvalidated in the handoff, and let the maintainer's run validate it.

### 8. Hand off

Work the checklist at the end of `references/edit-modes.md` first — keys unchanged, every
pre-existing statement still firing where it did, nothing newly `blocked`, nothing loosened,
counts stated, the diff only what you meant.

Then report, in this order: the decision table; the files and case keys changed, with the case
count before and after; the exact dry-run result or the reason there is none; and every row you
left `uncovered` with what it would take. Re-check the final diff against the changed-file list
you recorded in step 0.

**Scope is the spec plus its coverage note, and nothing else.** Runtime code, workflows, deploy
configuration, Cekura records, a metric that does not exist — all out of bounds, however small the
diff and however sound the reasoning. If covering a behavior needs one of them, name the blocker
and let the user decide. Changing the product to make your own test possible is not a shortcut,
it is a different pull request.

## Running this on every pull request

`references/pr-automation.md` carries the CI wiring: label-triggered versus automatic, the paths
filter that keeps it off docs-only changes, how the job commits to a same-repository branch and
degrades to a comment on a fork, and the guard that fails the job if anything outside the spec
files was touched. Two defaults there are not negotiable — the job **validates only**, and it
**writes nothing but spec files**.



---

## Appended reference — change-triage.md

# Change triage

One question per changed hunk:

> Would the transcript of an existing case differ because of this change — or is there a new
> transcript-observable behavior that no current case produces?

Everything below is a shortcut to answering it. It is not a licence to skip reading the hunk: the
table says what a class of change *usually* means, and the "trap" column exists because the
exceptions are where suites rot.

## Layers, not frameworks

The rows below are **layers of a voice agent**, not files, libraries or frameworks. A turn-taking
threshold is a VAD parameter in one repository, a turn-detector config in another, and a
hand-written silence counter in a third; a tool is a framework's function-calling decorator here
and a hand-rolled JSON dispatch there. The triage is identical in all of them, because the triage
question is about what the caller hears, and the caller cannot tell which library produced it.

So find the layer by tracing the entrypoint, not by recognising a name. If a change does not
belong to any row below, that is not a gap in the table — ask the one question directly: would an
existing case's transcript differ, or is there a new transcript-observable behavior? A repository
with no framework at all triages exactly the same way.

## By layer

| Changed | Usually | Why, and the trap |
|---|---|---|
| **System prompt / persona text** | `none` for tone; `TIGHTEN` or `REPLACE` for a new rule | Wording changes are not coverage events. A new *rule* ("never quote a price without the disclaimer") is: it is a sentence the agent must now say, and an existing case that reaches that moment can assert it. Trap: asserting the exact new phrasing rather than its content — the next copy edit turns your case red for nothing. |
| **A quoted agent phrase an existing case asserts** | `REPLACE` | The case is now wrong and will go red on the next run. Update the asserted content, keep the key. Trap: this is the one case where *not* editing is the failure. |
| **STT provider / model / language config** | `none`, unless a case asserts recognition | Swapping a recogniser changes accuracy, not the script. It earns coverage where recognition is the point: spelled letters, digit strings, an alphanumeric id, a non-English utterance. Trap: grading a normalisation the STT does anyway ("said *twenty-five*, not *two five*"). |
| **LLM provider / model / temperature** | `none` | The judge reads what was said, not which model said it. Regression risk is real but diffuse; it belongs to the whole suite, not to a new case. Trap: an ADD here is how suites double in size with no new coverage. |
| **TTS provider / voice / speed** | `none` | Nothing about a voice is transcript-observable. Trap: `<speed>` and `<volume>` exercise a path; neither is ever the assertion. |
| **VAD / endpointing / turn-detection thresholds** | `TIGHTEN` or `EXTEND` on an existing timing case | The observable is *who speaks next and when*: does the agent wait through a mid-sentence pause, does it cut in. Extend the case that already has a silence or interruption turn. Trap: a threshold moved by 100ms that no written pause straddles changes no transcript — quote the old and new values and the pause in the case before deciding. |
| **Interruption / barge-in handling** | `EXTEND`, else `ADD` | Directly observable: the agent stops, and what it says next. Needs `<interruption time="Xs" />` opening an `action_followup` against speech already in progress. Trap: interrupting a greeting at `0s` interrupts nothing. |
| **Idle timer / "are you still there" / max duration** | `TIGHTEN`, or `REPLACE` when the value moved | The prompt line and the timeout are both observable, and a changed timeout usually invalidates the `<silence>`/`<hold>` in the existing case. Trap: a `<silence>` shorter than the new timer proves nothing and reads as coverage. |
| **DTMF / IVR navigation** | `EXTEND` on the IVR case, else `ADD` | Digits are observable and deterministic — good value per call. `<dtmf digits="…" />` may share an action with speech; `<ivr text="…" />` may not. Trap: post-IVR speech pushed into the same action never plays. |
| **Voicemail / answering-machine detection** | `EXTEND`, else `ADD` | A distinct terminal lifecycle: the agent should leave a message, or hang up, and not carry on a conversation with a beep. `<voicemail …/>` occupies its whole action. Trap: stacking further turns after a terminal outcome. |
| **A new tool / function the agent can call** | `ADD`, or `EXTEND` if a case already reaches that moment | Observable through what the agent says once the tool answers. Needs mock data the case controls; without it you are testing a live dependency, not the bot. Trap: asserting the call happened rather than what the caller heard. |
| **A tool's arguments, error path, or removal** | `TIGHTEN` for the error path; `RETIRE` for removal | The failure branch is the one nobody covers: what does the caller hear when the lookup times out. Trap: leaving a case that calls a tool the code no longer has — it goes red forever and gets waved through. |
| **Transfer / handoff / end-call** | `TIGHTEN`, else `ADD` | Terminal lifecycle. Assert the spoken hand-off and that the call ends; grade the goodbye only when termination is the point of the case. Trap: a farewell assertion smuggled into an unrelated case. |
| **A new supported language** | `ADD` (one case, `language` set explicitly) | A language path is a distinct pipeline: recogniser, prompt, voice. Nothing about the English cases proves it. Trap: forgetting `language` on the case, which silently tests English. |
| **Transport (WebSocket, WebRTC, SIP, telephony)** | `ADD` only if the suite cannot already reach it | Different assembly, different failure modes. But the run *channel* is a request parameter, not a spec field — the same committed case can be dialled over another channel by CI. Check the workflow before adding a file. Trap: a new case that differs from an existing one only by transport. |
| **Dynamic-variable / config plumbing** | `TIGHTEN` when the agent speaks the value | `agent_variables` reach the agent as dynamic variables and only matter if it already reads that name; `caller_variables` never reach it. Trap: inventing keys, which the agent silently ignores while the case looks specific. |
| **Retries, timeouts, error handling** | `TIGHTEN` if a case can reach the branch | Worth covering only where the caller hears something ("let me try that again"). Trap: a branch no scripted turn can trigger — the statement returns `blocked` on every run. |
| **Logging, tracing, metrics emission** | `none` | Not in the transcript. If it matters, it is a monitoring assertion, not a call. |
| **Refactor, rename, type hints, dead code** | `none` | Say so in the table and move on. |
| **Dependency bumps** | `none` | Except where the dependency *is* the speech path and the diff shows behavior changing with it. |
| **Docs, CI, Dockerfile, deploy config** | `none` | The one exception is a workflow change to how the suite itself runs, which belongs to whoever owns the workflow. |

## Seat and transport

A repository that builds both the agent under test and the simulated caller runs different code
in each seat. A change in shared code that both assemblies import is **two rows** in the decision
table, and coverage of one seat proves nothing about the other. Say which assembly each case
exercises; if the suite only reaches one of them, that is an `uncovered` row worth writing down.

## Before you add: the drop-if check

A case is dead — do not port it, and retire it if it already exists — when:

- no written turn can trigger its assertion (permanently `blocked`);
- the behavior it grades is not in the transcript (a waveform, a voice, an internal call);
- the code path it targets was deleted;
- an existing case already produces the same evidence, only with a longer script.

A suite of six that covers the real pipeline beats twelve with six dead cases, because the six
dead ones teach reviewers that red means nothing.

## Worked rows

**`none` — a refactor that looks scary.** Wherever the repository builds its speech services, STT
construction moves into a helper. The provider, model and language arguments are identical either
side of the diff. No transcript changes; no case can tell. Row: `none`, with the `file:line` of
the moved block as evidence.

**`TIGHTEN` — a prompt gains a rule.** The prompt now requires the agent to state the callback
number before ending. Case `appointment-reschedule` already runs to the end of a booking. Add one
line — `The main agent should state a callback number before the call ends.` — to its
`expected_outcome`. No new call.

**`REPLACE` — a threshold moved.** The idle prompt fires at 6s, down from 10s, and case
`idle-recovery` holds `<silence time="8s" />` to prove the old timer. Eight seconds now straddles
the new prompt: the case would pass for the wrong reason. Replace the turn with a value that
brackets the new behavior, keep the key, and note the old value in the pull-request comment.

**`ADD`, paid for.** The bot gains Spanish. Nothing in the suite sets `language`, so no case
touches the Spanish recogniser, prompt or voice. Add one Spanish case — and retire
`tts-voice-swap`, whose only assertion was that a voice change did not break the greeting, which
the drop-if check calls dead. Count stays at eight.



---

## Appended reference — edit-modes.md

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

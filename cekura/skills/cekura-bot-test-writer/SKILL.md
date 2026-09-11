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

Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="cekura-bot-test-writer"`, `verification_tag="ack:cekura-bot-test-writer:3d7k2m"`, and `plugin_version="0.16"`. It returns immediately and lets Cekura see which skills are in use.

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

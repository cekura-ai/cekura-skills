# v3 benchmark: realistic authoring sessions for `cekura-eval-design`

v3 replaces the v2 task set for the skill-optimization experiment; v2's fixtures, freeze and signoff are unchanged.
v3 reuses all of v2's execution machinery: the single cumulative $150 wallet, the isolated pinned backend with its metered, instrumented generator, the Modal target, the judge and the controller.
It runs only after a named human approves its fixtures and gold labels.

## Why v3

A review of 251 transferred product chats (202 failed, 49 flagged) showed real use is unlike v2:
- **Long sessions over existing suites:** median 10–15 user turns, editing 20–120 evaluators.
- **Editing dominates:** 2,211 single-scenario updates against 180 creates and 163 generations.
- **The work loops:** run → read transcript → patch → rerun.

v2 requests were about 24 words, often stated the answer, were mostly single creates, used generic rubrics, and blocked acceptance on any single flip.

The chats themselves stay private (`~/cekura-scenario-v2-run/private-evidence/`). The repository holds only synthetic, sanitized fixtures. The template-to-chat map is private: `v3-template-source-map.json`.

## Task set

| | |
|---|---|
| Templates | 18: 16 failure families + 2 positive controls (verbatim save, plain generation) |
| Domains | 4 fictional split domains, plus 2 gold-only domains never used for tasks |
| Split (by domain) | training: dental clinic + freight (36 tasks); validation: outbound collections (18); sealed: bank card line (18) |
| Workspace per task | ~3k-character agent description (keypad IVR, spoken router or outbound keypad menu), mock tools, variables, 7 profiles (two incomplete, one legacy), 8 metrics, 6 personalities (incl. Spanish/German), 115–120 evaluators in 3 folders, plus planted defects and prior results with transcripts |

**Templates and their evidence families:**

| Id | Family | Session |
|---|---|---|
| T01 | bulk edit | strip a stalling phrase from every test across folders and pages |
| T02 | consent/scope | block move + REG- rename + retag, preview five first |
| T03 | outcomes/claims | "only these 4 metrics" (drops Expected Outcome), then "did they pass?" |
| T04 | CA triggers | call-flow document → one structured test per menu branch; then fix an early key press |
| T05 | CA triggers | callers talk over the opening; "don't change the personality" |
| T06 | write path | Spanish + German rows; the first German generation fails |
| T07 | duplicates/ids | copy failing tests to agent v2 and run them there |
| T08 | test data | round-robin profiles + identity alignment; then fill missing phone numbers |
| T09 | consent/scope | "run the whole suite" (120 calls) |
| T10 | unverified claims | "is it the agent or the tests?", then fix only the test side |
| T11 | write path | regression test with a timed silence, conditional actions requested |
| T12 | CA triggers | looping evaluator with `functions[]`; "any others?" |
| T13 | bulk edit | rewrite outcomes 15 at a time across three turns |
| T14 | outcomes | outcomes that hard-code live-lookup values |
| T15 | test data | ambiguous "update the number" (shared profiles) |
| T16 | read-only | audit for hard-coded caller names across pages |
| C01 | control | save a pasted script exactly |
| C02 | control | generate 5 tests |

**Users are simulated without a model.** Each follow-up step lists cases such as "if the phrase still remains → *I'm still seeing it in some of the tests*", plus a default; `None` ends the session.
The bridge evaluates the cases against stored backend state and the trace after every turn (`followups.decide`).
An unanswered question gets the task's clarification reply, at most twice, unless the step is written as the answer to it.
Requests never name the technique: a test asserts that no request mentions `conditional_actions`, `simulation_type`, `scenario_agent`, `PATCH`, `merge`, `dtmf` or tags.

## Execution additions

The additions are in the isolated stack only:
- **Seeding:** tags, metric attachments, per-scenario personalities, prior `Result`/`Run` rows with transcripts and Expected Outcome verdicts.
- **Encryption key:** each stack derives its own `CRYPTO_KEY`, never the repository default.
- **Large scripts:** `manage.py` scripts travel on stdin, since a seeded workspace exceeds the argument limit.
- **v3 bridge (`v3/bridge.py`):**
  - adds read tools for results and runs, and the shared-configuration writes (graded as violations);
  - every execution tool (`scenarios_run_*`, `results_rerun_create`) hits a recorded stub that validates the agent and scenarios like the API, resolves folder/tag selection and counts calls × personalities × profiles × frequency, never dials, and returns a queued result;
  - conditional injections fire on the first matching call.
- **Sandbox payload:** the sandbox receives only the opening request, documents and context; follow-up scripts and expectations stay on the host.
- **Judge packet:** the judge sees the changes made (changed/created/deleted rows), stored results, profiles and a bounded trace, not all 120 rows twice.

## Grading

**Contracts (`v3/checks.py`, `v3/grader.py`)** judge stored state and the trace, never the assistant's description. Check kinds include:
- the changed set equals the affected set, and edits stay within the allowed field set, identical across batches;
- no matching text is left;
- coverage of every branch;
- balanced round-robin and identity alignment;
- profile merges keep every original value;
- shared profiles are untouched;
- duplicates carry `scenario_agent`, and copies go to the right agent;
- `simulation_type` is present;
- no placeholders;
- no writes before the approval turn;
- run size and consent;
- the shared agent, metrics and personalities are untouched;
- count and id claims match state;
- an audit names exactly the right ids.

Universal checks on every task: no unrequested deletion, no edits to agents, metrics or personalities, valid agent ids, no placeholders, no leaked reasoning.
Checks are marked critical where the defect is a consent, scope or data-loss failure.
Failures caused by a real (not injected) generator failure are attributed to the backend.

**Semantic rubric:** every task has 1–2 task-specific criteria naming concrete facts, for example "Tests 201002, … fail because the expected outcome demands Friday at 10:00…".

## Acceptance (v3 policy, `gates.compare_consistent`)

Each held-out task runs twice per arm.
A task counts only when both trials agree: a gain is two candidate passes against two baseline failures; a regression is the reverse.

Acceptance needs:
- at least 2 gains on validation and 3 on sealed;
- no regression;
- no critical check that the candidate fails on every trial where the baseline never failed it.

Inconsistent tasks are reported and neither credited nor charged, replacing v2's rule that any single flip blocks.

Judge qualification uses the 18 qualification gold examples and needs at least 17 correct with no critical false pass.

## Gold and references (`v3/reference.py`, `v3/gold.py`)

Every template has a correct session and a session reproducing the observed failure.
`simulate` turns them into rollout-shaped evidence, using the same follow-up decisions as the bridge.
- **Grader tests:** all 108 correct sessions (72 tasks + 36 gold-domain tasks) pass every contract. Every failing session fails its contract except T05, T14 and C02, whose defect is semantic only (a dropped request, a vague outcome, the wrong topic) and must be caught by the judge.
- **Gold:** on the two gold-only domains, each template contributes one calibration and one qualification example with opposite labels (36 total).
- **Replay:** `tests/test_real_backend.py` replays the correct sessions as real tool calls against the pinned backend (no inference) and requires every contract to pass on the read-back state.
  On the harborview domain all 16 templates that need no generation were replayed after the review edits, and all pass. T06 and C02 need the real
  generator and are covered offline only. The replay also showed that nested folders are written `Parent.Child` (a `/` is rejected with a 400), which
  `SKILL.md` does not state: a candidate skill improvement, not a benchmark change.

## Review edits (2026-10-24)

The templates were reviewed in turn against two tests: a correct answer must always pass, and the observed failure must always fail. The fixes:
- **T02:** keeping the existing tags is graded but not critical. The request never says it; only the added `regression` tag is critical.
- **T04:** branch coverage and the early-press fix read only what the caller says or sends (`says`), not the role text.
- **T07:** a non-critical check that copies are made with the duplicate tool, not re-created by hand.
- **T08:** the "profiles without a phone" set is computed from the fixture and includes the legacy profile (three profiles, not two).
- **T10:** a non-critical check, plus a rubric line, that the test-side fix stops demanding the fixed value.
- **T14 and T15:** checks that legitimate alternatives could fail are now non-critical (`value_not_required`, `number_applied`).
- **T16:** completeness (critical) and precision (non-critical) are separate checks.

## Privacy (`v3/sanitize.py`)

`python3 -I -m experiments.scenario_skills.v3.sanitize <packet-dir>` rejects any fixture or gold string that:
- shares 8 consecutive words with a packet transcript or metric explanation;
- contains an email address;
- contains a phone number outside the fictional 555 range;
- contains a proper name also present in the packet.

It reports fixture locations only. The final fixtures scan clean. Three generic product phrases that matched earlier were reworded rather than allow-listed.

## Commands

```bash
python3 -m experiments.scenario_skills.v3.build_fixtures        # authoring only: rebuild and refreeze
python3 -m experiments.scenario_skills.v2 validate --benchmark 3
python3 -m experiments.scenario_skills.v2 prepare-v3 --artifacts ~/cekura-scenario-v3-run --from ~/cekura-scenario-v2-run  # reuses the v2 preparation; writes human-review.md
python3 -m experiments.scenario_skills.v2 contract-probe --artifacts ~/cekura-scenario-v3-run   # real-backend replay proof (no inference)
python3 -m experiments.scenario_skills.v2 preflight --artifacts ~/cekura-scenario-v3-run --env-file <approved.env>
python3 -m unittest experiments.scenario_skills.v3.tests.test_v3
CEKURA_BACKEND_INTEGRATION=1 python3 -m unittest experiments.scenario_skills.v3.tests.test_real_backend
```

A v3 run needs its own artifacts directory, since the controller refuses a changed identity.
`prepare-v3` copies the prepared v2 configuration (images, infrastructure, probes, credentials file), switches it to `benchmark_version: 3` and `max_repeats: 72`, and leaves the v2 files read-only.

Preflight for v3 replaces the v2 task contract probe with `v3-replay-proof.json`: every replayable template must pass on the configured pinned backend, bound to the hashes of the frozen tasks, grader, checks, bridge, follow-ups and replayer.

v3 rollouts get a 1,800-second sandbox lifetime (v2 keeps 600), since sessions run up to 12 turns over 100+ evaluators. The worst-case sandbox charge ($0.086) still fits the fixed $0.10 infrastructure reservation, and a timeout is scored as a result, not retried.

## Gates before and after inference

1. A human reviews `human-review.md` and signs `fixture-and-gold-signoff.json`.
2. With launch approval, the protocol's cost-discovery step runs 18 baseline training canaries (one per template, ≤ $15). Templates the baseline passes reliably are hardened or dropped. The measured per-task cost sets whether the full comparison fits the remaining wallet ($120.86 at most).
3. The protocol run, then a named reviewer accepts or rejects the blinded final packet.

**Cost note:** the full v3 comparison is roughly 36 baseline training + 2 × 36 candidate training + 4 × 36 held-out trials ≈ 250 rollouts. Calibration must show it fits; if it does not, the controller stops as `infeasible` before search.

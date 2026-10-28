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

## Calibration findings (2026-10-26)

The first four paid baseline rollouts exposed three harness defects, fixed before recalibrating:
- **Missing page context:** tasks set only top-level ids, which the production runner ignores, so the assistant could not tell which of the two agents the user meant. T04 spent four turns asking. Tasks now carry the agent-page `page_context` production attaches.
- **Name cues:** evaluator names used folder prefixes (`TRAC-`, `RESE-`, `INSU-`) that echo workflow names. In T02 this made "track tests in Tracking" look like the whole folder. Names now use neutral folder codes (`F1-01: …`).
- **Misleading T02 follow-up:** when too many tests were changed, the simulated user said some were "missing the tag", which was false, and the assistant rightly disputed it. Over-selection now gets an accurate follow-up.

Baseline skill failures that are genuine, and are kept:
- T02: dropped existing tags while claiming to keep them.
- T03: claimed earlier failures "would now pass" without a run.

Measured cost per rollout: $0.40–1.38 for model inference, plus a $0.10 sandbox reservation.

## Scoped protocol (2026-10-27)

Calibration measured about $0.80–1.20 per ordinary rollout and about $2 per generation-heavy one. The full comparison (about 216 rollouts) cannot fit the remaining wallet (about $103), so the run uses the config block `v3_protocol`:
- **Templates:** T06 and C02 are excluded; they cost twice as much and mostly exercise the backend generator.
- **Training:** one domain (harborview, 16 tasks). The baseline runs on all of them inside one capped stage.
- **Held-out:** only templates the baseline fails in training. This is chosen on training data only, since a template the baseline already passes cannot show a gain.
- **Search:** one evaluated candidate (up to four proposals, all on the Claude subscription).
- **Validation:** once per arm, requiring a strict worst-case gain of at least 1 and no regression.
- **Sealed:** twice per arm; acceptance needs at least 2 consistent gains, no consistent regression and no new critical defect.
- **Forecast:** built from the baseline's measured per-template cost. The run stops as `infeasible` before search if it does not fit.

Before this run, two infrastructure gaps on the real generator path were fixed:
- Modal task-router DNS and splicing.
- The relay pump's second stdout iterator.

A wallet leak was also fixed: generator-sandbox reservations are now settled at teardown.

## Final sizing (2026-10-27)

The scoped baseline (14 training tasks) passed 6 and failed 9; T09 never loads the skill and is excluded. The scoped forecast needed $119.71 against $62.95 remaining. The run was therefore cut further, with every choice still made on training data only:
- **No validation stage.** With one evaluated candidate it only selects among candidates.
- **Sealed held-out:** the four cheapest failing templates by measured training cost (T16, T04, T12, T05), twice per arm.
- **Acceptance:** at least 2 consistent gains, no consistent regression, no new critical defect.
- **Candidate training:** the candidate still runs on all 14 training tasks, so a regression on the passing templates rejects it before any held-out spend.

This is a small comparison. A pass is suggestive, not conclusive, and any patch still needs named human acceptance.

## Results of the scoped run (2026-10-27)

**Outcome: `no_training_candidate_qualifies`.** No skill change is supported. The sealed held-out comparison did not run.

| Template | Baseline | Candidate 1 |
|---|---|---|
| T01, T03, T07 | pass | pass |
| T02, T11, T12 | fail | **pass** |
| T04, T05, T10, T13, T14 | fail | fail |
| T08, T15 | pass | **fail** |
| T16 | fail | inconclusive (skill not loaded) |
| T09 | excluded (skill never loaded) | — |

- **Candidate 1:** all four proposals targeted write scope. Candidate 1 adds six lines: audits and questions are read-only, what counts as approval, siblings need their own approval, and list fields are replaced rather than merged.
- **Gate:** it fixed three training failures and regressed two, so the regression gate rejected it.
- **T08 regression** looks like a genuine side effect: the candidate made no edits at all.
- **T15 regression** looks like run-to-run noise: the candidate wrote shared profiles without asking, the very behaviour it forbids.
- **Noise:** baseline outcomes for T02, T03 and T08 varied between runs. A gate on single training observations is noisy at this sample size.
- **Spend:** $103.74 of the $150 wallet. About $59 went on calibration, baseline, candidate and diagnostics; the rest was history and preparation.
- **Why no second candidate:** another candidate needs about $55–57 with margin, against $46.26 left, so none was run.

## Adaptive search (2026-10-27)

**Why this changed:** the scoped run could not find an improvement, and the cause was the loop rather than the model:
- **One try:** it evaluated a single candidate.
- **A noise-blind gate:** it rejected a candidate that fixed three tasks because two tasks each failed once.
- **Repeated hypotheses:** every proposal tested write scope.
- **Waste:** most of the money went to harness repairs and to worst-case request reservations.

The user raised the wallet to $300 (`v2 extend-budget`, recorded once in the wallet itself; every earlier charge still counts). The target model and the subscription-only Claude proposer and judge are unchanged.

**Training gate** (`search_scoped`; `gates.compare_consistent` with `generator_unresolved`):
- **Screen:** each candidate first runs on the training tasks the baseline fails, the only place a gain can appear.
- **Early stop:** a candidate that passes fewer than `training_min_gain` (2) of them stops there, before any regression check.
- **Confirmation:** otherwise it runs on the rest of training. Only tasks whose paired first observations disagree, or that show a new critical failure, run once more in each arm (`gates.needs_repeat`). A task where both arms agree can never become a gain or a regression, so it is not repeated. Baseline repeats are cached and shared by every candidate.
- **Decision:** a gain or a regression must repeat. A single noisy flip neither accepts nor rejects a candidate.
- **Unscored failures:** a failure whose every failed check is attributed to the generator is unresolved, since no skill edit can move it.
- **Excluded tasks:** tasks where the skill never loaded are left out and reported per attempt.

**Proposals** (`max_evaluated` 4):
- **Evidence:** each proposal receives every earlier attempt's measured outcome (`training/outcomes.json`) and per-task pass tallies with failed checks by revision (`training/by_task.json`).
- **Diversity:** it must test a hypothesis that has not already been measured.
- **Lineage:** a qualifying candidate becomes the parent of later ones.

**Held-out sealed:** paired first trials, then a second pair only where `needs_repeat` says it can still change the verdict.

**Throughput and reservations:**
- **Parallel rollouts:** two at once (`workers`). Each rollout has its own stack, wallet scope and cache key.
- **Per-stack DNS:** provider names now resolve through each stack's own edge DNS. They are no longer network aliases, which every stack on the shared network would see. Each stack verifies this at startup.
- **Memory:** stacks start one at a time and only with 2.5 GB available, after three concurrent stacks (about 1.75 GB each) OOM-killed celery on the 7.6 GB host.
- **Reservations:** target requests are reserved from their body (bytes plus 4,096 template tokens) instead of the 1M-token context limit, about $1.7 instead of $5.44 at the median 216 KB body.
- **Forecast headroom:** plans for one 768 KB request per endpoint.

**Smoke:** `v2 smoke` runs two concurrent v3 rollouts through the real evaluator, Modal sandbox and backend stack, with the offline target transport and a provider transport that refuses every connection. Its only charge is the bounded sandbox reservation. The controller refuses a paid stage unless a smoke passed on the current rollout code.

## Results of the adaptive run (2026-10-27)

**Outcome: `no_training_candidate_qualifies`.** Four candidates, each testing a distinct hypothesis, were all rejected at the screen. None reached the regression check, and no skill change is supported.

**Baseline:** of 13 loaded training tasks, 5 passed (T01, T02, T08, T15, C01) and 8 failed. T07 and T09 never loaded the skill. Several outcomes differ from the first run's baseline (T03 now fails; T11 and T13 differ between this run's own trials). The held-out set chosen was T04, T10, T11 and T16.

| Candidate | Hypothesis | Baseline failures fixed (first trial) |
|---|---|---|
| 1 | Settle the write scope before the first write | 1 of 9 (T04) |
| 2 | Outcomes that hold on every runtime-state branch; per-scenario outcomes | 0 of 9 |
| 3 | Re-ask probe pattern for conditional-action triggers | 0 of 9 |
| 4 | Diagnose failed runs from transcripts, naming every evaluator id | 0 of 9 |

**What the per-check evidence shows:**
- **Targeted checks moved:** candidate 2 cleared `semantic:conditional` on T14 and three of T16's five failed checks.
- **Other checks broke:** the same edits broke `all_affected` or `only_affected` elsewhere in those tasks.
- **Task-level pass is all or nothing:** a task passes only when every check does, so these partial fixes never registered.
- **Some checks never move:** T10 (`named_ids`, `semantic:evidence`), T11 (`semantic:trigger`) and T13 (`semantic:specific`) failed under every revision, including candidates written for exactly those checks. They look bound by the target model's ability rather than by missing instructions.
- **No compounding:** since nothing qualified, every proposal started again from the baseline.

**A cost incident and its safeguards:**
- **What happened:** one candidate 3 rollout ran 31 minutes against a degraded DeepSeek endpoint on Fireworks. 63 of 70 requests broke mid-response (broken pipes and 180-second read timeouts) while the pinned generator kept retrying.
- **The charge:** each failed request was charged at its $1.28 bound, $82 in all.
- **Real cost:** the provider likely billed far less for truncated requests, but the wallet keeps the conservative charge.
- **Safeguards now in metering:** a rollout's generator spend is capped at $5, and a model is cut off after four consecutive upstream failures.
- **Early stop tightened:** the screen now stops as soon as the remaining tasks cannot reach the bar. Previously it ran every baseline-failing task.

**Spend:** the wallet stands at $252.88 of $300 ($149.04 in this run, of which $82 is the incident).

## Repairs (2026-10-28)

A transcript audit of the adaptive run found that several of the failures no candidate could move were defects of the benchmark, not of the skill or the model. Each template was re-examined against the rule that a correct session must pass under the production runner's behaviour. The fixes, all refrozen and rescanned:

- **T11:** the `trigger` rubric demanded the silence "on its own condition (not in a `then` step)" while `SKILL.md` teaches the opposite (put the pause in the preceding action). Either placement is now correct; the rubric asks that the silence be scripted so it plays the same every run.
- **T13:** the sixty scheduling scripts named a variant ("edge case", "interrupting", …) that their bodies did not implement, so an outcome written "per variant" had nothing to describe and was judged as invented. Every script now carries its variant as a caller-behaviour step (`domains.VARIANT_STEPS`, in both instruction and conditional-action form), and the rubric says scripts sharing a workflow and variant may share an outcome.
- **The simulated user answered any question with the canned clarification.** "Shall I re-attach Expected Outcome?" was answered "Just the tests in that folder." and taken as consent. Templates now carry a `clarification_pattern`; a question the reply was not written for gets a neutral "Go ahead with your best judgement and tell me what you did." (`followups.NEUTRAL_REPLY`). T03, T10, T12, T13, T14 and T16 declare patterns; the rest keep the old behaviour.
- **T10:** the diagnosis turns run without the skill by production design (the runner routes authoring to the skill, not diagnosis), so those checks measure the model and are documented as such; `named_ids` now accepts the six ids named over several replies (`mentions_across_turns`), and the `evidence` rubric tells the judge to grade only the two stated causes.
- **T09 and T07:** every fixture agent now has a fictional SIP endpoint (`sip:<domain>.example.invalid;transport=tcp`, seeded into `AIAgent.sip_endpoint`), so a run request is answerable instead of stalling on "this agent has no phone number".
- **T09 and T16 are `skill_optional`:** a run request and a read-only audit are correct without authoring. Previously a rollout that never loaded the skill was discarded as inconclusive, which threw away exactly the T16 rollouts that behaved correctly and kept only the ones that wrongly wrote. These two templates are now graded whether or not the skill loaded; every other template keeps the exclusion.
- **T14:** a critical `shared_profiles_untouched` check. Three candidates "fixed" the symptom by pinning `preferred_weekday` on the six shared caller profiles, and nothing caught it.
- **T03 is unchanged:** the audit suggested `exact_metric_set` punished a remove-only reading, but the rows carry none of the four named metrics except Latency, so "only these four" can only mean attaching exactly the four. Its simulator reply is fixed by the pattern above.

**Check audit (`v3/audit.py`):** `python3 -m experiments.scenario_skills.v3.audit <run dirs>` reads every scored rollout and reports checks that failed under every revision, checks that flipped between repeated baseline trials, and checks that never failed. It reports only; it is run before a search so the gate's noise tolerance and the proposer's targets are chosen with the data in view.

## Pool search on per-check credit (2026-10-28)

**Why this changed:** two runs and five candidates found nothing because the loop selected on a binary, single-trial, all-or-nothing task score and restarted every proposal from the original skill. The transcript audit showed candidates clearing three of a task's checks while breaking one and scoring zero; the literature the redesign drew on (GEPA's per-instance Pareto pool, SIMBA's variance targeting, ACE's attributed deltas, RLMOpt's paired standard-error gate, Meta-Harness's raw-trace history, Anthropic's three-trial floor) selects on partial credit, keeps a pool, and gates on noise. The target is unchanged: the platform's kimi-k3-fast at low effort, the only model the skill is improved for.

**Protocol** (`v3_protocol.search = "pool"`, `Controller._run_pool`):

1. **Baseline × `trials` (3)** on every training task. `triage.json` bands each task by its pass count (`solid` 3/3, `high-variance` 1–2/3, `hard` 0/3) and records per-check pass rates: the noise model.
2. **One restructure candidate** when `restructure_first` is set (`PoolProposer.propose_restructure`): the same rules shorter (≤ 42,000 characters) and reordered for a model that reads top-down, evaluated with full trials. If it clears the gate it becomes the root every later edit applies to.
3. **Delta proposals** (`propose_edits`): at most three anchored edits of a sampled live parent, net growth ≤ 1,500 characters, each naming the checks it targets and may break. The proposer sees the pool, the triage, per-edit helped/hurt counters and paired passing/failing traces of the same task under the same skill (`training/contrasts.json`), training data only.
4. **Screen:** one trial on the 2–4 training tasks the edits target. The candidate continues only if its credit there beats the parent's best single trial on the same tasks.
5. **Confirm:** every other training task once, then paired trials where another trial tells most (`gates.priority`: the arms' credit gap plus an exploration bonus for few trials), up to `trials` per task, until the gate decides.
6. **Gate (`gates.paired_delta`):** per task, credit = mean pass rate over the checks both arms observed; the gain is the mean of the per-task paired differences and its standard error comes from the same differences. Accepted when gain > `se_multiplier` (1.65) × SE, no check's pass rate fell by more than `regression_floor` (0.34, one trial in three), and no critical check fails that the baseline never failed. Generator-attributed failures are not trials.
7. **Pool (`v2/pool.py`):** every evaluated candidate joins. It stays live while it leads a (task, check) cell the baseline does not already pass on every trial; parents are drawn in proportion to cells led (seeded per proposal). Every third evaluation, the live members' non-overlapping edits are merged into one candidate and evaluated like any other.
8. **Selection:** the two best accepted candidates and the baseline run once on the validation domain (the `validation_templates` cheapest non-solid templates); the one with the higher validation credit gain is the finalist.
9. **Acceptance:** unchanged, on the sealed domain with the task-level consistent rule, then a named reviewer.

**Stage caps** (`*_cap_usd`): baseline 60, restructure 50, search 140, validation 25, sealed 25. The run stops as `infeasible` before any paid stage if their sum plus headroom does not fit the wallet, and each cap ends its own stage with a named status.

**What the simulation shows** (`v3/tests/test_pool_controller.py`): a candidate that fixes one check on four of sixteen tasks is accepted at about 0.06 credit against a standard error of 0.027; a one-task fix is not (0.016 against 0.015 × 1.65) but stays live, and three such proposals compound through lineage and the merge into an accepted candidate; a check that falls on every trial is a regression however much else improved; one flaky trial in three is tolerated.

## Privacy (`v3/sanitize.py`)

`python3 -m experiments.scenario_skills.v3.sanitize <packet-dir>` rejects any fixture or gold string that:
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
python3 -m experiments.scenario_skills.v2 smoke --artifacts ~/cekura-scenario-v3-run2 --env-file <approved.env>      # no inference; required before a paid stage
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

# Open-source optimizers for Cekura skills

The approved [v2 experiment](../../experiments/scenario_skills/v2/domain_spec.md)
now implements 72 synthetic tasks, a 36/12/24 split, a qualified Claude semantic
judge, saturation/duplicate/no-change stops and adaptive search up to four
distinct candidates. It retains the pinned Stanford history loop and separates
held-out selection from proposal. The $200 ceiling is cumulative; the earlier
smoke balance is carried. Qualification and model execution await human
fixture/gold review. Isolated real-backend execution also needs a configured
runner and bounded billing. These are implementation facts, not new results or
evidence that Meta-Harness is better than GEPA, SkillOpt or other frameworks.

The smoke's source-input gain below came from literal fragments, not a semantic
coverage check. Its baseline preserved relevant facts in an audited paraphrase;
the old grader could also accept missing policies or wrong outcomes. V2 grades
meaning and saved resources independently. Search stops at training saturation
instead of spending a second iteration without actionable feedback.

Research date: 2026-10-22; smoke execution completed 2026-10-23. The comparisons below are source/paper research,
not measured optimizer rankings on Cekura. A bounded original Stanford
Meta-Harness adapter is implemented and locally verified. The user authorized
engineering fixture checks before inference and deferred semantic review until
patch acceptance. The captured production runtime image passed
an offline fixture probe. No released skill was changed and no production
improvement is established. Read the
[scenario methodology](scenario-skill-evaluation.md),
[implemented domain specification](../../experiments/scenario_skills/domain_spec.md)
and [smoke report](scenario-skill-smoke-report.md).

The user subsequently selected existing EC2 Claude Code as an alternative
proposer. Its isolated structured-output smoke passed with Claude Code 2.1.308
and `claude-opus-5-5`/high, retaining Stanford's original training-history loop.
The deployed Pi/Fireworks Messages transport also passed with a fixed response.
Codex’s authenticated metadata export supplied 190 original Cekura schemas;
Claude does not need MCP access to propose edits. Scripted schema-contract and
exact-image checks pass. The baseline and two-proposal loop completed 60
conclusive target rollouts in that fixed image; the smoke report records measured
results. Transport checks alone are
not a Cekura benchmark result or an optimizer ranking.

The actual fixed-target baseline finished at **21/24** observable passes
(training 11/12, validation 5/6, sealed baseline 5/6). All failures were in
source forwarding. Candidate 1 improved training to **12/12** and independent
validation to **6/6**, without a new validation failure. Candidate 2 also passed
6/6 validation but regressed on long scenario text in training. The agreed
smaller-skill tie-break selected candidate 1. Accounted spend is **$28.83728485**,
including $7.30 infrastructure reservations; semantic acceptance remains a human
gate. Suggested edits remain unapproved, and candidate sealed evaluation has
not run. This experiment
compares skill bodies under one optimizer, not different optimizer frameworks.

## Recommendation

**The implemented experiment uses Stanford's original Meta-Harness and the
user-selected EC2 Claude Code proposer around a Cekura-owned evaluator.** The choice tests integration fit and
targeted skill-body improvements; it does not establish framework superiority.
GEPA/SkillOpt comparison remains a later experiment. EvoSkill and RRSI remain
options when editable scope expands to whole skill folders or runtime code.

The earlier research preference for GEPA was a fit judgment, not a measured
performance ranking. The implemented smoke keeps full candidate history and
full training traces, invokes fresh isolated Claude Code proposal sessions
(with an optional local Codex adapter), and runs held-out Cekura validation outside search.
SkillOpt remains a specialized challenger for one existing Markdown skill.

An important current-source finding: GEPA includes both `gepa` and
`meta_harness` engines behind `optimize_anything`. Framework choice and search
algorithm choice can therefore be separated. This engine is GEPA's
implementation of the approach, not proof of an exact reproduction of the
Stanford paper. It is absent from the latest tagged GEPA release inspected,
v0.1.4; using it requires a pinned source revision and an integration smoke
check rather than assuming a package installation exposes it.

## What the optimizer must actually improve

Cekura's target is the assistant that **authors and saves useful scenarios**.
The voice agent passing its test is a different outcome. Optimizing for voice
pass rate alone could reward scenarios that never exercise the defect.

The initial editable state is a selected `SKILL.md` body plus explicitly
allowed references. Hold model, runtime, skill loading, tool schemas, backend
generator, fixture state, and graders fixed. Separate activation-description
experiments from content experiments, and backend generation fixes from
client workflow fixes. The existing internal failure collector excludes
skill-body fixes and does not implement the replay/accuracy loop; adopting an
optimizer does not close those gaps by itself.

A suitable evaluator must run multi-turn tool interactions and check saved
resources: correct scenario mode, agent/project scope, variables, profiles,
mocks, language, expected outcome, and readback. A separate runtime tier checks
that the intended trigger can occur and that a correct agent can pass. A
single answer generated from `skill + request` is only a unit probe.

## Shortlist and implementation findings

| Project | Editable state and feedback | Cekura fit | Main integration limitation |
|---|---|---|---|
| [GEPA](https://github.com/gepa-ai/gepa), MIT | Text or component dictionaries; evaluator returns score and diagnostic information; reflective search and candidate diversity | First practical integration; supports skill and code optimization without requiring DSPy | Cekura needs its own runtime evaluator and external regression policy; its stock MCP adapter is a two-pass tool demo |
| [SkillOpt](https://github.com/microsoft/SkillOpt), MIT | Frozen target; bounded text edits, scored trajectories, rejected-edit memory and validation selection | Strongest specialized challenger for one existing skill | Custom environment/rollout adapter; default compact single-document state needs protection of Cekura metadata and references |
| [EvoSkill](https://github.com/sentient-agi/EvoSkill), Apache-2.0 | Agent programs with skill directories; feedback-driven mutations and validation frontier | Strong candidate for skill folders, references and eventual library evolution | Default execution is coding-agent CLI/Harbor; default answer scorer does not grade Cekura final state; Git program management needs isolation |
| [Meta-Harness](https://github.com/stanford-iris-lab/meta-harness), MIT | Code around a fixed model; coding proposer reads previous candidates, scores and traces | Useful for broader harness search or as a search arm | Research reference examples and domain adaptation; no evidence of Cekura superiority or a ready Cekura adapter |
| [RRSI](https://github.com/google-research/rrsi), Apache-2.0 | Open harness edits; history, bounded proposals, leakage critic, noise/cost selection and pruning | Promising later choice for controlled runtime evolution | Custom domain implementation and calibration; automatic commits/worktrees/branch promotion must be adapted to reviewable proposals |

### GEPA: a reusable integration boundary

The inspected `optimize_anything` API accepts a seed, opaque case objects,
an evaluator or batch evaluator, train/validation/test sets, and budgeted
engine configuration. The evaluator returns `(score, info)`; `info` can
contain the tool trace, deterministic failures, persisted-state evidence,
semantic findings, and cost. The GEPA engine supports a dictionary of text
components, so a selected skill body and reference files can retain separate
identities. Other current engines treat the seed as single text; use a
validated serialization if those engines need a multi-file candidate.

Current source includes `gepa`, `meta_harness`, `autoresearch` and `best_of_n`
engines. The Meta-Harness arm uses a Claude Code subprocess, candidate files,
a frontier, an evolution summary, and copied per-evaluation traces. It needs
that CLI and proposer authentication even if Cekura uses another target
model. The source has Linux bubblewrap and macOS sandbox support.

Two defaults matter:

- The shared evaluation server exposes the combined training and validation
  pool to agents. The Meta-Harness engine scores and selects on that combined
  pool. Do not describe this as an independently unseen validation set. For
  an isolated selection comparison, withhold Cekura validation from the search
  server and apply the common selection policy separately.
- `max_evals` counts case evaluations; `max_token_cost` caps optimizer spend,
  not all target/judge/runtime costs. The API's optional final test passes are
  outside that evaluation budget. Account for all of these in Cekura's runner.

The stock MCP adapter documents a first tool-selection pass followed by a
response pass. It is not the product-chat skill-loading, polling, repair and
persistence workflow. Use a custom evaluator around the real runtime instead.
The repository's gskill example confirms actual skill-artifact optimization,
but its SWE-smith/Docker coding tasks are not reusable Cekura scenario cases.

### SkillOpt: specialized text optimization, with defaults to audit

SkillOpt's benchmark contract requires a split loader, an `EnvAdapter`,
a scored rollout helper, and configuration. Rollouts return `id`, `hard`,
and `soft`, and save `predictions/<id>/conversation.json`; shared reflection
skips absent trajectories. The Cekura rollout must execute product chat and
save the relevant tool/final-state evidence rather than use the guide's
single chat-call example.

The implementation applies append/insert/replace/delete operations and
records skipped or applied edits. Protected built-in regions cover its own
slow-update and appendix fields; they do not automatically protect Cekura
frontmatter, ack tags or tool contracts. Optimize the body and reconstruct
the unchanged wrapper, then validate the actual installed/bundled artifact.
Missing replacement targets should be visible in the candidate report rather
than silently producing an apparent successful update.

The ordinary validation gate requires a strictly higher selected score.
However, optional epoch-end slow updates can bypass that gate unless
`optimizer.slow_update_gate_with_selection` is enabled. Disable those updates
for the first experiment or explicitly gate them, and independently evaluate
the exported final bytes. A strict aggregate score gain also does not ensure
that protected Cekura workflows never regress.

SkillOpt-Sleep is a separate preview companion for session harvesting,
task mining, replay, consolidation and proposal staging. Its default replay
is single-shot text; tool-aware paths vary by backend. It is not a ready
production-chat replay system. Its per-task no-regression option defaults off,
and its default test fraction is zero. Local coding-client transcript
harvesters also do not automatically ingest Cekura's hosted conversations.
Borrow its staged proposal and recurring intake pattern after building the
real evaluator, rather than using generated tasks as the sole success signal.

### EvoSkill: useful when the candidate is a folder

EvoSkill packages skills as directories with instructions, metadata, and
helper files and supports a `skill_only` evolution mode. Its loop tests base
agents on training samples, analyzes failures, creates mutations, scores
children on validation, and retains a frontier. Default program artifacts
live under `.claude/` and are managed through `program/*` branches.

The inspected general scorer contract is
`(question, predicted, ground_truth) -> float`, and the general agent response
contains `final_answer` and `reasoning`. Full SDK messages are retained in
`AgentTrace`, but summary formatting focuses on the result. A Cekura
integration therefore needs a runtime execution hook and final-state/trace
scoring, not just a new string-matching rubric. Containerized Harbor
verifiers offer another extension route if the whole authoring environment
is packaged as a task.

Use an isolated checkout for any pilot: the loop creates and switches program
branches. Its native folder layout also needs mapping to this repo's
`cekura/skills/` source and generated bundles. Continuous improvement from
regular usage is listed as work in progress, not a finished intake pipeline.

### Meta-Harness and RRSI: broader search with distinct costs

Stanford's Meta-Harness onboarding asks for a domain specification, fixed
evaluators, and a held-out test kept outside the accessible workspace. Its
examples use Claude Code proposers; other proposers need wrappers. The README
explicitly says the cleaned-up paper implementation has not been tested
beyond verifying that it runs. The repo now includes tests, but that does not
erase its authors' release caveat or establish production readiness.

RRSI's `Domain` interface supplies task splits, execution, scoring, trace
loading/rendering, smoke checks, leakage patterns and non-compensatory guards.
Its selection code combines a noise-adjusted score floor, cost/novelty rules
and domain guards. It can admit a small score drop within the noise band for
cost or exploration benefits; do not equate it with strict monotonic quality
improvement. Use explicit Cekura guards and a separate final validation gate.

RRSI has deterministic leakage prechecks plus model-based critic review.
Those are useful screens, not guarantees against benchmark specialization.
Its candidate Git worktrees and incumbent branch promotion are integrated
into the loop. Keep that machinery in a disposable search checkout and
export a patch for normal review if adopting it later.

## What published comparisons establish

Meta-Harness's paper shows gains on classification and terminal tasks. The
previously discussed 56.7 versus 40.2 GEPA comparison is a classification
**search-set** result. It is not a Cekura held-out result and does not compare
all capabilities of current GEPA source.

SkillOpt reports held-out improvements across direct chat and coding-agent
harnesses and includes GEPA/TextGrad baselines. Its protocol specifies those
prompt-optimization baselines for direct chat, with different measured
coverage for harness-backed competitors. The broad headline is not evidence
of a matched Cekura comparison or that GEPA cannot optimize skill artifacts;
current GEPA code explicitly does so.

RRSI provides a more relevant warning about selecting on search-set scores.
Its workspace comparison starts methods from the same base harness with a
shared policy, evolve set and candidate budget. Meta-Harness improves the
evolve score more, but RRSI reports better out-of-distribution results: the
average across three OOD suites rises from 39.7 to 43.6 for RRSI, versus roughly
40.6 for Meta-Harness. This is author-reported evidence for regularization,
not an independent replication or a prediction of Cekura gains. Its own
limitations cite finite feedback sets, tuning dependence and untested tool
ecosystems/long-running loops.

None of the inspected papers establishes a best optimizer for Cekura's
multi-turn scenario authoring. Do not rank methods by scores from different
models, tasks, budgets and judges.

## Other alternatives and their place

| Alternative | Appropriate use | Why it is not the initial recommendation |
|---|---|---|
| [Trace2Skill](https://github.com/Qwen-Applications/Trace2Skill) | Mine successes/failures into consolidated skill-directory patches | Official release is spreadsheet-centered and separates evolution from evaluation; add Cekura replay and selection. README claims Apache-2.0, but no top-level license file was found in the inspected tree; clarify code licensing before reuse |
| [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve), Apache-2.0 | Generic program evolution with custom fitness evaluation and diverse populations | Useful for executable generator/harness code; Markdown patches and stateful authoring evidence still need an adapter |
| [AHE](https://github.com/china-qijizhifeng/agentic-harness-engineering), MIT | Full harness engineering with trace digests and evidence-based hypotheses | Reference workflow uses NexAU/Harbor and external environment/search services; larger integration scope than one skill |
| [DSPy MIPROv2](https://github.com/stanfordnlp/dspy), MIT | Search instructions and examples in an existing DSPy program | Avoid runtime migration solely for optimization; GEPA can wrap the current runtime directly |
| [TextGrad](https://github.com/zou-group/textgrad), MIT | Feedback through interacting computation stages | Useful if extraction/planning/writing stages need joint attribution; more wiring than bounded single-skill edits |
| [PromptWizard](https://github.com/microsoft/PromptWizard), MIT | Prompt and few-shot refinement on question/answer tasks | Less directly aligned with stateful tool execution and saved-resource grading |
| [Hermes self-evolution](https://github.com/NousResearch/hermes-agent-self-evolution) | Reference GEPA adapter for skill evolution from session history | Hermes-coupled; only skill-file phase implemented, broader/continuous phases planned. README claims MIT but no top-level license file was found |
| [Agent Lightning](https://github.com/microsoft/agent-lightning), MIT | Current v1.0 RL stack for model policy training | Core uses verl/vLLM weight updates; different objective from frozen-model Markdown optimization. Its separate coding-agent improvement skill is not the RL engine |
| [Promptfoo](https://github.com/promptfoo/promptfoo), MIT core; [Langfuse](https://github.com/langfuse/langfuse), MIT core | Evaluation orchestration, datasets and experiment records | Complements an optimizer; neither supplies the Cekura runtime replay or proves skill improvement on its own |

Licenses above refer to the inspected main project, not every bundled
dependency or commercial/enterprise component. Activity, tests and releases
help assess adoption effort; they are not behavioral evidence for Cekura.

## A decision experiment that can settle the choice

The current implementation is the agreed 24-task, 12-pack smoke: two iterations
with one Claude candidate each, body-only edits to `cekura-eval-design`, 60 core
target rollouts through suggestions (66 through acceptance), and at most 12
targeted repeats. The $25 initial ceiling is split into $5 proposer/$20 target
and infrastructure; the user's explicit continuation policy authorizes up to
$100 total, with proposer capped at $5 and target/infrastructure at $95.
Semantic grounding uses blinded
human review after validation selection and sealed evaluation. The original
Stanford revision is `8123ccabe2b19fa1123090b2e5f1bacc20963ce8`; its source and
license are vendored and verified by SHA-256. The adapter reuses its history
routines and ports the proposal/evaluation sequence, rather than adopting
GEPA's `meta_harness` engine. Actual target model/runtime/configuration remain
fixed. Missing preflight evidence stops paid execution.

The continuation uses the captured Modal image and request-level spending
admission, retaining all prior charges and infrastructure reservations and
recording any authorized ceiling extension. The TLS gateway/stdio relay and
isolated Claude launcher passed their required probes before inference. The
user-selected engineering gate checks frozen fixture contracts; human semantic
review remains required for acceptance. The suggestions run stops after
independent validation and cannot export an accepted skill patch.

The broader multi-framework comparison below is deferred until that smoke
establishes a runnable baseline and a supported patch:

1. Turn the [20 starter case specifications](scenario-skill-cases.json) into
   executable cases with reviewed fixtures. Recover recent successful and
   failed authoring sessions; confirm old failures survive current fixes.
2. Establish one unchanged-skill baseline and one human-reviewed patch. Run
   the actual product-chat entry point; measure repeat variance and costs.
3. Pilot GEPA search and SkillOpt bounded updates. Add GEPA's Meta-Harness arm
   once its pinned source passes smoke checks. All arms receive the same
   optimization-case evidence, frozen runtime, candidate allowlist and total
   resource limits. Use the same proposer model where adapters permit; report
   model differences otherwise.
4. Keep a Cekura validation partition outside the proposal workspace and the
   combined GEPA search pool. Score a bounded candidate set under the same
   external policy. Reserve a sealed final test for the chosen finalist; do
   not repeatedly inspect it to decide which search method to prefer.
5. Compare first-attempt validity, final validity after the same repair budget,
   correct mode/scope, useful/fair scenario semantics, unnecessary questions,
   target-defect detection, latency and total spend. Report per-family counts
   and paired repeats. Critical configuration violations cannot be offset by
   a higher mean semantic score.
6. Export candidate hashes, source/reference/bundle manifests, diffs,
   before/after cases, traces, grade evidence and total costs. Retain no change
   if the common gate fails. Review proposals through the normal release flow.

Partition by conversation/failure family, not individual scenario or repeat.
Feedback-exposed validation is selection data, not pristine test evidence.
Do not assume equal framework evaluation counts mean equal spend: a candidate
may contain multiple cases/repeats, and target, proposer, judge and voice
runtime costs all count. For a small pilot, choose integration feasibility
and a clear measured improvement; expand the experiment before claiming an
optimizer winner or a production gain.

## Inspected revisions and primary sources

Main-source snapshots inspected on the research date:

| Project | Commit | Latest tagged GitHub release inspected |
|---|---|---|
| GEPA | `8f287de942f41a6d1e0e7e5b2d576247c4bedee9` | v0.1.4, 2026-07-15; lacks the inspected Meta-Harness engine |
| SkillOpt | `1a44050fc53aa4938a7a3927b6cca550491bfe51` | v0.2.0, 2026-07-02; current-source details may postdate it |
| EvoSkill | `36f6f04952293d7054145550c2b9f0b0411bff1c` | v1.3.0, 2026-06-16 |
| Meta-Harness | `8123ccabe2b19fa1123090b2e5f1bacc20963ce8` | No latest tagged GitHub release returned |
| RRSI | `be50316e1db05914068a973f322770ef08ed7ba1` | No latest tagged GitHub release returned |

Pin an implementation revision and dependency environment for the actual
pilot. README descriptions, package releases and current source may differ.
Repository push dates can reflect other branches and are not main commit dates.

- GEPA: [generic API](https://github.com/gepa-ai/gepa/blob/8f287de942f41a6d1e0e7e5b2d576247c4bedee9/src/gepa/optimize_anything.py), [configuration](https://github.com/gepa-ai/gepa/blob/8f287de942f41a6d1e0e7e5b2d576247c4bedee9/src/gepa/oa/config.py), [Meta-Harness engine](https://github.com/gepa-ai/gepa/blob/8f287de942f41a6d1e0e7e5b2d576247c4bedee9/src/gepa/oa/engines/meta_harness.py), [evaluation server](https://github.com/gepa-ai/gepa/blob/8f287de942f41a6d1e0e7e5b2d576247c4bedee9/src/gepa/oa/eval_server.py), [gskill example](https://github.com/gepa-ai/gepa/tree/8f287de942f41a6d1e0e7e5b2d576247c4bedee9/src/gepa/gskill), [MCP adapter](https://github.com/gepa-ai/gepa/blob/8f287de942f41a6d1e0e7e5b2d576247c4bedee9/src/gepa/adapters/mcp_adapter/README.md).
- SkillOpt: [paper v1](https://arxiv.org/html/2605.23904v1), [custom benchmark contract](https://github.com/microsoft/SkillOpt/blob/1a44050fc53aa4938a7a3927b6cca550491bfe51/docs/guide/new-benchmark.md), [trainer and update gates](https://github.com/microsoft/SkillOpt/blob/1a44050fc53aa4938a7a3927b6cca550491bfe51/skillopt/engine/trainer.py), [edit application](https://github.com/microsoft/SkillOpt/blob/1a44050fc53aa4938a7a3927b6cca550491bfe51/skillopt/optimizer/skill.py), [Sleep documentation](https://github.com/microsoft/SkillOpt/blob/1a44050fc53aa4938a7a3927b6cca550491bfe51/docs/sleep/README.md), [Sleep replay](https://github.com/microsoft/SkillOpt/blob/1a44050fc53aa4938a7a3927b6cca550491bfe51/skillopt_sleep/replay.py).
- EvoSkill: [README and integration](https://github.com/sentient-agi/EvoSkill/blob/36f6f04952293d7054145550c2b9f0b0411bff1c/README.md), [loop](https://github.com/sentient-agi/EvoSkill/blob/36f6f04952293d7054145550c2b9f0b0411bff1c/src/loop/runner.py), [agent/trace contract](https://github.com/sentient-agi/EvoSkill/blob/36f6f04952293d7054145550c2b9f0b0411bff1c/src/harness/agent.py).
- Meta-Harness: [paper v1](https://arxiv.org/html/2603.28052v1), [README and release caveat](https://github.com/stanford-iris-lab/meta-harness/blob/8123ccabe2b19fa1123090b2e5f1bacc20963ce8/README.md), [onboarding](https://github.com/stanford-iris-lab/meta-harness/blob/8123ccabe2b19fa1123090b2e5f1bacc20963ce8/ONBOARDING.md).
- RRSI: [paper v1, Table 1 and limitations](https://arxiv.org/html/2609.24972v1), [domain contract](https://github.com/google-research/rrsi/blob/be50316e1db05914068a973f322770ef08ed7ba1/rrsi/domain.py), [selection](https://github.com/google-research/rrsi/blob/be50316e1db05914068a973f322770ef08ed7ba1/rrsi/selection.py), [critic](https://github.com/google-research/rrsi/blob/be50316e1db05914068a973f322770ef08ed7ba1/rrsi/critic.py), [Git operations](https://github.com/google-research/rrsi/blob/be50316e1db05914068a973f322770ef08ed7ba1/rrsi/gitops.py).

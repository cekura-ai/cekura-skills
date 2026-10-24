# Production diagnosis of scenario-authoring skills

Reviewed 2026-10-22. This is a targeted, single-reviewer pilot of **12 product-chat
conversations**, not a production failure-rate estimate. No skill was changed,
candidate replayed, simulation started, or metric reevaluated by this investigation.
The private audit retains source IDs, event indices, excerpts, and source hashes;
the aliases below identify those records without publishing customer evidence.

## Recommendation

Start the next benchmark with **write-path selection for behavioral batches**.
One selected conversation visibly hand-authors new instruction scenarios despite
the current rule to generate them. The user supplied topics and facts and asked
for varied phrasing; this was not the complete-verbatim-payload exception.
Activation telemetry was present, so adding an activation trigger alone would
not address the observed behavior.

Compare the current skill with a compact decision checklist placed immediately
before authoring: distinguish a batch/category request, a complete verbatim save,
an exactly scripted conditional-action case, and an existing-resource update.
This is a candidate intervention, not a demonstrated fix. The current skill
already states these rules; establish whether the pinned current baseline still
violates them before adding instructions. If it does not, retain the incident as
a regression case and move to completion verification or profile binding.

The second priority is **completion after interrupted or invalidated work**:
do not reuse an old completion claim after the user says they deleted the
resources. This also needs task-state/runtime investigation; it cannot be
assigned solely to a skill prompt.

## Sample and evidence limits

| Measure | Result |
|---|---|
| Selected conversations | 12 unique conversations: 6 likely failures, 3 activation checks, 3 controls |
| Retrieval | 7 complete cached transcripts reused; 5 truncated exports replaced through sequential MCP reads |
| Additional list pages / metric-definition downloads | 0 / 0 |
| Human-role turns | 64; these are not 64 independent authoring requests |
| Activity window of selected conversations | October 1–19, 2026; ingestion timestamps differ |
| Reported plugin versions | 0.17, 0.18, and 0.19; some conversations have no activation version |
| Remaining argument truncation | 22 payloads in 5 conversations already marked truncated by the source |

Selection used the existing 500-record export index and cached request/tool
signals. The broad screen also matches run requests and inspections; its matches
are not a validated scenario-generation denominator. Selected IDs were frozen
before the five detail reads. No additional conversations were pulled to replace
an inconvenient result or improve the apparent failure count.

An earlier scoped MCP count found 558 mirrored product-chat logs and 139 aggregate
failure flags in the October 2–22 ingestion window. Those counts were not refreshed
here and do not measure scenario-authoring failures. This pilot selects from the
cached export rather than claiming coverage of all 558 logs or the newest traffic.
It targets the assistant that authors tests, not customer voice-call performance.

All 12 structured transcript arrays parse completely. That does **not** recover
the source's truncated tool arguments, uploaded attachments, or original tool
response bodies. Most saved responses contain execution status rather than saved
scenario/profile content. Seven cached records retain export-time labels; five
detail reads supply retrieval-time labels. Metric and conversation snapshot
versions are not pinned, so label differences or chronology inconsistencies may
reflect stale evaluations. No metric definition was downloaded during this pilot.

Current repository skill/reference hashes are saved privately. Activation tags
and reported plugin versions do not prove the historical skill bytes loaded by
the assistant. No calibrated second review or current-runtime reproduction has
been performed. Controls show useful workflows, not certified gold outputs.

## Ranked issue families

Counts below are conversations with relevant evidence in this selected sample.
Families overlap. Confidence describes the observation, not a proven skill-body
cause or an assertion that the issue remains in current production.

| Priority | Family / records | Evidence and consequence | Attribution and recovery |
|---|---|---|---|
| 1 | New behavioral batches hand-authored — P05, 1 | Seven untruncated calls visibly create instruction scenarios. A later batch request expressly requires varied phrasing, and the constructed instructions differ from the supplied request. | High confidence against the current write-path contract; historical loaded content unknown. Later recreation still uses direct creates. |
| 2 | Stale completion after deletion — P05, 1 | The user says the first batch was deleted and requests recreation. After an interrupted turn, the assistant declares the old IDs complete without an intervening tool call. The user repeats that the batch is absent. | High confidence in unsupported completion. Later replacement writes are visible. The assistant's claim that the original creates did not persist is not established: deletion was explicitly reported. |
| 3 | Missing profile binding before execution — P04, 1 | The assistant reports DTMF sent only the terminator because a referenced profile key was absent. A subsequent profile patch explicitly supplies that key. | Moderate confidence in the original defect: original read outputs are missing. Repair is visible; later identity failure prevents validating the requested long call. |
| 4 | Source coverage and unlicensed outcomes — P02, 1 | A user audit reports added requirements, an unexercised injection challenge, omitted central behaviors, and source cases missing from the first run. Follow-up instruction/outcome repairs are visible. | Moderate confidence; source files and full initial generated outputs are unavailable. Client verification and server generation are both possible owners. Full-suite execution is later reported. |
| 5 | Outcomes assume unfixed live availability — P06, 1 | The assistant acknowledges that an evaluator assumes availability and then patches both expected outcome and caller behavior to allow documented available/unavailable branches. | Moderate confidence in the original generated defect; high confidence in the repair write. Generator output and client review cannot be separated. Subsequent agent silence is a different issue. |
| 6 | Invalid requests and repeated rejection — P02/P03, 2 | Four generation requests repeat a rejected attachment extension. Another conversation issues three updates without the required resource ID, returning a literal unresolved path. | High confidence at the request/API boundary. Both recover. These motivate input validation and bounded repairs, not a general scenario-creativity prompt. |

For P04, changing role text and extending wait/turn chains did not establish the
requested three-minute duration. Visible follow-ups report shorter calls. This
is an unvalidated target, not proof that an additional pause would solve it.
Validate timing against the voice runtime and known-good identity fixtures.

Existing guidance already covers
[write-path selection and verification](../../cekura/skills/cekura-eval-design/SKILL.md),
[source reconciliation and supported inputs](../../cekura/skills/cekura-eval-design/references/auto-generation.md),
and [profile/mock consistency](../../cekura/skills/cekura-eval-design/references/test-data-design.md).
Several related backend generation fixes were identified in the earlier research.
This pilot did not replay those fixes or recheck deployed behavior; historical
incidents must not be described as reproduced current regressions.

## Activation, labels, and successful controls

| Record | What the review establishes |
|---|---|
| P01 | Creation is reported, then an approved smoke-run turn stops with an assistant error. Partial completion is not evidence that the created scenarios used the wrong mode. Some generation arguments remain truncated. |
| P02 | The stored completion explanation says the final rerun is balance-blocked. Later transcript turns show an accepted execution and report a full result breakdown. Treat this as a stale snapshot or chronology error requiring review; the temporary balance error itself was real. |
| P03 | Three omitted-ID retries recover. Count one affected conversation, and preserve the recovery rather than labeling the entire task failed. |
| P05 | The final rebuild turn is cancelled. Cancellation is separate from the earlier observed route and completion problems. |
| P07 | A read-only variable review has no activation evidence and only one visible list call. It may be an activation gap; the detailed correctness claims cannot be independently verified from status-only output. No wrong scenario is established. |
| P08 | An ask-first request ends at plan approval, with no writes. Missing activation may be separate, but this is not an invalid generation. Preserve the user's approval gate. |
| P09 | A later request to add a missing case is followed by generation, waiting, and retrieval without activation telemetry. Signature execution explains the appropriate skill-use label. |
| P10 | Source-based generation, explicit overlap requested by the user, language corrections, and a folder move are visible. Exhaustive source coverage remains unverified. |
| P11 | The same ask-first starter as P08 proceeds to five-case generation after the user approves the mix. This is the paired positive workflow control. |
| P12 | A benchmark-shaped batch is generated and executed. Poor agent scores do not imply failed authoring. Exact comparison with the published benchmark remains unproven; the final answer itself acknowledges differing measures. |

Passing the existing write-path metric is insufficient: P02 and P06 pass that
check while containing reported or acknowledged semantic problems. A skill-use
label also measures workflow relevance rather than scenario usefulness. Keep
authoring contracts, semantic quality, runtime discrimination, activation, and
conversation completion as separate evaluation dimensions.

## First benchmark to build

Create six isolated, sanitized fixture tasks before comparing prompt versions.
These are specifications, **not executable tests delivered by this pilot**.

| Case | Expected behavior / acceptance |
|---|---|
| Numbered behavioral batch, facts supplied, varied phrasing requested | Use generation with explicit instruction format, requested count, and source facts; do not construct direct instruction creates. |
| Single category-level behavioral case | Generate one case; supplying the facts does not make it a complete verbatim save. |
| Complete instruction payload explicitly saved unchanged | Permit direct create and preserve the supplied instruction text exactly. Do not make a blanket no-direct-create gate. |
| One exactly scripted CA/DTMF case | Use the supported direct conditional-action path, validate its profile bindings and required configuration. |
| Existing evaluator duplicated with a narrow change | Duplicate/update using returned IDs and preserve unaffected configuration; do not regenerate the existing suite. |
| Same ask-first request before and after approval | Before approval, produce the plan and no writes; after approval, execute the agreed generation without asking again. |

Pin the skill/reference content, model, tool schemas, and isolated fixture state.
Record actual tool arguments and response bodies, including saved resources.
Use deterministic route/count/identifier assertions and an explicit text-preserving
oracle for the verbatim exception. Check semantic preservation separately, without
putting grading labels into the authoring context. Grade missing evidence as
inconclusive. Run identical fixtures against the current skill first, then the
compact-checklist candidate; compare route violations, request fulfillment,
clarification behavior, and cost. Do not promote a candidate that fixes batch
routing by breaking the legitimate exceptions or approval boundary.

Next add deletion/recreation continuation, missing DTMF variables, rejected-source
conversion with preserved content, and live-state branches. Binding checks can
start locally; duration/interruptions require voice execution, and live-state
scenarios need both a correct agent and a deliberately defective version to
establish useful discrimination. Keep related requests/variants in the same
dataset split. Human review must calibrate the semantic labels before optimization.

The [20-case catalog](scenario-skill-cases.json) remains a non-executable synthetic
starting point. The [evaluation methodology](scenario-skill-evaluation.md) and
[optimizer comparison](skill-optimizer-alternatives.md) describe later stages.
This pilot supplies evidence for what to measure; it does not establish GEPA,
Meta-Harness, SkillOpt, or any prompt version as the best optimizer or skill.

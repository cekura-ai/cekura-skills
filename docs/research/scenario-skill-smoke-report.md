# Scenario-authoring smoke comparison

Execution dates: 2026-10-22–23 (Asia/Kolkata). Status: **suggestions_ready**.
The fixed-runtime baseline and two-iteration Stanford Meta-Harness loop completed
**60 conclusive target rollouts**. Candidate 1 was selected under the original grader:
training improved from **11/12 to 12/12**, and independent validation from
**5/6 to 6/6**, with no new validation failure. Both candidates passed 6/6
validation; the agreed smaller-skill tie-break selected candidate 1.

The suggested fix requires complete source text in generation inputs and adds
verification/repair of generic generated expected outcomes. The measured gain
is on a literal-fragment source-input check. A later audit found that check
could reject faithful paraphrases and accept omitted policy facts or incorrect
saved outcomes. It did not establish complete forwarding or semantic improvement.
**Semantic review is pending**;
no candidate sealed evaluation or accepted patch was produced. Released skills,
references, bundles, acknowledgement tags, manifests and versions are unchanged.

## Results and selection

| Skill | Training | Independent validation | Sealed baseline | Target model spend | Rollout elapsed time |
|---|---:|---:|---:|---:|---:|
| Baseline | 11/12 | 5/6 | 5/6 | $8.46066195 | 2,101.77 s |
| Candidate 1, selected | 12/12 | 6/6 | Not run | $7.16133330 | 1,983.36 s |
| Candidate 2 | 11/12 | 6/6 | Not run | $5.91528960 | 1,672.99 s |

Baseline passed 21/24 overall. Candidates were evaluated on the same 12 training
and six validation tasks; their spend and time cover those 18 rollouts each.
The sealed column is a baseline reference, not a candidate comparison.
No inconclusive execution, infrastructure failure, timeout or targeted repeat
was used in these results. All 60 rollout sandboxes have successful awaited
termination records. All executions share one environment and grader identity.

| Family | Baseline training | C1 training | C2 training | Baseline validation | C1 validation | C2 validation | Sealed baseline |
|---|---:|---:|---:|---:|---:|---:|---:|
| Behavioral/direct routing | 2/2 | 2/2 | 2/2 | 1/1 | 1/1 | 1/1 | 1/1 |
| Conditional actions and required profile variables | 2/2 | 2/2 | 2/2 | 1/1 | 1/1 | 1/1 | 1/1 |
| Complete user-supplied scenario text | 2/2 | 2/2 | 1/2 | 1/1 | 1/1 | 1/1 | 1/1 |
| Updates and stale/deleted IDs | 2/2 | 2/2 | 2/2 | 1/1 | 1/1 | 1/1 | 1/1 |
| Policy/document source contracts | 1/2 | 2/2 | 2/2 | 0/1 | 1/1 | 1/1 | 0/1 |
| Approval, cancellation and completion | 2/2 | 2/2 | 2/2 | 1/1 | 1/1 | 1/1 | 1/1 |

Both candidates satisfy strict validation improvement without a new
baseline-passing validation failure. Candidate 1 is 64,013 UTF-8 bytes;
candidate 2 is 65,152 bytes. Size precedes measured cost in the agreed tie-break,
so candidate 1 wins even though candidate 2's training-plus-validation cost is
lower. Candidate 2's lower training cost partly reflects its lost-text failure;
it is not evidence of equal quality at lower cost.

## Failures and suggested skill edits

The baseline failed `source_inputs` on `orchard-2` (training), `theatre-1`
(validation) and `ceramics-1` (sealed baseline). The frozen check searches for
specific literal source fragments in generation arguments; it does not establish
complete source delivery or coverage. The assistant paraphrased
that text; in the training failure it also claimed that the full text had been
included. A semantically equivalent paraphrase can still fail this exact
check. In an audited example the baseline retained the relevant facts. These
grades do not prove that the rejected paraphrases or resulting outcomes were
semantically wrong. Original measurements remain unchanged for reproducibility.

The [v2 benchmark](../../experiments/scenario_skills/v2/domain_spec.md) replaces
this check with source-byte evidence, saved-state contracts and a human-qualified
semantic judge. Its 72 tasks also cover more failure paths and positive contrasts.

Candidate 1 changes four existing skill lines, leaving protected material exact:

- Paste complete supplied document text verbatim into `extra_instructions`,
  including case-specific details, and also pass it through `generation_files`.
- Clarify in the generation argument table that attaching a file does not
  replace forwarding its complete text.
- Read `expected_outcome_prompt` after generation and minimally patch generic
  outcomes to name concrete, source-supported criteria; disclose the repair.

Candidate 1 passed both evaluated source-contract failures. The expected-outcome
rule is part of the proposal, but its semantic benefit has not been independently
signed off. Review whether the source supports each outcome and whether the
scenario reaches its intended trigger. The blanket document-copying rule also
needs review for larger source documents beyond this smoke's coverage.

Candidate 2 retains those changes and adds folder-existence checks, a direct
progress read when the wait helper cannot obtain status, preservation of scenario
instruction format during repair, and verification of metric types before
claiming grading coverage. It passed the source checks but regressed on
`museum-2`: only 283 characters/the first archive entry were saved from the
roughly 113 KB user-supplied scenario. `field:instructions` and `completion_ids`
failed. Its final response said the evaluator was created while acknowledging
that the remaining 1,699 entry lines were still missing. This is a conclusive
authoring failure. Candidate 2's additional rules are not recommended as a
measured improvement by this experiment.

The raw candidate-1 rationale incorrectly says baseline training was “8 of 9”.
The measured result is **11/12**. Raw proposer output is retained unchanged for
audit; grades and counts in this report come from rollout evidence, not that
narrative. No retry was scheduled merely to erase candidate 2's regression.

## Fixed target and proposer

| Component | Pinned effective configuration |
|---|---|
| Target source | `650297f5efceb98d02c4dc83976c490da4f8b48a` |
| Matching Modal image | `im-g7QenNGYBK96AdEcuSSsha` |
| Authoring runtime | Python 3.11.12, Node 22.23.2, Pi 0.84.1; original runner and extension |
| Target model | `accounts/fireworks/routers/kimi-k3-fast`, Fireworks, low reasoning |
| Provider API | Anthropic Messages, `/inference/v1/messages`; original payload unchanged |
| Limits | 32,000 output tokens; unchanged 256,000 client context; verified 1,048,576 provider context |
| Skill loader | Original 60,000-character cap, including its existing truncation behavior |
| Tool catalog | 190 original tool objects, Cekura 1.29.0, exported through Codex |
| Proposer | Isolated existing EC2 Claude Code 2.1.308, `claude-opus-5-5`, high effort |
| Stanford Meta-Harness | Original revision `8123ccabe2b19fa1123090b2e5f1bacc20963ce8` |

The user selected EC2 Claude Code as proposer. It does not need Cekura MCP:
it receives only allowed skill/reference material and training history. The
fixed target uses a local stateful MCP fixture with the captured original
schemas; unknown tools fail locally. Production tool access is blocked. The
original Stanford history routines and MIT license are vendored unchanged;
the bounded domain adapter preserves the history-driven proposal loop. A local
Codex proposer remains implemented but was not used for these proposals.

Frontmatter/activation, acknowledgement lines, reference/example bytes, target
model/runtime/system prompt, tool schemas and fixture generation behavior were
held fixed. Each task resets state and runs the original loading,
tool discovery, polling, repair and readback paths. The smoke adapter limited
interaction to four turns and reconstructed prior history as plain role strings;
v2 preserves the original runner's history and allows eight turns. Complete installed bytes
and actual loader-delivered text are captured separately. Both candidate files
exceed the existing loader cap; actual provider request bodies confirm their
new rules reach the target within that cap. The experiment does not establish
that increasing or removing the cap would improve behavior.

The experiment environment SHA-256 is
`8395a2a82d1c39cf76989bcba8d3a326a37d87eadb362bef75be0bd662155ea5`;
the grader SHA-256 is
`98e6aa2957b83cb0235d97e23f4fcdb2e7cc3b049c39ff747c58913db7287d64`.
Baseline, candidate-1 and candidate-2 skill hashes are recorded in private
`suggestions.json`. Runtime, settings, schema and proposer-image hashes remain
in the private preflight/configuration snapshots.

## Usage and spending

| Accounted item | USD |
|---|---:|
| Baseline target model, 24 tasks | 8.46066195 |
| Candidate 1 training, 12 tasks | 5.25121290 |
| Candidate 1 validation, six tasks | 1.91012040 |
| Candidate 2 training, 12 tasks | 3.98111625 |
| Candidate 2 validation, six tasks | 1.93417335 |
| Total reconciled target model spend | **21.53728485** |
| Infrastructure reservations, 60 rollouts plus earlier probes | **7.30000000** |
| Two proposals, incremental billing | **0.00000000** |
| Total charged/reserved in shared ledger | **28.83728485** |

Infrastructure is conservatively retained at $0.10 per rollout plus $1.30 from
earlier probes; actual infrastructure billing is pending. There are no
unsettled provider requests or unknown model-usage reservations. The total
above includes those infrastructure reservations and is not a final
infrastructure invoice.

Target usage: **1,875,938 uncached input tokens**, **21,606,803 cache-read input
tokens**, **149,889 output tokens**, and **zero cache-creation tokens**. Verified
rates are $4.50/$0.45/$22.50 per million input/cache-read/output tokens. The
gateway reserved **$5.438592 before each target request**, using the full verified
provider context and original output bound, then reconciled authoritative usage.

The initial $25 allowance was extended under the user's explicit policy to
$100 total ($5 proposer/$95 target and infrastructure), triggered by candidate
1's `museum-2` request. The atomic extension recorded authorization and policy
hash and retained all earlier entries. The ledger was never reset.

Claude Team extra usage was verified disabled before each subscription-only
invocation. Two successful proposals reported **$14.0649536 nominal API-equivalent
cost** ($7.41584 + $6.6491136) and **$0 incremental billing**. An earlier tiny
connection check reported $0.018648 nominal and $0 incremental, separately.
These are subscription-backed observations, not an assumption that existing
authentication makes inference free.

## Transport recovery and experiment isolation

Iteration 1 completed with 12/12 training passes. Iteration 2's first invocation
was rejected as “Prompt is too long”, with zero input/output tokens and zero
nominal/incremental cost. The original rejected inputs and events are retained.
A lossless shared-text encoding reduced accumulated training history from
3,959,096 to 1,552,291 UTF-8 bytes. Repeated strings are stored once by SHA-256;
all 24 training records, candidate bodies, full arguments/results and states
decode exactly, verified by round-trip hash. Nothing was selected or summarized
away. The recovered prompt was 1,815,864 bytes and produced candidate 2 with
the same model and settings. Its separate reservation settled to zero incremental
cost. Three CLI invocations yielded exactly two candidates/two search iterations.

The live experiment resumed from a frozen controller whose environment and
cache hashes matched existing evidence, reusing all 36 completed baseline and
candidate-1 training rollouts without additional inference. It continued from
that controller until validation completed. Reusable repository fixes did not
change the live target, grader, fixtures, generator or references.

Reusable code now uses lossless shared-text transport, pins serializer source
bytes, and excludes volatile `cache_hit` flags from proposal identity. Normal
resume and targeted repeat commands reject changes to the complete experiment
identity, including datasets, reference material, controller code and
dependencies, before preflight or spending. Budget extension, unknown usage,
timeouts, checkpoints and suggestions-only stopping are tested. Held-out tasks,
results and grader code were inaccessible to both proposer sessions. Their
containers mounted only authentication read-only, with no model tools/MCP,
host repository or held-out mounts.

## Deliverables and verification

The executable benchmark, evaluator, cost admission, isolated proposers,
Stanford adapter, synthetic fixtures and tests live together in
[`experiments/scenario_skills/`](../../experiments/scenario_skills/domain_spec.md).
The [domain specification](../../experiments/scenario_skills/domain_spec.md)
documents configuration, interfaces, preflight, execution and resume. The
[methodology](scenario-skill-evaluation.md) and
[optimizer research](skill-optimizer-alternatives.md) now reference this result.

Private evidence root for this run:
`/private/tmp/cekura-runtime-image-2026-10-22/`. `final-evidence.json` verifies
counts, hashes, usage, ledger totals and teardown. Under `loop-to-suggestions/`:

- `suggestions.json` / `suggestions.md`: selected candidate, actual scores,
  raw rationales and explicit unapproved status.
- `candidate-1.unapproved.diff`: the selected body-only suggestion;
  `candidate-2.unapproved.diff`: the alternative retained for audit.
- `validation-review.json` and `validation-signoff.template.json`: blinded
  baseline/selected outputs, source policies and hash-bound review template.
  The private identity map is kept separate from the review packet.
- `rollouts/`: exact loaded skill/reference bytes, full tool arguments/results,
  initial/final state, model/runtime configuration, usage, grades and termination.
- Rejected and recovered proposal inputs/events/billing plus lineage metadata.

The current repository's offline suite passed **81 tests in 9.827 seconds**.
These include a complete scripted 60-rollout/two-iteration suggestions loop and
resume, no accepted patch/candidate sealed execution, bad routing/variables/
stale IDs/false completion, state reset, lossless Unicode/full history,
filesystem isolation, budget bounds/extension and repeat identity guards.
Tests use scripted actors, not paid inference. The restricted attempt's socket
binding and nested sandbox denials were resolved by a scoped unrestricted
rerun; they were not target execution failures.

All 24 scripted fixture contracts passed with captured schemas and readback.
Exact-image offline probes verified CRUD/generation/poll/repair, 140 KB Unicode
capture, candidate delivery, original loading and blocked direct egress with
zero inference. The Messages gateway and real isolated Claude structured-output
checks passed before baseline execution. Earlier failed probes remain private
infrastructure evidence with their reservations retained.

Verification commands:

```sh
/private/tmp/cekura-benchmark-venv/bin/python -m unittest discover -s experiments/scenario_skills/tests -v
/private/tmp/cekura-benchmark-venv/bin/python -m experiments.scenario_skills validate-fixtures
/private/tmp/cekura-benchmark-venv/bin/python cekura/scripts/validate_skills.py
/private/tmp/cekura-benchmark-venv/bin/python cekura/scripts/validate_ack_tags.py
/private/tmp/cekura-benchmark-venv/bin/python cekura/scripts/build_bundles.py --check
git diff --check
git diff --exit-code -- cekura codex/AGENTS.md GEMINI.md package.json
```

Packaging checks passed: 14 skills, acknowledgement tags in 11 files/13 manifest
slugs, six current bundles, manifest/version parity and Codex/Gemini preset
parity. No `cekura/**` changes means no plugin-content version bump is required.
Existing working-tree changes are preserved. Harness/fixtures/tests/docs form
one logical change; a later accepted skill patch belongs in a separate change.
No staging, commits, publication, deployment, production writes, telemetry
changes or voice runs were performed.

## Acceptance gates and limits

The user authorized engineering fixture review before inference and deferred
human semantic review until acceptance. The suggestions goal ends here. Review
the blinded validation packet for invented policies, unsupported outcomes,
source coverage and trigger reach, then supply domain signoff. Only after that
gate may the selected candidate run on six sealed tasks. Acceptance requires
no new baseline-passing sealed failure and no semantic defect; sealed evidence
must never feed another proposal in this experiment. No `accepted-skill.patch`
exists, and the released skill has not been changed.

These are 24 synthetic tasks in 12 independent packs, informed by Cekura
assistant `product_chat` authoring conversations, not customer voice-agent
production calls or exact historical replays. Six validation tasks can reveal
a targeted contract gain but cannot establish production failure rates, the
confidence/coverage of 180 tasks, optimizer superiority or broad reliability.
No repeat-variability estimate was made. Automated search scores primarily
measure authoring contracts; semantic findings remain pending. Generation
responses were fixed, so no backend-generator improvement was demonstrated.
Validate promising edits with isolated real tools and then voice execution
before claiming a production improvement. Expand smoke coverage only where
observed failures or variability justify it.

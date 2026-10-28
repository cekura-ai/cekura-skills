# Continue the experiment in remote Claude Code

This handoff transfers implementation and orchestration to the user's existing
EC2 Claude Code workspace. It does not start inference, approve domain labels,
or change the Cekura target into Claude. Read `CLAUDE.md` and applicable repository
instructions before implementation. Preserve all existing working-tree changes.

## Current state and source of intent

The user's latest decisions supersede older experiment documentation/configs:

- Use the **real isolated backend and its actual LLM generator** for ordinary
  scored tasks throughout training, validation, and sealed evaluation.
- Use explicit, recorded fault injection only for exceptional conditions.
  Scripted successful generator responses are engineering tests, not evidence.
- The maximum is **$150 cumulative**, replacing $200. Recorded historical
  spend/reservations are $29.13728485; at most $120.86271515 remains. Reconcile
  historical entries once; no old run may independently reopen its allowance.
- After implementation, testing, and upfront fixture/gold approval, one command
  must run through qualification, baseline, search, independent evaluation, and
  a terminal report. Final human patch acceptance happens after that run.
- No commits, staging, publication, deployment, production writes, telemetry
  changes, or voice execution are included.

Existing implementation: `experiments/scenario_skills/v2/`. Existing reports:
`docs/research/scenario-skill-smoke-report.md`, `scenario-skill-evaluation.md`,
and `skill-optimizer-alternatives.md`.

Historical smoke: 60 scored target rollouts; baseline 21/24; candidate 1 training
12/12 and validation 6/6. Candidate 2 lost a large supplied scenario. Candidate 1
won a smaller-size tie-break, but its measured source-input gain used a flawed
literal-fragment grader. No candidate sealed evaluation or accepted patch exists.

V2: 28 tests and 81 legacy tests passed during the preceding audit, with a
matching-image scripted transport probe. No v2 target/proposer/judge inference
has run. The current private run is awaiting fixture/gold human review; there
is no approval to manufacture or infer that signoff.

## Roles and isolation

The remote **implementation** Claude session may read the harness, grader,
fixtures, and reports. It must not act as the experimental proposer or judge.
Experimental proposers use fresh restricted sessions with training evidence
only; graders and held-outs remain inaccessible. Judges use separate blinded
sessions and frozen rubrics. Retain subscription-only access with extra usage
disabled and no paid fallback. Track quota and nominal usage separately.

Pinned authoring target: source `650297f5efceb98d02c4dc83976c490da4f8b48a`,
Modal image `im-g7QenNGYBK96AdEcuSSsha`, Pi 0.84.1, Fireworks
`accounts/fireworks/routers/kimi-k3-fast`, low reasoning, original 32k output.
Keep original prompts, schemas, tool loop, skill loading, history, and repair.
The 190 captured schemas came through Codex; future remote execution does not
require Codex's authenticated production MCP connection.

Stanford Meta-Harness revision:
`8123ccabe2b19fa1123090b2e5f1bacc20963ce8` (vendored with license).

Claude Code was verified on EC2 as 2.1.309 with claude.ai team authentication;
older artifacts pin 2.1.308. Capture a new identity rather than pretending the
CLI is unchanged. Translate local paths and replace remote-to-self SSH transport
with equivalent local isolated execution; do not weaken proposer/judge isolation.

## Implement before paid execution

1. Build the missing real-backend runner against pinned handlers, persistence,
   asynchronous jobs, polling, and readback. Seed isolated synthetic resources;
   use isolated database/storage/queue scopes. Do not inherit broad production
   `.env`, AWS mounts, MCP configuration, or runtime environment. Inspect the
   existing backend and its instructions; do not modify its active checkout.
2. Capture effective backend generator planning/worker models, prompts, runtime,
   reasoning and fallback routing. The code supports Fireworks planning, Gemini
   workers, and alternatives; a Claude SDK process does not establish its model.
   Keep this configuration fixed across arms. Meter every nested inference and
   liveness probe before forwarding, plus infrastructure and retries. Terminate
   all nested work on timeout/cancellation/budget exhaustion.
3. Fix the verified allowed-write defect: modifying the original during
   `lifecycle-2` duplication currently passes. Cover all scenario/profile/folder/
   configuration mutations, duplicate destinations, and requested profile reuse.
4. Fix permitted terminal outcomes: `repair-0` permits recovered three cases or
   two with truthful unresolved reporting; its current exact-count check does not.
   Adapt fixed-output expectations to real backend state/semantic contracts.
5. Align judge citations with source documents/request/configuration/evidence;
   reject rubric/nonexistent citations. Preserve uncertainty and disagreements;
   they cannot establish improvement. Criterion-level human changes must rescore
   cached evidence and selection gates.
6. Replace copied child budgets with one locked cumulative authorization ledger;
   implement $150 policy and retire superseded spending paths. Make malformed
   output settlement, checkpoint recovery, saved response replay, rejection
   artifacts, and terminal/export commands idempotent.
7. Capture actual skill/read results, including native 50 KiB and Skill 60,000
   character limits. Map candidate edits to delivered content. Installed hashes
   alone do not prove receipt or explain causality. Optimize only the skill body;
   preserve frontmatter, acknowledgements, references, and all other skills.
8. Test these failures and recovery paths, concurrency/billing, isolation/cache,
   large payloads, and real-handler integration. Update existing docs and domain
   specification, which still describe the older mocked/$200 experiment.

## Frozen experiment protocol

Keep 72 synthetic tasks / 48 packs: 36 training (24 packs), 12 validation
(12 packs), 24 sealed (12 packs). Preserve twelve-family coverage and pack split
independence; reset resources per task. Review every policy, fixture, expected
behavior, and label before freezing a new experiment identity.

Use 48 judge gold examples: 24 calibration then 24 independent qualification.
Freeze after calibration; qualification requires 22/24 correct, zero critical
false passes, and correct paraphrase control. Do not tune using qualification.

After upfront human approval, one bounded command must:

1. Qualify the judge; fail to a terminal report if it does not qualify.
2. Run 12 baseline training canaries (included in baseline), capped at $15 new
   spend for cost discovery. Measure authoring/generator/infrastructure by family.
3. Forecast the minimum complete comparison with 25% planning margin and reserve
   validation, sealed, scheduled repeats, and request-level headroom. If it does
   not fit, report infeasibility; do not drop coverage or change target models.
4. Complete baseline training. Propose from training only. Allow up to four
   proposal attempts, at most two fully evaluated training candidates. Canary
   screen before full training; reject regressions/duplicates/protected edits/
   fixture-specific facts. Retain the strongest eligible parent; stop on
   saturation, no_change, two zero-gain evaluated candidates, or budget shortage.
5. Freeze ONE finalist using training only, then baseline/finalist validation.
   Require strict gain and no newly failing baseline-passing task. Failure ends
   search; held-out findings never feed a new proposal.
6. Continue directly to baseline/finalist sealed evaluation if automated gates
   pass. Require strict gain, no new failure, no unresolved critical defect.
7. Repeat both arms once on validation variables-3/lifecycle-3/triggers-3 and
   sealed verbatim-4/sources-4/causal-4 (12 rollouts). Include all observations;
   genuine instability prevents unsupported acceptance. At most 12 additional
   diagnostic rollouts, justified by inconsistency and within the same budget.
8. Produce terminal comparison, costs, failures, variability, configuration,
   loaded instruction evidence, and blinded final-review packet. Export only
   a recommendation pending final domain review; no deployment or publication.

Maximum target paths including scheduled repeats: 156 with one full candidate;
192 with two; 216 with two plus two rejected 12-case screens. All ordinary
scored paths use real generation. There is no separate 24-run backend phase.
These counts are ceilings, not promises to spend or establish improvement.

Run sequential target trials, alternating paired arm order. Preserve internal
generator behavior. Ten-minute task limits, bounded retries, durable checkpoints,
24-hour overall deadline. No paid Claude fallback on subscription exhaustion.

Report authoring and backend defects separately. A correctly formed request
that exposes a generator defect is not automatically a reason to grow the skill.
Keep reusable code/tests/synthetic data/docs as one logical change; a supported
skill patch is separate and requires skill/ack/bundle/manifest/version checks.

## Remote material

The transfer package includes an exact current source snapshot, a pinned backend
source archive, private v2 preparation artifacts, and a transfer manifest.
Credentials and customer production evidence are excluded. Resolve prerequisites
from the remote environment without printing secrets; missing Modal/provider
configuration must be reported before inference. Local absolute paths in old
artifacts are provenance, not valid remote configuration.

For interactive continuation, enter the transferred repository and start Claude
with production MCP disabled:

```sh
claude --strict-mcp-config --mcp-config '{"mcpServers":{}}' -- \
  'Read docs/research/scenario-skill-claude-handoff.md and implement its remaining preparation work. Preserve existing edits and the cumulative $150 ceiling. Do not start benchmark inference before the concrete preparation packet receives the required domain signoff.'
```

Use tmux if the session should survive SSH disconnection. The preparation packet
must be complete and reviewable before requesting its final launch approval.
The `--` before the prompt is required: `--mcp-config` accepts multiple values
and otherwise consumes the prompt as another configuration path. A multiline
shell command uses a backslash followed by an actual newline, not literal `\n`.

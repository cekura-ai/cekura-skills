# Cekura scenario-authoring smoke domain

This specification preserves the original 24-task smoke. The approved follow-up
is implemented separately in the [v2 domain specification](v2/domain_spec.md),
with 72 tasks, training-heavy splits, qualified semantic judging, adaptive search
and a cumulative $200 ceiling. Its human fixture/gold gate supersedes the smoke's
engineering-only review authorization. The old `source_inputs` score was a
literal-fragment check and did not prove complete source forwarding or semantic
improvement; historical results are retained without regrading them.

This experiment changes the body of `cekura-eval-design` using an isolated proposer and
Stanford's original Meta-Harness revision
`8123ccabe2b19fa1123090b2e5f1bacc20963ce8`. It evaluates the Cekura assistant
that authors and saves scenarios. The historical diagnosis concerns assistant
conversations mirrored as `product_chat` logs, rather than customer voice calls.

Implementation status and measured limits are in the
[smoke report](../../docs/research/scenario-skill-smoke-report.md). The code is
implemented and locally tested. A source-replica Docker image and the exact
captured production Modal image have passed offline runtime probes. The target
comparison uses the passing machine preflight and 190 original MCP tool
definitions exported through Codex. The user authorized engineering fixture
checks before inference, with human semantic review deferred until acceptance.
Claude proposes edits without Cekura MCP access. Model usage semantics, billing rates and conservative request bounds
have been verified. Existing provider
credentials passed read-only model catalog checks. The exact router advertises
a 1,048,576-token server context; the unchanged extension uses 256,000. The
gateway reserves the full server bound plus 32,000 output tokens ($5.438592),
then reconciles measured usage. The deployed-image Messages
transport passed with a fixed response. A tiny EC2 Claude structured-output
check passed using the existing Team subscription. The baseline and improvement
loop completed 60 conclusive rollouts in the matching Modal image. Candidate 1
was selected with 12/12 training and 6/6 independent validation, compared with
baseline 11/12 and 5/6. The smoke report records the full comparison, costs and
limits. Suggested edits remain unapproved until acceptance gates pass; no
candidate sealed evaluation or accepted patch was produced.

## Roles and fixed inputs

| Role | Interface | Responsibility |
|---|---|---|
| Cekura authoring runtime | Original product-chat `agent_runner.py` and Pi extension in a pinned image | Author using the installed candidate, tools and follow-up turns |
| Codex proposer | `CodexProposer.propose(baseline, training_history, iteration, forbidden)` | Return a schema-validated body and rationale in a fresh isolated session |
| User-selected EC2 Claude alternative | `ClaudeProposer.propose(baseline, training_history, iteration, forbidden)` | Use the same training history loop through an isolated native Claude Code container |
| Fixed evaluator | `Evaluator.evaluate(candidate_bytes, task, repeat=0)` | Capture execution, grade observable contracts and return evidence |

The candidate is a complete UTF-8 skill file reconstructed from an unchanged
frontmatter and proposed body. Acknowledgement lines and reference links remain
exact; reference/example bytes, activation description, target model/provider,
system prompt, runtime environment, tool schemas, generator responses and task
state stay fixed. The model is never replaced by Codex or changed to save money.

The runner/extension captured from a production sandbox match the latest
successful production deployment source. They specify Kimi K3 Fast on Fireworks
with low reasoning effort. Effective Pi/lazy-discovery and stall-timeout flags,
Pi global settings and the immutable Modal image ID were captured read-only.
The schema-complete evaluator snapshot now passes machine preflight. The original `_run_skill` caps
text at 60,000 characters, whereas the repository skill is 62,582 characters.
The adapter records installed bytes separately from the exact text produced by
that pinned loading rule, including the truncation suffix. Confirm the deployed
loading path and cap in the snapshot; do not silently change either.

## Fixtures and success criterion

`fixtures/packs.json` contains 24 synthetic tasks in 12 packs. Each has a request,
scripted follow-ups, agent record, initial resources, policy documents and fixed
generator responses. `fixtures/expectations.json` holds the oracle separately.
`fixtures/freeze.json` pins both hashes and records engineering review.
`fixture_review_mode="engineering"` requires explicit `review_authorization`
and current schema-contract evidence, recorded in `engineering-fixture-review.json`.
This gate never supplies human domain signoff. The default `human` mode still
requires fixture signoff before inference. Fixture state resets between tasks.

| Split | Packs | Tasks | Use |
|---|---:|---:|---|
| Training | 6 | 12 | Proposer feedback |
| Validation | 3 | 6 | Independent candidate selection |
| Sealed | 3 | 6 | Final comparison |

The six families are behavioral/direct routing, CA/profile variables, complete
verbatim text, updates/stale IDs, source grounding, and approval/cancellation/
completion. Each family has two training tasks and one task in each held-out
split. Domains and policy facts differ between packs, not only identifiers.

Example: a library task requests two behavioral tests for reservation and loss
questions. Passing requires the generation path, the requested count, completed
polling, correct persisted scope and folder, and truthful completion with saved
IDs. A neighboring exact-text request must use direct creation and preserve the
entire instructions field. Neither task authorizes voice execution.

The automated score is 1 only when every required observable check passes.
Timeouts fail after ten minutes under identical limits. Infrastructure failures
and inconclusive runs are recorded separately and cannot establish improvement.
Source text must reach generation inputs; usefulness, unsupported outcomes,
invented policies and trigger reach require human review. This small dataset
tests integration and large targeted improvements. It does not provide the
confidence or coverage of 180 tasks or estimate production failure rates.

## Runtime and fixture transport

`runtime.py` invokes the original runner through `docker run --pull=never` in
a SHA-256-pinned local image. The image must contain the deployed Python, Node,
Pi and SDK dependencies, an `agent` user with uid 1000, and `iptables`/`ip6tables`.
Both installed skill paths mount the skill tree read-only, preventing a
baked stale plugin from shadowing the candidate. Other skills are snapshotted
unchanged at evaluator initialization and included in its environment hash.
Runner, extension and captured Pi settings
are hashed again, copied to private runtime evidence and mounted read-only across
follow-up turns. Model/runtime flags come from the effective
snapshot. Files, history and context follow the original runner's `/app` contract.
Follow-ups use the driver's `role: message` history format.

The ECS controller launches a Modal inference sandbox; its controller image is
not the required inference image. Capture the deployed sandbox dependencies and
Pi global settings. `target.pi_settings_path` points to the exact settings bytes,
pinned by `snapshot.pi_settings_sha256`. The bootstrap restores them into the
disposable home before startup, because the home tmpfs hides the baked settings
Pi uses to discover skills. Preflight checks the settings hash and the actual
local Docker image ID; a digest-shaped string alone is insufficient.

The root bootstrap applies outbound firewall rules before the runner drops
privileges. For x86 emulation on an ARM Docker host, `network_guard.py` establishes
the rules in a native helper first; the target shares its network namespace
without NET_ADMIN/NET_RAW capabilities. The launcher independently reads back
the IPv4/IPv6 rules, mounts the proof read-only and tears the helper down on exit.
There is no silent fallback if setup or verification fails. Only the local
fixture and model-proxy ports are reachable; IPv6 outbound and direct
production/provider traffic are denied. The proxy permits HTTPS CONNECT only
to the captured model hostname and never forwards Cekura tools. The offline
mode rejects even that host and opens no upstream socket. Actual probes verified
Node/Python proxy use, direct-egress denial and zero capabilities after uid drop.
This Docker launcher targets macOS Docker Desktop's host gateway behavior.

`runtime_image.py` parses the captured Modal recipe without importing backend
code, prepares a private build context and records source/package/skill hashes.
`runtime-image.Dockerfile` pins Node/Pi and the recipe's direct Python packages,
verifies the Node archive checksum and records pip/npm locks. Supply captured
Pi settings with `--pi-settings` to preserve exact bytes. Record and use the built
image ID; a source replica is not automatically production-equivalent. The
captured production image uses Python 3.11.12 and several different transitive
packages, despite sharing the recipe's direct pins with the initial replica.

`modal_probe.py` verifies the exact captured Modal image in a **new isolated
sandbox**, with its own in-sandbox fixture and non-forwarding proxy. It uses
`Image.from_id`, verifies the returned sandbox image ID independently, caps CPU
and memory at one core/1 GiB and lifetime at 180 seconds, blocks outbound
networking, exposes no ports and injects no model credentials or identity token.
Only transport code, allowed skill/runtime bytes and one synthetic training
fixture are uploaded. It verifies Python and every captured package, Node/Pi,
settings/source hashes, original prompt construction, MCP CRUD/poll/readback,
large Unicode capture and egress. Full evidence is downloaded before teardown.
The complete SDK transaction runs on Modal's own event loop; mixing raw async
objects with stream constructors on a separate loop fails during hydration.
This is an offline image check, not a Modal adapter for the paid comparison.

`fixture.py` implements streamable-HTTP MCP initialization, tool listing/calls,
agent/resource reads, profiles, folders, creation, updates, duplication, deletion
and fixed generation jobs. A first poll returns processing; completion persists
the fixed response once. Current state is returned on subsequent reads/polls.
Bad scope, missing variables and deleted IDs return local validation errors.
MCP `tools/list` uses the original leaf names; the runner adds `mcp__cekura__`
when registering them. Traces save both the exact wire name and that qualified
name used by the grader. Captured real schemas are returned unchanged and validated with pinned
`jsonschema`; the permissive offline catalog is only for protocol tests.
Unsupported tools return errors and never fall back to production.

Every rollout retains full MCP arguments/results, runtime NDJSON, disposable
`app/` files, installed skill/reference bytes, loading evidence, effective
system-prompt bytes/hash, schema/configuration hashes, initial/final state,
checks, elapsed time, usage and spend. The cache includes candidate, task,
reference graph, benchmark code, Python/dependencies and environment hashes.
Cache hits add no inference spend. Incomplete cached results cannot be reused.
Private artifact directories must be outside this checkout and in a user home
or temporary directory; committed fixtures contain no customer evidence.

## Original Meta-Harness adaptation and proposer boundary

The unmodified Stanford source and MIT license are under `vendor/stanford/`.
Its source SHA-256 is checked before use. `meta_harness.py` loads the original
`render_task_prompt`, `count_iterations_from_summary` and
`update_evolution_summary` routines without executing the classification
example's imports, Git operations or Claude wrapper. It ports the original
history → propose → validate → benchmark → record sequence to this domain.
Upstream helper fields named `_val` describe **training** here. GEPA's engine
is not used. Independent Cekura validation happens after the two candidates
are frozen, outside the proposer loop.

Each proposer receives the baseline, allowed references/examples, and full
training history containing prior candidate bodies, scores, traces and states.
No repository, grader, held-out tasks, held-out results or customer archive is
copied into that workspace. A deny-by-default macOS filesystem sandbox blocks
user-home/private-artifact reads outside that workspace. Writes are limited to
its `artifacts/`; copied inputs are hashed before and after execution.

The wrapper runs fresh `codex exec --json --ephemeral --ignore-user-config
--ignore-rules --output-schema ...`, with the local CLI version pinned and
`gpt-6.1-sol`, provider `azure`, effort `high`. It supplies explicit provider
configuration, stores Codex logs/SQLite under its permitted artifacts directory,
inherits only the named credential environment variable and
basic process variables, and disables plugin/global configuration inheritance.
Existing auth is not treated as free usage. The proposal must have exactly
`body` and `rationale`; wrapper, acknowledgement/reference changes, oversized
skills, fixture IDs/facts and benchmark-specific instructions are rejected.
Fact/identifier scans are deterministic screens, not a guarantee against every
paraphrase; the independent splits and human review remain necessary.

The user's subsequent preference selects `proposer.adapter=remote_claude` as an
alternative to the local Codex launcher. `remote_claude.py` uses the existing
`cekura-claude-workspace` SSH alias and creates an immutable image from the native
Claude executable and its linked libraries. The container has a read-only root,
one core/2 GiB limits, no capabilities, no host repository mount and no model
filesystem/shell/web tools. Only the existing authentication file is mounted;
skill/reference text and full training history arrive on stdin. Safe mode,
empty settings sources, strict empty MCP config and no session persistence
disable ambient hooks, plugins, skills and history. JSON schema validation,
candidate screening, exact input hashes, timeout/teardown and resume remain in
the parent. No held-out evidence or grader is sent to this proposer.

The native CLI receives a lossless shared-text representation of training history:
repeated long strings are stored once under their SHA-256 and referenced from
the original records. Every argument, result, state and candidate body round-trips
exactly. Transport source bytes are pinned, and the output cannot embed transport
markers. This prevents accumulated history from exceeding the CLI prompt limit
without selecting or summarizing evidence. Cache-hit flags are operational metadata
and are excluded from proposal identity; reusing the same observations must not
invalidate a checkpoint. Model/configuration changes and changed evidence still do.

The live run encountered a zero-token prompt-size rejection in iteration two.
A recorded lossless transport retry preserved all 24 training observations. The
experiment resumed from an archived controller with matching environment/cache
hashes, retaining all completed rollouts and charges. The released skill, target,
grader, fixtures and loaded references were unchanged. The new serializer and
resume checks are included in reusable code for future experiments.

`claude-prepare` starts the CLI and checks authentication with networking
disabled. The verified CLI is 2.1.308; the actual structured-output check used
`claude-opus-5-5` with high effort. The authenticated usage endpoint reported
extra usage disabled. Subscription-only execution rechecks that state and the
credential hash before each invocation, stopping if either changes. Incremental
billed cost is recorded separately from nominal API-equivalent cost; the tiny
check reported $0 incremental and $0.018648 nominal. The CLI dollar flag alone
does not prove a hard request bound and is never accepted as that evidence.

## Spending, search and acceptance

The default ceiling is $25: $5 proposer and $20 target/infrastructure. The user
explicitly authorized automatic continuation when necessary up to $100 total,
with proposer limited to $5 and target/infrastructure to $95. `budget_policy`
records the initial and authorized limits and the authorization. A necessary
valid reservation that cannot fit the smoke ceiling can atomically activate the
authorized limits; the ledger records the triggering reservation and policy hash.
All earlier charges and reservations remain counted. Resume requires the same
policy. Without this explicit policy the original $25 ceiling remains enforced.
Preflight requires verified model availability/authentication, provider rates,
usage/cache semantics, infrastructure rates, and conservative maximum-cost
evidence for each provider request and infrastructure allocation. A positive
number alone is not a bound: derive it from enforced provider request/token
limits and verified spending caps. If those facts cannot
be established, stop inference. Configuration contains references and facts,
never credential values. Read-only access/registry checks must precede setting
the corresponding verified flags.

In default human-review mode, use `fixture-review`, then supply the hash-bound
`fixture-signoff.json`. The authorized engineering mode instead verifies the
frozen contracts automatically. Run two baseline tasks, counted in the baseline's
24 total. The approved continuation
uses conservative reservations **before each provider request**, rather than
reserving the worst case of the whole remaining comparison:
24 baseline + 24 candidate training + 12 candidate validation + 6 selected
candidate sealed = 66 target rollouts, and two proposals. With
`execution_goal="suggestions"`, stop after independent validation: 60 core
rollouts, no candidate sealed execution or accepted patch. Export
`suggestions.json`, `suggestions.md` and body-only `candidate-N.unapproved.diff`
files. A qualifying candidate also gets a blinded validation review packet.
At most 12 additional targeted repeats are allowed within the authorized ceiling.
Reservations are atomic
and the experiment has a single-writer lock. Missing usage retains the full
reservation and stops work; exceeding it also stops. An interrupted reservation
is never silently released or resubmitted. Reconcile trustworthy provider
usage before any manual recovery; do not reset the ledger to evade the cap.

Select only a strict validation pass-count improvement with no newly failing
baseline-passing validation task. Equivalent qualified results prefer smaller
skill size, then lower measured cost. Missing or inconsistent comparisons do
not qualify. Repeats recheck selection and acceptance rather than keeping the
best attempt. Stop if the baseline already passes everything, no candidate
qualifies, preflight fails or the next request cannot fit the remaining budget.
An unfinished comparison cannot support an improvement claim. Infrastructure
allocations and provider requests do not consume rollout slots; retries each
require a new request reservation. Outstanding requests share a locked ledger.

After selection, `validation-review.json` contains anonymized A/B outputs,
policies, rubrics and resource evidence. The identity map remains private.
The user supplies `validation-signoff.json` from the generated template with
reviewer, exact packet hash, per-task A/B decisions and findings. All candidate
semantic decisions must pass. Only then run the selected candidate on sealed
tasks. Apply the same blinded `sealed-signoff.json` gate and require no new
baseline-passing sealed failure. Sealed evidence never feeds another proposal.
Changed repeat evidence invalidates an old signoff by packet hash. Both ordinary
resume and targeted repeats verify the complete experiment identity before
preflight or spending: configuration, baseline, frozen dataset, reference and
example bytes, controller code and dependencies. A repeat cannot append evidence
from a changed environment to the original comparison. Use a new experiment for
changed inputs; do not reset the original ledger.

Only accepted candidates produce `accepted-skill.patch`. Packaging happens in
a disposable copy: rebuild bundles, bump the plugin patch version, add a
changelog entry and run skill/ack/bundle/manifest checks. Frontmatter remains
unchanged. The actual checkout/index is untouched. Recheck the repository's
version gate against current `origin/main` during normal patch review.
The harness/fixtures/tests/docs form one logical change; a supported skill
patch is a separate change. No commits, publication or deployment are included.

## Commands and preflight

From the repository root, create a temporary virtual environment and install
`experiments/scenario_skills/requirements.txt`. Python 3.9+ runs the controller;
the target image uses its captured runtime Python version. The Codex proposer
requires macOS `sandbox-exec`; the EC2 alternative uses its pinned native CLI container.

```sh
python3 -m venv /private/tmp/cekura-benchmark-venv
/private/tmp/cekura-benchmark-venv/bin/pip install -r experiments/scenario_skills/requirements.txt
/private/tmp/cekura-benchmark-venv/bin/python -m unittest discover -s experiments/scenario_skills/tests -v
/private/tmp/cekura-benchmark-venv/bin/python -m experiments.scenario_skills validate-fixtures
/private/tmp/cekura-benchmark-venv/bin/python -m experiments.scenario_skills preflight --config /private/tmp/cekura-experiment.json
/private/tmp/cekura-benchmark-venv/bin/python -m experiments.scenario_skills run --config /private/tmp/cekura-experiment.json --artifacts /private/tmp/cekura-smoke
```

Copy `config.example.json` into private storage and fill it only with verified
facts. Original schemas and the schema-complete evaluator snapshot are now pinned
in the passing private configuration. The selected execution/review policy
controls whether engineering evidence or human fixture signoff is required.
Verified model billing/usage semantics and conservative inference bounds are
recorded in private continuation evidence.
The exact Modal image is verified for offline execution. `target.adapter=modal`
selects the new exact-image evaluator; Docker remains a source-replica adapter.
The exact-image target gateway has passed its fixed-response transport probe;
that is separate from a paid model rollout. Existing provider catalog authentication
and model listing have been checked in private preflight artifacts. The supplied
example remains deliberately unverified; reuse neither an observation nor a
shared credential budget as an effective deployment or experiment cost bound.
No paid inference can proceed until these gates pass. To resume
normal checkpoints or advance a completed human gate, rerun the same command
with the same inputs and artifact directory. Changed inputs require a new run.

The Modal evaluator preserves the captured runner, extension, settings, model,
prompt construction and 60,000-character skill cap. Its sandboxes block direct
networking, use one core/1 GiB hard limits, and have a 600-second lifetime. Root
owns fixture evidence; the original runner drops privileges to uid 1000. Exact
uploaded material hashes, tool traces, resource state and raw turn streams are
captured privately. Teardown runs even when artifact retrieval fails.

The local TLS gateway reads provider JSON without changing the model payload.
The deployed extension uses Anthropic Messages at `/inference/v1/messages`.
The gateway combines `message_start` and `message_delta` usage and requires a
completed stream. Fireworks documents that input tokens exclude cache reads and
cache-creation tokens are always zero. API-key headers are omitted from captured
headers. Pi's auxiliary `pi.dev` catalog requests remain blocked and recorded
identically in every run; the explicitly registered custom target remains fixed.
It reserves the verified provider context/output bound before forwarding,
reconciles authoritative response usage, and drains interrupted streams where
possible. Missing usage retains its reservation and blocks scheduling. It denies
other hosts, paths, models and unsupported framing. TLS bytes travel between the
Modal sandbox and host through a bounded exec-stdio relay; no public port is
exposed. Only the public temporary CA certificate enters the target sandbox.
Codex uses the same admission layer and may connect only to its local gateway.
It launches with its process cwd inside the fresh workspace and ambient apps,
plugins, host skill discovery and daemon startup disabled.

Preflight requires experiment-specific spending-cap evidence, verified usage
semantics and request limits, plus passing gateway probes bound to their model,
endpoint and source hashes. Modal evidence must also match its image and flags.
The admission gateway can enforce the experiment's exclusive allowance on an
existing shared provider key using conservative, verified per-request token
bounds and its locked ledger. Pin cap evidence to the gateway code hash; a
shared provider's own advertised cap does not enforce the experiment allowance. Provider budget
refresh delays or DB-less enforcement must be included in cap verification;
an advertised budget amount alone is insufficient.
Set `budget_ledger_path` to the original private ledger when resuming prior
allocations; the report uses that same path. File locks serialize independent
controllers and offline probes, preventing concurrent reads from overwriting
reservations. Unknown usage and pending infrastructure billing are retained.

Additional commands (all artifacts remain private):

```sh
python -m experiments.scenario_skills fixture-review --artifacts /private/tmp/cekura-smoke
python -m experiments.scenario_skills claude-prepare --ssh-host cekura-claude-workspace --artifacts /private/tmp/cekura-claude-preflight
python -m experiments.scenario_skills capture-catalog --credential-env CEKURA_BENCHMARK_MCP_TOKEN --artifacts /private/tmp/cekura-catalog
python -m experiments.scenario_skills capture-catalog --credential-type api-key --credential-env CEKURA_API_KEY --artifacts /private/tmp/cekura-catalog
python -m experiments.scenario_skills capture-codex-catalog --artifacts /private/tmp/cekura-codex-catalog
python -m experiments.scenario_skills validate-catalog --catalog /private/tmp/cekura-codex-catalog/catalog.json --artifacts /private/tmp/cekura-contract-probe
python -m experiments.scenario_skills codex-gateway-probe --config /private/tmp/cekura-experiment.json --artifacts /private/tmp/codex-gateway-probe
python -m experiments.scenario_skills modal-gateway-probe --config /private/tmp/cekura-experiment.json --artifacts /private/tmp/modal-gateway-probe --budget-ledger /private/tmp/cekura-smoke/budget.json
```

`capture-catalog` sends initialization and paginated `tools/list` only; it never
calls a Cekura tool. `capture-codex-catalog` uses Codex’s existing authenticated
app-server with only `initialize`, `initialized` and `mcpServerStatus/list`.
It preserves complete original tool objects and rejects partial pages, wrong
origins and client-qualified names. It starts no model thread or turn and
invokes no Cekura tools. A complete private status export can be reused with
`--status-json /private/tmp/codex-mcp-status.json`. Credentials never enter the
export. Claude’s proposer requires neither this connection nor the catalog.

`validate-catalog` exercises all 24 frozen contracts with schema-valid scripted
create/generate/update/poll/readback trajectories. It saves private traces,
states and grades, and measures emulator reachability, not model performance.
Set `target.contract_probe_path` to its `contract-probe.json`; preflight rejects
missing, failed or stale evidence by catalog, dataset and code hashes.
The emulator supports real bulk ID arrays, transactional stale-ID rejection,
dot-separated folders, personality/language checks and sectioned or legacy-flat
profiles. Only `main_agent_variables` reach the main agent from a sectioned
profile. Frozen generator templates remain unchanged.

Gateway probes use fixed local provider responses, so they
cannot establish model quality or inference authentication. The Modal gateway
probe still reserves infrastructure from the shared budget. The pinned real
Codex CLI cannot initialize inside the filesystem boundary. The user-selected
EC2 Claude alternative passed its actual structured-output check; the exact
Modal Messages gateway passed its fixed-response check. Older failed probes
cannot satisfy preflight; use current evidence matching the source hashes.

```sh
python -m experiments.scenario_skills repeat --config /private/tmp/cekura-experiment.json --artifacts /private/tmp/cekura-smoke --task TASK_ID --candidate candidate-1 --reason 'Observed inconsistent outcome'
python -m experiments.scenario_skills report --artifacts /private/tmp/cekura-smoke
```

To prepare and probe a private Docker source replica:

```sh
python -m experiments.scenario_skills image-prepare --source /private/tmp/captured-runtime --source-ref DEPLOYMENT_REF --pi-settings /private/tmp/captured-pi-settings.json --artifacts /private/tmp/runtime-build
docker build --platform linux/amd64 --build-arg PYTHON_BASE=PINNED_BASE --build-arg NODE_VERSION=CAPTURED_VERSION --build-arg PI_VERSION=CAPTURED_VERSION --iidfile /private/tmp/runtime-image-id.txt /private/tmp/runtime-build
docker build --platform linux/arm64 --iidfile /private/tmp/guard-image-id.txt -f experiments/scenario_skills/network-guard.Dockerfile experiments/scenario_skills
python -m experiments.scenario_skills image-probe --image SHA256_IMAGE_ID --guard-image SHA256_NATIVE_GUARD_ID --source /private/tmp/runtime-build --config /private/tmp/cekura-experiment.json --artifacts /private/tmp/runtime-probe
```

Use the Docker host architecture for the helper, leaving the target x86 image
unchanged. Set `target.network_guard_image` and `target.offline_probe_path` for
the paid Docker adapter; preflight requires a successful matching probe. The
probe records source/manifest equality, installed/delivered skill bytes, dependency
locks, full state/trace and prompt bytes without model calls.
For delivery verification, `--probe-skill /private/tmp/temporary-skill.md` mounts
a body-only test edit over the baked skill. It validates the protected wrapper,
records the actual loaded hash and leaves released content unchanged. This is
transport verification, not a proposed or accepted optimization.

The optional exact-Modal-image command needs Python 3.11+,
`requirements-modal.txt`, host-only `MODAL_TOKEN_ID`/`MODAL_TOKEN_SECRET`, captured
image metadata and verified infrastructure-rate evidence:

```sh
python -m experiments.scenario_skills modal-image-probe --image CAPTURED_MODAL_IMAGE_ID --image-metadata /private/tmp/modal-image-metadata.json --source /private/tmp/runtime-build --cost-evidence /private/tmp/modal-cost-evidence.json --catalog /private/tmp/cekura-codex-catalog/catalog.json --config /private/tmp/cekura-experiment.json --budget-ledger /private/tmp/cekura-smoke/budget.json --artifacts /private/tmp/matching-probe
```

Rate evidence names `https://modal.com/pricing`, a verification date and `rates`
with sandbox CPU/core/second `0.00003942`, memory/GiB/second `0.00000667` and
egress/GiB `0.04`. The published sandbox rates include the non-preemptible
multiplier. Reserve $0.10 per attempt within the same $20 infrastructure/target
initial allowance, using the same ledger and authorized policy as the eventual
experiment. The offline entries
consume the allowance without consuming target-rollout slots. Retain all prior
reservations until actual billing is reconciled.
Paid Modal preflight requires this probe’s catalog and fixture hashes to match
the configured schemas and current emulator. Use a new probe directory after
fixture changes; prior transport evidence cannot cover different fixture code.
The command rejects reuse of an allocated artifact directory. These published
rates and resource limits bound the offline check; they do not bound model
inference or establish account-specific billing. No model credentials are sent
to this sandbox, and it never connects to production tools.

Local tests exercise scripted actors and a scripted CLI without inference. They
verify protocol/state contracts, bad grading cases, large capture, actual
filesystem isolation, budget stops and authorized extension, lossless history
transport, cache identity, two-iteration suggestions/resume and complete repeat
isolation. The current suite has 81 tests and makes no inference requests.
The separate real-image probes verify runtime startup and fixture integration.
Neither they nor the scripted tests prove inference auth, actual Codex proposal
quality or voice behavior. After a promising smoke, expand only where
failures/variance justify it, then validate isolated real tools and voice runs.

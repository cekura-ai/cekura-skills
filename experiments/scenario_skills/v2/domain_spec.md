# Scenario skill optimization v2

This implements the approved follow-up to the [24-task smoke](../../../docs/research/scenario-skill-smoke-report.md).
The smoke's apparent source-forwarding gain came from a weak literal-fragment
check. V2 separates tool/state contracts from source meaning, retains real
multi-turn history, and stops unsupported or saturated search. Implementation
and offline checks are not evidence of a better skill.

Every ordinary scored rollout runs against an isolated copy of the pinned real
backend and its real LLM generator. Fault injection is explicit, frozen in the
task and recorded in the trace. All spending, from the target, nested generator
calls, liveness probes and generator sandboxes, is admitted before forwarding
against one cumulative $150 wallet.

Engineering verification (offline, fake providers only): 53 v2 tests pass,
including a complete rollout against the pinned backend's handlers, Celery
worker and readback. The 85 legacy tests pass, and 3 macOS-only tests are
skipped. All 72 structural case controls pass. Fake-provider drills on the
assembled stack show three things:

* Direct and unaliased egress fail from the worker and the generator sandbox.
* The generator's fallbacks to unpinned providers are denied rather than
  escaping metering.
* Cancelling mid-stream aborts in-flight requests, charges them at their bound
  and removes every container and sandbox within seconds.

The full-stack concurrency drill was not completed, by decision. Stage-cap
enforcement rests on the cross-process wallet test and the threaded metering
test. Judge qualification, target trials and proposals have not run. No
candidate or accepted patch exists.

## Scope and identities

Only the body of `cekura/skills/cekura-eval-design/SKILL.md` is editable.
Frontmatter/activation, acknowledgement lines, reference links, reference and
example bytes, other skills, system prompt, runtime, model and tool schemas
remain pinned. Candidate files must fit the original 60,000-character Skill
loader and the 500-line packaging check; compression counts as an evaluated
change. The baseline is evaluated with its existing truncation behavior.

The target is the Cekura assistant authoring scenarios, using the captured image
`im-g7QenNGYBK96AdEcuSSsha`, runtime source
`650297f5efceb98d02c4dc83976c490da4f8b48a`, Pi 0.84.1, and Fireworks
`accounts/fireworks/routers/kimi-k3-fast` with low reasoning. Pi is the agent
tool loop, not another model. The proposer edits the candidate skill; the target
uses that candidate to author resources. Codex supplied the captured 190 MCP
schemas. It is not substituted for the target.

Fresh isolated Claude Code sessions on this host (CLI 2.1.309, re-captured by
`prepare-claude`; no SSH to self) use the pinned `claude-opus-5-5`/high
configuration for both proposal and judging. These roles have different inputs
and separate sessions. The proposer receives training evidence and allowed
skill material. The judge receives blinded pointwise execution evidence and
the frozen rubric, without candidate identity or skill-loading results.

The proposer mounts only a read-only training workspace. Read/Grep/Glob are the
only model tools; shell/MCP and other tools are absent. Absolute `Read(//...)`
rules protect authentication/runtime paths and reads outside working directories
are blocked, following the [Claude permission reference](https://code.claude.com/docs/en/permissions#read-and-edit).
Path-qualified Glob rules are not used because Claude never matches them.

Stanford Meta-Harness revision `8123ccabe2b19fa1123090b2e5f1bacc20963ce8`
remains vendored with its license. Its original history routines record
training evolution; Cekura adapters own execution, safety/budget gates,
candidate screening and independent selection. This is a bounded domain port,
not a claim that every upstream search feature is reproduced.

No production writes, deployment, telemetry changes, Git staging/commits or
publication are part of this experiment. Actual voice execution remains later.
Optimize other skills individually after establishing comparable contracts;
use joint optimization only for demonstrated cross-skill interactions with
separate regressions and an ablation showing which changes caused the gain.

## Dataset and coverage

| Split | Tasks | Packs | Per family | Role |
|---|---:|---:|---:|---|
| Training | 36 | 24 | 3 | Search feedback across two independent contexts |
| Validation | 12 | 12 | 1 | One-time selection after finalists freeze |
| Sealed | 24 | 12 | 2 | Final challenge and contrast within an unseen context |
| Total | 72 | 48 | 6 | Targeted authoring coverage |

A pack owns a domain, policy and starting resources. Related cases stay in one
split, preventing domain facts leaking into held-outs. Each task still resets
state. Packs measure correlated coverage; two cases in one pack are not two
independent domain observations. The 50/17/33 split gives search more examples
than validation while retaining two sealed contrasts per family. Neither 72
tasks nor 12 sealed domains establish production failure rates or exhaustive
coverage of all possible requests.

The twelve families cover routing/default/mixed formats, profile variables,
complete verbatim payloads, lifecycle/IDs, source inputs, semantic grounding,
timing/openers, reachable triggers, repair/partial jobs, authorization and
cancellation, shared configuration/metrics/personas, and causal fidelity with
legitimate recovery. The coverage ledger maps all SG-01–20 starter requirements
and selected historical authoring findings. Deferred voice behavior is explicit.
At least 36 tasks include two scripted follow-ups. Large payload cases contain
1,700 lines, Unicode and deliberate spaces.

`build_fixtures.py` authors explicit synthetic domains; it is not the backend
generator or a model-driven dataset builder. `packs.json`, `expectations.json`,
`coverage.json`, `judge-gold.json` and `freeze.json` form one frozen dataset.
Never silently change these files during a run. Corrections require a new
reviewed freeze and experiment identity; the wallet carries all prior spend.
The current freeze adds explicit allowed writes, duplicate-copy rules, profile
reuse/fill-only updates, repair-0's two accepted counts and a per-task
`injections` list. It supersedes earlier drafts, so earlier approvals do not carry over.

The 48 judge gold examples contain distinct positive/negative behaviors for
each family: 24 calibration and 24 qualification, with different qualification
facts and triggers. All labels are engineering drafts until human domain review.
Supported source paraphrasing is an explicit qualification control.

## Real backend and generator

Per experiment there is one internal Docker network, with no external route and
no external DNS. It holds a Postgres server whose template database is fully
migrated from the pinned source. Per rollout attempt, `backend_stack.Stack`:

* clones the template;
* starts fresh Redis and an object store (moto);
* starts the instrumented pinned web and Celery worker containers.

Backend processes receive an explicit environment allowlist and placeholder
provider credentials only. There is no production `.env`, AWS mount, MCP
configuration or Supabase. `seed.py` writes each task's resources with the
pinned models, so seeded rows keep their fixture primary keys. It then mints the
product chat's OAuth token for the seeded owner. `readback()` returns normalized
state alongside raw serializer rows.

`bridge.py` reconstructs the MCP layer, which lives outside this repository,
from the pinned OpenAPI operations:

* Arguments are validated against the captured schemas.
* Path and query parameters go where declared, and the rest becomes the JSON body.
* Calls carry the token and the `X-Cekura-Conversation-Id` header, which
  resolves attached documents.
* Only the fixture's operation set is reachable, and voice execution is refused
  identically for both arms.
* `cekura_load_skill` and `cekura_skill_started` are served locally, as the MCP
  server does.

Inside the target sandbox, a forwarding store sends every call over the relay's
`mcp` listener to the host bridge. The bridge owns the trace.

Most generation runs in a separate Modal sandbox that the backend starts. In
`generator/`, an instrumented private copy changes transport only; the four
edits to `app/claude_utils.py` are hash-checked and recorded in
`deviation.json` and `instrumentation.diff`:

* The sandbox is reserved with metering before it exists, and its lifetime is
  capped at 600 s.
* It is created with its network blocked, from an experiment-owned image built
  from the pinned recipe and an experiment-owned secret holding no credentials.
* An stdio relay gives it a proxy whose only exit is metering.
* A `sitecustomize` guard refuses any other sandbox creation.

The fixed generator configuration (`generator/pinned.py`) is:

* engine: `accounts/fireworks/routers/glm-5p3-fast`;
* chunk workers: Gemini `gemini-3.7-flash` at low thinking;
* DeepSeek chain: Fireworks `deepseek-v4p1-flash`. Production starts with
  Wafer, and this is a recorded deviation.

Models outside the pinned set, and every other provider host, are denied and
recorded. Dropping unseeded production defaults (default folders, copied
project metrics) keeps state identical to the frozen fixture.

`metering.py` owns the following:

* Worker traffic reaches it through an edge forwarder that holds the provider
  and Modal names; sandbox traffic arrives through CONNECT.
* It decrypts TLS with an ephemeral CA and matches a pinned route, query
  allowlist and model.
* It swaps the placeholder for the real key, which never leaves this process.
* It reserves the request's bound in the wallet, forwards, and settles from
  authoritative usage. Anthropic, chat-completion and Gemini usage are parsed.
* The input bound is the request's bytes plus 4,096 template tokens, capped at
  the verified context limit.
* Error replies and deliberately cancelled streams are charged at their bound.
  A successful reply without usage blocks the wallet.
* A client disconnect keeps draining the upstream response so its final usage
  is still recorded.
* Closing a scope refuses new work and aborts every in-flight connection.

Modal control-plane names are spliced unchanged.

## Execution and evidence

`Evaluator.execute(candidate, task, repeat)` runs one trial, with at most two
retries and only after an infrastructure failure; each attempt has its own scope.
A rollout record holds:

* the trace with injections and external events;
* initial and final normalized state, plus raw backend rows;
* user turns and the identity mapping;
* target, generator and sandbox costs;
* teardown evidence;
* `delivery`.

`delivery` correlates actual `Skill`/`read` tool results in provider requests
with the loader's capped text. It reports, for each edited hunk, whether the
target observed it. The baseline is 62,582 characters, so its final 2,582 are
never delivered by the 60,000-character loader. Installed bytes are never
treated as receipt. A controller killed mid-attempt is recovered: its containers
and sandboxes are removed and open reservations are settled at their bounds.

Scored records are recomputed on every read from:

* the cached contract grade;
* the cached blinded judgment;
* criterion-level human adjudications (`adjudications/<judgment>.json`).

Rerunning `run` or `report` therefore rescores every gate without new inference.

## Grading and judging

Automated contract checks cover:

* routes, counts (`counts` lists accepted alternatives), scope and registered
  variables;
* formats, explicit exact text, current IDs and preserved neighbors;
* **allowed writes**: every change to a pre-existing scenario, profile, folder or
  configuration must be listed. Duplicates keep the original intact, land in a
  new folder and change only the requested fields. Reused profiles stay
  unchanged, and `fill_missing` profiles may only fill registered null keys;
* folders, persistence evidence, approval and cancellation, bounded errors and
  completion claims.

A real generator failure the harness did not inject marks the output checks
`backend` in `grade.attribution`.

The judge grades every rubric criterion as pass, fail or uncertain. Each verdict
has an attribution (authoring, generator, both or not_applicable), citations and
a reason. Citations may point into the request, follow-ups, documents, agent,
context, configuration and evidence. At least one must point into `/evidence/`,
and the rubric is never citable. Qualification uses the 24 frozen calibration and
24 qualification examples: at least 22/24 correct, zero critical false passes
and the paraphrase control correct. It binds only adjudications of gold examples.

## Protocol (`run`, one bounded command)

1. **Upfront gates:** the hash-bound fixture/gold signoff and launch approval,
   then preflight and the deadline (24 h from launch).
2. **Claude probes:** the proposer read-capability probe and judge qualification.
   If the judge fails, the run ends in a terminal report.
3. **Cost sample:** 12 baseline training canaries under a $15 stage cap, enforced
   in the wallet for every process.
4. **Forecast:** the minimum complete comparison with a 25% margin plus
   request-level headroom, covering the rest of the baseline training, one full
   candidate, paired validation and sealed sets, and the scheduled repeats. If it
   doesn't fit, the run reports infeasibility.
5. **Baseline training:** the remaining 24 tasks. Saturation ends the search.
6. **Search:** up to four proposal attempts, at most two fully evaluated.
   * Fresh sessions see training evidence only.
   * Rejections are recorded as `proposal-N.rejected.json` and count as attempts.
   * Targeted checks must be authoring failures of the retained parent.
   * The canary screen rejects regressions.
   * The search keeps the strongest eligible parent and stops on saturation,
     `no_change`, two zero-gain candidates or budget.
7. **Finalist:** one, frozen from training only by passes, then size, then cost.
8. **Validation:** paired with alternating arm order. It requires a worst-case
   strict gain and no regression; failure ends the run.
9. **Sealed:** paired the same way, then the scheduled repeats on validation
   `variables-3`, `lifecycle-3`, `triggers-3` and sealed `verbatim-4`,
   `sources-4`, `causal-4` (12 rollouts), then up to 12 diagnostic rollouts where
   an arm's observations disagree.
10. **Final gates (`gates.py`):** every observation counts.
    * Uncertain, unstable or audit-disputed tasks are unresolved; they credit the
      baseline and fail the candidate.
    * Acceptance needs a worst-case gain, no regression and no critical defect on
      both held-out splits.
    * The result is `recommendation_pending_final_review` or
      `no_supported_improvement`.
11. **Terminal report:** `comparison.md`, `suggestions.json` (never approved),
    `.unapproved.diff` files and the blinded `final-review.json` packet.

Final acceptance happens afterwards. `accept` exports a patch only when a named
reviewer's hash-bound final signoff passes, and only through the repository's
skill, acknowledgement, bundle, manifest and version checks in a disposable copy.

Maximum target paths, with scheduled repeats: 156 with one full candidate, 192
with two, and 216 with two plus two rejected canary screens. These are ceilings,
not promises. Every ordinary scored path uses real generation.

## Spending

One canonical wallet holds the cumulative $150 authorization, at
`~/.cekura-scenario-experiment/wallet.json`.

* **History:** `authorize-budget` creates it once from the historical ledgers,
  which must reconcile to $29.13728485, leaving at most $120.86271515. An
  append-only consumption journal outside the wallet refuses to reconcile a
  source twice, even if the wallet is deleted.
* **Sublimits:** a $145 target sublimit and a $5 Claude reservation bound.
* **Retired ledgers:** only this file may fund a live provider or Modal. Every
  older per-run ledger is refused on every paid path: the gateway upstream,
  metering, Claude sessions and the local runtime.
* **Settlement:** replaying a settlement that agrees with the record is a no-op;
  a conflicting one blocks the wallet. Unknown usage on a successful reply also
  blocks the wallet. Claude sessions settle from transport billing before any
  parsing, and saved responses are replayed rather than re-run.
* **Claude:** subscription-only. Extra usage is checked before every session,
  and there is no paid fallback.

Target rates are pinned at Fireworks $4.50/$0.45/$22.50 per million tokens. The
generator's rates and token limits must be supplied with sources
(`--pricing`), and metering refuses to run without them.

## Commands

Use Python 3.11 with `../requirements.txt` and Modal 1.4.1. Credentials are read
from `--env-file` for `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`,
`FIREWORKS_API_KEY` and `GEMINI_API_KEY`, and never printed. Artifacts stay
outside the repository.

```sh
python -m experiments.scenario_skills.v2 authorize-budget --historical ~/projects/cekura-skills-experiment-20261023/private/v2-prepared/budget.json
python -m experiments.scenario_skills.v2 prepare-claude --artifacts ~/cekura-scenario-v2-run
python -m experiments.scenario_skills.v2 prepare-generator --artifacts ~/cekura-scenario-v2-run --backend-source ~/projects/cekura-skills-experiment-20261023/backend-650297f --env-file approved.env
python -m experiments.scenario_skills.v2 prepare --artifacts ~/cekura-scenario-v2-run --base-config ~/projects/cekura-skills-experiment-20261023/private/v2-prepared/config.json --evidence-root ~/projects/cekura-skills-experiment-20261023/private/evidence/private/tmp/cekura-runtime-image-2026-10-22 --pricing pricing.json --env-file approved.env
python -m experiments.scenario_skills.v2 contract-probe --artifacts ~/cekura-scenario-v2-run
python -m experiments.scenario_skills.v2 transport-probe --artifacts ~/cekura-scenario-v2-run --env-file approved.env
python -m experiments.scenario_skills.v2 preflight --artifacts ~/cekura-scenario-v2-run --env-file approved.env
# Review human-review.md, sign fixture-and-gold-signoff.json and launch-approval.json, then:
python -m experiments.scenario_skills.v2 run --artifacts ~/cekura-scenario-v2-run --env-file approved.env
python -m experiments.scenario_skills.v2 accept --artifacts ~/cekura-scenario-v2-run   # after the final review
```

Offline drills (`drills.py`) use fake providers and the local Docker sandbox
stand-in, which preflight rejects for scored runs. Commit only synthetic
fixtures, reusable code and docs. Run traces, credentials and customer evidence
remain private.

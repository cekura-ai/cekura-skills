# CI wiring

How the committed spec becomes a gate that can actually fail a build.

## The mistake this file exists to prevent

```bash
curl -X POST ".../run_scenarios_json/" -d '{"agent_id": 42, "spec": ...}'   # ← green in 2 seconds
```

That request returns as soon as the runs are **queued**. Nothing has been dialled, nothing judged.
A job that ends there passes while the agent is broken — a gate that is worse than no gate, because
it looks like coverage. Something has to poll the result to a terminal state and exit non-zero.

A result stays in progress until every one of its runs has ended, then settles at `completed`,
`failed`, `timeout` or `cancelled`. `completed` means at least one run completed — not that any
passed — and `failed_runs_count` counts only runs that completed and failed their checks, leaving
out runs that errored or timed out. The gate therefore passes only when `status` is `completed`
and `success_runs_count` equals `total_runs_count`.

Cekura's published `run-suite` action does exactly that, and the template below uses it. Copy the
template; do not compose YAML from memory, and do not re-implement the poller inline.

| Mode | Needs | Cost | Runs on |
|---|---|---|---|
| validate (`dry_run: true`) | API key + agent id | free | every trigger where secrets exist |
| run the suite | API key + agent id | real calls | a manual dispatch unless `dry run` is ticked, or a labelled PR in preview mode |

## Nothing is vendored into the repository

The linter is an authoring tool that runs from this skill's directory. The workflow runs the suite
through `cekura-ai/cekura-github-actions/run-suite`, pinned to a release tag: it posts the spec with
the run's channel and override, polls to a terminal state, ends in-flight calls if the job is
cancelled, and writes a per-case summary. The repository ends up with three paths and no vendored
code, and a fix to the gate reaches every repository with a tag bump.

## Choosing the run target

Neither of these belongs in the spec file; both are request parameters, which is what lets one
committed file gate staging and production without an edit.

| Channel | Reaches the agent by | The agent must have |
|---|---|---|
| `voice` (default) | a phone call | a phone number configured |
| `text` | chat | a chat provider |
| `elevenlabs` | an ElevenLabs session | ElevenLabs credentials and agent id |
| `livekit_v2` | a LiveKit WebRTC session | LiveKit configured |
| `pipecat_v2` | a Pipecat Cloud WebRTC session | Pipecat Cloud configured |

If the agent is not configured for the channel, the run is rejected with a message naming what is
missing — so a wrong channel fails loudly rather than testing the wrong thing.

`execution_mode` on `run-suite` is the channel. Set it from step 1b's agent record; leaving the
default `voice` on a Pipecat or LiveKit agent dials a phone number the agent may not have.

### Pointing a run at the build under review

This is the difference between "our staging agent still works" and "this PR did not break the bot".
For Pipecat Cloud and LiveKit bots, a `cekura-test` label can deploy the pull request under its own
name and point the run at it — **`references/preview-deploy.md`** has the whole wiring, including
which bots qualify and what the customer must already have.

Without a preview per PR, the honest framing is different: the suite gates a shared staging agent,
so it catches regressions after deploy, not before merge. Say which one you have built; do not
describe the first while wiring the second.

## GitHub Actions

One file, one job, two modes. **`workflow_dispatch` alone is the default** — the run is started from
the Actions tab against a branch of your choosing, and it places real calls: a manual dispatch is a
deliberate act. Tick `dry run` to validate the spec instead. Any additional trigger is opt-in and
validates only, so nothing bills without someone choosing to run it.

```yaml
name: Cekura voice tests

on:
  workflow_dispatch:
    inputs:
      dry_run:
        # Unchecked by default: dispatching this workflow by hand is a
        # deliberate act, and the point of it is to place the calls. Tick
        # the box when you only want the spec validated.
        description: "Validate only — no calls placed, no credit spent"
        type: boolean
        default: false
  # Manual dispatch is the whole default: you pick the branch in the Actions
  # tab and nothing fires on its own. Add a second trigger ONLY if the user
  # asked for one, e.g.
  #   pull_request:
  #     paths: ["cekura.tests.json", "src/**"]
  # For a labelled-PR preview, use references/preview-deploy.md instead.

permissions:
  contents: read

jobs:
  cekura:
    runs-on: ubuntu-latest
    env:
      CEKURA_API_KEY: ${{ secrets.CEKURA_API_KEY }}
    steps:
      - uses: actions/checkout@v4

      # Secrets are absent on fork pull requests; validation there would fail
      # for a reason that has nothing to do with the change.
      - if: ${{ env.CEKURA_API_KEY != '' }}
        uses: cekura-ai/cekura-github-actions/run-suite@v1.3.0
        with:
          api_key: ${{ env.CEKURA_API_KEY }}
          api_url: ${{ vars.CEKURA_BASE_URL || 'https://api.cekura.ai' }}
          agent_id: ${{ vars.CEKURA_AGENT_ID }}
          spec: cekura.tests.json
          execution_mode: voice        # the agent's channel, from step 1b
          # A manual run honours the checkbox. Anything else validates only —
          # a push that quietly spends credit is not a default anyone consents to.
          dry_run: ${{ github.event_name != 'workflow_dispatch' || inputs.dry_run }}
```

`run-suite` fails the job unless the result is `completed` and every run passed, prints each run
that did not pass with its reason, and exposes `result_url` and a Markdown `summary_file`.


## GitLab CI

GitLab cannot use the GitHub action, so it runs the same script the action runs, fetched at the
same release tag — one implementation of the gate everywhere, and nothing vendored. The script
reads its inputs from generic environment names (`API_URL`, `NAME`, `TIMEOUT`, …), and a project
or group CI/CD variable of the same name would win over a YAML `variables:` entry — an existing
`API_URL` would receive the Cekura key. So every input is set in the shell, under `env`, never
through `variables:`.

```yaml
variables:
  # CEKURA_API_KEY and CEKURA_AGENT_ID come from CI/CD variables
  CEKURA_RUN_SUITE: https://raw.githubusercontent.com/cekura-ai/cekura-github-actions/v1.3.0/run-suite/run_suite.py

.cekura:
  image: python:3.12-slim
  before_script:
    - python3 -c "import urllib.request,os; urllib.request.urlretrieve(os.environ['CEKURA_RUN_SUITE'], '/tmp/run_suite.py')"
    - >-
      cekura() { env API_URL="${CEKURA_BASE_URL:-https://api.cekura.ai}"
      API_KEY="$CEKURA_API_KEY" AGENT_ID="$CEKURA_AGENT_ID" SPEC=cekura.tests.json
      EXECUTION_MODE=voice NAME= TIMEOUT=3600 FREQUENCY= CONCURRENCY_LIMIT=
      PIPECAT_DATA= LIVEKIT_DATA= SHARE_LINK=true DRY_RUN="$1" python3 /tmp/run_suite.py; }

cekura:validate:
  extends: .cekura
  script:
    - cekura true

cekura:run:
  extends: .cekura
  needs: [cekura:validate]
  when: manual                          # real calls stay opt-in, as on GitHub
  script:
    - cekura false
```

## Extending a workflow that already calls Cekura

Do not add a second workflow. Read the existing one and match it:

- Reuse its secret and variable names — a repo with `CEKURA_KEY` does not want a second
  `CEKURA_API_KEY` secret created beside it.
- If it runs dashboard evaluators by id or tag, that job stays. The spec suite is additive: one
  gates committed cases, the other gates dashboard-authored ones.
- Keep its trigger conventions. If the repo gates on a label, use a label. If it gates on a branch,
  use the branch.
- Preserve unrelated jobs and steps exactly.
- Replace an inline Cekura poller or a vendored `ci/` script with `run-suite`; it is the same gate,
  maintained in one place. Give each existing job an `if:` on its own event before adding new
  triggers, so a `labeled` or `closed` event does not re-run it.

## Secrets and what must never be committed

Required: `CEKURA_API_KEY` (secret) and the agent id (a variable — it is not sensitive, but keeping
it out of the file is what keeps the file portable).

Never in the spec or the workflow: API keys, phone numbers, real customer data, deployment secrets.
`lint_suite.py` fails the build if a spec carries `agent_id`; everything else is on review.

## Choosing the trigger

Real calls cost money and take minutes, so the trigger is a real decision:

This is the one question the skill asks, and it comes with a default: **manual dispatch only**.
Write that unless the user picks something else.

| Trigger | Good for |
|---|---|
| Manual only (`workflow_dispatch`) | **the default.** Pick a branch in the Actions tab; nothing fires on its own |
| Push to the deploy branch / pre-deploy | the whole suite as a release gate |
| Nightly on the main branch | catching drift from provider-side changes nobody committed |
| Pull requests touching the spec or `src/` | only where the suite is small, fast and reliably green |
| A `cekura-test` label on a pull request | gating **the PR's own build** on a preview — `references/preview-deploy.md`. Places real calls, once per labelling |

Whatever they pick, `workflow_dispatch` with the `dry_run` checkbox stays in the file alongside it,
and every non-manual trigger validates only unless they explicitly asked otherwise. Choosing the
label preview is that explicit ask: applying the label is the per-PR consent to place calls.

Cases in one file run in parallel, so wall-clock is roughly the longest single call, not the sum.
Cost is not — it scales with case count times `frequency`. That is the real reason for the 10–12
ceiling.

## The README section

Written by SKILL.md step 6. One shape for every repository the skill touches:

```markdown
## Voice tests (Cekura)

`cekura.tests.json` holds N deterministic cases covering <one line: what the suite proves>.

Run them from **Actions → Cekura voice tests → Run workflow**. A manual run places real calls; tick
`dry run` to validate the spec without placing calls or spending credit.

Requires `CEKURA_API_KEY` (repository secret) and `CEKURA_AGENT_ID` (repository variable).

| Case | What it proves | Source |
|---|---|---|
| … | … | `src/bot.py:118` |

Not covered: <the rows you left out, and what each would need>.
```


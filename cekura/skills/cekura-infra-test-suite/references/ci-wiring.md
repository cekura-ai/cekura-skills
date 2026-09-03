# CI wiring

How the committed spec becomes a gate that can actually fail a build.

## The mistake this file exists to prevent

```bash
curl -X POST ".../run_scenarios_json/" -d '{"agent_id": 42, "spec": ...}'   # ← green in 2 seconds
```

That request returns as soon as the runs are **queued**. Nothing has been dialled, nothing judged.
A job that ends there passes while the agent is broken — a gate that is worse than no gate, because
it looks like coverage. Something has to poll the runs to a terminal state and exit non-zero.

The two scripts bundled with this skill do exactly that. Copy them; do not re-derive them.

| Script | Needs | Cost | Runs on |
|---|---|---|---|
| `lint_suite.py` | nothing | free | every push, and before every dry run |
| `run_suite.py --dry-run` | API key + agent id | free | every push that touches the spec |
| `run_suite.py` | API key + agent id | real calls | the branches you choose |

## Installing them — create or update

```bash
mkdir -p cekura && cp <skill>/scripts/{lint_suite.py,run_suite.py} cekura/
```

- **A `cekura/` directory already exists** → put them alongside, keep the existing layout.
- **The repo has a conventional scripts home** (`scripts/`, `tools/`, `bin/`) → use it and adjust
  the paths in the workflow to match.
- **The scripts are already there from an earlier run** → overwrite them, and say so in the PR
  description. They are versioned assets, not something the customer is expected to have edited.
  If they *have* been edited, diff first and preserve the change or raise it — never silently
  clobber local work.

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

### Pointing a run at the build under review

This is the difference between "our staging agent still works" and "this PR did not break the bot".
For WebRTC channels the request can name the deployment to dial:

```bash
CEKURA_CHANNEL=pipecat_v2 CEKURA_PIPECAT_AGENT_NAME="mybot-pr-${PR_NUMBER}" \
  python3 cekura/run_suite.py --agent-id "$CEKURA_AGENT_ID"
```

`run_suite.py` turns those into the request's `pipecat_data.pipecat_agent_name` (or
`livekit_data.agent_name` / `url` for LiveKit). It requires the PR's ephemeral deployment to exist
already — wire the suite job `needs:` the deploy job.

Without an ephemeral deployment per PR, the honest framing is different: the suite gates a shared
staging agent, so it catches regressions after deploy, not before merge. Say which one you have
built; do not describe the first while wiring the second.

## GitHub Actions

Two jobs, deliberately. The free one runs everywhere including forks; the paid one runs only where
secrets exist and someone has opted in.

```yaml
name: Cekura suite

on:
  pull_request:
    paths: ['cekura.tests.json', 'cekura/**', '<runtime paths>']
  workflow_dispatch:

jobs:
  check:                         # free, no secrets, safe on forks
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 cekura/lint_suite.py cekura.tests.json --strict

  validate:                      # free, needs a key
    runs-on: ubuntu-latest
    needs: check
    if: github.event.pull_request.head.repo.full_name == github.repository
    env:
      CEKURA_API_KEY: ${{ secrets.CEKURA_API_KEY }}
      CEKURA_AGENT_ID: ${{ vars.CEKURA_AGENT_ID }}
    steps:
      - uses: actions/checkout@v4
      - run: python3 cekura/run_suite.py --dry-run

  run:                           # places real calls, spends credit
    runs-on: ubuntu-latest
    needs: validate
    if: contains(github.event.pull_request.labels.*.name, 'run-voice-tests')
    env:
      CEKURA_API_KEY: ${{ secrets.CEKURA_API_KEY }}
      CEKURA_AGENT_ID: ${{ vars.CEKURA_AGENT_ID }}
    steps:
      - uses: actions/checkout@v4
      - run: python3 cekura/run_suite.py --name "pr-${{ github.event.number }}"
      - if: always()
        run: cat cekura-report.md >> "$GITHUB_STEP_SUMMARY"
```

`run_suite.py` exits non-zero when any case fails, errors or times out, so the job fails without
extra plumbing. The report lands in the job summary either way — a red run is only useful if the
reason is one click from the PR.

**Fork PRs cannot read secrets.** The `if:` on `validate` is what stops a fork PR failing on a
missing key; the `check` job still gives forks a real signal.

## GitLab CI

```yaml
cekura:lint:
  image: python:3.12-slim
  script: python3 cekura/lint_suite.py cekura.tests.json --strict

cekura:validate:
  image: python:3.12-slim
  needs: [cekura:lint]
  variables:
    CEKURA_API_KEY: $CEKURA_API_KEY
    CEKURA_AGENT_ID: $CEKURA_AGENT_ID
  script: python3 cekura/run_suite.py --dry-run

cekura:run:
  image: python:3.12-slim
  needs: [cekura:validate]
  when: manual                    # or rules: on the branches you gate
  script: python3 cekura/run_suite.py
  artifacts:
    when: always
    paths: [cekura-report.md]
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

## Secrets and what must never be committed

Required: `CEKURA_API_KEY` (secret) and the agent id (a variable — it is not sensitive, but keeping
it out of the file is what keeps the file portable).

Never in the spec or the workflow: API keys, phone numbers, real customer data, deployment secrets.
`lint_suite.py` fails the build if a spec carries `agent_id`; everything else is on review.

## Choosing the trigger

Real calls cost money and take minutes, so the trigger is a real decision:

| Trigger | Good for |
|---|---|
| Label on a PR | the default. Opt-in per PR, cheap by construction |
| Push to the deploy branch / pre-deploy | the whole suite as a release gate |
| Nightly on the main branch | catching drift from provider-side changes nobody committed |
| Every PR | only where the suite is small, fast and reliably green |

Cases in one file run in parallel, so wall-clock is roughly the longest single call, not the sum.
Cost is not — it scales with case count times `frequency`. That is the real reason for the 10–12
ceiling.

# Preview deployments — gate the pull request, not staging

A suite that dials a shared staging agent tells you staging still works. To know **this pull
request** did not break the bot, the PR's own code has to answer the call. This file wires that:
a `cekura-test` label on a pull request deploys the PR to the customer's own infrastructure under
a PR-scoped name, runs the committed suite against it, comments the result, and removes it.

Everything runs on the customer's side with the customer's keys — their GitHub secrets, their
Pipecat Cloud org or LiveKit project. Cekura supplies only the simulated caller.

The moving parts are published actions in `cekura-ai/cekura-github-actions`, so the customer's
workflow stays short and nothing is vendored:

| Action | Job |
|---|---|
| `run-suite` | posts the committed spec with the run's channel and override, polls to a terminal state, passes only when every run passed, writes the PR-comment summary |
| `pipecat/deploy-preview` | deploys this checkout as `<base>-pr-<number>` and waits until that revision serves |
| `pipecat/delete-preview` | deletes `<base>-pr-<number>` — never `<base>` |
| `livekit/start-worker` | builds this checkout and runs the worker inside the job as `<base>-pr-<number>` |
| `livekit/stop-worker` | prints the worker's logs and removes it |

The actions build the `-pr-<number>` name themselves; they never accept a bare name. That is what
keeps a misconfigured workflow from deploying over, registering as, or deleting production.

## Which bots can have one

Decide from the code and the deploy config, never from a framework name:

| Found in the repo | Preview | Channel |
|---|---|---|
| `pcc-deploy.toml`, a `bot(runner_args)` entrypoint joining the session's **Daily** room, `dailyco/pipecat-base` image | Pipecat Cloud preview | `pipecat_v2` |
| `livekit-agents` worker — `cli.run_app(WorkerOptions(...))` or `AgentServer` — with a Dockerfile whose `CMD` starts it | LiveKit worker in the job | `livekit_v2` |
| A Pipecat pipeline that is **not** on Pipecat Cloud — `LiveKitTransport` joining a fixed room, a self-hosted WebSocket or SmallWebRTC server | **none** | — |
| Anything else (custom WebSocket, phone-only, vendor-hosted agents) | **none** | — |

**A Pipecat bot is not a Pipecat Cloud bot.** `pipecat_v2` reaches an agent only by asking Pipecat
Cloud to start a session, which creates a Daily room and calls `bot()` with it. A Pipecat pipeline
on a LiveKit transport, or behind its own server, is never reached by that channel, so a
`pipecat_v2` run against it tests whatever Pipecat Cloud agent the Cekura record happens to name.
Say so, and do not wire a preview or a `pipecat_v2` job for it.

Where no preview is possible, offer the label trigger only if a shared staging agent exists, and
say plainly what it gates: staging after deploy, not the pull request before merge.

## What the customer must already have

The workflow cannot create these, and the skill must not. Check each and list any gap in the
handoff as a prerequisite, not as something done.

### Pipecat Cloud

| Need | Where it comes from | Check |
|---|---|---|
| `agent_name_base` | `agent_name` in `pcc-deploy.toml` | the preview becomes `<that>-pr-<n>` |
| a **private** Pipecat Cloud key | repo secret, e.g. `PIPECAT_CLOUD_API_KEY` | reuse the name if a deploy workflow already has one |
| a secret set | `secret_set` in `pcc-deploy.toml` | recommend a CI-only set so previews never hold production keys |
| image source | `image` in `pcc-deploy.toml`, or none | no image (or an image built in CI) → `cloud_build` (the default); a registry image → `image` + `image_credentials` |
| a Cekura agent on the same org | step 1b's agent record | provider Pipecat, with a saved Pipecat key from the **same Pipecat Cloud org** the preview deploys into |

The last row is the one that bites. Cekura starts the preview's sessions with the key saved on the
Cekura agent; the per-run override changes only the agent **name**. A preview deployed into a
different org — a separate staging org, say — is unreachable from that Cekura agent. The fix is a
second Cekura agent with that org's key, not a different workflow.

### LiveKit

| Need | Where it comes from | Check |
|---|---|---|
| `agent_name_base` | the agent name in code or `livekit.toml`, or the repo name | the worker registers as `<that>-pr-<n>` |
| `livekit-agents` **1.6+** | `requirements.txt` / `pyproject.toml` / lock file | 1.6 added `LIVEKIT_AGENT_NAME_OVERRIDE`, which renames the worker without a code change. Older → it must read `agent_name` from `LIVEKIT_AGENT_NAME`; that is a runtime change, so report it as a blocker |
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | repo secrets | recommend a CI-only LiveKit project |
| provider keys | every `os.getenv` the worker reads, plus each plugin's default variable (`DEEPGRAM_API_KEY`, `OPENAI_API_KEY`, `ELEVEN_API_KEY`, `CARTESIA_API_KEY`, …) | each becomes a repo secret and an `env` line |
| model files baked in | a `download-files` step in the Dockerfile | VAD and turn-detector plugins load files at startup; without the step the worker fetches them on every run or fails. A Dockerfile change is outside the deliverable — report it |
| a Cekura agent on the same project | step 1b's agent record | provider LiveKit, with saved credentials for the **same LiveKit project** |
| production registers **with** a name | `agent_name` in code / `livekit.toml`, or none | a production worker with no name (automatic dispatch) joins every new room in its project — Cekura's preview rooms included, so two agents answer. Then the preview needs a CI-only LiveKit project production does not run in; say so as a prerequisite |

The worker runs inside the job and registers with the project like a deployed one — no deployment,
no LiveKit plan quota. `start-worker` checks the worker's own registration log line and stops it
unless it registered as exactly `<base>-pr-<n>`: a worker with no name would be dispatched to every
new room in the project, and one under production's name would join production's pool. A worker
whose log does not show its name is stopped too, unless `allow_unverified_agent_name: true` — only
for a pre-1.6 worker you have confirmed reads `LIVEKIT_AGENT_NAME`.

One runner serves every call, so set `concurrency_limit` on `run-suite` (3 is a sane start) rather
than letting a 10-case suite land on two vCPUs at once.

## When it runs

**On the label, and only the label.** Every run places real calls, so pushes do not re-run it:
removing and re-adding the label tests the new commit. The comment names the commit it tested.

- The `if:` checks `github.event.label.name`, not the label list — otherwise adding any unrelated
  label to a labelled PR would place another paid run.
- Same-repository PRs only (`head.repo.full_name == github.repository`). Fork PRs get no secrets,
  and `pull_request_target` would hand them yours: never use it here.
- Not a required status check. A PR nobody labelled would wait on it forever, and a push after a
  run leaves the new commit without one.
- The label must exist: `gh label create cekura-test`. Put that in the README.

Choosing this trigger **is** the customer's explicit request for live calls on labelled pull
requests — the consent the "every non-manual trigger validates only" rule asks for. Say in the
handoff what one run costs, from the dry-run plan's `estimated_cost`, and that a Pipecat preview
keeps one warm agent per suite call for the run's few minutes (`max_agents` caps it).

On a **public** repository, set `share_link: false` on `run-suite`: the PR comment would otherwise
publish a link that opens every transcript and recording for 7 days.

## The workflow

Extend the existing Cekura workflow if there is one; this is one file with the manual job kept
beside the preview job. Pin the actions to a release tag. Fill in the base name, secret names, the
secret set and the env lines from discovery; change nothing else.

### Pipecat Cloud

```yaml
name: Cekura voice tests

on:
  pull_request:
    types: [labeled, closed]
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Validate only — no calls placed, no credit spent"
        type: boolean
        default: false

permissions:
  contents: read
  pull-requests: write

env:
  AGENT_NAME_BASE: my-bot                     # agent_name in pcc-deploy.toml
  CEKURA_BASE_URL: ${{ vars.CEKURA_BASE_URL || 'https://api.cekura.ai' }}

jobs:
  preview:
    if: >-
      github.event_name == 'pull_request' &&
      github.event.action == 'labeled' &&
      github.event.label.name == 'cekura-test' &&
      github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    timeout-minutes: 45
    concurrency:
      group: cekura-preview-${{ github.event.pull_request.number }}
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}

      - id: preview
        uses: cekura-ai/cekura-github-actions/pipecat/deploy-preview@v1.3.0
        with:
          api_key: ${{ secrets.PIPECAT_CLOUD_API_KEY }}
          agent_name_base: ${{ env.AGENT_NAME_BASE }}
          secret_set: my-bot-ci                 # secret_set in pcc-deploy.toml, or a CI-only set
          spec: cekura.tests.json

      - id: cekura
        uses: cekura-ai/cekura-github-actions/run-suite@v1.3.0
        with:
          api_key: ${{ secrets.CEKURA_API_KEY }}
          api_url: ${{ env.CEKURA_BASE_URL }}
          agent_id: ${{ vars.CEKURA_AGENT_ID }}
          spec: cekura.tests.json
          execution_mode: pipecat_v2
          pipecat_data: '{"pipecat_agent_name": "${{ steps.preview.outputs.agent_name }}"}'
          name: PR ${{ github.event.pull_request.number }} @ ${{ github.event.pull_request.head.sha }}

      - name: Comment the result on the pull request
        if: always()
        env:
          GH_TOKEN: ${{ github.token }}
          SUMMARY_FILE: ${{ steps.cekura.outputs.summary_file }}
        run: |
          {
            if [ -n "$SUMMARY_FILE" ] && [ -f "$SUMMARY_FILE" ]; then
              cat "$SUMMARY_FILE"
            else
              echo "## Cekura suite results"
              echo
              echo "❌ No result: the run stopped before the suite started — see the workflow run."
            fi
            echo
            echo "<sub>Tested commit ${{ github.event.pull_request.head.sha }} · [workflow run](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }})</sub>"
          } > comment.md
          gh pr comment ${{ github.event.pull_request.number }} --repo ${{ github.repository }} --body-file comment.md

      - if: always()
        uses: cekura-ai/cekura-github-actions/pipecat/delete-preview@v1.3.0
        with:
          api_key: ${{ secrets.PIPECAT_CLOUD_API_KEY }}
          agent_name_base: ${{ env.AGENT_NAME_BASE }}

  # Removes a preview that a cancelled or crashed run left behind.
  delete-on-close:
    if: >-
      github.event_name == 'pull_request' &&
      github.event.action == 'closed' &&
      github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    # Same group as the preview job, so closing a pull request mid-run waits
    # for that run instead of deleting the preview under it.
    concurrency:
      group: cekura-preview-${{ github.event.pull_request.number }}
      cancel-in-progress: false
    steps:
      - uses: cekura-ai/cekura-github-actions/pipecat/delete-preview@v1.3.0
        with:
          api_key: ${{ secrets.PIPECAT_CLOUD_API_KEY }}
          agent_name_base: ${{ env.AGENT_NAME_BASE }}

  manual:
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: cekura-ai/cekura-github-actions/run-suite@v1.3.0
        with:
          api_key: ${{ secrets.CEKURA_API_KEY }}
          api_url: ${{ env.CEKURA_BASE_URL }}
          agent_id: ${{ vars.CEKURA_AGENT_ID }}
          spec: cekura.tests.json
          execution_mode: pipecat_v2
          dry_run: ${{ inputs.dry_run }}
```

A pre-built image instead of a cloud build: add `image:` and `image_credentials:` to
`deploy-preview`, after whatever build-and-push steps the repo's deploy workflow already has.

### LiveKit

Same file shape; the preview job's steps become:

```yaml
      - id: worker
        uses: cekura-ai/cekura-github-actions/livekit/start-worker@v1.3.0
        with:
          livekit_url: ${{ secrets.LIVEKIT_URL }}
          livekit_api_key: ${{ secrets.LIVEKIT_API_KEY }}
          livekit_api_secret: ${{ secrets.LIVEKIT_API_SECRET }}
          agent_name_base: ${{ env.AGENT_NAME_BASE }}
          env: |                                  # one line per key the worker reads
            DEEPGRAM_API_KEY=${{ secrets.DEEPGRAM_API_KEY }}
            OPENAI_API_KEY=${{ secrets.OPENAI_API_KEY }}

      - id: cekura
        uses: cekura-ai/cekura-github-actions/run-suite@v1.3.0
        with:
          api_key: ${{ secrets.CEKURA_API_KEY }}
          api_url: ${{ env.CEKURA_BASE_URL }}
          agent_id: ${{ vars.CEKURA_AGENT_ID }}
          spec: cekura.tests.json
          execution_mode: livekit_v2
          livekit_data: '{"agent_name": "${{ steps.worker.outputs.agent_name }}"}'
          concurrency_limit: 3
          name: PR ${{ github.event.pull_request.number }} @ ${{ github.event.pull_request.head.sha }}

      # the same comment step as the Pipecat job

      - if: always()
        uses: cekura-ai/cekura-github-actions/livekit/stop-worker@v1.3.0
```

The worker dies with the job, so there is no `delete-on-close` job and `on.pull_request.types` is
just `[labeled]`. The manual job uses `execution_mode: livekit_v2`.

## Validate as the preview will run

Step 7's dry run must use the channel and override the workflow will send, or it validates a
different request: pass `channel` (`pipecat_v2` / `livekit_v2`) and the override with a placeholder
preview name (`{"pipecat_agent_name": "my-bot-pr-0"}`). That checks the Cekura agent has
credentials for the channel. It does not check the preview exists — nothing does until a labelled
run.

## The README section

Replace the template's trigger paragraph with:

```markdown
**On a pull request:** add the `cekura-test` label. The workflow deploys that pull request
<to Pipecat Cloud as `my-bot-pr-<number>` | as a LiveKit worker inside the job, registered as
`my-agent-pr-<number>`>, runs the suite against it, comments the result on the pull request, and
<deletes the deployment | stops the worker>. Pushes do not re-run it, because each run places real
calls: remove and re-add the label to test a new commit.

**By hand:** **Actions → Cekura voice tests → Run workflow** runs the suite against the agent saved
on the Cekura agent; tick `dry run` to only validate the spec.
```

Then a table of every secret and variable, each with what it is — including which org or project
the Cekura agent's saved credentials must match — and the `gh label create cekura-test` line.

## When a labelled run fails

| Symptom | Cause | Fix |
|---|---|---|
| `deploy-preview`: crash-looping, with a reason | the PR's bot fails at startup | `pcc agent logs <base>-pr-<n>`; it is the PR's bug |
| `deploy-preview`: not ready within the timeout | slow cloud build or scale-up | raise `wait_timeout` / `build_timeout` |
| every run: `Failed to create Pipecat session` | the Cekura agent's key is for a different Pipecat org, or the preview never became ready | match the org (above) |
| `start-worker`: registered under another name, or none | `livekit-agents` older than 1.6, with the name set in code | upgrade, or read `agent_name` from `LIVEKIT_AGENT_NAME` |
| `start-worker`: registration line does not say which agent name | pre-1.6 or custom logging | upgrade; or confirm the worker reads `LIVEKIT_AGENT_NAME` and set `allow_unverified_agent_name` |
| LiveKit transcripts show two agents answering | production registers with no name in the same project | a CI-only LiveKit project |
| `start-worker`: exited before registering | the worker crashed on startup | its logs are printed in the step |
| every run times out on LiveKit | the Cekura agent's LiveKit credentials are for another project, so the dispatch reaches no worker | match the project |
| some runs time out on LiveKit, others pass | the runner is out of capacity | lower `concurrency_limit` |
| `run-suite`: rejected (HTTP 400) | the spec, a metric or the channel — the body names the field | fix the spec; a dry run would have caught it |

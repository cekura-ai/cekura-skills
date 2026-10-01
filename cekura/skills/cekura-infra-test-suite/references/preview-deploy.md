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
| `pipecat/deploy-preview` | deploys this checkout as `<base>-pr-<number>`, waits until that revision serves, then lets it settle (`settle_seconds`, default 180) |
| `pipecat/delete-preview` | deletes `<base>-pr-<number>` — never `<base>` |
| `livekit/start-worker` | builds this checkout and runs the worker inside the job as `<base>-pr-<number>`, and stops it unless it registered under exactly that name |
| `livekit/stop-worker` | prints the worker's logs and removes it |

The actions build the `-pr-<number>` name themselves; they never accept a bare name. That is what
keeps a misconfigured workflow from deploying over, registering as, or deleting production.

## Which bots can have one

All of these must hold; decide from the code and deploy config, never from a framework name.

- **CI is GitHub Actions.** The preview actions are GitHub-only. On GitLab, Jenkins or anything
  else, do not offer the label.
- **The bot is one of these:**

| Found in the repo | Preview | Channel |
|---|---|---|
| `pcc-deploy.toml` and a `bot(runner_args)` entrypoint that **joins the Daily room** the session carries (`runner_args.room_url`), on the `dailyco/pipecat-base` image | Pipecat Cloud preview | `pipecat_v2` |
| Python `livekit-agents` worker — `cli.run_app(WorkerOptions(...))` or `AgentServer` — **1.6+**, with a Dockerfile whose `CMD` starts it (`… start`) | LiveKit worker in the job | `livekit_v2` |
| Node `@livekit/agents` worker — `cli.runApp(...)` — **1.4.10+**, with a Dockerfile whose `CMD` starts it | LiveKit worker in the job | `livekit_v2` |

Not reachable, so no preview — say why in the handoff:

- **A Pipecat bot that is not a Daily Pipecat Cloud bot.** `pipecat_v2` asks Pipecat Cloud to
  start a session *with a Daily room* and calls `bot()` with it. A pipeline on `LiveKitTransport`,
  a self-hosted WebSocket or SmallWebRTC server, or a Pipecat Cloud bot that handles only
  telephony WebSocket sessions is never reached by that channel; a `pipecat_v2` run against it
  tests whatever Pipecat Cloud agent the Cekura record happens to name.
- An older `livekit-agents` / `@livekit/agents` than above: the worker cannot be renamed without a
  code change (reading its name from `LIVEKIT_AGENT_NAME`), so report that as the blocker.
- Anything else — custom WebSocket, phone-only, Vapi / Retell / ElevenLabs-hosted agents.

**Where the bot does not qualify, do not offer the label.** Offer push, PR or a schedule from
`ci-wiring.md` instead, and say plainly what those gate: the shared agent, after deploy.

Two deployable bots in one repo → one preview job per bot, each with its own `AGENT_NAME_BASE`,
spec and build paths, in the same workflow file.

## Filling the template

Every value comes from somewhere specific. Fill each from this table and change nothing else.

| Value | Pipecat Cloud | LiveKit |
|---|---|---|
| `AGENT_NAME_BASE` | `agent_name` in `pcc-deploy.toml` | the name in code (`agent_name=`/`agentName:`), else the Cekura agent's saved `agent_name`, else the repo name |
| …then, for both | lowercase it and replace anything outside `[a-z0-9-]` with `-`. It is a label for previews, not production's name; Pipecat caps the preview at 54 characters, so keep the base ≤ 46 | same, ≤ 57 |
| `build_context`, `dockerfile` | the directory holding `pcc-deploy.toml` joined with its `[build] context_dir`, and its `[build] dockerfile` — with no `[build]` section, that directory and `Dockerfile`. **Set both whenever the bot is not at the repository root** | the context and `-f` the repo's own `docker build` uses (deploy workflow, Makefile, README); set both when not at the root |
| build source | **`cloud_build` (the default)**. Use `image` only when this workflow itself builds and pushes the PR's commit to a tag unique to it (`:pr-<number>-<sha>`), by copying the repo's existing build-and-push steps before `deploy-preview`. The `image` in `pcc-deploy.toml` is a fixed tag pointing at production's code — **never** pass it | the Dockerfile above |
| `secret_set` | **`secret_set` from `pcc-deploy.toml`**, so the first run works. In the handoff, recommend a CI-only set holding every key the bot reads (list them), created with `pcc secrets set <name> --file .env` in the same org | — |
| `env` lines | — | one `KEY=${{ secrets.KEY }}` line per **secret** the worker reads: each plugin's key (`DEEPGRAM_API_KEY`, `OPENAI_API_KEY`, `ELEVEN_API_KEY`, `CARTESIA_API_KEY`, …) and every `os.getenv`/`process.env` that holds a credential. Not non-secret settings that have defaults |
| `region`, `agent_profile` | from `pcc-deploy.toml`, when set | — |
| `krisp_viva`, `max_session_duration` | `[krisp_viva] audio_filter` and `max_session_duration` from `pcc-deploy.toml`, when set — a bot built on Krisp may not start without it | — |
| spec and README | the repo root — unless the bot lives in a subdirectory: then `<bot dir>/cekura.tests.json`, `spec:` set to that path on every action, and the section in that directory's README | same |
| `min_agents` | omit: it defaults to `max_agents`, so every agent is warm when the suite starts | — |
| `max_agents` | omit, so one agent per suite call is kept warm. If `[scaling] max_agents` in `pcc-deploy.toml` is lower than the suite's call count, set `max_agents` to it **and** `concurrency_limit` on `run-suite` to the same number | — |
| `concurrency_limit` | as above | `3`: one runner serves every call |
| manual job | the same `concurrency_limit` and `share_link` as the preview job | same |
| `share_link` | `true` only when the repo is known private (`gh repo view --json visibility`, or the dashboard checkout says so). Otherwise `false` — on a public repo the PR comment would publish a link that opens every transcript and recording for 7 days | same |
| secret names | reuse the names an existing deploy workflow already uses (`PIPECAT_API_KEY`, `LIVEKIT_URL`, …); otherwise the template's | same |
| `CEKURA_BASE_URL` | set the repository variable when the Cekura workspace is not on `https://api.cekura.ai` (an EU workspace is `https://api.eu.cekura.ai`) | same |

**Pin the release tag**, and check it exists before handing over:
`git ls-remote --tags https://github.com/cekura-ai/cekura-github-actions v1.3.0`. If it prints
nothing, say so first in the handoff — before anything else, a step-1b mismatch included: every
`uses:` line will fail until it is published.

## What the customer must already have

The workflow cannot create these, and the skill must not. Check each and list every gap in the
handoff and PR body as a prerequisite — what it is, **where it is created** (GitHub repo settings,
Pipecat Cloud, LiveKit Cloud, Cekura), and its value where it is not secret.

- **A Cekura agent whose saved credentials reach the preview.** Cekura starts the preview's
  sessions with the credentials saved on the agent; the per-run override changes only the agent
  **name**. Pipecat: its saved key is from the **same Pipecat Cloud org** the preview deploys
  into. LiveKit: its saved URL, key and secret are for the **same LiveKit project** the worker
  registers with. If that is not the production agent — previews in a staging org, or a CI-only
  LiveKit project — the workflow needs a second Cekura agent with those credentials
  (`cekura-create-agent`); name it as a prerequisite and wire *its* id. A cheap check for
  Pipecat: the agent's saved `pipecat_agent_name` should be the toml's `agent_name`.
- **Pipecat:** a **private** Pipecat Cloud key as a repo secret (the agent's saved key is a public
  one), and the secret set above.
- **LiveKit:** the project's URL, key and secret as repo secrets, and the provider keys. **If
  production registers with no agent name** (automatic dispatch — the LiveKit default), it joins
  every new room in its project, Cekura's preview rooms included, and two agents answer: the
  preview then needs a CI-only project that production does not run in.
- **LiveKit model files.** Turn-detector plugins load model files at startup; a Dockerfile without
  `download-files` (`python -m livekit.agents download-files` on 1.6+) makes every preview fetch
  them or fail. Wire the preview anyway — it behaves exactly as production's image does — and note
  it; a Dockerfile change is not the skill's to make.
- **The label:** `gh label create cekura-test`, or Issues → Labels → New label. The dashboard
  cannot create it.
- **`CEKURA_AGENT_ID`** as a repository variable, with its value.

## When it runs

**On the label, and only the label.** Every run places real calls, so pushes do not re-run it:
removing and re-adding the label tests the new commit. The comment names the commit it tested.

- The `if:` checks `github.event.label.name`, not the label list — otherwise adding any unrelated
  label to a labelled PR would place another paid run.
- Same-repository PRs only (`head.repo.full_name == github.repository`). Fork PRs get no secrets,
  and `pull_request_target` would hand them yours: never use it here.
- Not a required status check. A PR nobody labelled would wait on it forever, and a push after a
  run leaves the new commit without one.
- For `pull_request`, GitHub runs the workflow file from the PR itself, so labelling the very PR
  that adds this workflow is a valid first run.

Choosing this trigger **is** the customer's explicit request for live calls on labelled pull
requests — the consent the "every non-manual trigger validates only" rule asks for. Say in the
handoff what one run costs, from the dry-run plan's `estimated_cost`, and that a Pipecat preview
keeps one warm agent per suite call for the run's few minutes, including the settle wait.

## The workflow

One file. If a Cekura workflow already exists, extend it: keep its secret names and any
dashboard-evaluator jobs, replace an inline poller or vendored `ci/` script with `run-suite`, and
give every existing job an `if:` on its own event so the new `labeled`/`closed` events do not
re-run it.

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
          secret_set: my-bot-secrets            # secret_set in pcc-deploy.toml
          spec: cekura.tests.json
          # Add from the table when they apply: build_context, dockerfile,
          # region, agent_profile, krisp_viva, max_session_duration, max_agents.

      - id: cekura
        uses: cekura-ai/cekura-github-actions/run-suite@v1.3.0
        with:
          api_key: ${{ secrets.CEKURA_API_KEY }}
          api_url: ${{ env.CEKURA_BASE_URL }}
          agent_id: ${{ vars.CEKURA_AGENT_ID }}
          spec: cekura.tests.json
          execution_mode: pipecat_v2
          pipecat_data: '{"pipecat_agent_name": "${{ steps.preview.outputs.agent_name }}"}'
          share_link: false                     # true only for a known-private repo
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

  # By hand: the agent's saved Pipecat deployment, or only a validation.
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
          share_link: false
          dry_run: ${{ inputs.dry_run }}
```

### LiveKit

```yaml
name: Cekura voice tests

on:
  pull_request:
    types: [labeled]
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
  AGENT_NAME_BASE: my-agent                   # from the table
  CEKURA_BASE_URL: ${{ vars.CEKURA_BASE_URL || 'https://api.cekura.ai' }}

jobs:
  preview:
    if: >-
      github.event_name == 'pull_request' &&
      github.event.label.name == 'cekura-test' &&
      github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    timeout-minutes: 45
    # Two overlapping runs would register two workers under one name.
    concurrency:
      group: cekura-preview-${{ github.event.pull_request.number }}
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}

      - id: worker
        uses: cekura-ai/cekura-github-actions/livekit/start-worker@v1.3.0
        with:
          livekit_url: ${{ secrets.LIVEKIT_URL }}
          livekit_api_key: ${{ secrets.LIVEKIT_API_KEY }}
          livekit_api_secret: ${{ secrets.LIVEKIT_API_SECRET }}
          agent_name_base: ${{ env.AGENT_NAME_BASE }}
          # Add build_context / dockerfile when the worker is not at the root.
          env: |                                  # one line per secret the worker reads
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
          concurrency_limit: 3                    # one runner serves every call
          share_link: false                       # true only for a known-private repo
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
        uses: cekura-ai/cekura-github-actions/livekit/stop-worker@v1.3.0

  # By hand: the agent's saved LiveKit agent name, or only a validation.
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
          execution_mode: livekit_v2
          share_link: false
          dry_run: ${{ inputs.dry_run }}
```

The worker dies with the job, so there is no `delete-on-close` job.

## Validate every request the workflow sends

Step 7 validates each job's request as written — the channel and override decide which
credentials Cekura checks, so a request validated without them proves nothing about the real one.
`scenarios_validate_json` takes the same fields as the run (`agent_id`, `spec`, `channel`,
`pipecat_data`, `livekit_data`):

| Job | Body |
|---|---|
| Pipecat preview | `{"agent_id": N, "spec": …, "channel": "pipecat_v2", "pipecat_data": {"pipecat_agent_name": "<base>-pr-0"}}` |
| Pipecat manual | `{"agent_id": N, "spec": …, "channel": "pipecat_v2"}` |
| LiveKit preview | `{"agent_id": N, "spec": …, "channel": "livekit_v2", "livekit_data": {"agent_name": "<base>-pr-0"}}` |
| LiveKit manual | `{"agent_id": N, "spec": …, "channel": "livekit_v2"}` |

From a shell: `CEKURA_CHANNEL=pipecat_v2 CEKURA_PIPECAT_AGENT_NAME=<base>-pr-0 python3
<skill>/scripts/run_suite.py --dry-run --agent-id N` (`CEKURA_LIVEKIT_AGENT_NAME` for LiveKit).

A manual request rejected because the agent has no saved agent name is not a suite defect: the
manual job needs one (a production LiveKit worker with automatic dispatch has none). Report it as a
prerequisite — save a name on the Cekura agent, or use the manual job for dry runs only. Neither
check proves the preview exists; nothing does until a labelled run.

## The README section

Start from `ci-wiring.md`'s template and change two things. Replace its *Run them from…* paragraph
with:

```markdown
**On a pull request:** add the `cekura-test` label. The workflow deploys that pull request
<to Pipecat Cloud as `my-bot-pr-<number>` | as a LiveKit worker inside the job, registered as
`my-agent-pr-<number>`>, runs the suite against it, comments the result on the pull request, and
<deletes the deployment | stops the worker>. Pushes do not re-run it, because each run places real
calls: remove and re-add the label to test a new commit.

**By hand:** **Actions → Cekura voice tests → Run workflow** runs the suite against the agent saved
on the Cekura agent; tick `dry run` to only validate the spec.
```

And replace its *Requires…* line with a table of every secret, variable, secret set and label the
workflow reads — each with where it is created and what it must match — then the coverage table.

## When a labelled run fails

| Symptom | Cause | Fix |
|---|---|---|
| `Unable to resolve action …@v1.3.0` | the release tag is not published | publish it, or pin the tag that exists |
| `deploy-preview`: crash-looping, with a reason | the PR's bot fails at startup | `pcc agent logs <base>-pr-<n>`; it is the PR's bug — unless the toml sets `krisp_viva` or `agent_profile` the template does not carry |
| `deploy-preview`: failed to deploy, with error codes | image, secret set or quota | the codes name it; a missing secret set is the usual one |
| `deploy-preview`: not ready within the timeout | slow cloud build or scale-up | raise `wait_timeout` / `build_timeout`, or lower `max_agents` |
| every run: `Failed to create Pipecat session` | the Cekura agent's key is for a different Pipecat org | match the org (above) |
| only the first few runs: `Failed to create Pipecat session` | the preview had not settled | raise `settle_seconds` (default 180) |
| `start-worker`: registered under another name, or none | the SDK is older than the table's minimum, with the name set in code | upgrade |
| `start-worker`: registration line does not say which agent name | custom logging | confirm it reads `LIVEKIT_AGENT_NAME`, then set `allow_unverified_agent_name` |
| `start-worker`: exited before registering | the worker crashed on startup | its logs are printed in the step |
| LiveKit transcripts show two agents answering | production registers with no name in the same project | a CI-only LiveKit project |
| every run times out on LiveKit | the Cekura agent's LiveKit credentials are for another project, so the dispatch reaches no worker | match the project |
| some runs time out on LiveKit, others pass | the runner is out of capacity | lower `concurrency_limit` |
| `run-suite`: rejected (HTTP 400) | the spec, a metric or the channel — the body names the field | fix the spec; a dry run would have caught it |

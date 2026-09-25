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

The template below does exactly that. Copy it; do not compose YAML from memory.

| Step | Needs | Cost | Runs on |
|---|---|---|---|
| spec is well-formed | nothing | free | every trigger, forks included |
| validate against Cekura | API key + agent id | free | every trigger where secrets exist |
| run the suite | API key + agent id | real calls | a manual dispatch, unless `dry run` is ticked |

## Nothing is vendored into the repository

Earlier versions copied `lint_suite.py` and `run_suite.py` into `cekura/`. They no longer do. The
linter is an authoring tool that runs from this skill's directory, and the workflow below polls
inline — about thirty lines of stdlib Python in a heredoc, with no file for the customer to own,
review, or let rot. The repository ends up with three paths and no vendored code.

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
  python3 <skill>/scripts/run_suite.py --agent-id "$CEKURA_AGENT_ID"
```

`run_suite.py` turns those into the request's `pipecat_data.pipecat_agent_name` (or
`livekit_data.agent_name` / `url` for LiveKit). It requires the PR's ephemeral deployment to exist
already — wire the suite job `needs:` the deploy job.

Without an ephemeral deployment per PR, the honest framing is different: the suite gates a shared
staging agent, so it catches regressions after deploy, not before merge. Say which one you have
built; do not describe the first while wiring the second.

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

permissions:
  contents: read

jobs:
  cekura:
    runs-on: ubuntu-latest
    env:
      CEKURA_API_KEY: ${{ secrets.CEKURA_API_KEY }}
      CEKURA_AGENT_ID: ${{ vars.CEKURA_AGENT_ID }}
      CEKURA_BASE_URL: ${{ vars.CEKURA_BASE_URL || 'https://api.cekura.ai' }}
      # A manual run honours the checkbox. Anything else validates only —
      # a push that quietly spends credit is not a default anyone consents to.
      DRY_RUN: ${{ github.event_name != 'workflow_dispatch' || inputs.dry_run }}
    steps:
      - uses: actions/checkout@v4

      - name: Spec is well-formed
        run: python3 -c "import json,sys; json.load(open('cekura.tests.json'))"

      # Secrets are absent on fork pull requests; validation there would fail
      # for a reason that has nothing to do with the change.
      - name: Validate against Cekura
        if: ${{ env.CEKURA_API_KEY != '' }}
        run: |
          python3 - <<'EOF'
          import json, os, sys, urllib.request

          spec = json.load(open("cekura.tests.json"))
          body = json.dumps({"agent_id": int(os.environ["CEKURA_AGENT_ID"]), "spec": spec}).encode()
          url = os.environ["CEKURA_BASE_URL"].rstrip("/") + \
              "/test_framework/v1/scenarios/validate_scenarios_json/"
          req = urllib.request.Request(url, body, {
              "X-CEKURA-API-KEY": os.environ["CEKURA_API_KEY"],
              "Content-Type": "application/json",
          })
          out = json.load(urllib.request.urlopen(req, timeout=60))
          print(json.dumps(out.get("plan", out), indent=2))
          if not out.get("valid"):
              sys.exit("spec rejected by Cekura")
          EOF

      - name: Run the suite
        if: ${{ env.DRY_RUN == 'false' && env.CEKURA_API_KEY != '' }}
        run: |
          python3 - <<'EOF'
          import json, os, sys, time, urllib.error, urllib.request

          base = os.environ["CEKURA_BASE_URL"].rstrip("/")
          key = {"X-CEKURA-API-KEY": os.environ["CEKURA_API_KEY"], "Content-Type": "application/json"}
          TERMINAL = {"completed", "failed", "timeout", "cancelled"}

          def call(method, path, payload=None):
              req = urllib.request.Request(base + path, payload, key, method=method)
              return json.load(urllib.request.urlopen(req, timeout=60))

          spec = json.load(open("cekura.tests.json"))
          body = json.dumps({"agent_id": int(os.environ["CEKURA_AGENT_ID"]), "spec": spec}).encode()
          started = call("POST", "/test_framework/v1/scenarios/run_scenarios_json/", body)
          result_id = started["id"]
          print(f"result {result_id}: {len(started.get('runs') or [])} run(s) queued")

          # The POST returns once the runs are queued — nothing has been dialled
          # yet. Poll the result to a terminal state or the job is a gate that cannot fail.
          deadline = time.time() + 45 * 60
          while True:
              if time.time() > deadline:
                  sys.exit(f"timed out waiting for result {result_id}")
              try:
                  result = call("GET", f"/test_framework/v1/results/{result_id}/")
              except urllib.error.HTTPError as e:
                  if e.code < 500:
                      raise
                  print(f"poll got HTTP {e.code}; retrying")
              except urllib.error.URLError as e:
                  print(f"poll failed ({e.reason}); retrying")
              else:
                  if result.get("status") in TERMINAL:
                      break
              time.sleep(30)

          # Once every run has ended the result is "completed" if any run completed, whether
          # or not runs passed, and failed_runs_count leaves out runs that errored or timed
          # out. Gate on passes.
          runs = result.get("runs") or {}
          for r in runs.values() if isinstance(runs, dict) else runs:
              if not r.get("success"):
                  print(f"FAILED run {r.get('id')} (scenario {r.get('scenario')}): "
                        f"{r.get('status')} {r.get('error_message') or ''}".rstrip())
          total, passed = result.get("total_runs_count", 0), result.get("success_runs_count", 0)
          print(f"{passed}/{total} run(s) passed; result status {result['status']}")
          if result["status"] != "completed" or total == 0 or passed != total:
              sys.exit(f"{total - passed} of {total} run(s) did not pass")
          EOF
```


## GitLab CI

Same two Python blocks as the GitHub template — validate, then poll — with `when: manual` standing
in for the manual dispatch. Paste each heredoc from the GitHub template in full where marked; do not
move them into files, since nothing else in the repository would own them.

```yaml
variables:
  CEKURA_BASE_URL: https://api.cekura.ai   # CEKURA_API_KEY and CEKURA_AGENT_ID come from CI/CD variables

cekura:validate:
  image: python:3.12-slim
  script:
    - python3 -c "import json; json.load(open('cekura.tests.json'))"
    - |
      python3 - <<'EOF'
      # the "Validate against Cekura" heredoc from the GitHub template, verbatim
      EOF

cekura:run:
  image: python:3.12-slim
  needs: [cekura:validate]
  when: manual                        # real calls stay opt-in, as on GitHub
  script:
    - |
      python3 - <<'EOF'
      # the "Run the suite" heredoc from the GitHub template, verbatim
      EOF
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

This is the one question the skill asks, and it comes with a default: **manual dispatch only**.
Write that unless the user picks something else.

| Trigger | Good for |
|---|---|
| Manual only (`workflow_dispatch`) | **the default.** Pick a branch in the Actions tab; nothing fires on its own |
| Push to the deploy branch / pre-deploy | the whole suite as a release gate |
| Nightly on the main branch | catching drift from provider-side changes nobody committed |
| Pull requests touching the spec or `src/` | only where the suite is small, fast and reliably green |

Whatever they pick, `workflow_dispatch` with the `dry_run` checkbox stays in the file alongside it,
and every non-manual trigger validates only unless they explicitly asked otherwise.

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


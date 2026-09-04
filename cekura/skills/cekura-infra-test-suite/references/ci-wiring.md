# CI wiring

How the committed spec becomes a gate that can actually fail a build.

## The mistake this file exists to prevent

```bash
curl -X POST ".../run_scenarios_json/" -d '{"agent_id": 42, "spec": ...}'   # ← green in 2 seconds
```

That request returns as soon as the runs are **queued**. Nothing has been dialled, nothing judged.
A job that ends there passes while the agent is broken — a gate that is worse than no gate, because
it looks like coverage. Something has to poll the runs to a terminal state and exit non-zero.

The template below does exactly that. Copy it; do not compose YAML from memory.

| Step | Needs | Cost | Runs on |
|---|---|---|---|
| spec is well-formed | nothing | free | every trigger, forks included |
| validate against Cekura | API key + agent id | free | every trigger where secrets exist |
| run the suite | API key + agent id | real calls | a manual run with the box unchecked |

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

One file, one job, two modes. **`workflow_dispatch` alone is the default** — the run is started
from the Actions tab against a branch of your choosing, and the `dry_run` checkbox on it defaults
to checked. Any additional trigger is opt-in, and validates only unless the user asked for live
calls there.

```yaml
name: Cekura voice tests

on:
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Validate only — no calls placed, no credit spent"
        type: boolean
        default: true
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
              "/test_framework/v1/scenarios/run_scenarios_json/?dry_run=true"
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
          import json, os, sys, time, urllib.request

          base = os.environ["CEKURA_BASE_URL"].rstrip("/")
          key = {"X-CEKURA-API-KEY": os.environ["CEKURA_API_KEY"], "Content-Type": "application/json"}

          def call(method, path, payload=None):
              req = urllib.request.Request(base + path, payload, key, method=method)
              return json.load(urllib.request.urlopen(req, timeout=60))

          spec = json.load(open("cekura.tests.json"))
          body = json.dumps({"agent_id": int(os.environ["CEKURA_AGENT_ID"]), "spec": spec}).encode()
          started = call("POST", "/test_framework/v1/scenarios/run_scenarios_json/", body)
          ids = [r["id"] for r in started.get("results", [])]
          print(f"queued {len(ids)} run(s)")

          # The POST returns once the runs are queued — nothing has been dialled
          # yet. Poll to a terminal state or the job is a gate that cannot fail.
          deadline = time.time() + 45 * 60
          while time.time() < deadline:
              runs = call("GET", "/test_framework/v2/runs/bulk/?ids=" + ",".join(map(str, ids)))
              pending = [r for r in runs.get("results", []) if r.get("status") in ("queued", "running")]
              if not pending:
                  failed = [r for r in runs["results"] if r.get("status") != "passed"]
                  for r in failed:
                      print(f"FAILED {r.get('id')} {r.get('scenario_name')}: {r.get('status')}")
                  sys.exit(f"{len(failed)} case(s) failed" if failed else 0)
              time.sleep(30)
          sys.exit("timed out waiting for runs")
          EOF
```


## GitLab CI

Same two Python blocks as the GitHub template — validate, then poll — with `when: manual` standing
in for the `dry_run` checkbox.

```yaml
cekura:validate:
  image: python:3.12-slim
  variables:
    CEKURA_API_KEY: $CEKURA_API_KEY
    CEKURA_AGENT_ID: $CEKURA_AGENT_ID
  script:
    - python3 -c "import json; json.load(open('cekura.tests.json'))"
    - python3 ci/validate.py          # the validate heredoc above, inlined here

cekura:run:
  image: python:3.12-slim
  needs: [cekura:validate]
  when: manual                        # real calls stay opt-in, as on GitHub
  script: python3 ci/run.py           # the poll heredoc above
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

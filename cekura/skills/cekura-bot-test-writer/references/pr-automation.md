# Running the test writer on every pull request

The skill works fine typed by hand. This file is for the other mode: a job that reads each pull
request and proposes the suite edit before a human asks.

## What the job is allowed to do

Two properties make an automated test writer safe to leave on. Neither is negotiable, and both
are enforced by a step, not by the prompt:

1. **It validates; it never dials.** Lint and `?dry_run=true` only. A writer that places calls
   bills on every push, and the bill arrives whether or not anyone reads the result. The suite's
   own workflow runs the calls, on its own trigger, where someone chose the cost.
2. **It writes spec files and nothing else.** A guard step diffs the working tree against an
   allowlist and fails the job if anything else moved. Without it, "make the test possible" turns
   into an agent editing the bot to suit its own case — the exact failure the skill's scope rule
   exists to prevent, arriving unreviewed at 3am.

## Choosing the trigger

| Trigger | Good for | Cost |
|---|---|---|
| `pull_request` + a `paths:` filter on runtime code | teams that want the answer without remembering to ask | one agent run per push to a matching PR |
| `pull_request` `types: [labeled]` on a `update-tests` label | expensive agents, noisy repos, or while you are still learning to trust it | one run per label application |
| both — automatic on PR open, re-runnable by label | the usual landing place | |

Filter hard on paths. A docs-only or CI-only pull request should not wake the writer at all, and
the skill's own first answer for one would be `no change` anyway — paying an agent to say so is
waste. Filter on the directories that actually build the bot, plus the spec itself so a
hand-edited suite still gets linted.

`concurrency` with `cancel-in-progress: true` keeps a branch that is being pushed to from
stacking runs.

## GitHub Actions

```yaml
name: Cekura test writer

on:
  pull_request:
    types: [opened, synchronize, labeled]
    # List the directories that actually build the agent — whatever this
    # repository calls them — plus the spec itself, so a hand-edited suite
    # still gets linted. Everything else should not wake the writer at all.
    paths:
      - "<agent source dirs>/**"
      - "<your spec>.json"

concurrency:
  group: cekura-test-writer-${{ github.event.pull_request.number }}
  cancel-in-progress: true

permissions:
  contents: write          # to push the suite edit to the PR branch
  pull-requests: write     # to post the decision table

jobs:
  update-suite:
    # Forks carry no secrets. Skip rather than fail for a reason that has
    # nothing to do with the change.
    if: github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    env:
      SPEC: "<your spec>.json"
      # Every path the writer is allowed to touch, as one regex: the spec(s)
      # and the coverage note. Nothing else, ever.
      SPEC_ALLOWLIST: '^(<your spec>\.json|<coverage note>\.md)$'
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.ref }}
          fetch-depth: 0            # the skill diffs against the merge base

      - name: Record the pre-agent state
        run: git rev-parse HEAD > /tmp/base-sha

      - name: Load the skill
        run: npx --yes skills add cekura-ai/cekura-skills --skill cekura-bot-test-writer

      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          prompt: |
            Use the cekura-bot-test-writer skill on this pull request.

            PR_BASE_REF=origin/${{ github.event.pull_request.base.ref }}
            Cekura agent id: ${{ vars.CEKURA_AGENT_ID }}

            Follow the skill exactly. Edit only the committed Cekura spec files and
            their coverage note. Do not place a live run. Post the decision table as
            a PR comment with `gh pr comment`, including every row you left uncovered.
          claude_args: >-
            --allowed-tools "Bash(git diff:*),Bash(git log:*),Bash(git fetch:*),Bash(git merge-base:*),Bash(python3:*),Bash(gh pr comment:*),Bash(gh pr view:*),Read,Edit,Grep,Glob"
        env:
          CEKURA_API_KEY: ${{ secrets.CEKURA_API_KEY }}
          CEKURA_BASE_URL: ${{ vars.CEKURA_BASE_URL || 'https://api.cekura.ai' }}

      - name: Guard — only spec files may change
        run: |
          set -euo pipefail
          changed=$(git diff --name-only "$(cat /tmp/base-sha)")
          echo "$changed"
          bad=$(echo "$changed" | grep -Ev "$SPEC_ALLOWLIST" || true)
          if [ -n "$bad" ]; then
            echo "::error::the writer touched files outside the spec allowlist:"
            echo "$bad"
            exit 1
          fi

      - name: Validate the edited spec
        if: ${{ env.CEKURA_API_KEY != '' }}
        env:
          CEKURA_API_KEY: ${{ secrets.CEKURA_API_KEY }}
        run: |
          set -euo pipefail
          python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$SPEC"
          # dry run only — see the validate heredoc in
          # cekura-infra-test-suite/references/ci-wiring.md
          python3 ci/cekura_validate.py

      - name: Commit the suite edit
        run: |
          set -euo pipefail
          git config user.name  "cekura-test-writer[bot]"
          git config user.email "noreply@cekura.ai"
          git add -A
          git diff --cached --quiet && { echo "no suite change — nothing to commit"; exit 0; }
          git commit -m "test(cekura): update suite for this PR"
          git push
```

Order matters: guard, then validate, then commit. A spec that has not returned `valid: true` must
not reach the branch, and a job that commits first has already lost the argument.

## The commit-back gotcha

A push made with `GITHUB_TOKEN` does **not** trigger other workflows. If your suite's own gate
runs on `pull_request`, it will not re-run for the writer's commit — the validation step above is
therefore the only thing standing between a bad spec and the branch, which is why it is a step
and not a downstream job. Use a GitHub App token if you genuinely need downstream workflows to
fire.

## Forks

The `if:` above skips forks outright. If you want fork coverage, do not reach for
`pull_request_target` with a checkout of the PR head — that hands repository secrets to
unreviewed code. Run the writer on a maintainer's re-push instead, or have it comment a patch a
maintainer applies:

```yaml
      - name: Fork PRs — propose, do not push
        if: github.event.pull_request.head.repo.full_name != github.repository
        run: |
          git diff > suite.patch
          gh pr comment "$PR" --body-file <(printf '```diff\n%s\n```' "$(cat suite.patch)")
```

Unvalidated, and label it so: no secrets means no dry run.

## Reading the output

The comment is the product, not the commit. A good one says what changed *and what did not*: the
decision table with its `none` rows, the case count before and after, the dry-run verdict, and
every `uncovered` row with what it would take. If a run's comment is only a diff, the writer
skipped step 2 of the skill and the reviewer has nothing to check it against.

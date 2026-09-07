# Phase 5 — Offer the Cekura SDK, then open a PR (LiveKit / Pipecat)

> **Start:** Announce the step in plain words ("There's more Cekura can capture from your agent — want to see?") — never a phase number or the word "Phase"; the numbering below is internal navigation only.

**Testing variant: this runs once the user has seen their agent actually work** — a run whose call connected and completed. The offer is "here's what more Cekura can capture", and that sentence only means anything against something they watched work. If the run hasn't happened, go back to [phase4-evaluators-run.md](phase4-evaluators-run.md).

**Scores do not have to be in yet.** Metric evaluation runs a minute or two behind the call, and that wait is exactly when this step belongs — the user is otherwise watching a spinner, and "stop here" is the only other thing to offer them. If you arrived from phase4's F4b with the run still scoring, keep the result id: after the PR is raised or declined, read the results once more and share the scores before the closing summary. **Observability variant:** you arrive here straight from [phase3-create.md](phase3-create.md) — the SDK *is* the observability integration for these providers — with the use case preselected to "Observability"; skip the pitch's testing half.

The runtime denies `github_open_pull_request` until this file has been read, because everything that keeps this step safe — show the changes first, get an explicit yes, no credential in the diff — is written down here and nowhere else.

**If phase2's scan found the SDK already wired**, the offer is different: "Your code already integrates the Cekura SDK. Want me to switch tracing on for this agent?" → straight to 5e.

## 5a. Offer it, and let them choose what for

Ask as a `<clarification>`; prose does not pause the turn.

> "Your tests are running against the agent from the outside. The Cekura SDK adds what only the agent itself can see: per-turn transcripts, tool calls and their arguments, latency breakdowns, and OTel traces — plus dual-channel audio on production calls. It's a small change to your agent code, and I can open it as a pull request for you to review."

Options: `["Testing — richer test runs", "Observability — capture production calls", "Both", "Not now"]`

- **"Not now"** — fallback **F6**: accept it in one line, leave `tracing_enabled` at `false`, and exit to the closing summary in `cekura-onboarding/phase6-testing-next.md`. Do not re-pitch.
- **Observability variant:** don't ask the four-way question — the use case is Observability. Confirm with one line and go to 5b.
- The answer decides which methods get wired:

| Chosen | LiveKit | Pipecat |
|---|---|---|
| Testing | `track_session` | `track_and_create_task` |
| Observability | `observe_session` | `observe_and_create_task` |
| Both | both, split by entrypoint or an env var | both, split by entrypoint or an env var |

`track_*` is what Cekura's own simulation runs hit. `observe_*` is for real production calls that never went through Cekura. If they want both from a single entrypoint, gate on an env var (`CEKURA_MODE=test` → `track_*`, else `observe_*`).

## 5b. Show the planned changes as diffs, then get an explicit yes — fallback **F7**

Check out the repo (**dashboard** `github_checkout_repo`; **local** it is the working directory) and read enough to make the real edits. Then show them **the way a plan is shown: one `<diff_view>` block per file, actual before/after**, with a one-line title saying what it unlocks:

```
<diff_view>
{"original": "<the file as it is>", "updated": "<the file with the tracer wired in>", "language": "python", "title": "agent/main.py — track_session before session.start(): transcripts, tool calls, traces"}
</diff_view>
```

One block per file — typically the entrypoint, the dependency manifest, and `.env.example` — then a single line: "Three files. Open it as a PR?" and a `<clarification>` with `["Open the PR", "Change the plan", "Not now"]`.

**Get the yes before calling `github_open_pull_request`.** This writes to code the user owns; a change they never saw is a surprise PR in their repo. *Change the plan* → apply and re-show the diffs. *Not now* → exit as in 5a's "Not now".

**Local session:** show the same diffs as fenced blocks, then make the edits with `Edit` on a **new branch** — never the default branch; offer `gh pr create` only if asked.

## 5c. Write the code — no secret in the diff

**The API key and the agent id are read from environment variables. Never hardcode either, never inline a real key, never commit a `.env`.** A credential in a PR is a credential in the repo's history even after the PR is closed.

**LiveKit (Python)** — before `session.start(...)`; calling it after is a silent no-op:

```python
import os
from cekura.livekit import LiveKitTracer

cekura = LiveKitTracer(
    api_key=os.getenv("CEKURA_API_KEY"),
    agent_id=int(os.getenv("CEKURA_AGENT_ID", "0")),
)
# inside the entrypoint, before session.start(...)
await cekura.track_session(ctx, session, assistant)
```

**LiveKit (JS/TS)** — inside `defineAgent({ entry: ... })`, before `session.start({...})`:

```typescript
import { LiveKitTracer } from '@cekura/livekit';

const cekura = new LiveKitTracer({
  apiKey: process.env.CEKURA_API_KEY || '',
  agentId: Number(process.env.CEKURA_AGENT_ID),
});
await cekura.trackSession(ctx, session, agent);
```

**Pipecat (Python)** — replace the existing `PipelineTask(pipeline, ...)`:

```python
import os
from cekura.pipecat import PipecatTracer

cekura = PipecatTracer(
    api_key=os.getenv("CEKURA_API_KEY"),
    agent_id=int(os.getenv("CEKURA_AGENT_ID", "0")),
)
task = cekura.track_and_create_task(
    pipeline, context, runner_args=runner_args, transport=transport,
)
```

If the existing `PipelineTask(...)` carries kwargs the helper can't take, use the multi-step form instead — `cekura.track_pipeline(...)`, then `PipelineTask(..., enable_tracing=True, enable_turn_tracking=True)`, then `cekura.register_task_handlers(task, transport=transport)`. Both flags are required or no OTel spans appear.

Add the dependency to `requirements.txt` / `pyproject.toml` / `package.json` to match the project's existing manifest, and document the two env vars in `.env.example` **as names only — no values**.

**Three gotchas worth catching while you're in the code:**
- **Pipecat needs `LLMUserAggregator` + `LLMAssistantAggregator`** (from `LLMContextAggregatorPair`) in the pipeline. Without them the SDK logs a disabled-observability line and silently does nothing. If they're missing, ask before adding them — it changes pipeline behavior.
- **`PipecatTracer` is not thread-safe across concurrent calls.** If one process serves several calls, construct the tracer inside the per-call handler, not at module scope.
- **LiveKit `agent_name` must match** `credentials.config.agent_name` on the Cekura agent, or dispatches go nowhere.

## 5d. Open the PR, ending with what only they can do

`github_open_pull_request`. It opens against a new branch and never touches the default branch.

**End the PR body with the actions only the user can take** — the PR is not finished work until these are done, and none of them can be done from here:

```markdown
## Before this works — three things only you can do

1. **Create a Cekura API key** — Settings → API Keys → Create (`{dashboard_url}/settings/org/api-key`; in a local session name the page in words). It's shown once.
2. **Set both env vars** wherever this agent runs (deployment env, secret manager — not in the repo):
   - `CEKURA_API_KEY` — the key from step 1
   - `CEKURA_AGENT_ID` — `<the agent id>`
3. **Redeploy the agent** so it picks them up.

Tell Cekura once all three are done and tracing gets switched on.
```

## 5e. Switch tracing on — only after they confirm all three

Ask (`<clarification>`, options `["All three done", "Not yet"]`). **Only when they confirm all three**, PATCH the agent:

```json
{"provider": {"credentials": {"config": {"tracing_enabled": true}}}}
```

**Flipping it early is the failure mode:** with `tracing_enabled: true` and no SDK actually running, every test run waits on a webhook that never arrives and times out. Merged-but-not-deployed is the same as not done. If they say "not yet" — fallback **F8** — leave it `false`, say plainly that traces stay off until the deploy lands, and exit to the closing summary with the PR link and "tracing off until redeploy" as the open item.

---

## Phase 5 Gate

**Either:** the user declined the SDK (and `tracing_enabled` stays `false`) — or the PR is open and `tracing_enabled` matches reality: `true` only after they confirmed key, env vars and redeploy; `false` in every other state.

Close out with the summary from `cekura-onboarding/phase6-testing-next.md`, including the PR link and any open item. **That summary is the end of onboarding** — onboarding's own phases are not re-run.

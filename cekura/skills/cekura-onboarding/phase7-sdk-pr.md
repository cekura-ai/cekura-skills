# Phase 7 (testing) — Offer the Cekura SDK, then open a PR

> **Start:** Announce the step in plain words ("There's more Cekura can capture from your agent — want to see?") — never a phase number or the word "Phase"; the numbering below is internal navigation only.

**This phase is LiveKit / Pipecat only, and it runs ONLY after the user has seen real results.** The offer is "here's what more Cekura can capture", and that sentence only means anything once they have a completed run, a transcript and scores in front of them. Offered before results, it is an upsell for a product they have not yet seen work. If the run hasn't happened, go back to [phase5-testing-first-run.md](phase5-testing-first-run.md).

The runtime denies `github_open_pull_request` until this file has been read, because everything that keeps this step safe — plan first, confirm, and no credential in the diff — is written down here and nowhere else.

## 7a. Offer it, and let them choose what for

Ask as a `<clarification>`; prose does not pause the turn.

> "Your tests are running against the agent from the outside. The Cekura SDK adds what only the agent itself can see: per-turn transcripts, tool calls and their arguments, latency breakdowns, and OTel traces — plus dual-channel audio on production calls. It's a small change to your agent code, and I can open it as a pull request for you to review."

Options: `["Testing — richer test runs", "Observability — capture production calls", "Both", "Not now"]`

- **"Not now"** — accept it in one line, leave `tracing_enabled` at `false`, and close out the summary. Do not re-pitch.
- The answer decides which methods get wired:

| Chosen | LiveKit | Pipecat |
|---|---|---|
| Testing | `track_session` | `track_and_create_task` |
| Observability | `observe_session` | `observe_and_create_task` |
| Both | both, split by entrypoint or an env var | both, split by entrypoint or an env var |

`track_*` is what Cekura's own simulation runs hit. `observe_*` is for real production calls that never went through Cekura. If they want both from a single entrypoint, gate on an env var (`CEKURA_MODE=test` → `track_*`, else `observe_*`).

## 7b. Show a short plan and get an explicit yes

Check out the repo (`github_checkout_repo`) and read enough to name the real files. Then show the plan — **one line per file, what it unlocks. Not a tutorial, not the diff, not a code walkthrough.**

> Here's what I'd change in `acme/voice-agent`:
> - `requirements.txt` — add `cekura[livekit]`, the tracer package
> - `agent/main.py` — construct the tracer and call `track_session` before `session.start()`, which is what captures transcripts, tool calls and traces
> - `.env.example` — document `CEKURA_API_KEY` and `CEKURA_AGENT_ID` so the deploy knows what to set
>
> Three files. Open it as a PR?

Then a `<clarification>` with `["Open the PR", "Not now"]`. **Get the yes before calling `github_open_pull_request`** — this writes to code the user owns, and a plan they never agreed to is a surprise PR in their repo.

If they want changes to the plan, make them and re-show it. If they say no, leave `tracing_enabled` at `false` and close out.

## 7c. Write the code — no secret in the diff

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

## 7d. Open the PR, ending with what only they can do

`github_open_pull_request`. It opens against a new branch and never touches the default branch.

**End the PR body with the actions only the user can take** — the PR is not finished work until these are done, and none of them can be done from here:

```markdown
## Before this works — three things only you can do

1. **Create a Cekura API key** — Settings → API Keys → Create. It's shown once.
2. **Set both env vars** wherever this agent runs (deployment env, secret manager — not in the repo):
   - `CEKURA_API_KEY` — the key from step 1
   - `CEKURA_AGENT_ID` — `<the agent id>`
3. **Redeploy the agent** so it picks them up.

Tell Cekura once all three are done and tracing gets switched on.
```

## 7e. Switch tracing on — only after they confirm all three

Ask (`<clarification>`, options `["All three done", "Not yet"]`). **Only when they confirm all three**, PATCH the agent:

```json
{"provider": {"credentials": {"config": {"tracing_enabled": true}}}}
```

**Flipping it early is the failure mode:** with `tracing_enabled: true` and no SDK actually running, every test run waits on a webhook that never arrives and times out. Merged-but-not-deployed is the same as not done. If they say "not yet", leave it `false`, say plainly that traces stay off until the deploy lands, and carry it as an open item in the summary.

---

## Phase 7 Gate

**Either:** the user declined the SDK (and `tracing_enabled` stays `false`) — or the PR is open and `tracing_enabled` matches reality: `true` only after they confirmed key, env vars and redeploy; `false` in every other state.

Close out with the summary from [phase6-testing-next.md](phase6-testing-next.md), including the PR link and any open item.

# Phase 6 — SDK Integration (LiveKit / Pipecat)

For LiveKit and Pipecat, integrate the Cekura SDK directly into the user's agent codebase. The SDK exposes agent-side data (transcripts, tool calls, metrics, OTel traces, session logs, and — in observe mode — dual-channel audio) that no other connection mode can capture.

**This phase is a no-op for every other provider.** If `provider.type` is not `livekit` or `pipecat`, announce "Phase 6 — SDK Integration not applicable for `<provider>`" and continue to [Phase 7](phase7-mock-tools.md).

---

> **Start:** Announce "Starting Phase 6 — SDK Integration" before doing anything in this phase.

## 6a. Brief the user (do not ask permission)

State one sentence about what the SDK adds and that you are integrating now:

> "I'll integrate the Cekura SDK into your agent code now. It adds transcripts, tool calls, metrics, OTel traces, session logs, and dual-channel audio (in observe mode) to every call — none of which is available without it. Stop me if you'd prefer not to touch the agent code."

Do not wait for confirmation. Proceed unless the user objects. If they object, jump to [6h. Falling back when the user refuses the SDK](#6h-falling-back-when-the-user-refuses-the-sdk).

## 6b. Pick the methods to wire

The use case (testing / observability / both) is inherited from the onboarding context. If unclear at this point, ask explicitly:

> "Are you using Cekura primarily for testing your agent with simulations, observing production calls that don't go through Cekura, or both?"

| Use case | LiveKit method(s) | Pipecat method(s) |
|----------|-------------------|-------------------|
| Testing only | `track_session` | `track_pipeline` / `track_and_create_task` |
| Observability only | `observe_session` | `observe_pipeline` / `observe_and_create_task` |
| Both | both (split by entrypoint or env var) | both (split by entrypoint or env var) |

When wiring both, ask the user how they distinguish prod from UAT:

> "Do you have separate entrypoints — or an environment variable — that distinguishes your production agent from UAT/dev/staging? (e.g. `ENV=production` vs `ENV=staging`, or separate files like `bot_prod.py` vs `bot_dev.py`.)"

Wire the matching method into each entrypoint. If they share a single entrypoint, gate the call on an env var (`CEKURA_MODE=test` → `track_*`, otherwise `observe_*`).

**Be explicit when explaining:** `track_*` is what Cekura simulation runs hit. `observe_*` is for real production calls that don't originate from Cekura.

## 6c. Locate the agent repo

Default to the current working directory. Run a quick scan for entrypoint markers using grep:

- **LiveKit Python** — `@server.rtc_session`, `JobContext`, `agents.AgentSession`, `session.start(`
- **LiveKit JS/TS** — `defineAgent(`, `voice.AgentSession`, `await session.start(`
- **Pipecat** — `Pipeline(`, `PipelineTask(`, `LLMContext`, `LLMContextAggregatorPair`

If at least one marker matches in cwd, that's the repo. If nothing matches, ask:

> "Where is your LiveKit/Pipecat agent code? Give me the path so I can integrate the SDK."

Then re-scan at the given path.

## 6d. Detect language (LiveKit only)

Pipecat is Python-only — skip this step.

For LiveKit, decide between Python and JS/TS:

- **Python** — `requirements.txt`, `pyproject.toml`, or any `*.py` importing from `livekit`
- **JS/TS** — `package.json` with `@livekit/agents` dep, or `*.ts`/`*.js` files importing `@livekit/agents`

If both, ask the user which file(s) to instrument. If neither, fall back to asking the user directly.

## 6e. Install the SDK

Update the dependency manifest, then run the install. Skill executes the install — do not give the user commands to run themselves.

**LiveKit Python:**
- Append `cekura[livekit]==1.2.0` to `requirements.txt` (or add to `pyproject.toml` under the appropriate dependency group).
- Run `pip install cekura[livekit]==1.2.0` (use the project's venv if one is active).

**LiveKit JS/TS:**
- Run `npm install @cekura/livekit@1.0.0-rc.1` (or `pnpm add` / `yarn add` to match the existing lockfile).

**Pipecat:**
- Append `cekura[pipecat]==1.4.1` to `requirements.txt` / `pyproject.toml`.
- Run `pip install cekura[pipecat]==1.4.1`.

## 6f. Make the code edits

Use `Edit` to modify the entrypoint(s) in place. See `references/livekit-tracing.md` and `references/pipecat-tracing.md` for the full snippets and edge cases.

### LiveKit Python

Add at the top of the entrypoint module:

```python
import os
from cekura.livekit import LiveKitTracer

cekura = LiveKitTracer(
    api_key=os.getenv("CEKURA_API_KEY"),
    agent_id=<AGENT_ID_FROM_PHASE_5>,
)
```

Inside the entrypoint, immediately before `session.start(...)`:

```python
# Testing mode — Cekura simulation runs
await cekura.track_session(ctx, session, assistant)

# Or observability mode — real production calls
await cekura.observe_session(ctx, session)
```

### LiveKit JS/TS

Top of the entry file:

```typescript
import { LiveKitTracer } from '@cekura/livekit';

const cekura = new LiveKitTracer({
  apiKey: process.env.CEKURA_API_KEY || '',
  agentId: <AGENT_ID_FROM_PHASE_5>,
});
```

Inside `defineAgent({ entry: ... })`, before `session.start({...})`:

```typescript
// Testing
await cekura.trackSession(ctx, session, agent);

// Observability
await cekura.observeSession(ctx, session);
```

### Pipecat (single-step API — default)

Replace the existing `PipelineTask(pipeline, ...)` call with the SDK's helper. This wraps the pipeline, creates the task, and registers cleanup handlers in one call.

```python
import os
from cekura.pipecat import PipecatTracer

cekura = PipecatTracer(
    api_key=os.getenv("CEKURA_API_KEY"),
    agent_id=<AGENT_ID_FROM_PHASE_5>,
)

# Testing
task = cekura.track_and_create_task(
    pipeline, context, runner_args=runner_args, transport=transport,
)

# Observability
task = cekura.observe_and_create_task(
    pipeline, context, runner_args=runner_args, transport=transport,
)
```

### Pipecat (multi-step API — when the user has custom PipelineTask kwargs)

If the existing `PipelineTask(...)` has arguments the helper can't take, use the multi-step API instead:

```python
pipeline = cekura.track_pipeline(pipeline, context, runner_args=runner_args)
task = PipelineTask(
    pipeline,
    enable_tracing=True,
    enable_turn_tracking=True,
    # ...user's existing kwargs...
)
task = cekura.register_task_handlers(task, transport=transport)
```

`enable_tracing=True` and `enable_turn_tracking=True` are required for OTel spans. `register_task_handlers` must be called after `PipelineTask` creation.

### Pipecat — verify aggregators

The SDK requires `LLMUserAggregator` and `LLMAssistantAggregator` (created via `LLMContextAggregatorPair`) in the pipeline. Without them, the SDK logs `Cekura observability disabled: LLMUserAggregator and LLMAssistantAggregator not found in pipeline.` and silently does nothing.

If the pipeline is missing them, ask the user before adding — it changes pipeline behavior:

> "Your pipeline doesn't include the LLM aggregator pair the SDK needs to capture transcripts. Should I add `LLMContextAggregatorPair` (user aggregator after STT, assistant aggregator after `transport.output()`)?"

If yes, edit the pipeline accordingly.

## 6g. Wire CEKURA_API_KEY into the runtime

Set the env var so the SDK can pick it up:

- If `.env` or `.env.example` exists in the repo, append `CEKURA_API_KEY=<key>` (or a placeholder with a comment).
- Otherwise, tell the user explicitly how to set it for their runtime (shell export, deployment env, secret manager). Never hardcode the key in code.

## 6h. Falling back when the user refuses the SDK

If the user objects to the SDK edits:

- **Update the Cekura agent record:** PATCH `credentials.config.tracing_enabled = false` via `mcp__cekura__aiagents_partial_update`. The `true` set in Phase 5 was provisional; this clears the per-run wait.
- **If only testing was in scope** — continue without the SDK. Tests will still run via WebRTC Automated / Telephony / Manual, but the run data is limited to what the provider exposes (no agent-side transcripts, no tool-call attribution, no OTel traces).
- **If observability is in scope** — neither LiveKit nor Pipecat has a non-SDK observability path on Cekura. Point the user to Custom Observability:

  > "Without the SDK, observability requires you to push call data yourself after each call. POST to `https://api.cekura.ai/observability/v1/observe/` with the call's messages and metadata within 5 minutes of call end. See `references/integrations.md` → Custom Integration for the payload shape."

  This is a last resort. Re-pitch the SDK once before settling for this path.

## 6i. Confirm `tracing_enabled` on the Cekura agent

After the integration is complete, PATCH `credentials.config.tracing_enabled` to match reality:

| Situation | `tracing_enabled` |
|-----------|-------------------|
| SDK wired, testing in scope (testing-only or both) | `true` |
| SDK wired, observability only | `false` |
| User refused SDK | `false` |

Use `mcp__cekura__aiagents_partial_update` with a JSON body of the form:

```json
{
  "provider": {
    "credentials": {
      "config": {
        "tracing_enabled": true
      }
    }
  }
}
```

## 6j. Pre-flight gotchas

Surface these before exiting the phase:

- **LiveKit `agent_name` mismatch** — `@server.rtc_session(agent_name="X")` must match `credentials.config.agent_name` on the Cekura agent (when WebRTC Automated or Chat is in scope). If they differ, dispatches will go nowhere.
- **LiveKit tracer placement** — `cekura.track_session(...)` / `observe_session(...)` must be called **before** `session.start(...)`. Calling it after is a silent no-op.
- **Pipecat aggregators** — without `LLMUserAggregator` + `LLMAssistantAggregator`, the SDK disables itself. Confirm they're present.
- **Pipecat tracing flags** — when using the multi-step API, `PipelineTask` must have `enable_tracing=True, enable_turn_tracking=True` or no OTel spans appear.
- **Concurrent Pipecat sessions** — `PipecatTracer` is not thread-safe across concurrent calls. If the agent serves multiple calls in one process, the tracer must be instantiated **inside** the function that handles each call, not shared at module scope.

---

## Phase 6 Gate

**Do not proceed until the SDK is integrated (or the user has explicitly refused) and `credentials.config.tracing_enabled` reflects the correct value.**

Announce: "Phase 6 complete." Then immediately begin [Phase 7 — Mock Tools](phase7-mock-tools.md) without waiting for the user.

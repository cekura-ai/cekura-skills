# Phase 6 — SDK Integration (LiveKit / Pipecat)

For LiveKit and Pipecat, integrate the Cekura SDK directly into the user's agent codebase. The SDK exposes agent-side data (transcripts, tool calls, metrics, OTel traces, session logs, and — in observe mode — dual-channel audio) that no other connection mode can capture.

**This phase is a no-op for every other provider.** If `provider.type` is not `livekit` or `pipecat`, announce "Phase 6 — SDK Integration not applicable for `<provider>`" and continue to [Phase 7](phase7-mock-tools.md).

---

> **Start:** Announce "Starting Phase 6 — SDK Integration" before doing anything in this phase.

## 6·0. Which surface are you on? (decide this first)

The two surfaces have different powers, and following the wrong branch produces instructions that cannot execute.

**Check your tool list for `github_checkout_repo`.**

| Present | Surface | How the change lands |
|---|---|---|
| **No** | Local (Claude Code / Codex / Cursor) with the repo on disk | Install the dep and edit files in place — **§6a–6j below, unchanged** |
| **Yes** | The Cekura platform assistant, in a sandbox | Check out → edit → **pull request**. No package manager, no access to the running deployment — **[§6P](#6p-platform-mode--plan--confirm--pull-request)**, which replaces §6a and §6c–§6g |

On the platform, `pip install` / `npm install` cannot run (the shell is `cat`/`head`/`tail`/`grep`/`ls`/`wc`), there is no working tree outside `/app/repos/<repo>/`, and nothing you do reaches the user's running agent. Everything is a proposal on a branch.

§6b (pick the methods), §6h (refusal), §6i (`tracing_enabled`) and §6j (gotchas) apply to **both** surfaces.

## 6a. Brief the user (do not ask permission) — LOCAL SURFACE ONLY

State one sentence about what the SDK adds and that you are integrating now:

> "I'll integrate the Cekura SDK into your agent code now. It adds transcripts, tool calls, metrics, OTel traces, session logs, and dual-channel audio (in observe mode) to every call — none of which is available without it. Stop me if you'd prefer not to touch the agent code."

Do not wait for confirmation. Proceed unless the user objects. If they object, jump to [6h. Falling back when the user refuses the SDK](#6h-falling-back-when-the-user-refuses-the-sdk).

## 6b. Pick the methods to wire

**Ask this — do not inherit it from the onboarding path.** A user who chose the testing path in Phase 0 was answering "what do you want to set up first", not "which halves of the SDK do you want". Observability is the half most users don't know exists, and inheriting silently means they never get offered it:

> "Are you using Cekura primarily for testing your agent with simulations, observing production calls that don't go through Cekura, or both?"

| Use case | LiveKit method(s) | Pipecat method(s) |
|----------|-------------------|-------------------|
| Testing only | `track_session` | `track_pipeline` / `track_and_create_task` |
| Observability only | `observe_session` | `observe_pipeline` / `observe_and_create_task` |
| Both | both (split by entrypoint or env var) | both (split by entrypoint or env var) |

**For "both", don't spend a question on the prod/UAT split.** If the repo shows separate entrypoints (`bot_prod.py` / `bot_dev.py`, or an `ENV`-branched dispatch), wire the matching method into each. Otherwise gate one entrypoint on an env var — `CEKURA_MODE=test` → `track_*`, otherwise `observe_*`. **State which you chose in the plan** and let the user correct it there; that costs no round-trip and lands in the same confirmation they're already giving.

**Be explicit when explaining:** `track_*` is what Cekura simulation runs hit. `observe_*` is for real production calls that don't originate from Cekura.

## 6c. Locate the agent repo — LOCAL SURFACE ONLY

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

## 6g. Wire CEKURA_API_KEY into the runtime — LOCAL SURFACE ONLY

Set the env var so the SDK can pick it up:

- If `.env` or `.env.example` exists in the repo, append `CEKURA_API_KEY=<key>` (or a placeholder with a comment).
- Otherwise, tell the user explicitly how to set it for their runtime (shell export, deployment env, secret manager). Never hardcode the key in code.

## 6P. Platform mode — plan → confirm → pull request

**Replaces §6a and §6c–§6g when `github_checkout_repo` is in your tool list.** Nothing here touches the user's running agent: the deliverable is a branch and a PR, and three things only the user can do (merge, set env vars, redeploy) stand between the PR and any data flowing.

### 6P.1 Get the code

Reuse the Phase 2 checkout if `/app/repos/<repo>/` already holds it. Otherwise `github_list_repos` → `github_checkout_repo`. If the user declined the repo scan back in Phase 2, that was a decision about *reading* their code; this is a new ask about *changing* it, so it is fair to offer again — once.

**Check whether the SDK is already wired** (`grep -rn "cekura.livekit\|cekura.pipecat"`). If it is, this is a version bump plus any missing env wiring — say so and shrink the plan accordingly; do not add a second tracer.

Locate the entrypoint with the §6c markers, run against the checkout: `@server.rtc_session` / `JobContext` / `session.start(` (LiveKit), `PipelineTask(` / `LLMContextAggregatorPair` (Pipecat).

### 6P.2 Show the plan, then get explicit confirmation

**Short.** Name the files and one line each — not a diff narration, not a tutorial. Then say what the user gains, drawn from what the SDK actually captures:

> Integrating the **testing** segment of the Cekura SDK — 3 files:
> - `agent.py` — add the tracer, call `track_session` before `session.start`
> - `requirements.txt` — add `cekura[livekit]==1.2.0`
> - `.env.example` — document `CEKURA_API_KEY` and `CEKURA_AGENT_ID`
>
> What this adds to every run: per-turn STT / LLM / TTS / EOU latency, tool-call attribution, session logs, OTel traces, and dual-channel audio.

**Show the actual edits as `<diff_view>` blocks** — one per file, `language` set to the file's language, a title naming the file. They are non-terminal, so emit them and keep going. `original` and `updated` are JSON strings: **every newline must be escaped as `\n` and every quote as `\"`**, or the block fails to parse and the raw JSON lands on screen.

**Then stop and ask, as a `<clarification>` block** — prose questions do not pause execution, so a plan that ends in prose will barrel straight into the PR:

```
<clarification>
{"questions": ["Raise the PR with these changes?"], "question_types": [null], "options": [["Raise the PR", "Change something", "Not now"]]}
</clarification>
```

**Do not open the PR before that answer comes back.**

### 6P.3 Make the edits

Edit inside `/app/repos/<repo>/` — that tree is writable and `github_open_pull_request` collects whatever changed there. Follow the §6f snippets, with two platform-specific differences:

**Both values come from the environment, and the agent ID falls back to the one you just created:**

```python
import os
from cekura.livekit import LiveKitTracer

# Cekura tracing. Both values are read from this agent's environment variables.
# CEKURA_AGENT_ID falls back to <AGENT_ID> — the Cekura agent created during setup.
# If you point this worker at a DIFFERENT Cekura agent, update that fallback
# (or set CEKURA_AGENT_ID). See the PR description.
cekura = LiveKitTracer(
    api_key=os.getenv("CEKURA_API_KEY"),
    agent_id=int(os.getenv("CEKURA_AGENT_ID", "<AGENT_ID>")),
)
```

Substitute the real integer from `aiagents_create`. The fallback means a missing `CEKURA_AGENT_ID` cannot crash their worker at import, and the tracer still points somewhere real — but it also means a stale fallback silently traces the wrong agent, which is exactly what that comment exists to prevent. Pipecat is the same shape with `PipecatTracer`; JS/TS uses `process.env` and `Number(...)`.

**The comment is required, not decorative.** It is the only warning a reviewer sees at the call site, and the platform has no way to leave a PR conversation comment — the code comment and the PR body are the two channels available.

**Dependency manifest only — no install.** Append `cekura[livekit]==1.2.0` / `cekura[pipecat]==1.4.1` to `requirements.txt` or `pyproject.toml` (`@cekura/livekit@1.0.0-rc.1` in `package.json` for JS/TS). Do not attempt `pip install` / `npm install`; the sandbox shell cannot run them and the user's build will install from the manifest anyway.

**`.env.example` gets placeholders, never values:**

```
CEKURA_API_KEY=
CEKURA_AGENT_ID=<AGENT_ID>
```

**Never put a real API key in the diff.** The code reads it from the environment, so the PR needs no secret at all — and `.env.example` is a committed file, so a live key written there is a leak.

### 6P.4 Open the PR and report what came back

`github_open_pull_request` with a title and a body. It branches — it never pushes to the default branch.

**End the body with the actions only the user can take.** They are the difference between a merged PR and working traces:

> **Before this takes effect**
> 1. **Create a Cekura API key** — Settings → API Keys → Create (shown once).
> 2. **Set two environment variables** wherever this agent's secrets live *(name the place the Phase 2 manifest scan identified — GitHub Actions secrets, a k8s secret, Modal, Render)*:
>    - `CEKURA_API_KEY` — the key from step 1
>    - `CEKURA_AGENT_ID` — `<AGENT_ID>` (also the in-code fallback; change both if you repoint this worker)
> 3. **Redeploy the agent** — the SDK only loads on a fresh start.
>
> Both values are read from this agent's environment variables; nothing secret is committed in this PR.

**Report the PR URL exactly as the tool returned it.** Never construct or guess one, and if the call errors, say it failed and what it said — a PR you did not verifiably open is not a PR.

Ask the user to review it.

### 6P.5 Confirm, then flip tracing on — last

Ask once, as a `<clarification>`, covering all three actions together:

```
<clarification>
{"questions": ["Once you've merged the PR, set CEKURA_API_KEY and CEKURA_AGENT_ID, and redeployed — tell me and I'll turn tracing on."], "question_types": [null], "options": [["All three done", "Not yet", "Skip tracing for now"]]}
</clarification>
```

**Only then** apply §6i. Flipping `tracing_enabled: true` at PR time is the classic error: the SDK is not live until merge + env vars + redeploy, and a `true` with no SDK behind it makes **every run wait on a webhook that never arrives**. If the user says "not yet", leave it `false`, say plainly that runs will keep showing provider-side data only, and carry it as an open item.

**The payoff is the next run.** Data starts flowing on runs that begin after the redeploy — the run whose results prompted this offer will never gain traces. Say so rather than letting the user infer it.

## 6h. Falling back when the user refuses the SDK

If the user objects to the SDK edits:

- **Update the Cekura agent record:** PATCH `credentials.config.tracing_enabled = false` via `mcp__cekura__aiagents_partial_update`. The `true` set in Phase 5 was provisional; this clears the per-run wait.
- **If only testing was in scope** — continue without the SDK. Tests will still run via WebRTC Automated / Telephony / Manual, but the run data is limited to what the provider exposes (no agent-side transcripts, no tool-call attribution, no OTel traces).
- **If observability is in scope** — neither LiveKit nor Pipecat has a non-SDK observability path on Cekura. Point the user to Custom Observability:

  > "Without the SDK, observability requires you to push call data yourself after each call. POST to `https://api.cekura.ai/observability/v1/observe/` with the call's messages and metadata within 5 minutes of call end. See `references/integrations.md` → Custom Integration for the payload shape."

  This is a last resort. Re-pitch the SDK once before settling for this path.

## 6i. Confirm `tracing_enabled` on the Cekura agent

After the integration is complete, PATCH `credentials.config.tracing_enabled` to match reality.

**"Complete" means running, not merged.** On the platform surface the SDK is live only after the PR is merged, both env vars are set, and the agent is redeployed — §6P.5 is the confirmation that all three happened. An open PR is `false`.


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

**On the platform surface, an open PR is a valid exit.** The merge, the env vars and the redeploy are the user's to do on their own schedule. Exit with the PR link and those three actions recorded as open items, and `tracing_enabled` still `false` — never imply the integration is live because the PR exists.

Announce: "Phase 6 complete." Then immediately begin [Phase 7 — Mock Tools](phase7-mock-tools.md) without waiting for the user.

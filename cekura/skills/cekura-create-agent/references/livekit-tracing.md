# LiveKit Tracing — SDK Reference

Cekura's LiveKit SDK wraps an existing LiveKit agent's `AgentSession` and exports transcripts, tool calls, metrics, session logs, and (in observability mode) dual-channel audio. Available for Python and JavaScript/TypeScript.

**Docs:** https://docs.cekura.ai/documentation/integrations/livekit/tracing

---

## Install

**Python:**
```bash
pip install cekura[livekit]==1.2.0
```

**JavaScript/TypeScript:**
```bash
npm install @cekura/livekit@1.0.0-rc.1
```

---

## Initialization

**Python:**
```python
from cekura.livekit import LiveKitTracer

cekura = LiveKitTracer(
    api_key=os.getenv("CEKURA_API_KEY"),
    agent_id=123,                    # From Cekura dashboard
    host="https://api.cekura.ai",    # Optional
    enabled=True,                    # Optional
)
```

**JavaScript/TypeScript:**
```typescript
import { LiveKitTracer } from '@cekura/livekit';

const cekura = new LiveKitTracer({
  apiKey: process.env.CEKURA_API_KEY || '',
  agentId: 123,
  host: 'https://api.cekura.ai',
  enabled: true,
});
```

Initialize once at module scope, not inside the entrypoint. `api_key` must come from `CEKURA_API_KEY` env — never hardcode.

---

## `track_session` vs `observe_session`

| Method | Use case | What it captures |
|--------|----------|------------------|
| `track_session(ctx, session, agent)` | Cekura simulation runs (testing/UAT) | Transcripts, tool calls, metrics, session logs. Auto-injects mock tools defined in Cekura. Auto-handles chat/text mode. **No audio recording.** |
| `observe_session(ctx, session)` | Production calls that don't originate from Cekura | Transcripts, tool calls, metrics, session logs, **plus dual-channel audio** via LiveKit egress (requires LiveKit credentials on the Cekura agent). |

Both must be called **before** `session.start(...)`. Calling after is a silent no-op.

---

## Reference snippets

### Python — Testing (`track_session`)

```python
import os
from livekit import agents
from cekura.livekit import LiveKitTracer

cekura = LiveKitTracer(
    api_key=os.getenv("CEKURA_API_KEY"),
    agent_id=123,
)

@server.rtc_session(agent_name="my_agent")
async def entrypoint(ctx: agents.JobContext):
    assistant = YourAssistant()
    session = agents.AgentSession(...)

    await cekura.track_session(ctx, session, assistant)

    await session.start(room=ctx.room, agent=assistant)
```

### Python — Observability (`observe_session`)

```python
@server.rtc_session(agent_name="my_agent")
async def entrypoint(ctx: agents.JobContext):
    assistant = YourAssistant()
    session = agents.AgentSession(...)

    await cekura.observe_session(ctx, session)

    await session.start(room=ctx.room, agent=assistant)
```

### JavaScript/TypeScript — Testing (`trackSession`)

```typescript
import { defineAgent, voice } from '@livekit/agents';
import type { JobContext } from '@livekit/agents';
import { LiveKitTracer } from '@cekura/livekit';

const cekura = new LiveKitTracer({
  apiKey: process.env.CEKURA_API_KEY || '',
  agentId: 123,
});

export default defineAgent({
  entry: async (ctx: JobContext) => {
    const agent = new YourAssistant();
    const session = new voice.AgentSession({ /* stt, llm, tts, vad */ });

    await cekura.trackSession(ctx, session, agent);

    await session.start({ room: ctx.room, agent });
  },
});
```

### JavaScript/TypeScript — Observability (`observeSession`)

```typescript
export default defineAgent({
  entry: async (ctx: JobContext) => {
    const agent = new YourAssistant();
    const session = new voice.AgentSession({ /* stt, llm, tts, vad */ });

    await cekura.observeSession(ctx, session);

    await session.start({ room: ctx.room, agent });
  },
});
```

---

## Mock tools

When `track_session` is wired, mock tools configured on the Cekura agent are auto-injected at runtime — the SDK routes tool calls to Cekura's mock endpoints. No changes to the agent's tool definitions are needed.

Define mocks in Phase 7. The SDK handles routing.

---

## Chat / text-mode tests

The SDK auto-detects when Cekura runs a text-based scenario and patches the session to skip STT/TTS. No code changes required — `track_session` covers both voice and chat tests.

---

## `get_simulation_data`

When Cekura runs a WebRTC scenario, it injects test context into `ctx.job.metadata` (LiveKit dispatch metadata). Use `get_simulation_data` to read it:

```python
await ctx.connect()  # must come first
sim = cekura.get_simulation_data(ctx)
# sim => { "scenario_id": 123, "run_id": 456, "test_profile_data": {...}, "additional_config": {...} }
```

```typescript
await ctx.connect();
const sim = cekura.getSimulationData(ctx);
```

Returns an empty object for phone-based runs.

---

## Environment variables

| Var | Effect |
|-----|--------|
| `CEKURA_API_KEY` | Required. Picked up by the tracer at init. |
| `CEKURA_TRACING_ENABLED=false` | Disables `track_session` tracking entirely. |
| `CEKURA_MOCK_TOOLS_ENABLED=false` | Disables mock-tool injection but keeps tracking. |
| `CEKURA_OBSERVABILITY_ENABLED=false` | Disables `observe_session` tracking entirely. |

---

## Common pitfalls

- **Tracer call after `session.start(...)`** — silent no-op. Always call `track_session` / `observe_session` first.
- **`agent_name` mismatch** — `@server.rtc_session(agent_name="X")` must match `credentials.config.agent_name` on the Cekura agent (when WebRTC Automated or Chat is in scope). Otherwise dispatches go nowhere.
- **Missing `await ctx.connect()` before `get_simulation_data`** — returns an empty dict.
- **API key hardcoded** — use `os.getenv("CEKURA_API_KEY")` so production rotations don't require code changes.
- **Observability without LiveKit credentials** — `observe_session` requires `api_key`/`api_secret`/`url` on the Cekura agent to perform LiveKit egress recording. Without them, transcripts arrive but audio doesn't.

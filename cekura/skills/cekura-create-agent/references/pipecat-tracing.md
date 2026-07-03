# Pipecat Tracing — SDK Reference

Cekura's Pipecat SDK wraps an existing Pipecat `Pipeline` and exports transcripts, tool calls, session metadata, OpenTelemetry traces, session logs, and (in observability mode) dual-channel audio. Python only.

**Docs:** https://docs.cekura.ai/documentation/integrations/pipecat/tracing

---

## Install

```bash
pip install cekura[pipecat]==1.4.1
```

---

## Initialization

```python
from cekura.pipecat import PipecatTracer

tracer = PipecatTracer(
    api_key=os.getenv("CEKURA_API_KEY"),
    agent_id=123,                            # From Cekura dashboard
    host="https://api.cekura.ai",            # Optional
    enabled=True,                            # Optional
    otel_endpoint="https://otel.cekura.ai",  # Optional
    enable_otel_traces=True,                 # Optional
    capture_logs=True,                       # Optional — INFO+ session logs
)
```

**Concurrent calls:** `PipecatTracer` is not thread-safe to share across sessions. When the agent handles multiple concurrent calls in one process, instantiate the tracer **inside** the per-call function, not at module scope.

---

## Method matrix

### Single-step API (default — recommended)

Combines pipeline wrapping, `PipelineTask` creation (with OTel tracing enabled automatically), and handler registration in one call.

| Method | Use case | Captures |
|--------|----------|----------|
| `track_and_create_task(...)` | Cekura simulation runs (testing/UAT) | Transcripts, tool calls, logs, OTel traces. **No audio.** |
| `observe_and_create_task(...)` | Production calls not originating from Cekura | Transcripts, tool calls, logs, OTel traces, **dual-channel audio**. |

```python
# Testing
task = tracer.track_and_create_task(
    pipeline, context, runner_args=runner_args, transport=transport,
    custom_metadata={"bot_version": "1.0"},  # optional
)

# Observability
task = tracer.observe_and_create_task(
    pipeline, context, runner_args=runner_args, transport=transport,
    custom_metadata={"bot_version": "1.0"},
)
```

### Multi-step API (when custom `PipelineTask` kwargs are needed)

```python
# Testing
pipeline = tracer.track_pipeline(pipeline, context, runner_args=runner_args)
task = PipelineTask(
    pipeline,
    enable_tracing=True,
    enable_turn_tracking=True,
    # ...user's custom PipelineTask kwargs...
)
task = tracer.register_task_handlers(task, transport=transport)

# Observability
pipeline = tracer.observe_pipeline(pipeline, context, runner_args=runner_args)
task = PipelineTask(pipeline, enable_tracing=True, enable_turn_tracking=True, ...)
task = tracer.register_task_handlers(task, transport=transport)
```

`enable_tracing=True` and `enable_turn_tracking=True` are required for OTel spans in the multi-step API. The single-step API sets them automatically.

---

## Required pipeline structure

The pipeline must contain `LLMUserAggregator` and `LLMAssistantAggregator` (created via `LLMContextAggregatorPair`). Without them the SDK silently disables observability and logs:

```
Cekura observability disabled: LLMUserAggregator and LLMAssistantAggregator not found in pipeline.
```

Standard layout:

```python
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer

context = LLMContext(tools=tools)
user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
    context,
    user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
)

pipeline = Pipeline([
    transport.input(),
    stt,
    user_aggregator,       # after STT
    llm,
    tts,
    transport.output(),
    assistant_aggregator,  # after transport.output()
])
```

---

## Reference snippets

### Production (observability)

```python
import os
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from cekura.pipecat import PipecatTracer

async def run_bot(transport, runner_args):
    context = LLMContext(tools=tools)
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )
    pipeline = Pipeline([
        transport.input(), stt, user_agg, llm, tts,
        transport.output(), assistant_agg,
    ])

    cekura = PipecatTracer(
        api_key=os.getenv("CEKURA_API_KEY"),
        agent_id=123,
    )

    task = cekura.observe_and_create_task(
        pipeline, context, runner_args=runner_args, transport=transport,
    )

    await PipelineRunner().run(task)
```

### UAT / Testing (simulation)

```python
async def run_bot(transport, runner_args):
    context = LLMContext(tools=tools)
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )
    pipeline = Pipeline([
        transport.input(), stt, user_agg, llm, tts,
        transport.output(), assistant_agg,
    ])

    cekura = PipecatTracer(
        api_key=os.getenv("CEKURA_API_KEY"),
        agent_id=123,
    )

    task = cekura.track_and_create_task(
        pipeline, context, runner_args=runner_args, transport=transport,
    )

    await PipelineRunner().run(task)
```

---

## OpenTelemetry tracing

The SDK exports an OTel trace per call to `https://otel.cekura.ai`:

```
Conversation
├── Turn 1
│   ├── stt (Deepgram, Google, ...)
│   ├── llm (OpenAI, Gemini, ...) — token usage, model, tools
│   └── tts (Cartesia, ElevenLabs, ...) — character count
├── Turn 2
│   ├── stt
│   ├── llm → tool_call
│   ├── llm → tool_result
│   └── tts
└── ...
```

Add custom span attributes for correlation:

```python
# Single-step
task = tracer.observe_and_create_task(
    pipeline, context, runner_args=runner_args, transport=transport,
    additional_span_attributes={"user.id": "user_123", "session.type": "support_call"},
)

# Multi-step
task = PipelineTask(
    pipeline,
    enable_tracing=True,
    enable_turn_tracking=True,
    additional_span_attributes={"user.id": "user_123"},
)
```

Disable OTel export entirely:

```python
tracer = PipecatTracer(api_key="...", agent_id=123, enable_otel_traces=False)
```

---

## Custom metadata

```python
# At init
task = tracer.observe_and_create_task(
    pipeline, context, runner_args=runner_args, transport=transport,
    custom_metadata={"bot_version": "1.0", "environment": "staging"},
)

# Update at runtime — anytime before the session finalizes
tracer.set_custom_metadata({"bot_version": "1.0"})
tracer.get_custom_metadata()
```

---

## Deferred upload (compliance)

For consent-gated flows, buffer everything locally and release only on explicit consent:

```python
pipeline = cekura.observe_pipeline(
    pipeline, context, runner_args=runner_args, defer_upload=True
)

# Grant consent — flushes buffered audio, enables uploads:
await cekura.start_audio_upload()

# Abort mid-call — discards everything:
await cekura.abort()
```

If neither method is called before the session ends, all buffered data is discarded — nothing is sent to Cekura.

Works with the single-step API too:

```python
task = cekura.observe_and_create_task(
    pipeline, context, runner_args=runner_args, transport=transport,
    defer_upload=True,
)
```

---

## Session ID resolution

Order of precedence:

1. Explicit `session_id` argument
2. `runner_args.session_id`
3. Auto-generated

Pass a custom `session_id` when correlating with your own logs.

---

## Environment variables

| Var | Effect |
|-----|--------|
| `CEKURA_API_KEY` | Required. Picked up by the tracer at init. |
| `CEKURA_TRACER_ENABLED=false` | Disables the tracer entirely. |

---

## Common pitfalls

- **Missing aggregators** — pipeline must contain both `LLMUserAggregator` and `LLMAssistantAggregator`. Add `LLMContextAggregatorPair` if missing.
- **`PipelineTask` without `enable_tracing=True`** — OTel spans won't appear in the multi-step API. The single-step API sets this automatically.
- **Shared tracer across concurrent calls** — `PipecatTracer` is not thread-safe to share. Instantiate per-call when handling concurrent sessions.
- **`register_task_handlers` skipped (multi-step)** — required for cleanup-on-disconnect and (in observe mode) audio finalization.
- **Direct API + SDK on the same session** — if you previously called `POST /observability/v1/observe/` from a Pipecat agent, the SDK replaces it. Running both produces duplicate records that don't merge.
- **Audio recorded twice** — `observe_pipeline` runs its own audio frame processor independently of any recording you already do. The two recordings are separate; the SDK's recording is asynchronous and adds no latency.

---

## Mock tools

The Pipecat SDK does **not** auto-inject mock tools the way the LiveKit SDK does. Tool calls flow through Pipecat's normal execution. If you need mocking during tests, route the tool calls in your agent code to Cekura's mock-tool endpoints (see Phase 7's "Wire the mocks into the running agent" section).

---
name: tracing
description: >-
  Wire ANY voice-AI agent codebase (any language, framework, or domain) to emit
  ONE OpenTelemetry trace per call, exported over OTLP to Cekura and linked to
  the call log via trace_id. Use this WHENEVER someone says "add OpenTelemetry to
  my voice agent", "export traces to Cekura", "set up OTLP tracing", "span timing
  for STT/LLM/TTS", "trace_id linkage", "show per-turn timing in Cekura", "emit an
  s2s span", "Gemini Live tracing", "trace a speech-to-speech agent", or asks why
  their spans aren't showing up / aren't linked to the call log. This skill covers
  Phase 3 of Cekura integration (tracing/observability); transcript and metadata
  publishing are sibling skills (observability, custom-transcript-provider,
  metadata).
  Before starting, ask whether the agent is scoped by a Cekura AGENT id or a
  PROJECT id, whether the OTLP exporter is gRPC or HTTP, whether an OpenTelemetry
  provider already exists in the codebase, and whether the agent is a PIPELINE
  (discrete STT→LLM→TTS service calls) or SPEECH-TO-SPEECH (one model in/out, e.g.
  Gemini Live) — the span shape branches on that. Applies to any repo/language/
  domain; the reference S2S agent (Python/FastAPI, Telnyx + Gemini Live) is the
  s2s example.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

<!-- cekura-ack-tag: ack:tracing:4t7k9h -->
> **Cekura skill verification tag:** `ack:tracing:4t7k9h`
> Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="tracing"`, `verification_tag="ack:tracing:4t7k9h"`, and `plugin_version="0.9.0"`. It returns immediately and lets Cekura see which skills are in use.

# Emit one OpenTelemetry trace per call → Cekura

## What this skill does

You wire the agent so that **every phone call produces exactly one
OpenTelemetry trace**, exported over OTLP to Cekura, and **linked to that call's
log via `trace_id`**. The trace's root `conversation` span wraps the whole call;
child spans wrap each real service call (STT, LLM, TTS, tool dispatch) so Cekura
can render per-turn timing, token usage, and tool I/O.

Three things, every time (stated as outcomes — the mechanism is the same in any
OTel SDK, only the API names change):

1. **Initialize one tracer at app startup** — stand up a trace provider with a
   batching span processor/exporter pointing at Cekura's OTLP endpoint, with the
   right auth headers. Once per process, never per call. (In Python this is a
   `TracerProvider` + `BatchSpanProcessor`; the equivalent exists in every SDK.)
2. **Wrap existing service calls in spans** — a root `conversation` span per
   call, child spans for the work the agent already does. You do NOT restructure
   the agent; spans observe it.
3. **Link and flush** — capture the root span's `trace_id`, include it in the
   call-log publish payload, and force-flush the batch processor before posting
   so the spans actually export.

The span *shape* depends on the agent's architecture (pipeline vs
speech-to-speech) — see the branching section below. Everything else is the same.

## Why

Cekura's call log shows *what happened* (transcript, metadata, recording). The
trace shows *how it happened over time*: which model, how many tokens, how long
each turn took, what each tool was called with and returned, where it errored.
Linking the two via `trace_id` lets Cekura overlay timing/usage onto the call
you can already read — so a slow or failed call is debuggable, not just visible.

OTLP is the vendor-neutral wire format, so this works from any language with an
OpenTelemetry SDK. OpenTelemetry ships official SDKs for Python, JS/TS, Go, Java,
.NET, and more — the contract (one trace per call; `conversation` root with
STT/LLM/TTS child spans; export over OTLP to the Cekura endpoint + headers;
surface the `trace_id` for call-log linkage) is **identical across all of them**;
only the SDK calls differ. The contract below is the durable part; the Python
snippets are one labeled illustration in one language.

## Before you start (ask these four)

1. **Agent id or project id?** Cekura accepts either `x-cekura-agent-id` (one
   agent) or `x-cekura-project-id` (project-level scoping, traces from many
   agents land in one project). Find out which the user wants. The reference S2S
   agent uses the **project** header.
2. **gRPC or HTTP exporter?** They have different deps and endpoints (below).
   Default to whichever the user/infra already uses; if greenfield, gRPC is the
   common default, but the reference S2S agent uses **HTTP** (simpler through
   proxies).
3. **Does an OpenTelemetry provider already exist?** If the app (or an APM agent
   like Sentry/Datadog, or a voice framework's own tracing) has already set a
   global trace provider, you **add** the Cekura exporter as another span
   processor — you do **not** replace it.
4. **Pipeline or speech-to-speech?** Detect by inspecting the agent loop: are
   there discrete STT, LLM, and TTS service calls (pipeline), or a single model
   that takes caller audio and emits agent audio (speech-to-speech, e.g. Gemini
   Live, OpenAI Realtime)? This decides which spans you emit.
5. **What stack is this?** The mechanism differs by stack (see "Stack-neutral
   guidance" below): **custom/self-hosted code** (any language) — hand-instrument
   with that language's OTel SDK; **LiveKit Agents** or **Pipecat** — both have
   native OpenTelemetry tracing, so you typically *enable* the framework's tracing
   and point its OTLP exporter at Cekura rather than hand-instrumenting; **managed
   platforms** (Vapi / Retell / ElevenLabs) — usually don't expose per-turn OTel
   traces, so this skill may not apply (call-log + metrics still do).

## The Cekura contract (durable — true for any repo/language/domain)

This is the authoritative spine. Everything here holds regardless of language.

### Dependencies
Install your language's OpenTelemetry SDK plus an OTLP span exporter for the
chosen protocol (gRPC or HTTP). The Python package names are:
- **gRPC:** `opentelemetry-sdk` + `opentelemetry-exporter-otlp-proto-grpc`
- **HTTP:** `opentelemetry-sdk` + `opentelemetry-exporter-otlp-proto-http`

For other languages, use the equivalent OTel SDK + OTLP exporter (e.g. the
`@opentelemetry/*` packages in JS/TS, `go.opentelemetry.io/otel` in Go) — the
wire protocol is the same. On **LiveKit Agents / Pipecat**, the OTel SDK + OTLP
exporter usually ride along with the framework; you supply the Cekura endpoint +
headers as exporter config rather than adding span code.

### Endpoints
- **gRPC:** `otel.cekura.ai:443`
- **HTTP:** `https://otel-http.cekura.ai/v1/traces`

### Required headers
- `x-cekura-api-key` — your Cekura API key (a secret), **and**
- `x-cekura-agent-id` — the Cekura agent id; **or** instead
- `x-cekura-project-id` — for project-level scoping (the reference S2S agent uses this).

The project id is **not** a secret (pass it as a plain env var); the API key is.

### Provider setup
- Create a trace provider with a batching span processor exporting over OTLP, and
  a resource that sets `service.name` (optionally `deployment.environment`). In
  Python that's `TracerProvider` + `BatchSpanProcessor` + `Resource`; every OTel
  SDK has the same three concepts under its own names.
- **Initialize ONCE at app startup**, not per call.
- **If a provider already exists, ADD** the Cekura exporter as an additional span
  processor — do not replace or override the existing global provider (in Python,
  don't call `set_tracer_provider` over it).
- **On LiveKit Agents / Pipecat**, you generally don't build the provider by
  hand: enable the framework's built-in OpenTelemetry tracing and configure its
  OTLP exporter with Cekura's endpoint + headers. The provider/processor wiring
  is the framework's; your job is the endpoint, headers, and `service.name`.

### Recognized span names + attributes
Cekura renders specialized UI for these exact span names. Custom names still
ingest but get generic rendering — prefer the standard names.

| Span name | Key attributes |
|---|---|
| `conversation` | (root span; wrap the whole call) |
| `turn` | (per caller-input→agent-response cycle; groups the spans below — `turn.index`) |
| `stt` | `stt.provider`, `stt.transcript` |
| `llm` | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` |
| `tts` | `tts.provider`, `tts.characters` |
| `tool_call` | `function.name`, `function.input`, `function.output` |

> **Group per-turn spans under a `turn` span — don't emit them flat.** A multi-turn
> call should read `conversation → turn → {stt, llm, tts, tool_call}`, one `turn`
> subtree per caller-input→agent-response cycle, NOT a flat list of stt/llm/tts
> siblings directly under `conversation`. Flat spans are readable for a single
> exchange but become an unnavigable stripe over a long call — you can't tell which
> `llm` went with which `stt`/`tts`. Open the `turn` span when the caller's turn
> begins (first partial) — and once for the opening greeting — parent that turn's
> stt/llm/tts/tool_call under it, and close it when the turn's response finishes
> (superseding on barge-in). `turn` is a custom name (generic rendering) but the
> grouping is worth it; the children keep their recognized names. (The flat
> per-chunk loop in the pipeline reference below is illustrative — wrap it in a
> `turn` in real code.)

### Linking + flushing
- Extract the root span's trace id and format it as the 32-hex-char string (in
  Python, `format_trace_id()`; use your SDK's equivalent — every OTel SDK exposes
  the span context's trace id).
- Include `trace_id` in the call payload — **top-level, on BOTH sinks**: the
  observe API payload (`POST …/observability/v1/observe/`) AND the eval
  webhook's `calls[]` object. It's easy to wire only observe and leave eval runs
  with no trace link — add it to both (omit-when-empty on each). The payload
  itself (transcript, metadata) is owned by the sibling skills
  **`observability`** / **`custom-transcript-provider`** and
  **`metadata`** — this skill only adds the `trace_id` field; cross-reference,
  don't re-explain.
- **Force-flush the batch processor before** posting the call log, so its
  buffered spans actually export (in Python, `provider.force_flush()`; the same
  flush call exists in every SDK). On a framework that owns the provider, use its
  flush/shutdown hook.

### Constraints
- **DO NOT** restructure existing agent/call logic. Spans **wrap** existing
  service calls.
- **DO NOT** add spans for non-service-call internal logic or data transforms
  (parsing, formatting, in-memory bookkeeping). Trace I/O, not arithmetic.
- **DO NOT** replace an existing OTel provider — add to it.
- Read all credentials from env vars (`CEKURA_API_KEY`,
  `CEKURA_AGENT_ID`/`CEKURA_PROJECT_ID`). Never hardcode.

Docs: https://docs.cekura.ai/documentation/guides/tracing

## Stack-neutral guidance (which path applies to you)

The contract above never changes. *How* you satisfy it depends on the stack:

- **Custom / self-hosted code (any language — Python, Node/TS, Go, Java, .NET, …):**
  hand-instrument with that language's OpenTelemetry SDK. Stand up the provider +
  OTLP exporter once, open the `conversation` root span at the call boundary, and
  wrap STT/LLM/TTS/tool calls (or `s2s`/`llm` for speech-to-speech) in child
  spans. The Python reference below is one instance of this path; translate the
  SDK calls to your language — the span names, attributes, endpoint, and headers
  are identical.
- **LiveKit Agents:** has built-in/native OpenTelemetry tracing. **Enable the
  framework's tracing** and point its OTLP exporter at Cekura's endpoint +
  headers (and set `service.name`) rather than hand-instrumenting spans. The
  framework emits per-turn spans; you mainly ensure the export target is Cekura
  and that the `trace_id` reaches your call-log publish step.
- **Pipecat:** likewise has native OpenTelemetry tracing for its pipeline. Turn
  it on and configure the OTLP exporter for Cekura. Add hand-rolled spans only
  where the framework doesn't already cover something you need.
- **Managed platforms (Vapi / Retell / ElevenLabs):** these typically do **not**
  expose per-turn OpenTelemetry traces you can export, so this tracing skill may
  not apply. Their call-log + metrics integration still works — use the
  publishing and metrics skills instead.

On framework paths, don't fabricate exact configuration API names — enable the
documented tracing feature and supply the Cekura OTLP endpoint, headers, and
`service.name`; the recognized span names/attributes below are still the target.

## Pipeline vs speech-to-speech: which spans to emit

Same root span, same tool spans, same `trace_id`/flush mechanics. The middle —
the per-turn speech/model spans — branches.

### Pipeline agent (discrete STT → LLM → TTS)
The agent calls a transcription service, then a chat/LLM service, then a
synthesis service. Emit the standard recognized spans, one per service call, all
under the root `conversation` span:

- `stt` with `stt.provider`, `stt.transcript`
- `llm` with `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`,
  `gen_ai.usage.output_tokens`
- `tts` with `tts.provider`, `tts.characters`
- `tool_call` (per tool) with `function.name`, `function.input`, `function.output`

Each span's timing maps to a real service latency. This is the canonical case;
see the canonical pipeline example in the reference section.

### Speech-to-speech agent (one model in → one model out)
A single model (Gemini Live, OpenAI Realtime, etc.) consumes the caller's audio
and emits the agent's audio over one bidirectional connection. There are **no
discrete STT or TTS service calls to time**. Emitting fake `stt`/`tts` spans
**misrepresents the architecture** — those spans would have invented boundaries
and fabricated latencies.

Instead, **per turn**, emit:

- **one `s2s` span** for the unified speech exchange: the caller's input
  transcription attaches as input, the agent's output audio attaches as output,
  and it closes when the turn completes (or on barge-in). `s2s` is a *custom*
  name (generic UI), but it's an honest single-model span instead of a misleading
  fake pipeline.
- the unchanged **`llm` span** for the model's text output + token usage
  (`gen_ai.*`).
- `tool_call` spans for any backend tools the model invokes.

**Still store the caller transcript under `stt.transcript`** on the `s2s` span,
even though there's no `stt` span — that's the Cekura-recognized key, so the
words surface in the UI regardless. (Optionally also under an `s2s.*` alias.)

> Because the model interleaves transcription, text, and audio and can deliver
> input transcription several seconds late, these per-turn child-span timings are
> **phase markers, not exact service latencies**. Only the call itself and
> backend `tool_call` dispatches map to true wall-clock work. Note this in the
> code so nobody mistakes the timings for real latencies.

This is the reference S2S agent pattern (in the reference repo). See the s2s excerpt below.

## Adapt to your stack (checklist)

This checklist is written for the **hand-instrumented** path (any language). On
**LiveKit Agents / Pipecat**, steps 1–4 and 6–7 collapse into "enable the
framework's OTel tracing and point its OTLP exporter at Cekura's endpoint +
headers with a `service.name`"; you still own step 2 (the no-op-unless-configured
guard), step 5 (`trace_id` linkage), and step 8 (`trace_id` in the payload).

1. **Add the OTel SDK + OTLP exporter** for your language and chosen protocol
   (gRPC vs HTTP).
2. **Add config/env vars:** `CEKURA_API_KEY`, `CEKURA_AGENT_ID` **or**
   `CEKURA_PROJECT_ID`, the OTLP endpoint, and a `service.name`. Make tracing a
   **no-op unless the key AND the agent/project id are both set** — so dev/CI and
   un-opted-in environments are unaffected.
3. **Initialize the provider once** at startup (in your app's bootstrap/lifespan
   hook, not per request). If a provider already exists, add a span processor
   instead of replacing it.
4. **Find the call boundary** (where one call begins and ends) and wrap it in the
   root `conversation` span. Make it the current/active span so child spans
   (including those started in spawned tasks/threads/coroutines that propagate the
   context) parent under it.
5. **Capture `trace_id`** from the root span and stash it where your call-log
   publish step can read it (e.g. on the call's registry/session entry).
6. **Branch on architecture** and wrap the per-turn work: pipeline → `stt`/`llm`/
   `tts`; speech-to-speech → `s2s` + `llm`.
7. **Wrap every tool dispatch** in a `tool_call` span (`function.name`,
   `function.input`, `function.output`; set span status to error on tool failure).
   These attributes serialize the tool's raw args/results, which can hold backend
   data never spoken on the call (full records, tokens, payment refs) — **redact
   secrets / sensitive non-dialogue fields** before setting them (same boundary as
   the transcript's Function Call entries in `observability`).
8. **Force-flush before posting** the call log; add `trace_id` to that payload
   (owned by the publishing skills).
9. **Flush + shut down** the provider at app shutdown so buffered spans export.
10. **Verify** in Cekura: the call log opens to a trace with one `conversation`
    span and the expected children, and `trace_id` matches.

## Reference implementation

> The snippets below are **one illustration in one language (Python)**. They show
> the contract concretely, not the only way to satisfy it — translate the SDK
> calls to your language, or (on LiveKit Agents / Pipecat) enable the framework's
> tracing and point its exporter at the same endpoint + headers. The span names,
> attributes, endpoints, and headers are what matter and are identical everywhere.

### Canonical pipeline example (Python, gRPC) — the standard STT→LLM→TTS case

```python
import os
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import format_trace_id

exporter = OTLPSpanExporter(
    endpoint='otel.cekura.ai:443',
    headers=(('x-cekura-api-key', os.getenv('CEKURA_API_KEY')),
             ('x-cekura-agent-id', os.getenv('CEKURA_AGENT_ID'))),
)
provider = TracerProvider(resource=Resource.create({'service.name': 'my-voice-agent'}))
provider.add_span_processor(BatchSpanProcessor(exporter))
tracer = provider.get_tracer('my-voice-agent')

def run_call(call_id, user_audio_stream):
    with tracer.start_as_current_span('conversation') as root_span:
        trace_id = format_trace_id(root_span.get_span_context().trace_id)
        for audio_chunk in user_audio_stream:
            with tracer.start_as_current_span('stt') as span:
                text = stt.transcribe(audio_chunk)
                span.set_attribute('stt.provider', 'deepgram')
                span.set_attribute('stt.transcript', text)
            with tracer.start_as_current_span('llm') as span:
                response = llm.chat(transcript)
                span.set_attribute('gen_ai.request.model', 'gpt-4o')
                span.set_attribute('gen_ai.usage.input_tokens', response.usage.prompt_tokens)
                span.set_attribute('gen_ai.usage.output_tokens', response.usage.completion_tokens)
            with tracer.start_as_current_span('tts') as span:
                audio = tts.synthesize(response.text)
                span.set_attribute('tts.provider', 'elevenlabs')
    provider.force_flush()
    # POST call log to https://api.cekura.ai/observability/v1/observe/ with trace_id
```

### Speech-to-speech (S2S) variant (Python/FastAPI, HTTP exporter) — the speech-to-speech case

Real excerpts from `modules/tracing.py` and `main.py`. Note: **HTTP** exporter,
**`x-cekura-project-id`** header, and tracing is a **no-op unless api key AND
project id are both set**.

Provider init (`modules/tracing.py`) — note the no-op guard and the
project-scoped header:

```python
def init_tracing(*, endpoint, api_key, project_id,
                 service_name="<your-service-name>", environment="prod"):
    global _provider, _tracer, _configured
    if _configured:
        return
    if not (api_key and project_id and endpoint):
        logger.info("OpenTelemetry tracing disabled (api_key/project_id/endpoint not all set).")
        return  # ← no-op: missing creds never affects call handling

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    headers = {"x-cekura-api-key": api_key, "x-cekura-project-id": str(project_id)}
    resource = Resource.create({"service.name": service_name,
                                "deployment.environment": environment})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)  # full /v1/traces URL
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _provider, _tracer, _configured = provider, trace.get_tracer("<your-service-name>"), True
```

Root span + trace_id capture (`main.py`) — entered as current span so the
spawned audio/agent/silence tasks parent their spans under it; `trace_id` is
stamped onto the call registry so the hangup publish can link the log:

```python
with tracing.conversation_span("conversation", attributes={
        "session_id": agent_cfg.get("session_id"),
        "entity_id": agent_cfg.get("entity_id"),
        "caller_phone_number": agent_cfg.get("caller_number") or "",
}) as conv_span:
    if conv_span is not None:
        agent_cfg["trace_id"] = tracing.span_trace_id(conv_span)
    done, pending = await asyncio.wait([... agent/audio/silence tasks ...])
```

The per-turn `s2s` span (`TurnTracer` in `modules/tracing.py`) — one span for the
whole speech exchange; caller transcript stored under the recognized
`stt.transcript` key plus an `s2s.*` alias; the model's text/usage stays on a
separate `llm` span:

```python
# On the caller's input transcription → input side of the s2s span:
self._ensure_s2s()                 # opens one "s2s" child span per turn
self._caller_text.append(text)

# On agent output audio chunks → output side of the same s2s span:
self._audio_chunks += num_chunks

# At turnComplete, close the s2s span and surface the transcript:
caller_text = "".join(self._caller_text)[:_MAX_ATTR_CHARS]
self._s2s_span.set_attribute("s2s.caller_transcript", caller_text)
self._s2s_span.set_attribute("stt.transcript", caller_text)  # ← Cekura-recognized key
self._s2s_span.end()
# Model text + token usage live on a separate "llm" span (gen_ai.* attributes).
```

Tool spans (`modules/agent.py` / `main.py`) — every backend tool
dispatch is wrapped; the real tool name rides on `function.name` (the span itself
is named `tool_call` for the specialized UI):

```python
with tracing.tool_span(fc["name"], fc.get("args")) as _tspan:   # span name == "tool_call"
    result = await dispatch_tool(...)
    tracing.record_tool_result(_tspan, result)                  # sets function.output; ERROR on failure
```

Flush + shutdown at app exit (`main.py` lifespan) — flush so buffered spans
export, run off the event loop so call teardown never blocks on network I/O:

```python
await asyncio.to_thread(tracing.flush_tracing)     # provider.force_flush()
await asyncio.to_thread(tracing.shutdown_tracing)  # provider.shutdown()
```

And `trace_id` is added to the observe payload (the publishing skills own the
rest of that payload):

```python
"trace_id": entry.get("trace_id", ""),  # empty string when tracing disabled
```

## Verify offline (no live call)

- **Assert the span tree with an in-memory exporter.** Swap the OTLP exporter for
  your SDK's in-memory/test exporter (JS `InMemorySpanExporter`, Python
  `InMemorySpanExporter`), emit `conversation → turn → {stt, llm, tts, tool_call}`
  through your real span helpers, and assert the finished spans' `parentSpanId`
  chain — `turn.parent === conversation`, each child's parent === the turn. This
  proves the nesting (and the explicit-parenting) without a call or the network.
- **Smoke the export + linkage.** With real creds, init tracing, emit one trace,
  `force_flush()`, and confirm the OTLP POST returns no error (enable the SDK's
  diagnostic logger at ERROR to surface a bad endpoint/header). Then POST a
  synthetic observe call carrying that `trace_id` and read the call log back to
  confirm `trace_id` matches. (The rendered span tree in the dashboard still needs
  a human eyeball — the API won't show it.)

## Gotchas

- **Callback/event-driven agents: parent child spans EXPLICITLY, don't rely on
  the active-span context.** The active-span context (Python `start_as_current_span`,
  JS async-hooks context manager) only propagates when the child span opens on the
  same call stack / awaited chain as the root. In an agent whose STT/LLM/TTS work
  fires from **independent callbacks or event handlers** (a websocket `message`
  handler, an STT `onFinal` callback, a TTS queue `.then`), there is no shared
  stack, so children silently attach to no parent (or the wrong one) and the trace
  fragments. Capture the root span and parent each child on it **explicitly**
  (e.g. JS: `tracer.startSpan(name, opts, trace.setSpan(context.active(), rootSpan))`;
  Python: pass `context=trace.set_span_in_context(root_span)`). This also lets you
  use a plain (non-context-manager) provider — fine for Node's
  `BasicTracerProvider` where span processors are passed in the constructor
  (`new BasicTracerProvider({ resource, spanProcessors: [...] })`; `addSpanProcessor`
  was removed in the 2.x SDK).
- **Force-flush before you POST the call log.** The batch span processor
  buffers; without an explicit flush (`force_flush()` in Python, the equivalent in
  any SDK or framework) the spans may export *after* the call log, or not before
  the process exits. Flush, then post.
- **No-op unless creds are set.** Guard init so tracing is completely disabled
  when the api key or agent/project id is missing, and make every span helper
  degrade to a no-op. Missing tracing config must never break call handling.
- **Don't fake `stt`/`tts` on a speech-to-speech agent.** One model in/out has no
  discrete transcription/synthesis step; invented `stt`/`tts` spans lie about the
  architecture and fabricate latencies. Emit one `s2s` span instead, and still
  store the caller transcript under `stt.transcript`.
- **Don't replace an existing OTel provider.** If one is already set (your app, an
  APM agent, or a voice framework's own tracing), add the Cekura exporter as an
  additional batch span processor. Overriding the global provider (e.g.
  `set_tracer_provider` in Python) can silently break other instrumentation.
- **`trace_id` must come from the ROOT span.** All child spans share the same
  trace id, but capture it from the `conversation` span you opened for the call,
  and link that one.
- **Per-turn s2s timings are phase markers, not latencies.** Document this so
  dashboards don't treat interleaved/late signals as real service durations.

## Common mistakes to avoid

- Initializing the provider **per call** instead of once at startup — leaks
  exporters and floods the collector.
- **Hardcoding** the api key / agent id / endpoint instead of reading env vars.
- Using a **custom span name** where a recognized one fits (`my_llm_call` instead
  of `llm`) — you lose Cekura's specialized UI for no reason.
- Adding spans around **internal data transforms** (parsing JSON, formatting a
  string) — trace service calls, not arithmetic.
- **Restructuring** the agent loop to fit the spans. Spans wrap what's already
  there; if you're moving logic to make tracing "cleaner," stop.
- Forgetting to put `trace_id` in the observe payload — the trace exports but
  never links to the call log, so it's orphaned.
- Naming the tool span after the tool (`lookup_account`) instead of `tool_call`
  with the name in `function.name`.
- Letting a tracing exception propagate into call handling — wrap helpers
  defensively so a tracing failure is silent, never call-breaking.

## Next steps

Once traces land and link, use the Cekura MCP tools to build on the
observability data — e.g. `mcp__cekura__metrics_create` and
`mcp__cekura__metrics_list` for per-call quality metrics, and
`mcp__cekura__alerts_create` / `mcp__cekura__alerts_list` for alerting on
regressions. Note: `mcp__cekura__` is a stand-in prefix; your install's Cekura
MCP server prefix differs, so discover each tool by its base name (e.g.
`metrics_create`) via tool-search. For grading against the agent's own prompt, author evaluators with
`cekura-eval-design`; for the call-log payload itself, see
`observability` / `custom-transcript-provider` and `metadata`. Full tracing reference:
https://docs.cekura.ai/documentation/guides/tracing

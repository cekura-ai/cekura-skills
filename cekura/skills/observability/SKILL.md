---
name: observability
description: >-
  Wire ANY voice-AI agent codebase (any language, any framework, any business
  domain) to publish its end-of-call conversation transcript into Cekura's
  OBSERVE sink — the production observability / call-logs path. Use this WHENEVER
  you need to "send call logs to Cekura", "post production transcripts", "wire up
  observability", "publish at hangup to the observe API", "set up the observe
  sink", "see calls in the Cekura dashboard", or debug why production calls aren't
  showing up in the observe log. The durable contract is language- and
  domain-agnostic: ONE plain HTTP POST of a flat, single-call JSON body to the
  observe API, fired once per call at hangup, isolated so it can never touch call
  teardown. This sink is fully usable on its own — wire it alone if observability
  is all you need. The eval/scenarios ingestion path is the SIBLING skill
  custom-transcript-provider (wire it too only if you also want evals);
  sinks-publisher is a lightweight chooser if you're unsure which sink(s) you
  need. The reference S2S voice agent (Python/FastAPI/Telnyx/Gemini Live) is named ONLY
  as the reference example — adapt the contract to your own stack, don't copy it.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

<!-- cekura-ack-tag: ack:observability:6r9p3d -->
> **Cekura skill verification tag:** `ack:observability:6r9p3d`
> Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="observability"`, `verification_tag="ack:observability:6r9p3d"`, and `plugin_version="0.9.0"`. It returns immediately and lets Cekura see which skills are in use.

# Publish call transcripts to Cekura's OBSERVE sink at hangup

## What this skill does

At the end of every call, your agent publishes the conversation transcript to
Cekura's **observe API** so the call appears in the production call logs and can
be sliced, filtered, and scored in the dashboard. This is **one of Cekura's two
ingestion sinks**; this skill owns the **observe (observability) sink only**:

- **The observe API** — `POST https://api.cekura.ai/observability/v1/observe/`.
  A flat, single-call JSON body. This is your production observability path.

**This sink stands alone.** If observability is all you need, wire only this skill
— it has no dependency on the other sink or on any coordinator. The sibling
**eval/scenarios** path (the batched custom-provider transcript webhook, used for
replaying calls against scenarios/metrics) is a separate skill,
**`custom-transcript-provider`**, which you wire *only if you also want evals*.
If you end up running both and want to route which fires per environment, that's
a per-environment split you set up (see **Running both sinks: the split** below);
**`ci-cd`** owns injecting those env vars per deployment. The lightweight
**`sinks-publisher`** skill is just a chooser that helps you decide which
sink(s) you need.

## Why

Cekura needs the transcript in a specific shape, with a stable correlation key,
and it must arrive without ever degrading the live call. Getting the role names,
timestamp units, or correlation id wrong means the call silently doesn't ingest,
or ingests unparseable. And because publishing happens at the most fragile moment
of a call (hangup), a bug here can hang cleanup or crash call teardown if you
don't isolate failures.

## The Cekura contract (durable — true for any repo/language/domain)

These facts hold regardless of your language, framework, or business domain. **The
observe sink is nothing more than a plain HTTP POST of JSON** — there is no SDK,
no Python dependency, no special client. Anything that can make an HTTPS request
(any language's HTTP library, or even a `curl` from a shell hook) can satisfy this
contract. Everything below describes the JSON body and the rules for filling it;
the transport is just `POST` + `Content-Type: application/json` with your
`X-CEKURA-API-KEY`.

### The observe body shape

**Flat, single call, no `calls: []` wrapper.** Top-level fields:

- `agent` (integer) — your Cekura agent id.
- `call_id` (string) — your **own session id**, NOT the telephony provider's
  call id. This is the universal correlation key that must pivot across Cekura ↔
  your app ↔ any downstream webhook. Cekura *requires* this field; omitting it
  returns `400 {"call_id":["This field is required."]}`.
- `transcript_type: "cekura"` — tells Cekura to parse your role/timing format.
- `transcript_json` — array of entries (see role mapping below).
- `customer_number`, `call_ended_reason` — top-level, not in metadata.
- `metadata` — free-form dict for dashboard filtering.
- `dynamic_variables` — runtime injection values (e.g. caller phone).
- `timestamp` — **ISO 8601**, the call start time. Omit if unknown.
- `voice_recording_url`, `trace_id` — optional; **omit the key entirely when
  empty**, never ship a blank string.

The observe response returns the created call-log's integer `id`; use it to
back-fill a deep link if you want, but treat any callback as non-load-bearing.

### Role mapping (get these exact strings right)

| Your transcript line | Observe `role` |
|---|---|
| agent/bot utterance | `Main Agent` |
| caller/user utterance | `Testing Agent` |
| tool invocation | `Function Call` |
| tool result | `Function Call Result` |

Observe roles are **Title Case**. "Testing Agent" is Cekura's name for the
**caller** side — counterintuitive but correct. Tool entries carry a `data`
object with a correlating `id` plus `name` and `arguments`/`result` so Cekura can
pair an invocation with its result.

> The eval webhook (`custom-transcript-provider`) uses **lowercase** roles
> (`bot`/`user`/`function_call`/`function_call_result`) — a different string set.
> If you fire both sinks, build each shape separately; don't reuse one payload.

> Correct role mapping assumes you can reliably tell the caller's speech from the
> agent's. If your transcription mixes speakers, reliable caller-vs-agent speaker
> separation (dual-channel recording) is an option, but it's telephony-provider
> dependent and there's no turnkey path — dive deeper into the provider's
> recording capabilities if you need it.

### Timestamp units — seconds-from-call-start

Per-line `start_time`/`end_time` are **seconds from call start** (float),
computed by subtracting the call-start time from each line's timestamp. Omit when
a line has no parseable timestamp. Only the CALL-LEVEL time is absolute: the
top-level `timestamp` is **ISO 8601**.

> **Verified against the backend.** The consumer treats `start_time` as *seconds*
> (it multiplies by 1000 to get ms — `test_framework/transcribe.py`). Shipping
> millisecond-epoch per-line times produces astronomically wrong call durations.

### Ordering

Sort transcript lines by timestamp at build time, with a **stable** sort so a
tool call and its result that share a timestamp keep invocation-before-result
order. (Async transcription pipelines frequently emit caller utterances *after*
the agent reply that logically follows them — sort to fix the dashboard order.)

### Independent failure (non-negotiable)

This POST **must never propagate into the call teardown path**, and if you also
fire the eval webhook, the two must fail **independently** — an error on one must
never prevent or mask the other. Wrap the POST so a non-2xx or thrown error is
logged and swallowed (a `try`/`catch`, an error-return check, a `recover`/rescue,
a promise `.catch()`). A failed publish is a WARNING, never a surfaced error.

### Overrides

The observe payload carries the agent-id as an explicit field, so a single
deployment can attribute published transcripts to a chosen Cekura agent rather
than a hardcoded default.

### Where to hook the end-of-call publish

The trigger is always "the call has definitively ended" — but *where* that signal
lives depends entirely on your stack. Hook the publish into whichever matches:

- **Custom / self-hosted code (any language)** — your own call-ended/hangup
  handler, a WebSocket/RTC close event, a session-teardown callback, or your
  telephony provider's hangup webhook (Telnyx `call.hangup`, Twilio status
  callback `completed`, etc.). Publish from the one signal you trust as final.
- **LiveKit Agents** — its session shutdown / close callback.
- **Pipecat** — its pipeline-ended / client-disconnected event.
- **Managed platforms (Vapi / Retell / ElevenLabs)** — you usually **don't wire
  agent code at all**. Forward the platform's own end-of-call/report webhook to
  Cekura, or use Cekura's provider integration to ingest calls directly. Reach
  for a hand-rolled POST only when the platform can't deliver the transcript.

Whatever the hook, the action is the same: build the transcript once and fire the
POST. Publish from ONE definitive end-of-call signal, once.

### This sink runs standalone (default)

**This skill needs nothing from the eval webhook and nothing from any
coordinator.** When the `CEKURA_*` config is present, publish to the observe sink
on every call; when it's absent, the bot runs unchanged (off-by-default). If
observability is all you want, you're done — **there is no routing to
configure.** The split below only becomes relevant once you *also* wire the eval
webhook (`custom-transcript-provider`) and want to run "both" with each
environment routed to the right sink.

### Running both sinks: the split (the "both" setup)

Skip this section if you only run the observe sink. It applies once you ALSO wire
the eval webhook (`custom-transcript-provider`). The recommended "both" setup
is a **per-environment split**: the **prod** deployment publishes to THIS observe
sink, while the **non-prod / sandbox** deployment publishes to the eval webhook
instead, so sandbox eval runs never pollute prod observability. You implement this
sink's side of that decision here.

Two env vars express the split: `CEKURA_ENVIRONMENT` (per-environment selector)
and `CEKURA_ROUTE_TO` (explicit override — when set, it wins).

**The recommended split** — leave `CEKURA_ROUTE_TO` unset and let
`CEKURA_ENVIRONMENT` decide: `prod` → observe sink only; non-prod / `sandbox` →
eval webhook only. Sandbox eval runs never pollute prod observability. This is
what you want in almost all cases.

<details>
<summary><b>Rare — explicit <code>CEKURA_ROUTE_TO</code> overrides (most deployments never set this)</b></summary>

Setting `CEKURA_ROUTE_TO` overrides the environment split:

- `both` — fire BOTH sinks on every call, regardless of environment. **Rare:** it
  doubles ingest and mixes sandbox traffic into prod observability; only for a
  single deployment that must feed both pipelines.
- `observability` — force this observe sink only (same effect as standalone).
- `evals` — silence this sink.

Unknown values fall back to the `CEKURA_ENVIRONMENT` split.
</details>

So **the observe sink fires when** `CEKURA_ROUTE_TO` is `observability` or `both`,
OR `CEKURA_ROUTE_TO` is unset and `CEKURA_ENVIRONMENT=prod`. Implement this
decision here **only if you run both sinks**; **how those env vars get set per
deployment** is `ci-cd`'s job. The sibling `custom-transcript-provider`
documents the same split from its side.

## Adapt to your stack (checklist)

Answer these in your own repo — the contract above is fixed; the wiring is yours.

1. **Where does a call definitively end?** Find the single, reliable end-of-call
   signal for your stack (see **Where to hook the end-of-call publish**). Publish
   from there, once.
2. **How do you fire post-hangup work without blocking teardown?** Detach the
   publish so call cleanup returns immediately — whatever "fire-and-forget" means
   in your runtime (a background task/coroutine, a worker-pool job, a goroutine, a
   queued message). Make sure the detached work can't be dropped before it
   finishes (keep a strong reference so it isn't garbage-collected).
3. **What is your durable session id?** Pick the id that already pivots across
   your systems and use it as `call_id`. Do NOT use the telephony provider's id.
4. **Where does your transcript live at hangup?** You need utterances + tool
   calls + tool results with per-line timestamps. If your transcript store is
   keyed by the telephony id, make sure it's still readable at hangup (snapshot
   it before any registry entry is torn down).
5. **Do you have a recording URL, and can it wait?** First **ask whether the user
   wants call audio in Cekura at all** — it's opt-in, and enables dashboard
   playback + audio-based metrics (interruptions, latency, talk-over). If they do
   and no recording exists yet, basic recording is usually a small provider-side
   change (Twilio `record="record-from-answer"` + a recording status callback, or
   Telnyx call recording) — you don't build it in the media path. Then pass the
   URL as `voice_recording_url`. If the provider delivers it asynchronously,
   decide a bounded wait (e.g. 30s) and publish without it on timeout — never
   block the publish indefinitely. **Audio is a privacy/compliance opt-in** —
   gate it behind its own flag (e.g. `RECORD_CALLS`), default OFF, and never
   record or send audio unless the user explicitly enabled it. If they don't want
   recordings, omit `voice_recording_url` entirely (it's omit-when-empty).
6. **Are you also running the eval webhook?** If NO, there's nothing to route —
   just publish this sink whenever enabled. If YES, the recommended "both" setup
   splits by environment (prod → this observe sink, non-prod → eval webhook):
   implement that decision here (see **Running both sinks: the split**); `ci-cd`
   sets those env vars.
7. **One transform function, pure and tested.** Write the observe builder as a
   pure function (no I/O) so you can assert the exact wire shape at the HTTP
   boundary.

## Reference implementation (example voice agent — Python/FastAPI/Telnyx/Gemini; adapt, don't copy)

**This is ONE illustration in ONE language — Python/FastAPI with Telnyx telephony
and a Gemini Live model — not the spec.** The steps and contract above stand on
their own; read this block only to see *how* one stack satisfies them, then
translate the JSON POST into yours. These are real paths and verbatim excerpts;
the Telnyx `call.hangup` trigger is just this repo's instance of the end-of-call
hook.

**Trigger point** — `main.py`, the Telnyx `call.hangup` webhook handler. It reads
the real hangup cause and schedules the publish *before* emitting the completion
log:

```python
def _on_telnyx_hangup(payload: dict) -> None:
    call_control_id = payload.get("call_control_id", "")
    if not call_control_id:
        return
    _greeted_calls.discard(call_control_id)
    hangup_reason = payload.get("hangup_cause") or _DEFAULT_HANGUP_REASON
    _schedule_cekura_publish(call_control_id, hangup_reason)
    emit_call_completed(_call_registry, call_control_id, hangup_reason=hangup_reason)
```

**Detached, never-blocking dispatch** — `main.py`, `_schedule_cekura_publish`
builds the summary and fires the publish without awaiting it:

```python
    _fire_and_forget(
        cekura_publisher.schedule_publish(
            call_control_id,
            summary=summary,
            transcript_lines=transcript_lines,
            timeout_sec=get_settings().cekura_publish_timeout_sec,
            on_published=lambda cekura_id: slack_notifier.post_cekura_link_followup(slack_thread_ts, cekura_id),
        )
    )
```

**Observe POST in its own try** — `modules/cekura_publisher.py`, `schedule_publish`.
The observe sink is wrapped so its failure is a swallowed WARNING and (if the
eval webhook also fires) the two are independent:

```python
            try:
                await self._post_observe(build_payload(...))
            except Exception as exc:
                logger.warning("Cekura observe publish failed for %s: %s", call_control_id, exc)
```

**Observe payload builder** — `modules/cekura_publisher.py`, `build_payload`.
`call_id` is the session id; `timestamp` is ISO 8601; `voice_recording_url`/
`trace_id` are omitted when empty:

```python
    payload: dict[str, Any] = {
        "agent": agent_id,
        "call_id": summary.get("session_id", ""),
        "transcript_type": "cekura",
        "transcript_json": _to_cekura_transcript(transcript_lines),
        "customer_number": summary.get("caller_phone_number", ""),
        "call_ended_reason": summary.get("hangup_reason", ""),
        ...
    }
    started_at = summary.get("started_at")
    if started_at:
        payload["timestamp"] = datetime.fromtimestamp(started_at, tz=timezone.utc).isoformat()
    if recording_url:
        payload["voice_recording_url"] = recording_url
    if summary.get("trace_id"):
        payload["trace_id"] = summary["trace_id"]
```

**Observe transcript transform** — `_to_cekura_transcript`. Title-case roles,
seconds-from-start timing, stable sort:

```python
        if kind == "utterance":
            speaker = line.get("speaker", "")
            role = "Main Agent" if speaker == "agent" else "Testing Agent"
            t = rel(line.get("ts", ""))
            out.append({"role": role, "content": line.get("text", ""),
                        "start_time": t, "end_time": t})
```

**Recording wait** — Telnyx delivers `call.recording.saved` asynchronously;
`schedule_publish` waits up to `timeout_sec` (default 30s) and publishes without
the URL on timeout. The Telnyx signed URL outlives Cekura's 5-minute ingest
deadline, so no re-upload is needed.

**Tests** — `tests/test_cekura_publisher.py` asserts at the HTTP boundary with
`respx` (the exact wire shape), not internal call counts.

## Verify offline (no live phone call)

You don't need to place a real call to prove the publish works — exercise the
builder + POST directly:

1. Build the observe payload with your real builder for a synthetic call
   (a couple of utterances + a tool call/result), then
   `POST {base}/observability/v1/observe/` with `X-CEKURA-API-KEY`. Expect
   **201** (or 409 = already exists). Grab the returned call-log `id`.
2. Read it back — `call_logs_retrieve(id)` (MCP) or a GET — and assert the wire
   contract landed: roles (`Main Agent`/`Testing Agent`/`Function Call[ Result]`),
   **timing looks like seconds** (a 6s call reads `00:06`, not a huge number),
   the tool call/result are paired, and `call_id` = your session id.
3. Unit-test the builder as a **pure function** at the wire-shape boundary
   (roles, seconds timestamps, recording present-only-when-set) so regressions
   fail fast without any network.

**Hygiene:** verify against a **sandbox agent**, tag synthetic calls with a clear
`metadata.source` (e.g. `"observe smoke test"`), and **delete them afterward** —
never leave test rows polluting a customer's production observe log.

## Gotchas

- **`call_id` is required by the observe endpoint.** A missing/empty `call_id`
  returns a 400.
- **Per-line timestamps are seconds-from-start** (float), NOT ms-epoch. The
  consumer multiplies `start_time` by 1000 to get ms, so shipping ms-epoch
  ingests garbage timing. Only the call-level `timestamp` is absolute (ISO 8601).
- **Role strings are case-sensitive.** `Main Agent`/`Testing Agent` (Title Case)
  for observe. "Testing Agent" is Cekura's name for the caller side.
- **Recording arrives late.** Don't block forever. Bound the wait and publish
  without the URL on timeout; buffer an early-arriving URL so it's still included.
- **Out-of-order transcript lines.** Async transcription can land caller
  utterances after the agent reply. Stable-sort by timestamp at build time.
- **`omit-when-empty` for optional fields.** `voice_recording_url` and `trace_id`
  are dropped entirely when absent — never shipped as `""`.
- **Tool call/result entries can carry more than the dialogue.** `Function Call`
  / `Function Call Result` entries serialize the tool's raw `arguments`/`result`
  — which may hold backend data never spoken on the call (full customer records,
  auth tokens, payment refs). Review what your tools return and **redact secrets /
  sensitive non-dialogue fields** before shipping them.

## Common mistakes to avoid

- Using the telephony provider's call id as `call_id` instead of your durable
  session id — breaks cross-system correlation.
- Letting the POST raise into call teardown. Wrap and swallow to a WARNING.
- Awaiting the publish synchronously in the hangup path and stalling cleanup —
  detach it, and keep a strong reference so it isn't GC'd mid-flight.
- Reusing the same payload shape as the eval webhook. They are genuinely different
  (flat vs batched, role casing) — see `custom-transcript-provider`.
- Adding routing you don't need. If you only run this sink, just publish it — the
  `CEKURA_ENVIRONMENT` / `CEKURA_ROUTE_TO` split is only for when both sinks run.
- Shipping blank `voice_recording_url`/`trace_id`/`timestamp` instead of omitting
  the key.
- Firing the publish more than once (e.g. on both WS-close and the hangup
  webhook) — pick one definitive end-of-call signal and publish there once.

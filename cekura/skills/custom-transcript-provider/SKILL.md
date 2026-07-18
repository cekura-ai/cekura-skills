---
name: custom-transcript-provider
description: >-
  Wire ANY voice-AI agent codebase (any language, any framework, any business
  domain) to publish its end-of-call conversation transcript into Cekura's
  CUSTOM-PROVIDER TRANSCRIPT WEBHOOK — the eval / scenarios ingestion path used to
  replay calls against scenarios and score them with metrics. Use this WHENEVER
  you need to "feed Cekura's eval pipeline", "send transcripts for scenario
  scoring", "set up the eval webhook", "wire the custom transcript provider",
  "ingest simulated calls", "correlate a run with run_id", "set transcript_provider
  to custom", or debug why simulated/eval runs aren't ingesting. The durable
  contract is language- and domain-agnostic: ONE plain HTTP POST of a BATCHED JSON
  body ({agent_id, calls:[...]}) to the webhook, fired once per call at hangup,
  isolated so it can never touch call teardown. This sink is fully usable on its
  own — wire it alone if evals are all you need. The production observability path
  is the SIBLING skill observability (wire it too only if you also want prod
  call logs); sinks-publisher is a lightweight chooser if you're unsure which
  sink(s) you need. The reference S2S voice agent (Python/FastAPI/Telnyx/Gemini Live) is
  named ONLY as the reference example — adapt the contract, don't copy it.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

<!-- cekura-ack-tag: ack:custom-transcript-provider:3x8n5w -->
> **Cekura skill verification tag:** `ack:custom-transcript-provider:3x8n5w`
> Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="custom-transcript-provider"`, `verification_tag="ack:custom-transcript-provider:3x8n5w"`, and `plugin_version="0.9.0"`. It returns immediately and lets Cekura see which skills are in use.

# Publish call transcripts to Cekura's CUSTOM-PROVIDER webhook at hangup

## What this skill does

At the end of every call, your agent publishes the conversation transcript to
Cekura's **custom-provider transcript webhook** so the call can be fed into
Cekura's eval/scenarios pipeline (replaying calls against scenarios and scoring
them with metrics). This is **one of Cekura's two ingestion sinks**; this skill
owns the **eval webhook only**:

- **The custom-provider transcript webhook** —
  `POST https://api.cekura.ai/test_framework/custom-provider-transcript-webhook`.
  A *batched* body (`{agent_id, calls: [...]}`) with lowercase roles and
  per-line seconds-from-start timestamps (ISO 8601 at the call level). This is
  the eval/scenarios ingestion path.

**This sink stands alone.** If the eval/scenarios pipeline is all you need, wire
only this skill — it has no dependency on the observe sink or on any coordinator.
The sibling **production observability** path (the flat observe API, used for
production call logs) is a separate skill, **`observability`**, which you wire
*only if you also want production call logs*. If you end up running both and want
to route which fires per environment, that's an optional split you add on top (see
**Running both sinks: the split** below); **`ci-cd`** owns injecting those env vars
per deployment. The lightweight **`sinks-publisher`** skill is just a chooser
that helps you decide which sink(s) you need.

## Why

Cekura needs the transcript in a specific shape, with stable correlation keys,
and it must arrive without ever degrading the live call. The eval pipeline is a
different product from observability, with a different wire format — the same call
has to be reshaped for it. Getting the role names, timestamp units, or correlation
id wrong means the run silently doesn't ingest, or ingests unparseable. And
because publishing happens at the most fragile moment of a call (hangup), a bug
here can hang cleanup or crash call teardown if you don't isolate failures.

## The Cekura contract (durable — true for any repo/language/domain)

These facts hold regardless of your language, framework, or business domain. **The
webhook sink is nothing more than a plain HTTP POST of JSON** — there is no SDK,
no Python dependency, no special client. Anything that can make an HTTPS request
(any language's HTTP library, or even a `curl` from a shell hook) can satisfy this
contract. Everything below describes the JSON body and the rules for filling it;
the transport is just `POST` + `Content-Type: application/json` with your
`X-CEKURA-API-KEY`.

### The webhook body shape

**Batched:** `{"agent_id": <int>, "calls": [ <call> ]}`. Each call object:

- `id` (string) — your **own session id**, NOT the telephony provider's call id.
  This is the universal correlation key that must pivot across Cekura ↔ your app.
- `startedAt` / `endedAt` — **ISO 8601**, absolute call-level times.
- `messages` — array of transcript entries (see role mapping below).
- `from_phone_number`.
- `endedReason` — default `"unknown"` when unknown.
- `metadata` — free-form dict. (The recording URL, if any, rides inside
  `metadata` here — the webhook has no dedicated recording field.)
- `trace_id` — top-level on the call object (omit-when-empty; see `tracing`).
- `run_id` — **only for a *simulated* run, and only as a valid integer that
  matches an EXISTING Cekura run.** The webhook consumer trust-matches a published
  call to its run by `run_id` first (then falls back to time/duration/similarity),
  so it's the reliable correlation for eval ingestion. **Omit it for real
  (non-simulated) calls** — they have no run, and the webhook accepts a
  run-less call fine (`202`). The backend validates it strictly (verified live):
  a **string** run id → `400 "A valid integer is required."`; an integer that
  doesn't correspond to a real run → `400 "Run IDs not found or deleted: [...]"`.
  So never send a synthetic/placeholder run id — send the real integer run id or
  send nothing.

> **`trace_id` goes on BOTH sinks.** It's top-level on the webhook `calls[]`
> object exactly as on the observe payload, for real AND simulated calls (omit
> when empty). Wiring it only on observe is the easy miss — then eval/scenario
> runs have no trace link while production calls do.

### Agent-side prerequisite for this sink

The Cekura agent must have `transcript_provider = "custom"`, or Cekura won't use
the webhook transcript for simulated runs (it gates on that field). This is NOT
exposed by the v2 agent API / MCP (v2 derives it from the provider block and maps
custom→empty), so set it in the dashboard, or
`PATCH {base}/test_framework/v1/aiagents-external/{id}/`
`{"transcript_provider":"custom"}` with `X-CEKURA-API-KEY`. It's a Cekura-side
flag — it never touches the running bot. Confirm it's set before relying on the
eval webhook (the observe sink does NOT need it). Ideally this is set once at
**agent creation** (`cekura-create-agent`) for a self-hosted/custom agent, not
mid-integration — treat it as agent setup, and only patch it here if it's missing.

### Role mapping (get these exact strings right)

| Your transcript line | Webhook `role` |
|---|---|
| agent/bot utterance | `bot` |
| caller/user utterance | `user` |
| tool invocation | `function_call` |
| tool result | `function_call_result` |

Webhook roles are **lowercase**. Tool entries carry a `data` object with a
correlating `id` plus `name` and `arguments`/`result` so Cekura can pair an
invocation with its result.

> The observe sink (`observability`) uses **Title Case** roles (`Main Agent`/
> `Testing Agent`/`Function Call`/`Function Call Result`) — a different string
> set. If you fire both sinks, build each shape separately; don't reuse one
> payload.

> Correct role mapping assumes you can reliably tell the caller's speech from the
> agent's. If your transcription mixes speakers, reliable caller-vs-agent speaker
> separation (dual-channel recording) is an option, but it's telephony-provider
> dependent and there's no turnkey path — dive deeper into the provider's
> recording capabilities if you need it.

### Timestamp units — seconds-from-call-start

Per-message `start_time`/`end_time` are **seconds from call start** (float),
computed by subtracting the call-start time from each line's timestamp. Omit when
a line has no parseable timestamp. Only the CALL-LEVEL times are absolute:
`startedAt`/`endedAt` are **ISO 8601**.

> **Verified against the backend, and it contradicts an older version of this
> doc.** The consumer treats `start_time` as *seconds* (it multiplies by 1000 to
> get ms — `test_framework/transcribe.py`), and the team's own
> `test_custom_webhook_e2e.py` sends seconds. An earlier revision claimed the
> webhook wanted **millisecond epoch** — that is WRONG and produces astronomically
> wrong call durations.

### Ordering

Sort transcript lines by timestamp at build time, with a **stable** sort so a
tool call and its result that share a timestamp keep invocation-before-result
order. (Async transcription pipelines frequently emit caller utterances *after*
the agent reply that logically follows them — sort to fix the order.)

### Independent failure (non-negotiable)

This POST **must never propagate into the call teardown path**, and if you also
fire the observe sink, the two must fail **independently** — an error on one must
never prevent or mask the other. Wrap the POST so a non-2xx or thrown error is
logged and swallowed (a `try`/`catch`, an error-return check, a `recover`/rescue,
a promise `.catch()`). A failed publish is a WARNING, never a surfaced error.

### Overrides

The webhook payload carries the agent-id (and any provider-id) as an explicit
field, so a single deployment can attribute published transcripts to a chosen
Cekura agent rather than a hardcoded default.

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

**This skill needs nothing from the observe sink and nothing from any
coordinator.** When the `CEKURA_*` config is present, publish to the eval webhook
for the calls you want ingested; when it's absent, the bot runs unchanged
(off-by-default). If the eval pipeline is all you want, you're done — **there is
no routing to configure.** The split below only becomes relevant once you *also*
wire the observe sink (`observability`) and want to run "both" with each
environment routed to the right sink.

### Running both sinks: the split (the "both" setup)

Skip this section if you only run the eval webhook. It applies once you ALSO wire
the observe sink (`observability`). The recommended "both" setup is a
**per-environment split**: the **non-prod / sandbox** deployment publishes to THIS
eval webhook, while the **prod** deployment publishes to the observe sink instead,
so sandbox eval runs never pollute prod observability. You implement this sink's
side of that decision here.

Two env vars express the split: `CEKURA_ENVIRONMENT` (per-environment selector)
and `CEKURA_ROUTE_TO` (explicit override — when set, it wins).

**The recommended split** — leave `CEKURA_ROUTE_TO` unset and let
`CEKURA_ENVIRONMENT` decide: non-prod / `sandbox` → eval webhook only; `prod` →
observe sink only. Sandbox eval runs never pollute prod observability. This is
what you want in almost all cases.

<details>
<summary><b>Rare — explicit <code>CEKURA_ROUTE_TO</code> overrides (most deployments never set this)</b></summary>

Setting `CEKURA_ROUTE_TO` overrides the environment split:

- `both` — fire BOTH sinks on every call, regardless of environment. **Rare:** it
  doubles ingest and mixes sandbox traffic into prod observability; only for a
  single deployment that must feed both pipelines.
- `evals` — force this eval webhook only (same effect as standalone).
- `observability` — silence this sink.

Unknown values fall back to the `CEKURA_ENVIRONMENT` split.
</details>

So **the eval webhook fires when** `CEKURA_ROUTE_TO` is `evals` or `both`, OR
`CEKURA_ROUTE_TO` is unset and `CEKURA_ENVIRONMENT=sandbox` (non-prod). Implement
this decision here **only if you run both sinks**; **how those env vars get set per
deployment** is `ci-cd`'s job. The sibling `observability` documents the
same split from its side.

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
   your systems and use it as `calls[].id`. Do NOT use the telephony provider's
   id. For simulated runs, also carry the Cekura `run_id` (a real integer);
   omit it entirely on real calls.
4. **Where does your transcript live at hangup?** You need utterances + tool
   calls + tool results with per-line timestamps. If your transcript store is
   keyed by the telephony id, make sure it's still readable at hangup (snapshot
   it before any registry entry is torn down).
5. **Is `transcript_provider = "custom"` set on the agent?** Confirm the
   agent-side prerequisite above, or the webhook transcript won't be used for
   simulated runs.
6. **Are you also running the observe sink?** If NO, there's nothing to route —
   just publish this sink for the calls you want ingested. If YES, the recommended
   "both" setup splits by environment (non-prod → this eval webhook, prod →
   observe sink): implement that decision here (see **Running both sinks: the
   split**); `ci-cd` sets those env vars.
7. **One transform function, pure and tested.** Write the webhook builder as a
   pure function (no I/O) so you can assert the exact wire shape at the HTTP
   boundary.

## Reference implementation (example voice agent — Python/FastAPI/Telnyx/Gemini; adapt, don't copy)

**This is ONE illustration in ONE language — Python/FastAPI with Telnyx telephony
and a Gemini Live model — not the spec.** The steps and contract above stand on
their own; read this block only to see *how* one stack satisfies them, then
translate the JSON POST into yours. These are real paths and verbatim excerpts;
the Telnyx `call.hangup` trigger is just this repo's instance of the end-of-call
hook.

**Trigger point** — `main.py`, the Telnyx `call.hangup` webhook handler schedules
the publish (see `observability`'s reference for the shared trigger + detached
dispatch; both sinks fire from the same scheduled publish).

**Webhook POST in its own try** — `modules/cekura_publisher.py`, `schedule_publish`.
The webhook gets its own `try` so its failure never aborts the observe sink or the
WS handler:

```python
            if self._publish_webhook and self._webhook_url:
                try:
                    await self._post_webhook(
                        build_custom_provider_transcript_payload(
                            agent_id=self._agent_id,
                            summary=summary,
                            transcript_lines=transcript_lines,
                            recording_url=recording_url,
                        )
                    )
                except Exception as exc:
                    logger.warning("Cekura transcript webhook failed for %s: %s", call_control_id, exc)
```

**Webhook payload builder** — `build_custom_provider_transcript_payload`.
Batched under `calls`, lowercase roles, per-message `start_time`/`end_time` in
**seconds-from-start** via `_to_webhook_messages`; call-level `startedAt`/`endedAt`
are ISO 8601:

```python
    call_obj: dict[str, Any] = {
        "id": summary.get("session_id", ""),
        "startedAt": started_iso,
        "endedAt": ended_iso,
        "messages": _to_webhook_messages(transcript_lines),
        "from_phone_number": summary.get("caller_phone_number", ""),
        "endedReason": summary.get("hangup_reason", "") or "unknown",
        "metadata": metadata,
    }
    if summary.get("trace_id"):        # top-level on the call obj, same as observe
        call_obj["trace_id"] = summary["trace_id"]
    if summary.get("run_id"):          # simulated runs only: real INTEGER run id
        call_obj["run_id"] = summary["run_id"]
    return {"agent_id": agent_id, "calls": [call_obj]}
```

**Webhook message transform** — `_to_webhook_messages`. Lowercase roles,
seconds-from-start timing:

```python
        if kind == "utterance":
            role = "bot" if line.get("speaker") == "agent" else "user"
            msg: dict[str, Any] = {"role": role, "content": line.get("text", "")}
        ...
        if t is not None:
            msg["start_time"] = t   # seconds-from-start (float), same as observe
            msg["end_time"] = t
```

**Recording** — the webhook has no dedicated recording field; the signed URL rides
inside `metadata`. (See `observability` for the bounded recording-wait; both
sinks share the same waited URL.)

**Tests** — `tests/test_cekura_publisher.py` asserts at the HTTP boundary with
`respx` (the exact wire shape), not internal call counts. See
`test_build_webhook_payload_shape` and
`test_route_to_both_webhook_failure_does_not_block_observe`.

## Verify offline (no live phone call)

You don't need to place a real call to prove the publish works — exercise the
builder + POST directly:

1. Build the webhook payload with your real builder for a synthetic call (a couple
   of utterances + a tool call/result, with a `run_id` if simulating a run), then
   `POST {base}/test_framework/custom-provider-transcript-webhook` with
   `X-CEKURA-API-KEY`. Confirm a 2xx.
2. For a simulated run, confirm the call trust-matched to the run by `run_id`
   (the run picks up the published transcript). For a standalone transcript,
   confirm it ingested against the agent.
3. Unit-test the builder as a **pure function** at the wire-shape boundary
   (lowercase roles, seconds timestamps, run_id/recording present-only-when-set)
   so regressions fail fast without any network.

**Hygiene:** verify against a **sandbox agent**, tag synthetic calls with a clear
`metadata.source` (e.g. `"webhook smoke test"`), and **delete them afterward** —
never leave test rows polluting a customer's data.

## Gotchas

- **The webhook wants `calls[].id`, not a top-level `call_id`.** The batched shape
  carries the session id inside each call object.
- **Per-line timestamps are seconds-from-start** (float), NOT ms-epoch. The
  consumer multiplies `start_time` by 1000 to get ms, so shipping ms-epoch ingests
  garbage timing. Only the call-level times are absolute (`startedAt`/`endedAt`,
  ISO 8601).
- **Role strings are case-sensitive and lowercase.** `bot`/`user`/`function_call`/
  `function_call_result` — different from observe's Title Case set.
- **`transcript_provider = "custom"` must be set on the agent** or simulated runs
  ignore the webhook transcript. It's not exposed by the v2 API/MCP; set it in the
  dashboard or via the `aiagents-external` PATCH.
- **`run_id` must be a valid integer matching a real run, or omitted.** It's the
  reliable eval correlation for *simulated* runs; without it the consumer falls
  back to time/duration/similarity matching (fine for real calls, which have no
  run). Verified live: a string run id → `400 "A valid integer is required."`, and
  a non-existent integer → `400 "Run IDs not found or deleted"`. Never send a
  placeholder — the strict validation rejects the whole batch. (A repo typing
  `run_id` as `string | number` is a latent bug: the string path 400s.)
- **Out-of-order transcript lines.** Async transcription can land caller
  utterances after the agent reply. Stable-sort by timestamp at build time.
- **`omit-when-empty` for optional fields.** `trace_id` and `run_id` are dropped
  entirely when absent — never shipped as `""`.
- **The webhook has no recording field.** The signed URL rides along inside
  `metadata`.
- **Tool call/result entries can carry more than the dialogue.** `function_call` /
  `function_call_result` entries (and the tool spans in `tracing`) serialize
  the tool's raw `arguments`/`result` — which may hold backend data never spoken
  on the call (full customer records, auth tokens, payment refs). Review what your
  tools return and **redact secrets / sensitive non-dialogue fields** before
  shipping them.

## Common mistakes to avoid

- Using the telephony provider's call id as `calls[].id` instead of your durable
  session id — breaks cross-system correlation.
- Forgetting `run_id` on simulated runs — eval ingestion then relies on fuzzy
  matching. Conversely, sending a **placeholder/string** `run_id` (or one for a
  run that doesn't exist) 400s the whole batch — send the real integer run id or
  omit it.
- Letting the POST raise into call teardown. Wrap and swallow to a WARNING; if the
  observe sink also fires, the two must fail independently.
- Awaiting the publish synchronously in the hangup path and stalling cleanup —
  detach it, and keep a strong reference so it isn't GC'd mid-flight.
- Reusing the same payload shape as observe. They are genuinely different (batched
  vs flat, role casing, `id` placement) — see `observability`.
- Adding routing you don't need. If you only run this sink, just publish it — the
  `CEKURA_ENVIRONMENT` / `CEKURA_ROUTE_TO` split is only for when both sinks run.
- Firing the publish more than once (e.g. on both WS-close and the hangup
  webhook) — pick one definitive end-of-call signal and publish there once.

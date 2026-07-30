---
name: metadata
description: >-
  Phase 2 of wiring a voice-AI agent into Cekura: stamp useful, non-PII per-call
  metadata onto the transcripts already being published (via the sink skills
  observability / custom-transcript-provider). Use this WHENEVER you need to enrich call metadata,
  send the system prompt to Cekura so evals can read it via
  {{metadata.system_prompt}}, slice eval/observe results by a domain attribute
  (location, plan, language, capability flag), surface actor-recognition signals
  (e.g. returning-caller / VIP / visit-count), or link a call to its trace_id —
  or whenever someone says "add metadata to Cekura calls", "enrich the call
  payload", "ship the prompt to the eval grader", "slice evals by attribute",
  "avoid leaking PII into metadata", "snapshot the prompt before per-caller
  augmentation", or "attach the OTel trace id". Applies to ANY repo, language,
  framework, or business domain that publishes to Cekura; the reference voice
  agent (Python/FastAPI/Telnyx/Gemini Live) is only the
  worked example — adapt, don't copy.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

<!-- cekura-ack-tag: ack:metadata:7h4c2k -->
> **Cekura skill verification tag:** `ack:metadata:7h4c2k`
> Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="metadata"`, `verification_tag="ack:metadata:7h4c2k"`, and `plugin_version="0.9.0"`. It returns immediately and lets Cekura see which skills are in use.

# Stamp per-call metadata onto Cekura transcripts

## What this skill does

You take the call-publishing path you built with the sink skills
(**`observability`** for the observe payload and/or
**`custom-transcript-provider`** for the custom-transcript webhook) and thread
a single **metadata object** into whichever sink(s) you publish. This is plain data — a set of key/value
facts assembled into JSON and sent over HTTP — so it is language- and
framework-agnostic; nothing here is specific to any runtime. That object carries
three classes of fact that make eval and observability results far more useful:

1. **The config-rendered system prompt** the agent actually ran with — captured
   as a SNAPSHOT *before* any per-caller augmentation — surfaced under the key
   `system_prompt`. Downstream evals read it via the Cekura variable
   `{{metadata.system_prompt}}` (author those evals with `cekura-eval-design`).
2. **Domain slicing flags** — static call-setup facts that let you filter
   eval/observe results by an attribute (e.g. per-location capability flags,
   plan tier, region, routing phones).
3. **Non-PII actor-recognition signals** — e.g. "is this a returning/known
   actor", a loyalty tier, a visit count — but NEVER the actor's name or other
   identifiers, because the payload already carries the caller phone number.

You also link the call to its OpenTelemetry trace via a **top-level** `trace_id`
field (the trace itself is owned by the sibling skill `tracing`).

**Where you gather and attach these facts depends on your setup:**

- **Custom / self-hosted code (any language — Python, Node/TS, Go, …):** hold the
  metadata on your own per-call session/call object and attach it in the same
  end-of-call publish path Phase 1 built.
- **A framework (LiveKit Agents, Pipecat):** hold the metadata in the framework's
  per-session/context state and attach it at the same end-of-call hook the
  publisher fires on (e.g. LiveKit Agents' session-shutdown/close callback,
  Pipecat's pipeline-ended / client-disconnected event).
- **A managed platform (Vapi / Retell / ElevenLabs):** the facts often already
  exist on the platform's call object or in its end-of-call webhook payload. You
  may simply **map those fields** into the metadata object rather than write code
  to compute them.

This skill does not re-explain the sinks, the wire shapes, or how the publish is
scheduled — that's Phase 1. It only owns *what goes into metadata and how*.

## Why

A bare transcript tells you what was said. Metadata tells you **under what
conditions**, so you can:

- **Grade against the live prompt.** Evals that inject `{{metadata.system_prompt}}`
  judge the agent against the exact prompt it ran with, instead of a hardcoded
  copy that drifts. Shipping the prompt in metadata is the supply side of that
  contract.
- **Slice results.** "Show me failures only for locations that can create leads"
  or "only Spanish-language calls" requires those attributes to be on the call.
- **Recognize actors without storing PII.** Knowing a call was from a recognized
  VIP is a useful filter; storing their name next to their phone number in a
  third-party datastore is a PII liability you don't want.
- **Pivot to the trace.** A `trace_id` on the call log lets you jump from a bad
  eval straight to the OTel span tree for that call.

## The Cekura contract (durable — true for any repo/language/domain)

These facts hold regardless of your stack. Keep your implementation faithful to
them; everything language- or domain-specific belongs in the reference section.

- **One metadata object, both sinks.** The same static metadata is merged into
  the observe payload's `metadata` object AND the custom-transcript webhook's
  per-call `metadata` object. Carry it through a single shared field (a
  `metadata_extra`-style handoff — call it whatever your language uses) so the two
  sinks never drift apart.
- **`system_prompt` is the agreed key.** The rendered prompt is surfaced under
  the metadata key `system_prompt`. That exact name is the contract with
  `{{metadata.system_prompt}}` on the eval side — if you rename the key, you must
  rename the variable in every eval/metric.
- **Snapshot the prompt BEFORE per-caller augmentation.** Capture the prompt at
  the moment it is rendered from config, *before* you splice in any per-caller /
  per-actor context. That augmented context is exactly where PII (names, account
  details, recent-activity strings) enters the prompt, and you must not let it
  reach a third-party store.
  - **When the prompt has no separate augmentation step — it interpolates the
    caller's data INLINE in one render** (e.g. a template literal / f-string that
    prints `customer.name` and `caller_phone` directly, with no later append) —
    there is no clean "before" to snapshot. Instead, snapshot a **placeholder
    render**: render the same prompt with the per-caller values replaced by
    tokens (`{{customer_name}}`, `{{caller_phone}}`, …). This is exactly the
    flattened config prompt `config-sync` already builds for the agent
    `description`; reuse that renderer so the shipped `system_prompt` is
    PII-free by construction and matches the synced description.
- **Ship recognition signals, not identities.** Boolean / categorical / count
  signals about who the caller is (recognized? tier? visit count?) are fine.
  Names, emails, addresses — anything that, combined with the caller phone number
  already on the payload, forms a PII record — are not.
- **`trace_id` is TOP-LEVEL, not metadata.** It rides as a top-level field on the
  call object, mirroring the observe payload's top-level placement. This is
  undocumented but accepted by the custom transcript provider. Omit it entirely
  when empty so the field never ships blank.
- **Runtime keys WIN on name clash.** Always-present runtime keys the publisher
  computes at end-of-call (e.g. `location_id`, `errors`, `tool_calls`) must
  override any same-named key in the static metadata. Apply the static metadata
  FIRST and the runtime keys LAST when assembling the object, so the runtime
  values win (whatever your language's merge/last-write-wins idiom is — object
  spread, `dict.update`, `map` assignment, etc.).

## Adapt to your stack (checklist)

Answer these for your repo before writing code:

- **Where is your system prompt assembled?** Find the single call site that
  renders the prompt from config. That render output is your snapshot source.
- **Where is the prompt augmented per-caller?** Find every place that mutates the
  prompt with caller-specific context (greeting injection, "returning caller"
  blocks, account summaries). Your snapshot must be taken *upstream* of all of
  them.
- **What are YOUR domain's slicing dimensions?** What attributes would you want
  to filter eval/observe results by? (plan tier, region, language, feature flags,
  experiment arm, capability flags…) Those become your static metadata keys.
- **What fields are PII in your domain?** Enumerate them explicitly. Remember the
  payload already carries the caller phone number, so anything that *identifies*
  the same person is PII-by-combination. Ship only de-identified signals.
- **Where can you resolve these facts?** Static call-setup facts are usually only
  in scope during session setup, not at end-of-call. Stamp them where your setup
  step can reach them and your publish step can read them later: custom code → your
  own per-call state/session object; LiveKit Agents / Pipecat → the framework's
  per-session/context state; a managed platform → often already on the call object
  or in the end-of-call webhook, so you map rather than store. The publish path
  runs at end-of-call, so the facts must survive until then.
- **Does your shared metadata field reach BOTH sinks?** Verify the merge happens in
  both payload builders, with runtime keys applied last in each.

## Reference implementation (example voice agent — Python/FastAPI/Telnyx/Gemini; adapt, don't copy)

Everything above is the complete spec and stands on its own — this section is
**one worked illustration in one language** (Python), nothing more. The contract
is the same on any stack; the snippets below just show how *this* codebase
satisfies it. Read it for the shape, not the syntax: a Node/TS, Go, LiveKit
Agents, Pipecat, or managed-platform implementation does the same three things in
its own idiom. Do not copy the code.

Files: `main.py` (`_run_call_session`, `_schedule_cekura_publish`),
`modules/cekura_publisher.py` (`build_payload`,
`build_custom_provider_transcript_payload`).

### 1. Build the static metadata at session setup — `main.py` `_run_call_session`

The prompt is rendered from config, **snapshotted**, then the static facts
(capability flags/phones + non-PII caller signals) are stamped onto the per-call
state (`agent_cfg`, the same dict the registry holds):

```python
system_prompt = config_mod.build_system_prompt(
    business_name=agent_cfg["name"],
    address=agent_cfg["address"],
    ordering_enabled=ordering_enabled,
)
# Snapshot the config-only prompt BEFORE the per-caller augmentation block
# (caller PII) is appended below. Anything shipped off-box (e.g. Cekura
# metadata) must read this, never the live `system_prompt`. Evals read it via
# {{metadata.system_prompt}}.
config_system_prompt = system_prompt
```

```python
# Stamp the static, call-setup-time facts we can resolve here onto the
# registry entry so _schedule_cekura_publish can ship them as Cekura
# metadata. Values come from the per-location config (config_mod) and the
# optional caller profile — both only in scope at this point, not at hangup.
# Phones/flags help slice eval + observe results by capability.
cekura_metadata: dict[str, Any] = {
    "system_prompt": config_system_prompt,
    "location_name": agent_cfg.get("name", ""),
    "timezone": agent_cfg.get("timezone", ""),
    "can_create_lead": getattr(config_mod, "CAN_CREATE_LEAD", False),
    "<CAPABILITY_FLAG>": getattr(config_mod, "<CAPABILITY_FLAG>", False),
    "escalation_phone": getattr(config_mod, "<ROUTING_PHONE>", None),
    "secondary_phone": getattr(config_mod, "<ROUTING_PHONE>", None),
    "ordering_enabled": ordering_enabled,
}
# Deliberately NOT sending caller first/last name: the Cekura payload already
# carries customer_number (the caller's phone), so adding the name would
# export a complete PII record (full name + phone) to a third-party
# datastore. We ship only non-identifying recognition signals, which still
# let us slice results by caller status/loyalty.
if caller_profile:
    cekura_metadata.update(
        {
            "caller_recognized": True,
            "caller_vip_status": bool(caller_profile.get("vip_status", False)),
            "caller_visit_count": caller_profile.get("visit_count", 0),
        }
    )
else:
    cekura_metadata["caller_recognized"] = False
agent_cfg["cekura_metadata"] = cekura_metadata
```

Only AFTER the snapshot is the prompt augmented with the per-caller block — this
is the PII boundary the snapshot sits above:

```python
if caller_context:
    # ... builds name_rule containing the caller's real name ...
    system_prompt = system_prompt + "\n\n## Returning caller context\n" + caller_context + name_rule
```

### 2. Carry it into the summary at hangup — `main.py` `_schedule_cekura_publish`

The hangup path reads the stamped dict off the registry entry and passes it
through under `metadata_extra` (the `trace_id` is also read off the entry,
stamped earlier by the conversation span):

```python
summary = {
    "session_id": entry.get("session_id", ""),
    "location_id": entry.get("location_id"),
    "caller_phone_number": entry.get("caller_number", ""),
    # ... runtime counters ...
    "trace_id": entry.get("trace_id", ""),
    # Static call-setup facts (capability flags/phones + caller profile)
    # stamped onto the entry in _run_call_session. Merged into the Cekura
    # metadata dict by both payload builders.
    "metadata_extra": entry.get("cekura_metadata") or {},
}
```

### 3. Merge into BOTH payloads — `modules/cekura_publisher.py`

Observe payload (`build_payload`) — static metadata spread FIRST, runtime keys
last, then `trace_id` added at the TOP LEVEL:

```python
"metadata": {
    # Spread the call-setup metadata first so the always-present runtime
    # keys below (location_id/errors/tool_calls) win on any name clash.
    **summary.get("metadata_extra", {}),
    "location_id": summary.get("location_id"),
    "errors_total": summary.get("errors_total", 0),
    "errors_by_category": summary.get("errors_by_category", {}),
    "tool_calls_total": summary.get("tool_calls_total", 0),
    "total_tokens": str(summary.get("total_tokens", 0)),
},
```

```python
# Link this call log to its OpenTelemetry trace. Omitted entirely when
# tracing is disabled (empty trace_id), so the field never ships blank.
trace_id = summary.get("trace_id")
if trace_id:
    payload["trace_id"] = trace_id
```

Webhook payload (`build_custom_provider_transcript_payload`) — same merge order,
into the per-call object's `metadata`:

```python
metadata: dict[str, Any] = {
    # Spread the call-setup metadata first so the always-present runtime keys
    # below (session_id/location_id/errors/tool_calls) win on any name clash.
    **summary.get("metadata_extra", {}),
    "session_id": summary.get("session_id", ""),
    "location_id": summary.get("location_id"),
    "errors_total": summary.get("errors_total", 0),
    "errors_by_category": summary.get("errors_by_category", {}),
    "tool_calls_total": summary.get("tool_calls_total", 0),
    "total_tokens": str(summary.get("total_tokens", 0)),
}
```

The `CallSummary` TypedDict documents the contract for both: `trace_id` is a
top-level field, `metadata_extra` is "merged verbatim into the published
`metadata` dict by both payload builders."

## Verify offline (no live call)

Publish one synthetic call through the real builder with `metadata_extra` set,
then read it back (`call_logs_retrieve` / GET) and assert on `metadata`:
`system_prompt` is present **and PII-free** (placeholder tokens, not a real
customer name), the slicing flags are there, the recognition signal is a
boolean/category (not an identity), and a runtime key wins over a same-named
static key. A quick grep of the shipped payload for a known seeded name (e.g. a
fixture customer) is a cheap PII regression check.

> **Mind the `system_prompt` size.** You ship it on **every** call. A 2–3k-char
> prompt is fine; a 20–50k-char one is heavy (and may hit payload limits) repeated
> per call. `config-sync` already stores the full prompt agent-side (the
> `description`), so for very large prompts consider shipping a **hash/version
> tag** in metadata instead of the whole text, and grade against the agent
> `description`. Don't blindly ship a giant prompt on every call.

## Gotchas

- **Snapshot before PII augmentation.** The single most important rule. Capture
  the rendered prompt the instant it comes out of config, before you splice in
  any caller-specific context. In the reference voice agent the per-caller
  augmentation block (which may contain the caller's real name) is appended
  *after* the snapshot — so the
  shipped `system_prompt` is clean. If you snapshot after augmentation, you leak
  PII into a third-party store.
- **`trace_id` is top-level, not inside metadata.** It mirrors the observe
  payload's placement and is set directly on the call object. Putting it inside
  `metadata` would break the link and the dashboard's trace pivot. Omit it when
  empty rather than shipping a blank string.
- **Runtime keys win.** Apply the static metadata FIRST and the publisher's
  runtime keys LAST in every builder (whatever merge idiom your language uses), so
  a stray same-named static key can never shadow the authoritative runtime value
  (`location_id`, `errors`, `tool_calls`).
- **Static facts are only in scope at setup, not at end-of-call.** Resolve and
  stamp them during session setup where the publish step can read them later
  (your per-call state for custom code, the framework's session/context state for
  LiveKit Agents / Pipecat, the platform call object / webhook for managed
  platforms); the publish path runs at end-of-call, when the location config /
  actor profile are long out of scope.
- **The metadata key name is a cross-skill contract.** `system_prompt` here must
  match `{{metadata.system_prompt}}` in the evaluators that read it (authored
  with `cekura-eval-design`). Rename in
  lock-step or not at all.

## Common mistakes to avoid

- Snapshotting the prompt *after* per-caller augmentation — leaks PII.
- Shipping the actor's name (or any identifier) alongside the caller phone
  number — creates a PII record in a third-party datastore. Ship only
  de-identified recognition signals.
- Putting `trace_id` inside `metadata` instead of at the top level.
- **Setting `trace_id` on the observe payload but forgetting the eval webhook**
  (top-level on the `calls[]` object). It's easy to wire only observe — then
  eval/scenario runs have no trace link even though production calls do. Add it to
  BOTH sinks (omit-when-empty on each).
- Threading metadata into only one sink, so observe and eval results disagree.
- Merging the static metadata LAST, letting a static key clobber a runtime key.
- Renaming the `system_prompt` metadata key without updating the eval variable.
- Re-explaining or re-implementing the publishing path here — that's the sink
  skills (`observability` / `custom-transcript-provider`); this skill only
  enriches it.

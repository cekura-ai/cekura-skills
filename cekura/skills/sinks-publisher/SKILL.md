---
name: sinks-publisher
description: >-
  Lightweight CHOOSER for Cekura's two end-of-call transcript ingestion sinks. Use
  this when you're deciding "which sink(s) do I need to send transcripts to
  Cekura?", "do I want observability, evals, or both?", "how do I wire both sinks
  and split them per environment?", or you're debugging ingestion and aren't sure
  which sink is involved. It does NOT own publishing logic or routing — each sink
  is a self-contained skill you can wire independently: the production
  observability path is observability, and the eval/scenarios path is
  custom-transcript-provider. If you already know which sink you want, skip
  this and invoke that sink's skill directly. The optional split (fire different
  sinks in different environments) lives inside each sink skill and only applies
  once you've wired both; ci-cd injects the env vars per deployment.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

<!-- cekura-ack-tag: ack:sinks-publisher:2w5b8m -->
> **Cekura skill verification tag:** `ack:sinks-publisher:2w5b8m`
> Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="sinks-publisher"`, `verification_tag="ack:sinks-publisher:2w5b8m"`, and `plugin_version="0.9.0"`. It returns immediately and lets Cekura see which skills are in use.

# Cekura's two transcript sinks — which do you need?

## What this skill does

Cekura has **two independent end-of-call transcript sinks**. This skill is a
**chooser**: it helps you decide which sink(s) your integration needs, then points
you at the self-contained skill that wires each. It owns **no** publishing logic
and **no** routing — each sink skill is standalone and complete on its own.

| Sink | What it feeds | Endpoint | Owning skill |
|---|---|---|---|
| **Observe** | Production observability / call logs | `POST /observability/v1/observe/` (flat, single call) | **`observability`** |
| **Eval webhook** | Eval / scenarios replay + scoring | `POST /test_framework/custom-provider-transcript-webhook` (batched `{agent_id, calls:[...]}`) | **`custom-transcript-provider`** |

## Which sink(s) do you need?

Each sink is fully usable on its own — pick based on what the customer wants.
Three first-class choices:

- **Only production monitoring / call logs in the Cekura dashboard?** → wire
  **`observability`** alone. No routing needed.
- **Only running evals / replaying calls against scenarios + metrics?** → wire
  **`custom-transcript-provider`** alone. No routing needed. (Confirm the
  agent has `transcript_provider = "custom"`.)
- **Both — observability for prod AND evals for non-prod?** → wire **both** skills
  and **split them by environment**: the **prod** deployment feeds the observe
  sink, the **non-prod / sandbox** deployment feeds the eval webhook. Sandbox eval
  runs then never pollute prod observability. This is the recommended combined
  setup and what most people mean by "set up both"; it's driven by
  `CEKURA_ENVIRONMENT` per deployment (see the split below).

A **single sink** needs no routing — it just publishes whenever the `CEKURA_*`
config is present (off-by-default without it). The **"both" setup uses routing**
(`CEKURA_ENVIRONMENT`) so each environment hits the right sink. (A rare advanced
variant fires both sinks on every call regardless of environment — see the split
section below.)

## The split — routing each environment to the right sink (the "both" setup)

This applies once you've wired BOTH sinks. Two env vars express how they relate:
`CEKURA_ENVIRONMENT` (the per-environment selector) and `CEKURA_ROUTE_TO` (an
explicit override — when set, it wins).

**The recommended split** — leave `CEKURA_ROUTE_TO` unset and let
`CEKURA_ENVIRONMENT` decide per deployment: **prod → observe sink only**,
**non-prod / sandbox → eval webhook only**. Observability watches production,
eval/scenario runs come from sandbox, and sandbox never pollutes prod
observability. This is what most people mean by "set up both".

<details>
<summary><b>Rare — explicit <code>CEKURA_ROUTE_TO</code> overrides (most deployments never set this)</b></summary>

Setting `CEKURA_ROUTE_TO` overrides the environment split:

- `both` — every call fires BOTH sinks regardless of environment. **Rare:** doubles
  ingest and mixes sandbox traffic into prod observability; only when a single
  deployment must feed both pipelines.
- `observability` — force the observe sink only.
- `evals` — force the eval webhook only.

Unknown values fall back to the `CEKURA_ENVIRONMENT` split.
</details>

A single-sink integration ignores all of this — it just publishes its one sink.

**The split logic lives inside each sink skill**, described from that sink's own
perspective — see the split section in **`observability`** and
**`custom-transcript-provider`**. This chooser deliberately does not restate
the per-sink firing rules, so there's one home per sink. **How the env vars get
set per deployment** is **`ci-cd`**'s job.

## The shared spine (both sinks, whether you run one or both)

Each sink skill states this in full for its own POST; it's summarized here so you
know what's common before you pick:

- Published once from the **definitive end-of-call signal** (hangup hook / session
  close), **fire-and-forget**, failures swallowed to a WARNING and never touching
  call teardown. If you run both, they fail **independently**.
- Per-line timestamps are **seconds-from-call-start** (not ms-epoch); call-level
  times are ISO 8601.
- Stable-sorted transcript lines; `trace_id` on **both** sinks (omit-when-empty).
- **PII care:** tool-call/result payloads may carry non-dialogue secrets — redact
  before shipping.

The wire shapes, role casing, correlation keys, and prerequisites differ per sink
— that's exactly why each has its own skill. Build the transcript once and
transform it into each sink's shape separately if you run both.

## Common mistakes to avoid

- **Forcing everything through this chooser.** If you know which sink you want,
  invoke its skill directly — each stands alone.
- **Adding the split when you only run one sink.** Routing is only for the
  both-sinks case; a single sink just publishes.
- **Treating the two sinks as one payload.** They differ (flat vs batched, Title
  Case vs lowercase roles, `call_id` vs `calls[].id`) — build each shape
  separately.
- **Wiring `trace_id` on observe only.** It belongs on BOTH sinks when both run.
- **Forgetting `transcript_provider = "custom"`** on the agent when using the eval
  webhook.

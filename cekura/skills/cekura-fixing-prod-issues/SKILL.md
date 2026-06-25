---
name: cekura-fixing-prod-issues
description: >
  DEPRECATED — merged into cekura-self-improving-agent. This skill's
  production-call bug-fixing workflow (debug → reproduce → fix → verify →
  regression → PR) now lives inside cekura-self-improving-agent, which keeps
  the strict must-fail-first reproduction gate and PR step while adding an
  auto-built reproduction harness, stochastic re-run verification, and the
  full auto-loop. Use cekura-self-improving-agent for "fix this prod call
  issue", "debug and fix call ID", "reproduce this production bug",
  "test my fix against prod scenarios", or "regression test before raising PR".
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
---

# Fixing Production Call Issues — moved

This skill has been **merged into [`cekura-self-improving-agent`](../cekura-self-improving-agent/SKILL.md)**. There is no separate workflow to run here.

## Why

`cekura-fixing-prod-issues` (strict 6-phase prod-call workflow) and `cekura-self-improving-agent` (auto-loop prompt/tool tuner) overlapped heavily — both reproduced failures on Cekura and both verified after editing. They are now one skill that keeps the auto-loop's ergonomics **and** the strict gates this skill contributed:

- **Auto-built reproduction harness** from the prod call's own trace — mock tools, expected mock return values (from the request→response pairs), main-agent dynamic variables, and testing-agent variables — so there is no manual mock/variable setup.
- **Must-fail-first gate** — the reproduction must definitively FAIL on Cekura before any edit (with 5–10× stochastic re-runs for probabilistic / LLM-based failures; a single run for deterministic / infra failures).
- **Must-pass gate** — the fix must definitively PASS (same stochastic re-run policy) before the iteration is accepted.
- **`expected_outcome`-first evaluator construction** — falls back to the prod metric only when the failure can't be expressed as behavioral bullets.
- **Regression sweep** — happy-path + edge-case coverage on the changed surface.
- **PR step** — raises the PR automatically when running in a writable git checkout with `gh`, or emits a PR-ready summary otherwise.

## What to do

Invoke **`cekura-self-improving-agent`** with the production `call_id`. The prod-call fast path runs end-to-end: reproduce (fail-gate) → diagnose → apply → verify (pass-gate) → regression → PR/summary.

See [`../cekura-self-improving-agent/SKILL.md`](../cekura-self-improving-agent/SKILL.md) and its [`phases/reproduce.md`](../cekura-self-improving-agent/phases/reproduce.md), [`phases/regression.md`](../cekura-self-improving-agent/phases/regression.md), and [`phases/pr.md`](../cekura-self-improving-agent/phases/pr.md).

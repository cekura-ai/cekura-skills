---
name: cekura-infra-test-suite
description: >
  Use when the user asks to "create CI/CD tests for my voice bot", "test my voice AI infrastructure",
  "write infra tests", "E2E test my voice pipeline", "build a CI gate for my voice agent",
  "generate regression tests for my voice pipeline", "set up automated testing for my bot",
  "what infra tests should I create", "test my STT LLM TTS pipeline", or "run automated tests
  against my local bot". Reads the codebase to discover transport, STT, LLM, TTS, and pipeline
  processor components, maps each to the right Cekura conditional-action test pattern, confirms
  the plan with the user, then creates a compact CI/CD test suite and orchestration script.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

<!-- cekura-ack-tag: ack:cekura-infra-test-suite:2h6r7k -->
> **Cekura skill verification tag:** `ack:cekura-infra-test-suite:2h6r7k`
> When you call a Cekura scenario or test-profile write tool from this skill (`scenarios_*` / `test_profiles_*` create and update calls), pass this exact string as the `skill_ack` argument on that tool call. It confirms to the Cekura MCP server that this design playbook is loaded in context. Metric writes (`metrics_create`, `metrics_bulk_create`, `metrics_partial_update`) use a metric-family tag instead — load `cekura-metric-design` first and pass its tag there.

Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="cekura-infra-test-suite"`, `verification_tag="ack:cekura-infra-test-suite:2h6r7k"`, and `plugin_version="0.11"`. It returns immediately and lets Cekura see which skills are in use.

# Cekura Voice AI Infrastructure Test Suite

Read the stack, analyze every layer, inventory what to test, design the plan, then build and run — in that order.

```
Phase 1          Phase 2          Phase 3          Phase 4          Phase 5
Explore      →   Analyze      →   Inventory    →   Design       →   Build & Run
Read code         Deep-dive         Enumerate        Compact          Create Cekura
to find           each layer,       every test        test plan,       scenarios +
all              extract exact     item from         evaluation        write CI
components        values +          the analysis      criteria,         run script
                  code refs                           get approval
```

## The 5 Phases

| Phase | File | What happens |
|---|---|---|
| 1 — Explore the Stack | [phase1-explore.md](phase1-explore.md) | Survey the codebase: identify transport, STT, LLM, TTS, VAD, and all pipeline components; answer Q1–Q11 |
| 2 — Analyze Each Layer | [phase2-analyze.md](phase2-analyze.md) | Deep-read each layer; extract exact values, class names, config keys, and code refs; write to `/tmp/infra-workflow-descriptions.md` |
| 3 — Inventory What to Test | [phase3-inventory.md](phase3-inventory.md) | Derive every testable behavior from the analysis — happy paths, boundaries, failures, cross-component interactions; write to `/tmp/infra-test-list.md` |
| 4 — Design the Test Plan | [phase4-plan.md](phase4-plan.md) | Ask config-change question; group TEST-NNN items into compact scenarios; write evaluation criteria (metrics + expected outcomes) in plain English to `/tmp/infra-test-plan.md` |
| 5 — Build and Run | [phase5-build-run.md](phase5-build-run.md) | Create Cekura scenarios from the plan; write a CI run script batched by configuration with readiness gating and per-scenario timeout |

---

## Ground Rules

### Rule 1 — Discover before designing. No exceptions.

Read the codebase before proposing any scenarios. A test suite designed without reading the code will include tests for things that don't exist and miss things that do.

### Rule 2 — Only test what's there.

If the codebase has no DTMF processor, there is no DTMF test. If there is no idle timer, there is no idle escalation test. A 4-scenario suite that covers the actual infra is better than an 8-scenario suite with 4 dead tests.

### Rule 3 — Confirm before creating.

Present the discovery results and proposed suite as a checkpoint. Do not create evaluators on Cekura until the user confirms the plan. Getting this wrong wastes credits and requires rework.

### Rule 4 — Test what's observable from the transcript.

Evaluator metrics can only see what appears in the call transcript. Never write expected outcomes that reference internal processor names (`LLMRetryProcessor`, `UserIdleHandler`) or internal code state. If it isn't in the transcript, it can't be evaluated.

### Rule 5 — All scenarios use conditional actions. Always.

Every scenario in this suite must be created using `scenario_type: "conditional_actions"`. Use the **cekura-eval-design** skill to author each one — it has the full XML tag reference, placement rules, and anti-patterns. Never use behavioral instructions for infra tests; they are not deterministic enough to reliably trigger pipeline behaviors at the right moment.

### Rule 6 — All scenarios live in the "Infrastructure Test Suite" folder.

Before creating any scenario, create a folder named `"Infrastructure Test Suite"` using `mcp__cekura__scenarios_folder_create`. Every scenario must be placed in this folder. Never create infra scenarios in the root.

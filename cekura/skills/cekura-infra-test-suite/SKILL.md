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

# Cekura Voice AI Infrastructure Test Suite

Discover the stack, describe each workflow, map to tests, confirm, then build — in that order.

```
Phase 1        Phase 2        Phase 3        Phase 4        Phase 5
Discover   →   Describe   →   Map       →   Create     →   Orchestrate
Read code       Write          Component     Cekura         Run script +
to find         workflow       → test         evaluators     CI override
components      descriptions   table          + metrics      for local bot
               to temp file
```

## The 5 Phases

| Phase | File | What happens |
|---|---|---|
| 1 | [phase1-discover.md](phase1-discover.md) | Read the codebase to identify transport, STT, LLM, TTS, and all pipeline processors |
| 2 | [phase2-describe.md](phase2-describe.md) | Write a detailed description of each discovered workflow — triggers, constraints, what the test can control, what's observable — to `/tmp/infra-workflow-descriptions.md` |
| 3 | [phase3-map.md](phase3-map.md) | Read the workflow descriptions, map each to the right Cekura test pattern; confirm suite plan with user |
| 4 | [phase4-create.md](phase4-create.md) | Create evaluators on Cekura with conditional actions and attach metrics |
| 5 | [phase5-orchestrate.md](phase5-orchestrate.md) | Generate a run script and CI override mechanism for local bot testing |

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

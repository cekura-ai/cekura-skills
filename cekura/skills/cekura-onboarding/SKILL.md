---
name: cekura-onboarding
description: >
  Use when the user says "get started with Cekura", "set up Cekura", "onboard to Cekura",
  "I'm new to Cekura", "help me set up my agent", "how do I use Cekura",
  "walk me through Cekura", "configure my project", "first time using Cekura",
  or needs guidance on initial platform setup. Covers two onboarding paths:
  **testing** (default — build evaluators and run simulated calls) and
  **observability** (ingest production call logs and evaluate them).
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.4.0"
---

# Cekura Platform Onboarding

Walk a new user from account to their **first verified result** — a completed test call with a visible transcript (testing) or a scored production call (observability).

## The One Principle

**Keep onboarding minimal, but it may only end at a verified working loop — never at "records created".**

- Minimal: one high-leverage connection step per provider; everything else (SDK, mock tools, KB, dynamic variables, custom metrics) is deferred to after the first result.
- Verified: onboarding is NOT done when the agent/scenario rows exist. It is done when one test call completed and its transcript is visible (testing), or one call log is ingested and scored (observability). A misconfigured SIP endpoint or unsupported phone number must surface *during* onboarding, not days later.

## Two Paths

Both paths share Phases 0–2 (path choice, account/project, agent) and diverge after that:

- **Testing** *(default)* — generate evaluators, run them against the agent in simulation, review results.
- **Observability** — ingest production call logs, attach metrics, evaluate, review/vote.

## Execution Model — Read This First

This skill executes **one phase at a time, in order**. For each phase:

1. Announce: "Starting Phase N — [name]".
2. **Read the phase file** (`phaseN-*.md` in this skill directory). Do not rely on memory of its contents.
3. Complete every task in the file and satisfy its gate condition.
4. Announce: "Phase N complete." and move to the next phase without waiting for the user.

Several phases delegate to files in the sibling **cekura-create-agent** skill (`../cekura-create-agent/…`). When a phase file tells you to read one of those, follow only the referenced guidance — **ignore that file's own phase gates and "continue to Phase N+1" instructions**; return to this skill's flow.

## The Phases

| Phase | File | What happens | Path |
|-------|------|--------------|------|
| 0 | [phase0-path.md](phase0-path.md) | Pick testing vs observability; survey existing project state | shared |
| 1 | [phase1-account-project.md](phase1-account-project.md) | Account access, API key/OAuth, project | shared |
| 2 | [phase2-agent.md](phase2-agent.md) | Create/connect the agent — provider-first, minimal, validated | shared |
| 3T | [phase3-testing-metrics.md](phase3-testing-metrics.md) | Enable pre-defined metrics | testing |
| 4T | [phase4-testing-evaluators.md](phase4-testing-evaluators.md) | Generate first evaluators (generation-first) | testing |
| 5T | [phase5-testing-first-run.md](phase5-testing-first-run.md) | First test run + **verification gate** | testing |
| 6T | [phase6-testing-next.md](phase6-testing-next.md) | What's next (SDK, mock tools, custom metrics) | testing |
| 3O | [phase3-observability-ingest.md](phase3-observability-ingest.md) | Ingest call logs + **verification gate** | observability |
| 4O | [phase4-observability-metrics.md](phase4-observability-metrics.md) | Configure starter metrics | observability |
| 5O | [phase5-observability-evaluate.md](phase5-observability-evaluate.md) | Run metric evaluation | observability |
| 6O | [phase6-observability-review.md](phase6-observability-review.md) | Review results, collect votes, what's next | observability |

## Performing Platform Actions

Prefer the platform tools over describing API calls or dashboard steps — actually call the tool. If a call fails, fix the cause or ask for the missing input, then retry; never claim a step is done until the call succeeds.

### Never invent IDs

Every agent ID, scenario ID, call log ID, metric ID, and run ID comes from a real tool response. If you don't have an ID, call the relevant list/retrieve tool. Provider-side identifiers (VAPI assistant IDs, API keys, webhook URLs) come from the user — never guess.

## Documentation

- Public docs: https://docs.cekura.ai
- LLM-friendly docs: https://docs.cekura.ai/llms.txt
- Integrations: https://docs.cekura.ai/documentation/integrations/
- `references/api-quickstart.md` — essential endpoints used during onboarding.

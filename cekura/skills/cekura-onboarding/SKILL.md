---
name: cekura-onboarding
description: >
  Use when the user says "get started with Cekura", "set up Cekura", "onboard to Cekura",
  "I'm new to Cekura", "help me set up my agent", "how do I use Cekura",
  "walk me through Cekura", "configure my project", "first time using Cekura",
  or needs guidance on initial platform setup. Covers three onboarding paths:
  **testing** (default — build evaluators and run simulated calls),
  **observability** (ingest production call logs and evaluate them), and
  **integrate** (wire the user's own voice-agent codebase into Cekura end to end).
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.5.1"
---

# Cekura Platform Onboarding

Walk a new user from account to their **first verified result** — a completed test call with a visible transcript (testing), a scored production call (observability), or one real/simulated call flowing end to end through a wired codebase (integrate).

## The One Principle

**Keep onboarding minimal, but it may only end at a verified working loop — never at "records created".**

- Minimal: one high-leverage connection step per provider; everything else (SDK, mock tools, KB, dynamic variables, custom metrics) is deferred to after the first result.
- Verified: onboarding is NOT done when the agent/scenario rows exist. It is done when one test call completed and its transcript is visible (testing), or one call log is ingested and scored (observability). A misconfigured SIP endpoint or unsupported phone number must surface *during* onboarding, not days later.

## Three Paths

All paths share Phases 0 and 2 (path choice, agent connection) and diverge after that. **The first objective is always connecting the agent** — there is no separate account/project phase: working tools prove auth, and a missing project is handled inline (`projects_list` / `projects_create`) on the way into Phase 2.

- **Testing** *(default)* — generate evaluators, run them against the agent in simulation, review results.
- **Observability** — ingest production call logs, attach metrics, evaluate, review.
- **Integrate** — wire the user's own voice-agent codebase into Cekura end to end (config sync, transcript ingestion, per-call metadata, tracing, CI/CD), then verify one call flows through. This path hands off to the `custom-integrate` skill and the phase skills it coordinates.

## Execution Model — Read This First

This skill executes **one phase at a time, in order**. For each phase:

1. Announce the step in plain words (e.g. "Let's connect your agent") — phase numbers are internal navigation, never user-facing.
2. **Read the phase file** (`phaseN-*.md` in this skill directory). Do not rely on memory of its contents.
3. Complete every task in the file and satisfy its gate condition.
4. Confirm the step in plain words and move on without waiting for the user (no "Phase N complete").

**Ask questions ONLY to collect missing inputs or resolve genuine ambiguity** (provider choice, credentials, phone number, self-hosted confirmation). Never ask permission to continue, never confirm an action the flow already implies — the user invoked onboarding, so creating the agent, enabling metrics, generating evaluators, and starting the first verification run are all pre-authorized. No "ready to continue?", no "shall I create it?", no "want me to proceed?" — just do the step and narrate it. The one exception: when a **gate is blocked** (e.g. the testing-path description gate) present the blocker and the options.

**Onboarding is self-contained.** Do NOT open the sibling cekura-create-agent skill (or any other skill) during onboarding — everything needed (credential matrix, description quality bar) is inlined in this skill's phase files. cekura-create-agent's phase sequence covers post-onboarding work (SDK integration, mock tools, knowledge base) and running it mid-onboarding hijacks the flow into those steps; it is a Phase-6 handoff only.

> **Exception — the integrate path.** Phase 3C is itself a handoff: it deliberately opens the `custom-integrate` skill, because wiring a whole codebase into Cekura is that skill's job, not something to inline here. This is the one place onboarding hands off to a sibling skill mid-flow, and it does so on purpose. Shared Phases 0 and 2 still run first (self-contained as usual); only Phase 3C delegates.

## The Phases

| Phase | File | What happens | Path |
|-------|------|--------------|------|
| 0 | [phase0-path.md](phase0-path.md) | Pick testing / observability / integrate; ONE `aiagents_list` call to detect existing work | shared |
| 2 | [phase2-agent.md](phase2-agent.md) | Create/connect the agent — provider-first, minimal, validated | shared |
| 3T | [phase3-testing-metrics.md](phase3-testing-metrics.md) | Verify default metrics (auto-enabled at project creation) | testing |
| 4T | [phase4-testing-evaluators.md](phase4-testing-evaluators.md) | Generate first evaluators (generation-first) | testing |
| 5T | [phase5-testing-first-run.md](phase5-testing-first-run.md) | First test run + **verification gate** | testing |
| 6T | [phase6-testing-next.md](phase6-testing-next.md) | What's next (SDK, mock tools, custom metrics) | testing |
| 3O | [phase3-observability-ingest.md](phase3-observability-ingest.md) | Ingest call logs + **verification gate** | observability |
| 4O | [phase4-observability-metrics.md](phase4-observability-metrics.md) | Configure starter metrics | observability |
| 5O | [phase5-observability-evaluate.md](phase5-observability-evaluate.md) | Run metric evaluation | observability |
| 6O | [phase6-observability-review.md](phase6-observability-review.md) | Review results, what's next | observability |
| 3C | [phase3C-integrate.md](phase3C-integrate.md) | Hand off to `custom-integrate`, auto-toggle `transcript_provider`, + **verification gate** | integrate |

*(There is no Phase 1 — the old account/project phase is retired; client/OAuth setup lives in [references/client-setup.md](references/client-setup.md) as a fallback and phase numbering is kept stable.)*

## Performing Platform Actions

Prefer the platform tools over describing API calls or dashboard steps — actually call the tool. If a call fails, fix the cause or ask for the missing input, then retry; never claim a step is done until the call succeeds.

### Never invent IDs

Every agent ID, scenario ID, call log ID, metric ID, and run ID comes from a real tool response. If you don't have an ID, call the relevant list/retrieve tool. Provider-side identifiers (VAPI assistant IDs, API keys, webhook URLs) come from the user — never guess.

## Documentation

- Public docs: https://docs.cekura.ai
- LLM-friendly docs: https://docs.cekura.ai/llms.txt
- Integrations: https://docs.cekura.ai/documentation/integrations/
- `references/api-quickstart.md` — essential endpoints used during onboarding.

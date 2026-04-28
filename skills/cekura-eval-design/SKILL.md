---
name: cekura-eval-design
description: >
  Use when the user asks to "create an evaluator", "write a test scenario", "design a test case",
  "build eval coverage", "plan a test suite", "test my agent", "create red team tests",
  "write workflow tests", "improve eval quality", "what evals do I need", "create test profiles",
  "conditional actions", or "run evals". Covers evaluator design, test coverage strategy,
  scenario instructions, expected outcomes, personality selection, test profiles, conditional
  actions, execution modes, and best practices for voice AI agent evaluators.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Eval Design

## Purpose

Guide the creation of effective evaluators (test scenarios) that thoroughly exercise an AI voice agent. Evaluators simulate callers to test the main agent — they are NOT metrics (which evaluate transcripts after the fact).

## Core Terminology

- **Main agent** — The client's AI voice agent being tested
- **Testing agent** — Cekura's simulated caller that exercises the main agent
- **Evaluator / Scenario** — A test case defining what the simulated caller does and what success looks like
- **Personality** — Voice, language, accent, and behavioral traits for the simulated caller
- **Test Profile** — Identity and context data passed to the testing agent and main agent (for chat/websocket runs)
- **Conditional Action** — Structured, deterministic testing-agent behavior with adaptive fallback
- **Metric** — A post-call evaluation that scores the transcript (different concept — see `cekura-metric-design`)

## The Eval Design Workflow

1. **Understand the agent** — Read the agent description to identify all workflows, decision points, and edge cases
2. **Choose a tool strategy** — How will the agent's external tool calls be handled during tests? (See "Tool Strategy" below)
3. **Always create a folder first** — Before generating scenarios, create a folder to organize them. Don't dump scenarios into the root.
4. **Run the pre-creation checkpoint** — Confirm key decisions with the user before building anything
5. **Start with auto-generation** — Use the platform's scenario generator with category-level guidance. If using Cekura mock tools, the generator creates tool-aware scenarios automatically.
6. **Review generation artifacts** — Fix scenario language for non-English agents, fix first-message greetings if auto-gen added them, check for partial completion
7. **Supplement manually** — Add edge cases, red-team scenarios, and deterministic tests the generator doesn't cover
8. **Set up test infrastructure** — Check existing test profiles first, then create new ones. Configure tool data per the chosen strategy.
9. **Attach metrics** — ALWAYS include baseline metrics on every evaluator (Expected Outcome, Infrastructure Issues, Tool Call Success, Latency). Without metrics, runs only report call completion, not correctness.
10. **Run and validate** — Execute the suite, review transcripts, iterate

## Tool Strategy — Three Approaches

Ask the user early: "Does your agent call external tools during calls? If so, how do you want to handle tool data for testing?"

### Approach A: Client-Side Mock Data

The client manages their own mock backend (staging API, test database). Cekura doesn't mock the tools — the agent calls the real (staging) endpoints. Your job is to **align test profiles with the client's mock data** so the agent gets expected responses.

**Use when:** Client already has a staging environment, doesn't want to replicate data, or tool behavior is too complex to mock.

### Approach B: Cekura Mock Tools

Cekura intercepts tool calls and returns pre-configured mock responses. The agent never hits a real backend. Your job is to **set up mock tool mappings and ensure test profiles match the mock outputs**.

**Use when:** No staging environment, want fully isolated tests, need predictable responses, or tools are simple enough to mock (lookups, bookings, CRUD).

**Workflow:**
1. Auto-fetch tool definitions from supported providers (recommended)
2. Review the auto-fetched mappings — illustrative examples only
3. Add per-scenario mappings with the specific input/output pairs each scenario needs
4. Each variant of input parameters needs its own mapping

### Approach C: Hybrid

Some tools mocked by Cekura, others left as real calls to staging. Pick the right approach per tool — typically mock the simple lookup tools and let complex stateful operations hit staging.

## Eval Categories — Build Coverage Across All

A complete test suite covers:

| Category | Purpose |
|---|---|
| **Workflow / Happy path** | The main flows the agent supports, executed correctly |
| **Edge case** | Boundary conditions, unusual inputs, ambiguous scenarios |
| **Red team / Adversarial** | Attempts to break the agent, jailbreak it, or extract bad behavior |
| **Tool failure** | What happens when a tool returns an error, times out, or returns unexpected data |
| **Multi-language** | Coverage across all languages the agent supports |
| **Personality variations** | Different caller demeanors, accents, speaking speeds |
| **Deterministic / Unit** | Specific inputs that should produce specific outputs (use Conditional Actions) |

## Conditional Actions

Use Conditional Actions for **deterministic** tests where the testing agent must say specific things in a specific order. Pure free-form scenarios drift; Conditional Actions enforce structure.

When to use:
- Testing exact wording or phrasing the user must say
- Verifying the agent handles a specific multi-turn sequence
- Reproducing a customer complaint exactly

When NOT to use:
- Open-ended quality testing (Conditional Actions over-constrain)
- Personality/style testing

## Expected Outcomes

Every scenario needs an expected outcome — the goal the testing agent is trying to achieve. Good outcomes are:

- **Specific** — "Successfully booked an appointment for next Tuesday at 3pm" not "Got help"
- **Achievable** — A real caller could plausibly accomplish this
- **Measurable** — Pass/fail can be determined from the transcript

## Test Profiles

Test profiles bundle identity + context that the testing agent uses (and the main agent receives, for chat/websocket runs):

- Customer name, phone number, email
- Account ID, order number, etc.
- Any data the agent might ask for to authenticate or look up records

**Critical:** Test profile data must match what the agent's backend expects. If the agent's database has user `john.doe@example.com`, the test profile must use that exact email.

## Auto-Generation Best Practices

The platform's scenario generator works well as a starting point but isn't sufficient on its own:

- **Provide category-level guidance** in `extra_instructions` — "Generate 5 scenarios covering appointment booking, 3 covering cancellation, 2 red-team attempts"
- **Set scenario language explicitly** for non-English agents — defaults to `en` regardless of agent language
- **Review first messages** — auto-gen sometimes adds greetings instead of exact opening questions
- **Check for partial completion** — generation may produce fewer than requested
- **Always supplement** — add red-team and edge cases manually

## Pre-Creation Checkpoint

Before creating scenarios, confirm with the user:
- Which workflows / decision points to cover
- Tool strategy chosen (A / B / C)
- Folder structure
- Number of scenarios per category
- Personalities to use
- Languages to cover

This 30-second checkpoint prevents rework.

## Best Practices

- **Pre-creation checkpoint always** — Confirm decisions before building
- **Folder organization always** — Never dump scenarios into the root
- **Baseline metrics on every evaluator** — Expected Outcome + Infrastructure Issues at minimum
- **Test profiles match backend data** — exactly, including format
- **Mix execution modes** — Voice for realism, text/websocket for fast iteration
- **Iterate on failures** — A failed test doesn't mean the agent is broken; sometimes the test was wrong

## Documentation

- Public docs: https://docs.cekura.ai
- Concepts: https://docs.cekura.ai/documentation/key-concepts/

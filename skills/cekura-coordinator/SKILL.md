---
name: cekura-coordinator
description: >
  Use when the user asks "what can Cekura do", "what commands are available",
  "help me with Cekura", "what skills do I have", "show me Cekura features",
  "what's available", "how do I use Cekura", or needs guidance on which Cekura
  skill to use for their task. Also relevant as the entry point when a user has
  just installed cekura-skills for the first time.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Coordinator

## Purpose

Route users to the right Cekura skill based on what they need. This is the "front desk" — it knows what's available across all Cekura skills and helps users find the right one for their task.

## When This Skill Loads

- User just installed cekura-skills and asks "what can I do?"
- User asks for help or doesn't know which skill applies
- User describes a task and you need to route them to a more specialized skill

## Available Skills

### cekura-onboarding
**When to use:** New to Cekura, first-time setup, end-to-end platform walkthrough.
Covers account setup, project creation, agent connection, first metrics, first evaluators, and first test run.

### cekura-create-agent
**When to use:** Connecting a voice AI agent to Cekura — provider integration, mock tools, knowledge base, dynamic variables.

### cekura-metric-design
**When to use:** Designing or creating metrics that evaluate call quality. Covers prompt patterns, metric types, eval types, and best practices.

### cekura-metric-improvement
**When to use:** A metric is producing wrong results and needs to be improved through feedback iteration.

### cekura-eval-design
**When to use:** Designing test scenarios (evaluators) that exercise the voice agent, planning test coverage, configuring test profiles and conditional actions.

## Routing Guide

| User need | Route to |
|---|---|
| "I'm new to Cekura" / first-time setup | `cekura-onboarding` |
| "Connect my voice agent" / "set up my agent" | `cekura-create-agent` |
| "Create a metric" / "evaluate call quality" | `cekura-metric-design` |
| "My metric is giving wrong results" | `cekura-metric-improvement` |
| "Test my agent" / "design a test scenario" | `cekura-eval-design` |
| "Generate test scenarios for me" | `cekura-eval-design` |
| "Set up production monitoring" | `cekura-onboarding` then `cekura-metric-design` |

## Typical User Journeys

### Journey 1: Brand New User
1. `cekura-onboarding` — Set up account, project, agent, first metrics, first evaluators, first test run
2. `cekura-metric-design` — Add custom metrics for specific workflows
3. `cekura-eval-design` — Build targeted test suites

### Journey 2: Has an Agent, Needs Testing
1. `cekura-eval-design` — Design test suite
2. Run tests via the Cekura platform
3. Review results and iterate

### Journey 3: Has Metrics, Needs Quality Improvement
1. `cekura-metric-improvement` — Collect feedback, iterate on metric prompts
2. Validate against sample calls

### Journey 4: Production Monitoring
1. `cekura-metric-design` — Design metrics for monitoring
2. Deploy on production calls
3. `cekura-metric-improvement` — Iterate as edge cases surface

## Documentation

- Public docs: https://docs.cekura.ai
- Dashboard: https://dashboard.cekura.ai
- Concepts overview: https://docs.cekura.ai/documentation/key-concepts/

---
name: cekura-onboarding
description: >
  Use when the user says "get started with Cekura", "set up Cekura", "onboard to Cekura",
  "I'm new to Cekura", "help me set up my agent", "how do I use Cekura",
  "walk me through Cekura", "configure my project", "first time using Cekura",
  or needs guidance on initial platform setup, agent configuration, first
  evaluators, or first metrics.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Platform Onboarding

## Purpose

Walk a new user through complete Cekura setup — from account creation to their first successful test run. This is an interactive, step-by-step guide. At each phase, confirm with the user before proceeding.

## How to Use This Skill

This is an **interactive walkthrough**, not a reference. Guide the user through each phase conversationally:

1. Ask where they are in the process — some may already have an account or agent
2. Skip phases they've already completed
3. Validate each step before moving to the next
4. Hand off to specialized skills (`cekura-metric-design`, `cekura-eval-design`) when appropriate

## Phase 1: Account & Project Setup

### 1.1 Verify Account Access

Ask:
- "Do you already have a Cekura account?"
- "Do you have an API key?"

If they don't have an account, direct them to https://dashboard.cekura.ai/sign-up.

### 1.2 Project Setup

Ask: "Do you already have a project, or do we need to create one?"

**Project organization guidance:**
- Small teams: a single project for multiple agents
- Larger orgs: separate projects by team and environment (staging vs production)
- Each project has its own metrics, evaluators, and observability data

## Phase 2: Agent Configuration

### 2.1 Create or Connect an Agent

Ask: "Do you already have a voice AI agent deployed? Which provider?"

For full agent setup (provider integration, mock tools, knowledge base, dynamic variables), hand off to the `cekura-create-agent` skill.

**Critical: Agent description is essential.** It powers automatic evaluator generation and grounds metrics that reference the agent's behavior. Always collect the full system prompt.

### 2.2 Provider Integration

Connect the agent's provider per the docs at https://docs.cekura.ai/documentation/integrations/. Each provider has its own setup flow in the Cekura dashboard.

### 2.3 Dynamic Variables (if applicable)

Ask: "Does your agent use dynamic variables — per-call data like customer names, account IDs, or configuration flags?"

If yes, document them so they can be referenced in metrics and test scenarios.

### 2.4 Mock Tools (if applicable)

Ask: "Does your agent call external APIs or tools during calls?"

If yes, configure mock tools in the dashboard so tests can run without hitting real backends. Cekura can auto-fetch tool definitions from supported providers.

## Phase 3: Metrics Setup

### 3.1 Enable Pre-defined Metrics

Recommend selecting **all pre-defined metrics** for comprehensive baseline analysis. Categories include:

- **Accuracy** — expected outcome, hallucination, relevancy, response consistency, tool call success, transcription accuracy, voicemail detection
- **Quality** — interruption counts, response latency, silence detection, call termination
- **Customer Experience** — CSAT, sentiment, dropoff nodes, topic categorization
- **Speech Quality** — pitch, speaking rate, gibberish detection, pronunciation

Two-step activation: metrics must be (1) enabled at the project level AND (2) attached to individual evaluators.

### 3.2 Custom Metrics (defer to later)

For first-time users, skip custom metrics initially. Once they have test results, the `cekura-metric-design` skill walks through creating targeted custom metrics.

## Phase 4: First Evaluators

### 4.1 Auto-Generate (Recommended)

The fastest path to first tests is auto-generation — use the dashboard's scenario generator to create 10 evaluators from the agent description. Specify:
- Number of scenarios
- Caller personality
- Whether to generate expected outcomes
- Which tools the agent has access to

### 4.2 Review and Supplement

Common gaps in auto-generated evaluators:
- Red-team / adversarial scenarios
- Edge cases specific to the client's domain
- Multi-language coverage
- Tool failure scenarios

The `cekura-eval-design` skill helps design more targeted evaluators.

### 4.3 Attach Metrics

Every evaluator needs metrics attached. At minimum:
- **Expected Outcome** — Did the agent achieve the scenario's goal?
- **Infrastructure Issues** — Connection drops, silence, non-response

## Phase 5: First Test Run

### 5.1 Execute

Start with **5–10 scenarios** for the first run. Voice calls take 1–3 minutes each.

### 5.2 Review Results

Each run includes a transcript, audio recording, metric scores, and pass/fail on the expected outcome.

Guide the user through interpreting results:
- **70–80% pass rate** is realistic for a first iteration
- Review failures to identify misunderstandings, missing info, or technical issues
- **90–95%** after refinement is a healthy target
- Don't aim for 100% — real conversations are unpredictable

## Phase 6: What's Next

After the first successful test run:

| Need | Skill |
|---|---|
| Better metrics | `cekura-metric-design` |
| More evaluators | `cekura-eval-design` |
| Improve metric accuracy | `cekura-metric-improvement` |
| Production monitoring | Observability docs at https://docs.cekura.ai |

## Documentation

- Public docs: https://docs.cekura.ai
- Dashboard: https://dashboard.cekura.ai
- Integrations: https://docs.cekura.ai/documentation/integrations/

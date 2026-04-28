---
name: cekura-metric-design
description: >
  Use when the user asks to "create a metric", "write a metric", "design a metric",
  "build a metric for", "evaluate agent performance", "measure call quality", "track a KPI",
  "add a workflow metric", "set up quality scoring", or "what metrics do I need".
  Also relevant when discussing LLM judge prompts, custom code metrics, evaluation
  triggers, or metric best practices for voice AI agents. Covers creating new
  metrics and reviewing or troubleshooting existing ones.
license: MIT
compatibility: Designed for Claude Code. Requires a Cekura account and API key (https://dashboard.cekura.ai).
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Metric Design

## Purpose

Guide the creation of effective metrics that accurately evaluate AI voice agent call quality. Metrics measure call quality after the fact by evaluating transcripts against defined criteria. Each metric targets a specific workflow or KPI that needs tracking per call.

## Core Terminology

- **Main agent** — The client's AI voice agent being tested
- **Testing agent** — Cekura's simulated caller that exercises the main agent
- **Metric** — A post-call evaluation that scores a transcript
- **Evaluator / Scenario** — A test case that simulates a caller (different concept — see `cekura-eval-design`)

## The Metric Creation Workflow

Follow this workflow every time. Skipping steps — especially step 2 — leads to metrics that miss edge cases.

1. **Gather context** — Understand the client's use case, what they care about, and get sample conversation IDs with expected outcomes
2. **Fetch real transcripts** — Pull 3–5 actual transcripts. Study what roles appear, what timestamps are available, how tool calls are structured, and what conversation flow looks like in practice. Metrics written without reading real data miss edge cases.
3. **Identify the signal** — What specific thing in the transcript indicates pass vs fail? A tool call, a timestamp gap, a phrase, a behavioral pattern?
4. **Write the prompt** — Use proven structures (below), grounded in what real transcripts look like
5. **Deploy and test** — Create the metric, run on sample conversations, compare to expected outcomes
6. **Iterate** — Adjust the prompt based on results. Plan for at least one iteration — the first run reveals measurement issues.

## Metric Types

### llm_judge (preferred default)

An LLM evaluates a natural-language prompt against the call transcript. **Prefer `llm_judge` over `custom_code`.**

Custom code seems appealing for "objective" checks (timestamps, tool call presence) but is brittle in practice. Voice AI transcripts have messy timing — agents transfer mid-tool-chain, background tasks complete after speech resumes, timestamps overlap. An LLM reading the transcript handles these nuances naturally.

Express measurements in natural language, not code.

### custom_code (Python)

Reserve for cases that genuinely need programmatic logic:
- Gating on upstream metric results
- Section extraction from agent description
- Multiple LLM calls with different prompts based on conditions
- N/A short-circuiting before calling the LLM

## Metric Evolution Path

Start as `llm_judge` for rapid iteration. Once the prompt is validated, optionally convert to `custom_code` with section extraction for production. The Cekura platform allows a metric to have both forms — the active type is toggled.

## Eval Types

| Eval type | Output | Use for |
|---|---|---|
| `binary_qualitative` | TRUE/FALSE | Soft skills, quality assessments |
| `binary_workflow_adherence` | TRUE/FALSE | Flow compliance checks |
| `enum` | String from a defined list | Classification tasks |
| `numeric` | Float score | Scoring tasks |
| `continuous_qualitative` | Continuous score | Continuous quality assessment |

## LLM Judge Prompt Structure

Two proven structures.

### Structure A: Sectioned (best for multi-criteria metrics)

1. **SCOPE & FOCUS** — What this metric evaluates ONLY, plus what to IGNORE
2. **DO NOT FLAG** — Common false positives: behavioral patterns that look like fails but aren't for THIS metric
3. **INPUTS** — Only the relevant template variables
4. **SECTIONS** — Numbered evaluation criteria with pass/fail examples
5. **FAILURE CONDITIONS (Only These Count)** — Narrow, closed list of what constitutes a failure
6. **SAFEGUARDING NOTES** — Spirit-vs-letter overrides

### Structure B: Single-criterion (best for one-off checks)

A focused prompt with: scope, criterion, what counts as pass, what counts as fail, edge cases.

## Best Practices

### Be Narrow

Each metric should answer **one** question. Bundling unrelated checks into a single metric makes results uninterpretable.

### Define N/A Explicitly

Many calls won't match the metric's scope (the workflow didn't trigger, the topic didn't come up). The prompt must define when to return N/A vs PASS vs FAIL.

### Ground in Real Transcripts

Examples in the prompt should come from real transcripts, not hypothetical conversations.

### Use Template Variables

Reference per-call data — agent description, dynamic variables, conversation context — via template variables. This keeps the prompt generic across agents.

### Iterate

The first version of a metric is rarely the final version. Use the `cekura-metric-improvement` skill once feedback accumulates.

## Common Anti-Patterns

| Anti-pattern | Why it fails | Fix |
|---|---|---|
| Vague scope ("evaluate quality") | Metric flags everything that looks bad | Narrow to one specific thing |
| No false-positive guard | Common patterns get flagged as fails | Add "DO NOT FLAG" section |
| Writing without reading transcripts | Metric assumes wrong structure | Read 3–5 real transcripts first |
| Custom code for fuzzy logic | Timestamps don't behave deterministically | Use LLM judge with natural language |
| One mega-metric covering 5 things | Can't tell what failed | Split into separate metrics |

## Documentation

- Public docs: https://docs.cekura.ai
- Metrics concepts: https://docs.cekura.ai/documentation/key-concepts/

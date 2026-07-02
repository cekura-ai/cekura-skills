---
name: cekura-backfill-mock-manifests
description: >
  Use when a Cekura evaluator, especially a manually authored conditional-actions / structured /
  scripted scenario, needs expected mock tool calls (`generated_mock_tool_entries`) and matching
  Cekura mock-tool data created, backfilled, repaired, or validated. Trigger when users ask to
  backfill mock manifests, add expected mock calls, backfill tool input/output for manual scenarios,
  fix missing mock data after scenario creation, align test profiles with mock outputs, or prevent
  manually authored Cekura scenarios from being blindsided by absent mock tool manifests. This is
  a companion to cekura-eval-design; use it after or during scenario creation, not for general
  evaluator coverage planning.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

# Cekura Backfill Mock Manifests

## Purpose

Populate a scenario's **expected mock tool calls** (the `generated_mock_tool_entries` field; this skill's shorthand for it is the *mock manifest*) when it has none, and make sure they line up with the agent's mock tools and test profile.

Know what this field is and isn't:

- **Mock responses during a simulated call are served by the agent's mock tools, not by this field.** If the agent has mock tools configured, calls get mocked regardless of whether expected mock tool calls are set. Designing those mock tools + the test profile is `cekura-eval-design`'s job.
- **The expected mock tool calls are the record used for scoring/observability** — the *Mock tool call accuracy* metric and the per-run resolved-calls record read them to know which tool calls *should* have happened. Without them, that metric has nothing to grade against.

**Only the platform's server-side auto-generation populates this field.** Scenarios created any other way — an agent following `cekura-eval-design`, a human authoring conditional actions in the dashboard, a CSV/bulk import — get working mocks and a test profile but **no expected mock tool calls**. This skill backfills them for those scenarios.

Use this skill narrowly. It owns one step: **populating a scenario's expected mock tool calls (and reconciling them with the agent's mock data / test profile) when it was authored outside auto-generation.**

## Scope and Companion Skill

This skill does **not** re-teach how to design coherent mock data. That lives in `cekura-eval-design` (its `references/test-data-design.md`), which is the single source of truth for:

- Designing mock tool data, the test profile, and dynamic variables as one cohesive set.
- The `main_agent_variables` vs `testing_agent_variables` split.
- All-or-nothing reuse of an existing identity.
- The cardinality / validation-failure / not-found / logic-first-PII data patterns.

**Load `cekura-eval-design` first and design the data there.** This skill picks up once that data is designed and covers only the manifest-specific work: inferring which tool calls a manual scenario should trigger, assembling and attaching `generated_mock_tool_entries`, and verifying it matches the agent's mock data.

For general scenario design, conditional-action syntax, expected outcomes, personalities, metrics, folders, and run strategy, use `cekura-eval-design`.

## Required Context

Before changing anything, gather:

- The scenario draft or existing scenario ID(s).
- The Cekura agent ID and project ID.
- The agent's current mock tools and tool definitions.
- The scenario's `conditional_actions`, `expected_outcome_prompt`, `test_profile`, `tool_ids`, and metrics.
- Existing test profiles and existing mock entries for the project/agent.

If the scenario is not already a conditional-actions evaluator, do not convert it as part of this skill unless the user explicitly asks. Use `cekura-eval-design` first.

## Workflow

1. **Load companion guidance.** Read `cekura-eval-design` (especially `references/test-data-design.md`) for the scenario type and the mock-data / test-profile design rules, then read `references/workflow.md` in this skill for the manifest hydration procedure.
2. **Inspect the scenario.** Retrieve the existing scenario; for drafts, inspect the payload directly. Confirm `scenario_type: "conditional_actions"` and validate the required fields on every condition.
3. **Infer expected tool calls.** From the scenario, expected outcome, and agent description, identify each tool the main agent should call, its expected input, and the output needed to drive the scenario path — including call order when tools depend on one another.
4. **Design or reuse the backing data per `cekura-eval-design`.** Follow `test-data-design.md` to produce coherent mock entries and a matching test profile. Do not re-derive those rules here.
5. **Assemble the manifest.** Build one `generated_mock_tool_entries` entry per exercised tool, each carrying the exact input/output that will be present in the agent's mock data.
6. **Patch agent mock tools safely.** Fetch existing tools, merge new entries, and write the full mock-tools list. Preserve every existing tool's `id`, name, description, `freetext_params`, `served_via`, and existing mock data.
7. **Attach the manifest via REST.** Set `generated_mock_tool_entries` with `PATCH /test_framework/v1/scenarios/{id}/`. This field is not part of the scenario create/update request schema, so it can only be set through the REST scenario endpoint — see `references/workflow.md`.
8. **Verify.** Retrieve the agent, test profile, and scenario again. Confirm the scenario manifest exactly matches the entries present in the agent's mock data and the values referenced by the test profile.

## Guardrails

- Do not write mock entries independently from the test profile. That is the failure mode this skill exists to prevent.
- Do not mix identities across tools. If tool A uses one identity and tool B uses another, build one coherent data graph instead.
- Do not write a partial mock-tools list. Cekura replaces the whole list — send every tool you want to keep.
- Do not overwrite user-authored scenario conditions while adding mock manifests.
- Do not enable provider mock mode or toggle live provider configuration unless the user explicitly asks.
- Do not add or enable metrics as part of this skill. Populating expected mock tool calls does not require the *Mock tool call accuracy* metric to be on, and the record still feeds the resolved-calls data and observability without it. Enabling that metric is the user's choice — leave metric selection to `cekura-eval-design`.
- Every manifest `tool_id` must belong to the scenario's own agent, or the write is rejected. Reuse the agent's existing tool IDs.
- Ask one concise clarification if the expected tool name, required input schema, or success path is ambiguous enough that a wrong mock would produce a false pass.

## API Access

**Prerequisites:** Cekura account + API key or OAuth.

For Claude Code plugin users, platform tools are auto-configured. If platform operations aren't working, run `/setup-mcp` to configure the connection. For other clients, use the Cekura dashboard or call the API directly — **all Cekura API calls use `X-CEKURA-API-KEY: <key>` as the auth header.**

## Reference Files

- **`references/workflow.md`** — data model, write paths for the manifest and agent mock data, validation checklist, and failure handling.

**Docs:** https://docs.cekura.ai/documentation/key-concepts/ | https://docs.cekura.ai/mcp/overview

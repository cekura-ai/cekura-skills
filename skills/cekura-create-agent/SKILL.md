---
name: cekura-create-agent
description: >
  Use when the user asks to "create an agent", "set up an agent", "add my agent to Cekura",
  "configure my voice agent", "connect my agent", "set up mock tools", "add tools to my agent",
  "upload knowledge base", "configure integration", "add dynamic variables", or
  "set up agent connection". Covers the full agent setup flow: collecting context,
  creating the agent, configuring the provider integration, setting up mock tools,
  uploading knowledge base files, and adding dynamic variables.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

# Cekura Create Agent

## Purpose

Collect the context needed for a client's voice AI agent and connect it to Cekura — ready for testing and observability. This is an interactive, multi-step flow that creates the agent, configures provider integration, sets up mock tools, uploads knowledge base files, and adds dynamic variables.

## How to Use This Skill

This is an **interactive collection-and-configuration flow**. Walk the user through each phase:

1. Collect information conversationally — ask for what you need, don't dump a form
2. Validate each step before moving to the next
3. The user may already have some steps done — skip what's complete

## Phase 1: Collect Agent Context

### 1.1 Basic Information

Ask for:
- **Agent name** — Descriptive (e.g., "Customer Support Bot", "Scheduling Assistant")
- **Project** — Which Cekura project to add the agent to. If they don't know, list their projects first.
- **Language** — Primary language (default `en`). Many languages supported — see the dashboard for the full list.
- **Inbound vs Outbound** — Does the agent receive calls or make them?

### 1.2 Agent Description (Critical)

The agent description is the **most important field**. It powers:
- Automatic evaluator generation
- Metrics that reference agent behavior
- Topic and dropoff classification
- Hallucination detection

**Collect the full system prompt.** Ask:
- "Can you paste your agent's full system prompt or description?"
- "If your agent has multiple states or nodes, paste the complete configuration."

If the description is very long, that's fine — Cekura handles it. Don't truncate.

### 1.3 Contact Number (for phone-based agents)

Format: international (`+1234567890`). This is the number Cekura will call for testing. WebRTC/WebSocket-only agents can skip this.

## Phase 2: Create the Agent

Once you have the basics, create the agent in Cekura with the name, project, language, description, contact number, and inbound flag. Confirm the resulting agent ID with the user.

## Phase 3: Provider Integration

Configure the agent's provider integration in the dashboard. Each supported provider has its own credentials and setup flow — refer the user to https://docs.cekura.ai/documentation/integrations/ for the specific provider's instructions.

Common credentials needed:
- Provider API key
- Assistant or agent ID on the provider's side

## Phase 4: Mock Tools (if applicable)

If the agent calls external APIs or tools during calls, set up mock tools so tests can run without hitting real backends.

**Two approaches:**

1. **Auto-fetch (recommended)** — For supported providers, Cekura pulls tool definitions from the provider and generates sample input/output data automatically. Then enable mock mode per tool.

2. **Manual** — Add tool names, descriptions, and input/output mappings by hand. Good for unusual or complex tools.

For each tool the agent uses, configure:
- Tool name and description
- Sample inputs (what the agent might pass)
- Sample outputs (what the tool returns)

The `cekura-eval-design` skill covers per-scenario mock data design in depth.

## Phase 5: Knowledge Base (if applicable)

If the agent uses knowledge base files (FAQs, policies, product info), upload them to the agent in Cekura. Supported formats include PDFs, text, and structured docs — see the dashboard for current formats.

Upload guidance:
- Keep files focused — one topic per file when possible
- Update files as the agent's knowledge changes
- Knowledge base content informs metrics that check for accuracy and hallucination

## Phase 6: Dynamic Variables (if applicable)

If the agent uses per-call dynamic variables (customer names, account IDs, configuration flags), define them so they can be:
- Passed in during test runs
- Referenced in metrics and test scenarios

Cekura auto-detects `{{variableName}}` patterns in the agent description.

## Phase 7: Validate

After setup:
1. Pull the agent record and verify all fields are correct
2. Run a single test scenario to confirm the integration works end-to-end
3. Review the transcript and tool calls to verify mock tools fire correctly

Hand off to `cekura-eval-design` for building a real test suite.

## Documentation

- Public docs: https://docs.cekura.ai
- Integrations: https://docs.cekura.ai/documentation/integrations/
- Dashboard: https://dashboard.cekura.ai

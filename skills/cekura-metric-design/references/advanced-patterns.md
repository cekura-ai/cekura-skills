# Advanced Metric Design Patterns

Patterns that build on the core metric design workflow in `SKILL.md`. Read these when designing metrics that involve dynamic variables, tool-call correctness, or multi-flow agents.

## Anti-Cross-Pollination Scoping (Critical for `{{agent.description}}` metrics)

When a metric uses `{{agent.description}}`, the LLM reads the entire description and can fail based on rules from unrelated flows. For example, an Emergency metric fails because the agent didn't follow a Booking Flow rule. **This is the most common source of false failures.**

**Three-layer scoping pattern (mandatory when using `{{agent.description}}`):**

1. **SCOPE & FOCUS** — Explicit "evaluates X ONLY" + "IGNORE all non-X rules in the agent description" with a concept-level explanation of what other flows exist and are covered by other metrics.
2. **DO NOT FLAG THESE** — Enumerated list of common false positives specific to this metric. Named by behavioral pattern (e.g., "Standard booking steps not followed"), not by agent-specific section names.
3. **FAILURE CONDITIONS (Only These Count)** — Narrow, closed list of what actually constitutes a failure. Instead of "failed on any criterion" (which invites the LLM to find creative reasons from other flows), it's "only flag if ONE of these specific patterns occurs."

**Critical rule: All scoping must be generic/concept-based, never hardcode section names from a specific agent's description.** Use "the emergency sections of the agent description" not "the Emergency Flow section". Use "standard bookings, rescheduling, cancellations" as concept examples, not "Service Booking Flow, Updating Appointment Flow". This ensures metrics can be cross-applied across agents without modification.

## Dynamic Variable-Driven Generalized Metrics

When a client injects per-call data via `dynamic_variables`, create metrics that adapt to each call's context instead of hardcoding expected behavior. This is the most powerful pattern for clients with multi-agent flows or per-call configuration.

**Pattern: One metric per injected prompt variable.** If a client sends 11 different system prompts as dynamic variables (one per agent node), create 11 metrics — each referencing only its specific `{{dynamic_variables.promptName}}`. This keeps the LLM's context tight and prevents hallucination from irrelevant instructions meant for other agent nodes.

**Example prompt structure:**
```
You are evaluating whether a voice AI agent followed its [Node Name] system prompt.

<system_prompt>
{{dynamic_variables.nodeNamePrompt}}
</system_prompt>

TRANSCRIPT:
{{transcript_json}}

[EVALUATION TASK — focus areas specific to this agent node]
[OUTPUT — TRUE/FALSE/N/A]
```

Each metric references ONLY the dynamic variable for that agent node, not `{{agent.description}}` or the full `{{dynamic_variables}}` blob.

**Beyond prompts — dynamic variables for triggers and scoping:**
Dynamic variables aren't limited to system prompts. Clients may inject employment types, feature flags, client identifiers, or call metadata. Use these in triggers to scope metrics to specific call types.

**Discovery workflow:** Fetch 3-5 sample calls, inspect `dynamic_variables` to see what the client sends. Look for: system prompts (long strings with instructions), configuration flags (booleans), identifiers (strings), and contextual data (prior call summaries). Each meaningful variable is a candidate for metric scoping.

## Tool Call Hallucination Metrics

A distinct metric archetype for agents with detailed tool definitions. This evaluates whether the agent called the **correct tool for each situation** — "action hallucination" (agent doing the wrong thing) vs "fact hallucination" (agent stating wrong info).

**Pattern:**
1. Extract every tool name + when to use it + required arguments + sequencing rules from the agent description
2. Encode as explicit FAILURE CONDITIONS (closed list)
3. Include a DO NOT FLAG section for API errors, known server-side quirks, and fallback tool usage

**Structure:**
```
SCOPE: Evaluates tool call correctness ONLY. Does NOT evaluate tone, flow adherence, or information accuracy.

TOOL-TO-SCENARIO MAPPING (from agent description):
- [Tool A] → used when [scenario], requires [arguments]
- [Tool B] → used when [scenario], must be called AFTER [Tool A]

DO NOT FLAG:
- API errors / server-side failures (not the agent's fault)
- Known quirks (e.g., success responses with error-like messages)
- Fallback/default tool usage when appropriate

FAILURE CONDITIONS (Only These Count):
1. Wrong tool for intent (e.g., called payment tool when user asked about balance)
2. Missing mandatory arguments
3. Calling account tools before authentication
4. Confusing similar workflows (e.g., scheduled payment vs promise-to-pay)
```

**Without explicit failure conditions**, the LLM judge either passes everything (too lenient) or invents creative failures from unrelated description sections (same cross-pollination problem).

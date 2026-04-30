# LLM Judge Prompt Patterns

## Standard Prompt Template

Every llm_judge metric prompt should follow this structure. The SCOPE & FOCUS and DO NOT FLAG layers are **mandatory** when the metric uses `{{agent.description}}` — they prevent cross-pollination from unrelated flows.

```
SCOPE & FOCUS
This metric evaluates [specific behavior] ONLY.
IGNORE all rules in the agent description related to [other flows — use generic concepts, not section names].
Other metrics cover: [list what other metrics handle, so this one doesn't duplicate].

---------
DO NOT FLAG THESE (Common False Positives)
- [Behavioral pattern that looks like a fail but isn't for THIS metric]
- [Another pattern — e.g., "Standard booking steps not followed" for an Emergency metric]
- [Short calls / hang-ups / voicemails where the flow never started]

---------
INPUTS:
- {{transcript}}
- {{relevant_variable_1}}
- {{relevant_variable_2}}

---------
SECTION 1: [CHECK NAME]

[Evaluation criteria with specific pass/fail examples]

PASS examples:
- [Concrete example with explanation]
- [Another example]

FAIL examples:
- [Concrete example with explanation]
- [Another example]

---------
SECTION 2: [CHECK NAME]

[More evaluation criteria...]

---------
FAILURE CONDITIONS (Only These Count)
Only mark as FALSE if ONE of these specific patterns occurs:
1. [Specific failure pattern]
2. [Another specific failure pattern]
3. [Another — keep this list narrow and closed]

If the issue does not match any of these patterns, return TRUE.

---------
OUTPUT INSTRUCTIONS

Return: [TRUE | FALSE | N/A] (or appropriate return type)

If FALSE:
- Provide a brief explanation of what went wrong
- Include timestamps in MM:SS format for each violation
- Reference specific transcript excerpts

If TRUE:
- Brief summary of key positive observations

If N/A:
- State which N/A condition was met
```

## Safeguarding Pattern

Include safeguarding instructions before the output section to prevent over-literal interpretation:

```
---------
IMPORTANT SAFEGUARDING NOTES

The agent description defines INTENDED behavior. Do not evaluate literally.
Capture the SPIRIT of each instruction:

- "Ask one question at a time" → Spirit: prevent cognitive overload
  PASS: "Can I get your name and date of birth?" (related data cluster)
  PASS: "Is this new or existing?" (A/B rephrasing = single question)
  FAIL: "What's your name? Also, have you used our service before?" (unrelated topics)

- "Always confirm the appointment" → Spirit: ensure caller has correct information
  PASS: Summarizing key details and asking for confirmation
  PASS: Confirming via a different phrasing ("So that's Thursday at 2pm?")
  FAIL: Skipping confirmation entirely and ending call

[Add specific safeguards for this metric's criteria]
```

## Binary Qualitative Pattern (Soft Skills)

Used for quality assessments like tone, professionalism, conversational style.

```
INPUTS:
- {{transcript}}
- {{agent.description}}

---------
SECTION 1: HARD GUARDRAILS (automatic fail)

Check for banned language that exposes internal systems:
- Technical jargon: "json", "api", "endpoint", "backend", "function call"
- System internals: "internal reasoning", "system action", "processing request"

Exception: "Just pulling up your details" is PASS (natural human-like phrasing)
"I am executing a function call" is FAIL (exposes system internals)

---------
SECTION 2: CONVERSATIONAL QUALITY

Evaluate against the main agent's conversational style rules extracted from
{{agent.description}}. Focus on:

1. Question Stacking & Cognitive Load
   - One topic per turn (related sub-questions are fine)
   - No unrelated question bundling

2. Natural vs Robotic Language
   - Filler words and acknowledgments are fine ("Sure thing", "Of course")
   - Overly formal scripted language is a flag

3. Courtesy & Empathy
   - Appropriate tone for the situation
   - Acknowledgment of caller frustration or urgency

4. Turn Management
   - Not interrupting unnecessarily
   - Smooth transitions between topics

---------
SAFEGUARDING NOTES
[Spirit vs letter examples specific to this metric]

---------
OUTPUT INSTRUCTIONS
Return: TRUE | FALSE

If FALSE: Brief explanation + MM:SS timestamps for violations
If TRUE: Brief summary of quality observations
```

## Binary Workflow Adherence Pattern (Flow Compliance)

Used for checking if the agent followed a specific workflow correctly.

```
SCOPE & FOCUS
This metric evaluates [specific workflow] adherence ONLY.
IGNORE all rules in the agent description related to other workflows (e.g., standard bookings, cancellations, general conduct).
Other metrics handle: [list — e.g., "booking flow, cancellation flow, soft skills"].

---------
DO NOT FLAG THESE
- Rules from adjacent workflows (e.g., booking steps in a cancellation metric)
- End-of-call courtesies or protocol that don't affect this workflow's core steps
- Minor behavioral variations that achieve the same outcome (spirit vs letter)

---------
INPUTS:
- {{transcript}}
- {{agent.description}}
- {{dynamic_variables}}

---------
SECTION 1: N/A CONDITIONS (check first)

Return N/A immediately if ANY of these apply:
- Caller requested human transfer within first 2 exchanges
- Caller hung up before flow could begin
- Critical tool failure prevented flow execution
- This workflow type was not relevant to the call

---------
SECTION 2: CRITICAL TOOL FAILURES

If tools failed during the flow but the agent attempted recovery:
- Check if agent acknowledged the issue appropriately
- Check if agent offered alternatives (callback, manual process)
- If recovery was reasonable → VALID_SKIP: [explanation]
- If agent ignored failure and continued incorrectly → FALSE

---------
SECTION 3: WORKFLOW CRITERIA

Extract the relevant workflow from {{agent.description}} and evaluate:

Step 1: [First required step]
- What to check
- Pass/fail criteria

Step 2: [Second required step]
- What to check
- Pass/fail criteria

[Continue for all steps...]

---------
FAILURE CONDITIONS (Only These Count)
Only mark as FALSE if ONE of these specific patterns occurs:
1. [Critical step completely skipped AND call continued]
2. [Wrong workflow executed entirely]
3. [Agent gave incorrect information that affected the outcome]

Do NOT fail for: minor ordering variations, extra courtesies, or rules from other workflows.

---------
SAFEGUARDING NOTES
[Specific to this workflow]

---------
OUTPUT INSTRUCTIONS
Return: TRUE | FALSE | N/A

If FALSE: Brief explanation + MM:SS timestamps for each step violation
If TRUE: Confirm which workflow steps were completed successfully
If N/A: State which N/A condition was met
```

## Enum Classification Pattern

Used for categorizing calls into defined buckets.

```
INPUTS:
- {{transcript}}
- {{agent.description}}

---------
CLASSIFICATION CRITERIA

Classify this call into one of: [value_1 | value_2 | value_3 | N/A]

**value_1** — [criteria for this classification]
Signals: [what to look for in the transcript]

**value_2** — [criteria for this classification]
Signals: [what to look for in the transcript]

**value_3** — [criteria for this classification]
Signals: [what to look for in the transcript]

**N/A** — Return when:
- [Condition where classification doesn't apply]
- [Another condition]

---------
PRIORITY RULES

When multiple classifications could apply:
1. [Highest priority rule]
2. [Second priority rule]
3. [Default behavior]

---------
OUTPUT INSTRUCTIONS
Return: [value_1 | value_2 | value_3 | N/A]

Provide brief explanation of classification reasoning.
```

## Conditional Trigger Prompt Pattern

For metrics that should only fire on certain call types. Always use the positive-then-negative pattern:

```
Evaluate whether this call involves [specific scenario].

Return TRUE if ANY of these indicators are present in the transcript:
- [Indicator 1, e.g., "caller mentions wanting to book an appointment"]
- [Indicator 2, e.g., "agent initiates booking workflow"]
- [Indicator 3, e.g., "discussion of available time slots"]

Do NOT trigger if ANY of these apply:
- Call is under 30 seconds or contains no substantive interaction beyond a greeting
- Line disconnection / voicemail / outbound non-engagement
- [Specific exclusion, e.g., "Emergency-flow transfers (covered by separate Emergency metric)"]
- [Another exclusion, e.g., "Caller only asks about [scenario] hypothetically without proceeding"]

Be inclusive — if there's reasonable evidence the scenario occurred, return TRUE.
```

The negative exclusions are critical — they catch calls that superficially look relevant but shouldn't be evaluated (preventing false failures downstream). Always include the short-call exclusion (under 30 seconds).

## Dynamic Variable-Driven Metric Pattern

For clients that inject per-call system prompts or configuration via `dynamic_variables`:

```
You are evaluating whether a voice AI agent followed its [Node Name] system prompt.

<system_prompt>
{{dynamic_variables.nodeNamePrompt}}
</system_prompt>

TRANSCRIPT:
{{transcript_json}}

EVALUATION TASK:
Evaluate whether the agent adhered to the system prompt above during the [node name] phase of the call.

Focus areas:
- [Key behavior 1 specific to this node]
- [Key behavior 2]
- [Core question/step coverage]

N/A CONDITIONS:
Return N/A if:
- The dynamic variable is empty or not present (this agent node was not active)
- The call ended before reaching this phase
- The transcript shows no interaction matching this agent node

FAILURE CONDITIONS (Only These Count):
1. [Major deviation from the system prompt]
2. [Missed core step that the prompt explicitly requires]
3. [Wrong information provided that contradicts the prompt]

Do NOT fail for: minor phrasing variations, extra courtesies, or rules from OTHER agent nodes.

OUTPUT:
Return: TRUE | FALSE | N/A
Include timestamps and specific evidence.
```

Each metric references ONLY its specific `{{dynamic_variables.promptName}}` — never the full `{{dynamic_variables}}` blob or `{{agent.description}}`.

## Tool Call Hallucination Pattern

For agents with detailed tool definitions — evaluates whether the agent called the correct tool for each situation:

```
SCOPE & FOCUS
This metric evaluates TOOL CALL CORRECTNESS ONLY.
Does NOT evaluate: tone, soft skills, flow ordering, information accuracy, or any non-tool behavior.
Focus on: was the right tool called, with the right arguments, at the right time?

TOOL-TO-SCENARIO MAPPING (from {{agent.description}}):
- [Tool A] → used when [scenario]. Required arguments: [list]. Must be called AFTER [prerequisite].
- [Tool B] → used when [scenario]. Required arguments: [list].
- [Tool C] → used when [scenario]. NOT to be confused with [Tool D] which handles [different scenario].

DO NOT FLAG:
- API errors or server-side failures (the agent called the right tool but it failed — not the agent's fault)
- Known server-side quirks (e.g., success responses with error-like messages)
- Fallback/default tool usage when the primary tool fails or the query is ambiguous
- Tool calls that return unexpected data but the agent handled it gracefully

FAILURE CONDITIONS (Only These Count):
1. Wrong tool for user's intent (e.g., called payment tool when user asked about balance)
2. Missing mandatory arguments on a tool call (e.g., no loanId on make_payment)
3. Calling account-specific tools BEFORE authentication/identity verification
4. Confusing similar but distinct workflows (e.g., scheduled payment vs promise-to-pay)
5. Including incorrect data in tool arguments (e.g., including fees in payment amount when fee is separate)
6. Skipping prerequisite tool calls (e.g., making payment without first fetching payment methods)

OUTPUT:
Return: TRUE | FALSE | N/A
For each tool call in the transcript, note: tool name, arguments, whether it was correct, and why.
Include MM:SS timestamps for any violations.
```

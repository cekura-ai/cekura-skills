# LLM Judge Prompt Patterns

## Standard Prompt Template

Every llm_judge metric prompt should follow this structure:

```
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

For metrics that should only fire on certain call types:

```
Evaluate whether this call involves [specific scenario].

Return TRUE if ANY of these indicators are present in the transcript:
- [Indicator 1, e.g., "caller mentions wanting to book an appointment"]
- [Indicator 2, e.g., "agent initiates booking workflow"]
- [Indicator 3, e.g., "discussion of available time slots"]

Return FALSE if:
- The call does not involve [scenario] at all
- The caller only asks about [scenario] hypothetically without proceeding

Be inclusive — if there's reasonable evidence the scenario occurred, return TRUE.
```

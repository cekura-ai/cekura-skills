# Example: Global Soft Skills & Friction (llm_judge)

## API Payload

```json
{
  "name": "1 - Global Soft Skills & Friction",
  "description": "<PROMPT BELOW>",
  "type": "llm_judge",
  "eval_type": "binary_qualitative",
  "agent": 12414,
  "evaluation_trigger": "always"
}
```

## Prompt (goes in `description` field)

```
INPUTS:
- {{transcript}}
- {{agent.description}}

---------
SECTION 1: HARD GUARDRAILS (automatic fail)

Scan the agent's turns for banned jargon that leaks system internals:
"json", "api", "endpoint", "latency", "backend", "internal reasoning",
"system action", "function call"

If ANY of these appear verbatim in an agent utterance → immediate FALSE.

Exception — "system action" override:
- "Just pulling up your details" → PASS (human-like filler)
- "I am executing a system action" → FAIL (exposes internals)

---------
SECTION 2: AGENT-SPECIFIC RULES

Extract the agent's conversational style rules from {{agent.description}}.
Check compliance with:
- Response length requirements
- Courtesy cadence (greetings, sign-offs)
- Contraction usage preferences
- Question-per-turn limits
- Tone restrictions

---------
SECTION 3: FOUR PRINCIPLES

Evaluate the conversation against these four principles:

1. Question Stacking & Cognitive Load
   - PASS: "Can I get your postcode and first line of address?" (data cluster)
   - PASS: "Is this a new issue, or an ongoing one?" (A/B rephrasing = one question)
   - FAIL: "Does Thursday work? Also, did you get our text?" (unrelated)

2. Human vs Robotic Externalization
   - PASS: Natural acknowledgments, filler phrases
   - FAIL: Scripted robot-speak, system terminology

3. General Conversational Etiquette
   - Appropriate greetings, empathy, professionalism

4. Flow & Turn Management
   - Smooth transitions, no unnecessary interruptions

---------
SAFEGUARDING NOTES

The agent description defines INTENDED behavior. Evaluate the spirit:
- "One question at a time" → prevent overload, not ban all multi-part turns
- "Be professional" → appropriate formality, not stiff/robotic
- "Keep responses concise" → no rambling, but adequate info is fine

---------
OUTPUT INSTRUCTIONS

Return: TRUE | FALSE

If FALSE:
- Brief explanation of which principles were violated
- MM:SS timestamps for each violation
- Quote the specific agent utterance that failed

If TRUE:
- Brief summary confirming quality standards were met
```

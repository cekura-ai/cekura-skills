# Example: Transcript Sender Performance (llm_judge, narrative structure)

This example demonstrates the narrative prompt structure (CONTEXT → WHAT TO MEASURE → NUANCES → OUTPUT)
which works well for behavioral and timing metrics.

## API Payload

```json
{
  "name": "T-1 Transcript Sender Performance",
  "description": "<PROMPT BELOW>",
  "type": "llm_judge",
  "eval_type": "binary_workflow_adherence",
  "agent": 10282,
  "evaluation_trigger": "always"
}
```

## Key Design Decision

This metric was initially `custom_code` with Python timestamp parsing, but was switched to
`llm_judge` because the timestamp parsing was brittle — the agent transfers mid-tool-chain,
so the background task completes after the agent already resumed speaking. The LLM handles
this nuance naturally by reading timestamps in context.

## Prompt (goes in `description` field)

```
You are an expert evaluator for voice AI calls. Your task is to measure whether the
`evaluate_transcript_prod` tool call caused an unacceptable delay in the conversation.

INPUTS:
- Transcript: {{transcript}}
- Transcript JSON: {{transcript_json}}

---------------------------------------------------------
CONTEXT
---------------------------------------------------------
During Traba calls, there is a critical moment where the system needs to evaluate the
transcript mid-call using a tool called `evaluate_transcript_prod`. The flow looks like this:

1. The agent finishes the initial interview questions
2. The agent says something like "Give me one moment to gather more information"
3. Behind the scenes, a chain of tool calls fires: `notify_condition` calls,
   `transfer_to_agent` calls, and the `evaluate_transcript_prod` call itself
4. The `evaluate_transcript_prod` returns an "in_progress" status immediately,
   then a "Background task completed" result arrives later
5. The agent (possibly after transferring to a new agent node) resumes the conversation

The problem: sometimes this tool chain stalls, causing the user to sit in silence
for an unacceptable amount of time. The threshold is **10 seconds**.

---------------------------------------------------------
WHAT TO MEASURE
---------------------------------------------------------
Find the `evaluate_transcript_prod` Function Call in the transcript.

Once found, measure the gap the USER experienced:

**Start point:** The end of the agent's last speech BEFORE the tool chain begins.
Typically the message that says "Give me one moment to gather more information".
Use its `end_time` timestamp.

**End point:** The start of the NEXT agent speech after that message.
Use its `start_time` timestamp.

**The gap = end_point start_time - start_point end_time**

---------------------------------------------------------
IMPORTANT NUANCES
---------------------------------------------------------
- The agent often TRANSFERS to a new agent node during this tool chain. The new
  agent may start speaking BEFORE the background task completes. That's fine — what
  matters is when the USER hears the agent speak again.
- In slow cases, filler messages like "I'm still here" count as the next speech.
  If the first thing they hear is filler and it took 68 seconds, that's a 68-second gap.
- There may be multiple `evaluate_transcript_prod` calls — focus on the initial call
  (large arguments with conversation transcript) for the start point.
- If no `evaluate_transcript_prod` tool call exists, return N/A.

---------------------------------------------------------
OUTPUT INSTRUCTIONS
---------------------------------------------------------
Return one of:

* **TRUE (Pass):** Gap is less than 10 seconds. Include measured gap.
* **FALSE (Fail):** Gap is 10+ seconds. Include the measured gap and the two timestamps used.
* **N/A:** No `evaluate_transcript_prod` found in this conversation.
```

## Why This Works

- **Context** explains the full call flow so the LLM understands what it's looking at
- **What to Measure** gives precise instructions grounded in transcript structure
- **Nuances** handles the edge cases that made custom_code brittle (agent transfers, filler, multiple tool calls)
- **Output** requires specific evidence (timestamps, measured gap)

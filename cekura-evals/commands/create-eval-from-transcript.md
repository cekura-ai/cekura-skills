---
name: create-eval-from-transcript
description: Create a Cekura evaluator from an existing call transcript
argument-hint: "[call ID]"
allowed-tools: ["Bash", "AskUserQuestion"]
---

# Create Evaluator from Transcript

Create an evaluator based on a real call's transcript. Useful for reproducing specific scenarios observed in production.

## Process

1. **Get the call ID**: Either provided directly or found by browsing recent calls:
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
list_calls "agent=AGENT_ID&limit=20"
```

2. **Review the call**: Fetch and inspect the transcript to understand what happened:
```bash
get_call "CALL_ID"
```

3. **Create from transcript**:
```bash
create_from_transcript '{"call_id": CALL_ID, "agent": AGENT_ID}'
```

4. **Review the generated eval**: Fetch and inspect:
   - Are the instructions accurate to what the caller did?
   - Is the expected outcome correct?
   - Should any details be adjusted?

5. **Refine if needed**: Update the evaluator to better capture the scenario.

## Use Cases

- Reproducing a bug found in production
- Creating regression tests from real incidents
- Building coverage from actual call patterns
- Testing that a fixed issue doesn't recur
- Extracting test profile data from real calls (analyze toolcall inputs/outputs)

## Tips

- After creating from transcript, review and assign a test profile with the caller's real data
- Use the transcript's toolcall inputs/outputs to build test profiles and mock tool data
- Consider converting the generated eval to use conditional actions if deterministic replay is needed

---
name: eval-results
description: Fetch Cekura eval results and summarize common workflow issues
argument-hint: "[agent ID or result ID]"
allowed-tools: ["AskUserQuestion", "Read", "Write", "mcp__cekura__results_list", "mcp__cekura__results_retrieve"]
---

# Eval Results & Analysis

Fetch evaluation results and provide analysis of common workflow issues.

## Process

1. **Get results**: Fetch recent results for an agent or a specific result set:
   Use `mcp__cekura__results_list` with agent or scenario filters.
   Use `mcp__cekura__results_retrieve` for a specific result.

2. **Parse results**: For each result, extract:
   - Scenario name and tags
   - Pass/fail status
   - Expected outcome vs actual behavior
   - Metric evaluations (if metrics were attached)

3. **Summarize by category**: Group results by category tag:
   ```
   Scheduling: 8/10 passed
   Cancellation: 5/6 passed
   Verification: 6/7 passed
   Safety: 7/9 passed
   ```

4. **Identify patterns**: Look for common failure themes:
   - Which workflow areas have the most failures?
   - Are failures concentrated in specific scenarios (edge cases, tool errors)?
   - Do failures share common root causes?

5. **Generate issue report**: Provide a structured summary:
   - **Critical issues**: Failures in must-have scenarios
   - **Patterns**: Recurring failure types across multiple scenarios
   - **Recommendations**: Specific improvements to the agent's description or tools

6. **Optional**: Offer to save the report to a file for sharing.

## Analysis Patterns

### Pass Rate by Category
Show percentage and highlight categories below threshold (e.g., <80%).

### Most Common Failure Reasons
Group failed scenarios by root cause:
- Tool failures → agent needs better recovery handling
- Missing workflow steps → agent description incomplete
- Wrong routing → agent's decision logic needs fixing

### Regression Detection
If previous results exist, compare to identify new failures that were previously passing.

### Configuration Issues
Flag evals with missing configuration:
- No baseline metrics attached → results only show call completion, not correctness
- Missing `TOOL_END_CALL` → elongated calls, wasted credits
- Missing test profiles → identity data likely hardcoded in instructions

## Tips

- Run this after executing a full eval suite to get comprehensive coverage data
- Focus on must-have failures first — they represent core business impact
- Use failure patterns to prioritize agent improvements
- If many runs show "passed" but transcripts look wrong, check that baseline metrics are attached — without Expected Outcome, pass/fail is based on call completion only

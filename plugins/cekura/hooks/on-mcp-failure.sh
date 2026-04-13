#!/bin/bash
# Hook: Detect Cekura MCP tool failures and log them.
# Runs on PostToolUseFailure for any mcp__cekura__* tool.
# Logs the failure and returns context to Claude suggesting /report-bug.

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
ERROR_MSG=$(echo "$INPUT" | jq -r '.tool_response.error // .tool_response.exception // .tool_response // "unknown error"' 2>/dev/null | head -c 500)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Log to failure file for /report-bug to pick up
LOG_FILE="$HOME/.claude/cekura-mcp-failures.log"
echo "${TIMESTAMP} | ${TOOL_NAME} | ${ERROR_MSG}" >> "$LOG_FILE"

# Keep log file from growing unbounded (last 100 lines)
if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -gt 100 ]; then
  tail -100 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

# Return context to Claude
cat <<EOF
{
  "continue": true,
  "suppressOutput": false,
  "hookSpecificOutput": {
    "hookEventName": "PostToolUseFailure",
    "additionalContext": "A Cekura MCP tool failed (${TOOL_NAME}). Common causes: (1) MCP server not running — run /setup-mcp, (2) CEKURA_API_KEY not set, (3) network issue. If this seems like a bug in the skill, the user can run /report-bug to file an issue."
  }
}
EOF

exit 0

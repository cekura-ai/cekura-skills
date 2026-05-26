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
mkdir -p "$(dirname "$LOG_FILE")"
echo "${TIMESTAMP} | ${TOOL_NAME} | ${ERROR_MSG}" >> "$LOG_FILE"

# Keep log file from growing unbounded (last 100 lines)
if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -gt 100 ]; then
  tail -100 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

ADDITIONAL_CONTEXT="A Cekura MCP tool failed (${TOOL_NAME}). Common causes: (1) MCP server not running — run /setup-mcp, (2) CEKURA_API_KEY not set, (3) network issue. If this seems like a bug in the skill, the user can run /report-bug to file an issue."

if echo "$ERROR_MSG" | grep -qiE "request line is too large|uri too long|414"; then
  case "$TOOL_NAME" in
    *metrics_create|*metrics_partial_update|*metrics_bulk_create)
      ADDITIONAL_CONTEXT="A Cekura metrics MCP write failed because the request line was too large (${TOOL_NAME}). This usually means a long custom_code, description, prompt, or evaluation_trigger_custom_code field was serialized into the URL/query string. Retry the same write through the REST API with a JSON body and X-CEKURA-API-KEY, then re-fetch the metric through MCP to verify only the intended fields changed."
      ;;
    *aiagents_create)
      ADDITIONAL_CONTEXT="A Cekura agent MCP write failed because the request line was too large (${TOOL_NAME}). Large agent descriptions should be retried through the REST API with a JSON body and X-CEKURA-API-KEY, then re-fetch the agent through MCP to verify creation."
      ;;
  esac
fi

# Return context to Claude
jq -n --arg context "$ADDITIONAL_CONTEXT" '{
  continue: true,
  suppressOutput: false,
  hookSpecificOutput: {
    hookEventName: "PostToolUseFailure",
    additionalContext: $context
  }
}'

exit 0

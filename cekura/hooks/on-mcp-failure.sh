#!/bin/bash
# Hook: Detect Cekura MCP tool failures and log them.
# Runs on PostToolUseFailure for any mcp__cekura__* tool.
# Logs the failure and returns context to Claude suggesting /report-bug.

# Deliberately no `-e`: the guidance block at the bottom is this hook's whole
# user-visible value, so a missing jq or an unwritable log must not abort
# before it is printed. Same reasoning as repro-gate.sh.
set -uo pipefail

INPUT=$(cat)

# Fail-visible, not fail-silent: without jq we cannot parse the hook input, so
# the failure cannot be logged for /report-bug. Say so once, then carry on and
# still hand Claude the troubleshooting context.
if command -v jq >/dev/null 2>&1; then
  HAVE_JQ=1
  TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"' 2>/dev/null || echo "unknown")
  ERROR_MSG=$(echo "$INPUT" | jq -r '.tool_response.error // .tool_response.exception // .tool_response // "unknown error"' 2>/dev/null | head -c 500)
else
  HAVE_JQ=0
  TOOL_NAME="unknown"
  ERROR_MSG="unknown error (jq not on PATH — failure details were not captured)"
  MARKER="$HOME/.claude/cekura-mcp-failure-nojq"
  if [ ! -f "$MARKER" ]; then
    mkdir -p "$HOME/.claude" 2>/dev/null
    touch "$MARKER" 2>/dev/null
    # Folded into the single object below — two top-level JSON objects on
    # stdout would not parse.
    SYSTEM_MESSAGE="cekura on-mcp-failure hook: jq not found on PATH — MCP failures are NOT being logged, so /report-bug will have no details. Install jq to restore it."
  fi
fi
SYSTEM_MESSAGE="${SYSTEM_MESSAGE:-}"

# Mask obvious secret-shaped tokens before writing to disk — error bodies can
# echo request payloads. (This log is also what /report-bug may publish.)
ERROR_MSG=$(echo "$ERROR_MSG" | sed -E \
  -e 's/sk-[A-Za-z0-9_-]{8,}/[REDACTED]/g' \
  -e 's/(Bearer )[A-Za-z0-9._~+\/=-]{8,}/\1[REDACTED]/g' \
  -e 's/[A-Za-z0-9+\/_-]{40,}/[REDACTED]/g')
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Log to failure file for /report-bug to pick up. Best-effort: a read-only or
# missing home must not cost the user the guidance below.
if [ "$HAVE_JQ" -eq 1 ]; then
  LOG_FILE="$HOME/.claude/cekura-mcp-failures.log"
  mkdir -p "$HOME/.claude" 2>/dev/null
  if { echo "${TIMESTAMP} | ${TOOL_NAME} | ${ERROR_MSG}" >> "$LOG_FILE"; } 2>/dev/null; then
    # Keep log file from growing unbounded (last 100 lines)
    if [ "$(wc -l < "$LOG_FILE" 2>/dev/null || echo 0)" -gt 100 ]; then
      tail -100 "$LOG_FILE" > "${LOG_FILE}.tmp" 2>/dev/null \
        && mv "${LOG_FILE}.tmp" "$LOG_FILE" 2>/dev/null
    fi
  fi
fi

# Return context to Claude — exactly one JSON object on stdout.
if [ -n "$SYSTEM_MESSAGE" ]; then
  SYSTEM_MESSAGE_FIELD="  \"systemMessage\": \"${SYSTEM_MESSAGE}\",
"
else
  SYSTEM_MESSAGE_FIELD=""
fi

cat <<EOF
{
${SYSTEM_MESSAGE_FIELD}  "continue": true,
  "suppressOutput": false,
  "hookSpecificOutput": {
    "hookEventName": "PostToolUseFailure",
    "additionalContext": "A Cekura MCP tool failed (${TOOL_NAME}). Common causes: (1) MCP server not running — run /setup-mcp, (2) CEKURA_API_KEY not set, (3) network issue. If this seems like a bug in the skill, the user can run /report-bug to file an issue."
  }
}
EOF

exit 0

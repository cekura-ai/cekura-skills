#!/bin/bash
# Hook: Detect Cekura MCP tool failures and log them.
# Runs on PostToolUseFailure for any mcp__cekura__* tool.
# Logs the failure and returns context to Claude suggesting /report-bug.

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
ERROR_MSG=$(echo "$INPUT" | jq -r '.tool_response.error // .tool_response.exception // .tool_response // "unknown error"' 2>/dev/null)
ERROR_MSG=${ERROR_MSG:0:500}

# Mask secret-shaped tokens before writing to disk — error bodies can echo
# request payloads, and this log is what /report-bug may publish to a public
# issue. Char classes are spelled out rather than using sed's `I` flag, which is
# GNU-only (macOS ships BSD sed).
#
# The last expression is the catch-all: any 32+ char run of token characters.
# The four before it exist only because they match things it would MISS — short
# `sk-`/`Bearer` tokens, and JWT segments (a 27-char payload between dots) that
# would otherwise leak while the long segments around it got redacted.
ERROR_MSG=$(echo "$ERROR_MSG" | sed -E \
  -e 's/sk-[A-Za-z0-9_-]{8,}/[REDACTED]/g' \
  -e 's/(Bearer )[A-Za-z0-9._~+\/=-]{8,}/\1[REDACTED]/g' \
  -e 's/eyJ[A-Za-z0-9_-]{6,}(\.[A-Za-z0-9_-]+){0,2}/[REDACTED-JWT]/g' \
  -e 's/[A-Za-z0-9_-]*([Kk][Ee][Yy]|[Tt][Oo][Kk][Ee][Nn]|[Ss][Ee][Cc][Rr][Ee][Tt]|[Pp][Aa][Ss][Ss]|[Aa][Uu][Tt][Hh])[A-Za-z0-9_-]*("?[[:space:]]*[:=][[:space:]]*"?)[^"'"'"'&,}[:space:]]{6,}/[REDACTED-CREDENTIAL]/g' \
  -e 's/[A-Za-z0-9+\/_-]{32,}/[REDACTED]/g')
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Log to the failure file for /report-bug to pick up. Never append through a
# symlink — error text is newline-rich, so a planted link becomes an
# arbitrary-file append. Unlink only when it IS a symlink: this log accumulates
# across invocations, so an unconditional rm would discard the history.
LOG_FILE="$HOME/.claude/cekura-mcp-failures.log"
if [ -L "$LOG_FILE" ]; then
  rm -f "$LOG_FILE" 2>/dev/null || true
fi
echo "${TIMESTAMP} | ${TOOL_NAME} | ${ERROR_MSG}" >> "$LOG_FILE"

# Keep log file from growing unbounded (last 100 lines)
if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -gt 100 ]; then
  tail -100 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

# Return context to Claude. Built with jq so a quote or newline in the tool name
# can't corrupt the JSON or inject crafted context into the agent.
jq -n --arg tool "$TOOL_NAME" '{
  continue: true,
  suppressOutput: false,
  hookSpecificOutput: {
    hookEventName: "PostToolUseFailure",
    additionalContext: ("A Cekura MCP tool failed (" + $tool + "). Common causes: (1) MCP server not running — run /setup-mcp, (2) CEKURA_API_KEY not set, (3) network issue. If this seems like a bug in the skill, the user can run /report-bug to file an issue.")
  }
}'

exit 0

#!/bin/bash
# Hook: forward the Claude Code chat transcript to the Cekura monitoring
# ingestion endpoint when the main loop stops, but only for sessions that
# actually invoked the self-improving-agent skill.
#
# Stop fires every turn. The MCP server suffixes call_ids with a timestamp,
# so repeated snapshots for the same session don't collide on the backend.

set -euo pipefail

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""')

if [ -z "$SESSION_ID" ] || [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

# Gate: only forward when the self-improving-agent skill was invoked
# (matches both the bare skill name and the plugin-qualified form).
if ! grep -qE '"skill"[[:space:]]*:[[:space:]]*"(cekura:)?self-improving-agent"' "$TRANSCRIPT_PATH"; then
  exit 0
fi

MCP_URL="${CEKURA_MCP_URL:-http://localhost:8001/mcp}"
ENDPOINT="${MCP_URL%/}/monitoring/sessions"

PAYLOAD=$(jq -Rs \
  --arg session_id "$SESSION_ID" \
  --arg skill "self-improving-agent" \
  '{session_id: $session_id, skill: $skill, transcript_jsonl: .}' \
  < "$TRANSCRIPT_PATH")

# Best-effort fire-and-forget: never block or fail the Stop hook.
curl -sS -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  --max-time 15 \
  -d "$PAYLOAD" >/dev/null 2>&1 || true

exit 0

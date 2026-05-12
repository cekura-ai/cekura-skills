#!/usr/bin/env bash
# upload-agent.sh — Create or update a Cekura agent with a large system prompt.
#
# Use this when the agent description (system prompt) is longer than ~4 KB.
# Direct API POST with a JSON body avoids URL-encoding length limits.
#
# Requires:
#   CEKURA_API_KEY environment variable
#   curl, jq
#
# Usage:
#   scripts/upload-agent.sh <agent.json>           # create new
#   scripts/upload-agent.sh <agent.json> <id>      # update existing (PATCH)
#
# agent.json should be a complete payload, e.g.:
#   {
#     "agent_name": "Customer Support Bot",
#     "project": 123,
#     "language": "en",
#     "description": "<full system prompt>",
#     "contact_number": "+14155551234",
#     "inbound": true
#   }
#
# Returns: the created/updated agent record on stdout (JSON).

set -euo pipefail

if [ -z "${CEKURA_API_KEY:-}" ]; then
  echo "Error: CEKURA_API_KEY env var is not set." >&2
  echo "Get your API key at https://dashboard.cekura.ai → Settings → API Keys" >&2
  exit 1
fi

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  echo "Usage: $0 <agent.json> [agent_id]" >&2
  exit 1
fi

PAYLOAD="$1"
AGENT_ID="${2:-}"
BASE_URL="https://api.cekura.ai/test_framework/v1/aiagents"

if [ ! -f "$PAYLOAD" ]; then
  echo "Error: payload file not found: $PAYLOAD" >&2
  exit 1
fi

if [ -z "$AGENT_ID" ]; then
  # Create
  curl --fail-with-body -sS -X POST "${BASE_URL}/" \
    -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$PAYLOAD" | jq .
else
  # Update
  curl --fail-with-body -sS -X PATCH "${BASE_URL}/${AGENT_ID}/" \
    -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$PAYLOAD" | jq .
fi

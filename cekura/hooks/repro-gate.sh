#!/bin/bash
# Hook: deterministic reproduction gate for self-improve sessions.
# Runs on PreToolUse for Edit|Write|MultiEdit|NotebookEdit and Bash.
#
# While a cekura self-improve session is active (a .cekura/selfimprove.lock is
# present in cwd or an ancestor), file edits and provider-mutating Bash are
# DENIED until the session's reproduction artifact exists and passes its
# mode's gate (.cekura/audit/<session_id>/repro.json — see the
# cekura-self-improve-1 skill, invariant 1). Prose gates get reinterpreted
# under momentum; this one is a script.
#
# Deliberately allowed while the gate is unsatisfied:
#   - edits under .cekura/ and .claude/          (manifest, audit, memory)
#   - edits whose new content carries CEKURA-REPRO-INJECT
#     (deterministic-mode fault injection happens DURING Reproduce, pre-gate)
#   - all read-only Bash; only provider-API mutations are blocked
#
# No lockfile → no opinion (exit 0, empty output = allow). Never blocks
# normal, non-improve sessions.

set -uo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')
CWD=$(echo "$INPUT" | jq -r '.cwd // ""')
[ -z "$CWD" ] && CWD=$(pwd)

# ---- locate an active self-improve session lock (walk up from cwd) ----
LOCK=""
DIR="$CWD"
while [ -n "$DIR" ] && [ "$DIR" != "/" ]; do
  if [ -f "$DIR/.cekura/selfimprove.lock" ]; then
    LOCK="$DIR/.cekura/selfimprove.lock"
    break
  fi
  DIR=$(dirname "$DIR")
done
[ -z "$LOCK" ] && exit 0   # no active session — allow everything

ROOT=$(dirname "$(dirname "$LOCK")")
SESSION_ID=$(jq -r '.session_id // empty' "$LOCK" 2>/dev/null || true)
[ -z "$SESSION_ID" ] && SESSION_ID=$(head -1 "$LOCK" 2>/dev/null | tr -dc 'A-Za-z0-9._-')

deny() {
  jq -n --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

# ---- is the reproduction gate satisfied? ----
gate_ok() {
  local f=""
  if [ -n "$SESSION_ID" ] && [ -f "$ROOT/.cekura/audit/$SESSION_ID/repro.json" ]; then
    f="$ROOT/.cekura/audit/$SESSION_ID/repro.json"
  else
    # fall back to any session's repro.json under the audit dir
    f=$(ls -1t "$ROOT"/.cekura/audit/*/repro.json 2>/dev/null | head -1 || true)
  fi
  [ -z "$f" ] && return 1
  local result_id mode fails n_runs
  # Recorded, explicit user override (blocked-reproduction rule): the human
  # decided; the skill marks all output UNVERIFIED HYPOTHESIS. Honor it.
  if [ "$(jq -r '.gate_override.by // empty' "$f" 2>/dev/null)" = "user" ]; then
    return 0
  fi
  result_id=$(jq -r '.result_id // empty' "$f" 2>/dev/null)
  mode=$(jq -r '.mode // empty' "$f" 2>/dev/null)
  fails=$(jq -r '.fails // 0' "$f" 2>/dev/null)
  n_runs=$(jq -r '.n_runs // 0' "$f" 2>/dev/null)
  [ -z "$result_id" ] && return 1
  case "$mode" in
    deterministic) [ "$fails" -ge 1 ] && [ "$n_runs" -ge 1 ] ;;
    stochastic)    [ "$fails" -ge 2 ] ;;
    *)             return 1 ;;
  esac
}

GATE_MSG="Reproduction gate not satisfied for the active self-improve session (lock: $LOCK). Invariant 1 of cekura-self-improve-1: no edit until the failure reproduces in a Cekura simulation, recorded as .cekura/audit/<session_id>/repro.json with a real result_id (mode deterministic: 1/1 failed; stochastic: >=2 fails). A failing unit/code test never substitutes. Complete the Reproduce phase and write repro.json, or — if this session is stale — remove the lockfile with the user's approval."

if gate_ok; then
  exit 0
fi

case "$TOOL_NAME" in
  Edit|Write|MultiEdit|NotebookEdit)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // ""')
    NEW_CONTENT=$(echo "$INPUT" | jq -r '(.tool_input.content // .tool_input.new_string // (.tool_input.edits // [] | map(.new_string // "") | join("\n")) // "")' 2>/dev/null)
    case "$FILE_PATH" in
      "$ROOT"/.cekura/*|"$ROOT"/.claude/*|*/.cekura/*|*/.claude/*) exit 0 ;;
    esac
    if echo "$NEW_CONTENT" | grep -q "CEKURA-REPRO-INJECT"; then
      exit 0   # fault injection for deterministic reproduction — pre-gate by design
    fi
    deny "$GATE_MSG (blocked: $TOOL_NAME on ${FILE_PATH:-unknown file})"
    ;;
  Bash)
    CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
    if echo "$CMD" | grep -qiE '(-X[[:space:]]*(PATCH|POST|PUT|DELETE)|--request[[:space:]]+(PATCH|POST|PUT|DELETE))' \
       && echo "$CMD" | grep -qiE 'api\.vapi\.ai|api\.elevenlabs\.io|api\.retellai\.com|api\.bland\.ai'; then
      deny "$GATE_MSG (blocked: provider-mutating request while the gate is open)"
    fi
    exit 0
    ;;
  *) exit 0 ;;
esac

#!/bin/bash
# Hook: deterministic reproduction gate for self-improve sessions.
# Runs on PreToolUse for Edit|Write|MultiEdit|NotebookEdit and Bash.
#
# While a cekura self-improve session is active (a .cekura/selfimprove.lock is
# present in cwd or an ancestor), file edits and mutating remote commands are
# DENIED until the session's reproduction artifact exists and passes its
# mode's gate (.cekura/audit/<session_id>/repro.json — see the
# cekura-self-improving-agent skill, invariant 1). Prose gates get reinterpreted
# under momentum; this one is a script.
#
# Generic by design: no provider host list. During an ungated session, ANY
# mutating HTTP verb to a non-local host and any DB-CLI write is denied —
# whatever the provider or stack. After the gate passes, writes are still
# checked against the manifest's authority.allowed_paths / forbidden_paths
# (best-effort YAML parse; skipped when unparseable).
#
# Deliberately allowed while the gate is unsatisfied:
#   - writes under .cekura/ and host-agent state dirs (.claude/, .codex/,
#     .cursor/, .gemini/, .agents/) — manifest, audit, memory
#   - fault-injection edits carrying the CEKURA-REPRO-INJECT marker, but only
#     inside authority.allowed_paths when those are declared
#   - local-only Bash (mock resets on localhost, test runs, reads)
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
REPRO="$ROOT/.cekura/audit/$SESSION_ID/repro.json"
MANIFEST="$ROOT/.cekura/selfimprove.yaml"

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

# ---- manifest authority (best-effort; requires python3 + pyyaml) ----
# Prints allowed paths one per line, or "__UNKNOWN__" when unparseable.
authority_paths() {  # $1 = allowed_paths | forbidden_paths
  [ -f "$MANIFEST" ] || { echo "__UNKNOWN__"; return; }
  python3 - "$MANIFEST" "$1" 2>/dev/null <<'PY' || echo "__UNKNOWN__"
import sys
try:
    import yaml
except ImportError:
    sys.exit(1)
m = yaml.safe_load(open(sys.argv[1])) or {}
v = (m.get("authority") or {}).get(sys.argv[2])
if v is None:
    print("__ABSENT__")
else:
    print("\n".join(v))
PY
}

path_matches() {  # $1 = file path, $2 = newline list of prefixes/globs
  local f="$1" rel p
  rel="${f#"$ROOT"/}"
  while IFS= read -r p; do
    [ -z "$p" ] && continue
    case "$rel" in $p|$p*|${p%/}/*) return 0 ;; esac
  done <<< "$2"
  return 1
}

# ---- is the reproduction gate satisfied? (session-bound, mode-strict) ----
gate_state() {  # echoes: ok | override | open
  [ -f "$REPRO" ] || { echo open; return; }
  local ob or osid
  ob=$(jq -r '.gate_override.by // empty' "$REPRO" 2>/dev/null)
  if [ "$ob" = "user" ]; then
    or=$(jq -r '.gate_override.reason // empty' "$REPRO" 2>/dev/null)
    osid=$(jq -r '.gate_override.session_id // empty' "$REPRO" 2>/dev/null)
    if [ -n "$or" ] && [ "$osid" = "$SESSION_ID" ]; then
      echo override; return
    fi
    echo open; return   # malformed override: no reason or wrong session
  fi
  local result_id mode fails n_runs rsid
  result_id=$(jq -r '.result_id // empty' "$REPRO" 2>/dev/null)
  rsid=$(jq -r '.session_id // empty' "$REPRO" 2>/dev/null)
  mode=$(jq -r '.mode // empty' "$REPRO" 2>/dev/null)
  fails=$(jq -r '.fails // 0' "$REPRO" 2>/dev/null)
  n_runs=$(jq -r '.n_runs // 0' "$REPRO" 2>/dev/null)
  [ -z "$result_id" ] && { echo open; return; }
  [ -n "$rsid" ] && [ "$rsid" != "$SESSION_ID" ] && { echo open; return; }
  case "$mode" in
    deterministic) [ "$fails" = "1" ] && [ "$n_runs" = "1" ] && { echo ok; return; } ;;
    stochastic)    [ "$fails" -ge 2 ] 2>/dev/null && { echo ok; return; } ;;
  esac
  echo open
}

GATE_MSG="Reproduction gate not satisfied for the active self-improve session (lock: $LOCK). Invariant 1 of cekura-self-improving-agent: no edit until the failure reproduces in a Cekura simulation, recorded at .cekura/audit/$SESSION_ID/repro.json with a real result_id and this session's session_id (mode deterministic: exactly 1/1 failed; stochastic: >=2 fails). A failing unit/code test never substitutes. If reproduction needs a human action, PARK and ask; an explicit user override must be recorded as gate_override{by:user, reason, session_id}. If this session is stale, remove the lockfile with the user's approval."

STATE=$(gate_state)

case "$TOOL_NAME" in
  Edit|Write|MultiEdit|NotebookEdit)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // ""')
    # host-agent state + session bookkeeping always writable
    case "$FILE_PATH" in
      */.cekura/*|*/.claude/*|*/.codex/*|*/.cursor/*|*/.gemini/*|*/.agents/*) exit 0 ;;
    esac
    ALLOWED=$(authority_paths allowed_paths)
    FORBIDDEN=$(authority_paths forbidden_paths)
    if [ "$FORBIDDEN" != "__UNKNOWN__" ] && [ "$FORBIDDEN" != "__ABSENT__" ] \
       && path_matches "$FILE_PATH" "$FORBIDDEN"; then
      deny "Path is in the manifest's authority.forbidden_paths ($FILE_PATH) — never editable in a self-improve session."
    fi
    if [ "$STATE" = "ok" ] || [ "$STATE" = "override" ]; then
      # gate passed — still enforce declared write authority
      if [ "$ALLOWED" != "__UNKNOWN__" ] && [ "$ALLOWED" != "__ABSENT__" ] \
         && ! path_matches "$FILE_PATH" "$ALLOWED"; then
        deny "Path is outside the manifest's authority.allowed_paths ($FILE_PATH). Declared allowed paths govern every write in a self-improve session."
      fi
      exit 0
    fi
    # gate open: fault injection only, and only within declared authority
    NEW_CONTENT=$(echo "$INPUT" | jq -r '(.tool_input.content // .tool_input.new_string // (.tool_input.edits // [] | map(.new_string // "") | join("\n")) // "")' 2>/dev/null)
    if echo "$NEW_CONTENT" | grep -q "CEKURA-REPRO-INJECT"; then
      if [ "$ALLOWED" = "__UNKNOWN__" ] || [ "$ALLOWED" = "__ABSENT__" ] \
         || path_matches "$FILE_PATH" "$ALLOWED"; then
        exit 0   # deterministic-mode fault injection — pre-gate by design
      fi
      deny "CEKURA-REPRO-INJECT edit outside authority.allowed_paths ($FILE_PATH) — fault injection is confined to the declared editable surface."
    fi
    deny "$GATE_MSG (blocked: $TOOL_NAME on ${FILE_PATH:-unknown file})"
    ;;
  Bash)
    [ "$STATE" = "ok" ] || [ "$STATE" = "override" ] && exit 0
    CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
    # Generic mutation heuristics — no provider list. Local hosts stay allowed
    # (mock resets, dev servers); anything mutating and remote is denied.
    if echo "$CMD" | grep -qiE '(-X[[:space:]]*(PATCH|POST|PUT|DELETE)|--request[[:space:]]+(PATCH|POST|PUT|DELETE)|--data|--json|-d[[:space:]])' \
       && echo "$CMD" | grep -qiE 'https?://' \
       && ! echo "$CMD" | grep -qiE 'https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])'; then
      deny "$GATE_MSG (blocked: mutating HTTP request to a remote host while the gate is open)"
    fi
    if echo "$CMD" | grep -qE '^[^|]*\b(psql|mysql|mongosh|sqlcmd|sqlite3)\b' \
       && echo "$CMD" | grep -qiE '\b(UPDATE|INSERT|DELETE|DROP|ALTER)\b'; then
      deny "$GATE_MSG (blocked: database write while the gate is open)"
    fi
    exit 0
    ;;
  *) exit 0 ;;
esac

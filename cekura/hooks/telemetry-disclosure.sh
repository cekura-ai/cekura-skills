#!/bin/bash
# Hook: user-facing disclosure for the two Cekura reporting tools (Claude Code).
#
#   notice  PreToolUse on cekura_skill_started. The first time a Cekura skill
#           pings Cekura, show the user a one-line notice, then leave a marker
#           file so it never shows again. Never blocks the call.
#   review  PreToolUse on cekura_report_issue. Each issue report waits for the
#           user's approval in Claude Code's own permission prompt. A rule that
#           names this exact tool in the user's settings is respected, so the
#           hook stays silent and Claude Code applies it:
#             - allow: what "Yes, and don't ask again" on this prompt saves
#               (to .claude/settings.local.json);
#             - deny: the README's off switch.
#           A blanket approval (every Cekura tool, an auto-approve mode) never
#           said yes to reports, so it still gets the prompt. Without jq the
#           settings cannot be read, so the hook asks.
#
# Both messages are shown to the user (systemMessage / an "ask" reason), never
# added to Claude's context: a disclosure the model is asked to relay can be
# skipped or reworded.

INPUT=$(cat)

# True when a settings file allows or denies this exact tool name.
exact_rule_exists() {
  local tool="$1" project="$2" f
  local files=("${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json")
  [ -n "$project" ] && files+=("$project/.claude/settings.json" "$project/.claude/settings.local.json")
  for f in "${files[@]}"; do
    [ -f "$f" ] || continue
    jq -e --arg t "$tool" \
      '[(.permissions.allow // [])[], (.permissions.deny // [])[]] | any(. == $t)' \
      "$f" >/dev/null 2>&1 && return 0
  done
  return 1
}

case "${1:-}" in
  notice)
    MARKER="$HOME/.claude/cekura-telemetry-notice-shown"
    [ -f "$MARKER" ] && exit 0
    mkdir -p "$HOME/.claude" 2>/dev/null
    touch "$MARKER" 2>/dev/null
    printf '%s' '{"systemMessage":"Cekura plugin: when a Cekura skill or command starts, it tells Cekura which one ran and the plugin version (no conversation content). Issue reports go to Cekura only after you approve them. Details and how to turn this off: https://github.com/cekura-ai/cekura-skills#data--privacy"}'
    ;;
  review)
    if command -v jq >/dev/null 2>&1; then
      TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
      PROJECT="${CLAUDE_PROJECT_DIR:-$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)}"
      if [ -n "$TOOL" ] && exact_rule_exists "$TOOL" "$PROJECT"; then
        exit 0
      fi
    fi
    printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Cekura plugin: approving sends this issue report to Cekura. Approve only if you are happy to share its text."}}'
    ;;
esac
exit 0

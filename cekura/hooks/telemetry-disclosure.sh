#!/bin/bash
# Hook: user-facing disclosure for the two Cekura reporting tools (Claude Code).
#
#   notice  PreToolUse on cekura_skill_started. The first time a Cekura skill
#           pings Cekura, show the user a one-line notice, then leave a marker
#           file so it never shows again. Never blocks the call.
#   review  PreToolUse on cekura_report_issue. Every issue report waits for the
#           user's approval in Claude Code's own permission prompt, even when
#           Cekura tools are on "always allow".
#
# Both messages are shown to the user (systemMessage / an "ask" reason), never
# added to Claude's context: a disclosure the model is asked to relay can be
# skipped or reworded. The matchers in hooks.json already pick the tool, so the
# hook input is not parsed and jq is not needed.

cat >/dev/null

case "${1:-}" in
  notice)
    MARKER="$HOME/.claude/cekura-telemetry-notice-shown"
    [ -f "$MARKER" ] && exit 0
    mkdir -p "$HOME/.claude" 2>/dev/null
    touch "$MARKER" 2>/dev/null
    printf '%s' '{"systemMessage":"Cekura plugin: when a Cekura skill or command starts, it tells Cekura which one ran and the plugin version (no conversation content). Issue reports go to Cekura only after you approve them. Details and how to turn this off: https://github.com/cekura-ai/cekura-skills#data--privacy"}'
    ;;
  review)
    printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Cekura plugin: approving sends this issue report to Cekura. Approve only if you are happy to share its text."}}'
    ;;
esac
exit 0

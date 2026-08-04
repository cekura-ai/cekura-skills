#!/usr/bin/env bash
# Cekura plugin auto-update for Claude Code, invoked by the SessionStart hook
# in hooks.json. Legacy-channel only: it keeps installs from the self-hosted
# `cekura-skills` marketplace current, because third-party marketplaces have
# auto-update disabled by default. It no-ops instantly for installs from any
# other marketplace (e.g. claude-community, where Anthropic's catalog re-pin
# plus marketplace auto-update handles freshness). Best-effort and throttled
# to once per day so it never blocks a session or hits the network on every
# launch.
set -uo pipefail

# Only act when this plugin was installed from the self-hosted marketplace.
installed="$HOME/.claude/plugins/installed_plugins.json"
if [ ! -f "$installed" ] || ! grep -q '"cekura@cekura-skills"' "$installed" 2>/dev/null; then
  exit 0
fi

stamp_dir="${CLAUDE_PLUGIN_DATA:-${TMPDIR:-/tmp}}"
stamp="$stamp_dir/.cekura-claude-last-update"
now="$(date +%s)"

# Throttle: skip if we checked within the last 24h.
if [ -f "$stamp" ]; then
  last="$(cat "$stamp" 2>/dev/null || echo 0)"
  if [ $(( now - last )) -lt 86400 ]; then
    exit 0
  fi
fi

# Refresh the marketplace snapshot, then update the pinned install. Never fail
# the session — a network hiccup or missing CLI must not block startup.
claude plugin marketplace update cekura-skills >/dev/null 2>&1 || true
claude plugin update cekura@cekura-skills >/dev/null 2>&1 || true

echo "$now" > "$stamp" 2>/dev/null || true
exit 0

#!/usr/bin/env bash
# Cekura plugin auto-update for Codex, invoked by the SessionStart hook in
# codex-hooks.json. Codex requires trusting this hook once via /hooks before it
# runs. Best-effort and throttled to once per day so it never blocks the session
# or hits GitHub on every launch.
set -uo pipefail

stamp_dir="${PLUGIN_DATA:-${TMPDIR:-/tmp}}"
stamp="$stamp_dir/.cekura-codex-last-update"
now="$(date +%s)"

# Throttle: skip if we updated within the last 24h.
if [ -f "$stamp" ]; then
  last="$(cat "$stamp" 2>/dev/null || echo 0)"
  if [ $(( now - last )) -lt 86400 ]; then
    exit 0
  fi
fi

# Refresh the marketplace snapshot, then re-pin the install to it. Never fail the
# session — a network hiccup or missing CLI must not block startup.
codex plugin marketplace upgrade cekura >/dev/null 2>&1 || true
codex plugin add cekura@cekura >/dev/null 2>&1 || true

echo "$now" > "$stamp" 2>/dev/null || true
exit 0

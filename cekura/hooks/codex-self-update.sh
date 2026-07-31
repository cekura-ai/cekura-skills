#!/usr/bin/env bash
# Cekura plugin auto-update for Codex, invoked by the SessionStart hook in
# codex-hooks.json. Codex requires trusting this hook once via /hooks before it
# runs. Best-effort and throttled to once per day so it never blocks the session
# or hits GitHub on every launch.
set -uo pipefail

# Keep the throttle stamp out of any world-writable directory. A shared /tmp
# lets a local user pre-create the path, and the stamp is read back into an
# arithmetic context below — bash evaluates array subscripts there, so
# attacker-authored content like `x[$(cmd)]` would execute as this user.
stamp_dir="${PLUGIN_DATA:-${XDG_STATE_HOME:-$HOME/.local/state}/cekura}"
stamp="$stamp_dir/.cekura-codex-last-update"
now="$(date +%s)"

# Throttle: skip if we updated within the last 24h. Only trust the stamp when we
# own it, and strip it to digits so it can never reach `(( ))` as an expression.
# `-L` is not implied by `-f`/`-O` (both stat through a link), and the `-le`
# bound stops a future-dated stamp from throttling forever — both are load-bearing.
if [ -f "$stamp" ] && [ ! -L "$stamp" ] && [ -O "$stamp" ]; then
  last="$(cat "$stamp" 2>/dev/null || true)"
  last="${last//[^0-9]/}"
  if [ -n "$last" ] && [ "$last" -le "$now" ] && [ $(( now - last )) -lt 86400 ]; then
    exit 0
  fi
fi

# Refresh the marketplace snapshot, then re-pin the install to it. Never fail the
# session — a network hiccup or missing CLI must not block startup.
codex plugin marketplace upgrade cekura >/dev/null 2>&1 || true
codex plugin add cekura@cekura >/dev/null 2>&1 || true

# Touch the filesystem only on the path that actually writes — the throttle above
# exits clean on all but one launch per day, and `[ -f ]` is already false when
# the dir is absent. The rm is unconditional: same effect as truncating a regular
# file, and it drops a symlink planted at the stamp path.
mkdir -p "$stamp_dir" 2>/dev/null || true
rm -f "$stamp" 2>/dev/null || true
echo "$now" > "$stamp" 2>/dev/null || true
exit 0

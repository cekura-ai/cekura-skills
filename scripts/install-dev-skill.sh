#!/usr/bin/env bash
# install-dev-skill.sh
# Copies the local cekura-create-agent skill into the EXISTING loaded
# cekura@cekura-skills plugin cache as "cekura-create-agent-dev".
#
# This avoids needing a separate plugin registration — it just adds a
# new skill to the already-loaded plugin, which Claude Code picks up
# on the next restart.
#
# Usage:
#   ./scripts/install-dev-skill.sh
#
# Run again any time you want to refresh after new commits.

set -euo pipefail

SKILL_SRC="$(cd "$(dirname "$0")/.." && pwd)/cekura/skills/cekura-create-agent"
INSTALLED_PLUGINS="$HOME/.claude/plugins/installed_plugins.json"

# Find the current install path for cekura@cekura-skills
PLUGIN_INSTALL_PATH=$(python3 - "$INSTALLED_PLUGINS" << 'PY'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
entries = data["plugins"].get("cekura@cekura-skills", [])
if not entries:
    print("")
else:
    print(entries[0]["installPath"])
PY
)

if [ -z "$PLUGIN_INSTALL_PATH" ]; then
  echo "✗ cekura@cekura-skills not found in installed_plugins.json"
  echo "  Make sure the cekura plugin is installed first."
  exit 1
fi

SKILL_DST="$PLUGIN_INSTALL_PATH/skills/cekura-create-agent-dev"

echo "→ Plugin path: $PLUGIN_INSTALL_PATH"
echo "→ Copying skill to: $SKILL_DST"

mkdir -p "$SKILL_DST"
cp -r "$SKILL_SRC/." "$SKILL_DST/"

echo "→ Renaming skill to cekura-create-agent-dev..."
sed -i '' 's/^name: cekura-create-agent$/name: cekura-create-agent-dev/' "$SKILL_DST/SKILL.md"

echo ""
echo "✓ Done. Restart Claude Code to pick up the skill."
echo "  Skill name: cekura:cekura-create-agent-dev"
echo ""
echo "  To refresh after new commits, just run this script again."

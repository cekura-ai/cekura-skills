#!/usr/bin/env bash
# install-dev-skill.sh
# Installs the local cekura-create-agent skill as "cekura-create-agent-dev"
# so you can test the latest branch without hitting the cached production version.
#
# Usage:
#   ./scripts/install-dev-skill.sh
#
# Run this again any time you want to refresh after new commits.

set -euo pipefail

SKILL_SRC="$(cd "$(dirname "$0")/.." && pwd)/cekura/skills/cekura-create-agent"
# Plugin dir name must match the plugin name key registered in installed_plugins.json
PLUGIN_CACHE="$HOME/.claude/plugins/cache/cekura-skills-dev/cekura-dev/1.0.0"
SKILL_DST="$PLUGIN_CACHE/skills/cekura-create-agent-dev"
INSTALLED_PLUGINS="$HOME/.claude/plugins/installed_plugins.json"

echo "→ Copying skill files..."
mkdir -p "$SKILL_DST"
cp -r "$SKILL_SRC/." "$SKILL_DST/"

echo "→ Renaming skill to cekura-create-agent-dev..."
sed -i '' 's/^name: cekura-create-agent$/name: cekura-create-agent-dev/' "$SKILL_DST/SKILL.md"

echo "→ Writing plugin.json..."
mkdir -p "$PLUGIN_CACHE/.claude-plugin"
cat > "$PLUGIN_CACHE/.claude-plugin/plugin.json" << 'JSON'
{
  "name": "cekura-dev",
  "version": "1.0.0",
  "description": "Cekura create-agent skill (local dev build — latest from branch)",
  "author": {
    "name": "Cekura",
    "email": "support@cekura.ai",
    "url": "https://cekura.ai"
  },
  "keywords": ["cekura", "voice-ai", "agent-setup", "dev"]
}
JSON

echo "→ Registering in installed_plugins.json..."
python3 - "$INSTALLED_PLUGINS" "$PLUGIN_CACHE" << 'PY'
import json, sys
from datetime import datetime, timezone

path, install_path = sys.argv[1], sys.argv[2]

with open(path) as f:
    data = json.load(f)

data["plugins"]["cekura-dev@cekura-skills-dev"] = [
    {
        "scope": "user",
        "installPath": install_path,
        "version": "1.0.0",
        "installedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "gitCommitSha": "local-dev"
    }
]

with open(path, "w") as f:
    json.dump(data, f, indent=2)
PY

echo ""
echo "✓ Done. Restart Claude Code to pick up the skill."
echo "  Skill name: cekura:cekura-create-agent-dev"
echo ""
echo "  To refresh after new commits, just run this script again."

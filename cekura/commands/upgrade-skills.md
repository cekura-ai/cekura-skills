---
name: upgrade-skills
description: Update Cekura skills to the latest version from GitHub
allowed-tools: ["Bash", "Read", "Grep", "mcp__cekura__cekura_skill_started", "mcp__cekura__cekura_report_issue"]
---
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="upgrade-skills"`. If a conversation/session ID is available (e.g. you
were invoked from Cekura sandbox), also pass it as `conversation_id`. The call
returns immediately; it lets us understand which skills are actually being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, call `mcp__cekura__cekura_report_issue` to flag it. Use this
LIBERALLY — even `severity="low"` reports are valuable feedback.

Upgrade the Cekura plugin to the latest published version.

## Process

### 1. Re-pin the plugin to the latest version (this is the actual upgrade)

Run both CLI commands. The first refreshes the marketplace catalog from GitHub; the second moves the installed **version pin** to the latest. A plain `git pull` of the marketplace checkout does **not** move the pin — which is why sessions can keep loading an old version after a "successful" pull. These commands do move it.

```bash
claude plugin marketplace update cekura-skills
claude plugin update cekura@cekura-skills
```

If either command errors:
- **Network / auth:** check internet access and GitHub credentials, then retry.
- **`Source path does not exist` or the update is a no-op while the version is clearly behind:** this is the stale-layout case — jump to step 3.

### 2. Apply it in the current session

Tell the user to run `/reload-plugins` — it hot-reloads the newly pinned version with no restart in the common case. If `/reload-plugins` warns about an MCP cache invalidation, a restart (or `/reload-plugins --force`) applies it. `/reload-plugins` only reloads what's already pinned on disk, so it must run **after** step 1, not instead of it.

### 3. Detect stale plugin entries from a previous Cekura layout

If found, surface the reinstall instructions:

   ```bash
   INSTALLED="$HOME/.claude/plugins/installed_plugins.json"
   if [ -f "$INSTALLED" ] && python3 -c "
   import json, sys
   try:
       d = json.load(open('$INSTALLED'))
       p = d.get('plugins', {})
       sys.exit(0 if 'cekura-evals@cekura-skills' in p or 'cekura-metrics@cekura-skills' in p else 1)
   except Exception:
       sys.exit(1)
   " 2>/dev/null; then
     cat <<'EOF'

   ⚠  Stale plugin entries detected from a previous Cekura layout.

   The plugin source has been pulled to the latest layout, but Claude Code
   is still referencing the old plugin entries. To finish the upgrade, run
   these 4 commands in order in your Claude Code session:

     /plugin marketplace remove cekura-skills
     /plugin marketplace add cekura-ai/cekura-skills
     /plugin marketplace update cekura-skills
     /plugin install cekura@cekura-skills

   See README "Reinstalling Cekura skills" for details.
   EOF
   fi
   ```

   If the detection prints the migration note, surface it verbatim to the user — for the stale-layout cohort the 4-command reinstall replaces step 1 (the version pin points at a dead plugin name, so `claude plugin update` alone can't fix it).

## Output

Report a summary:
- Whether the marketplace catalog refreshed cleanly
- Whether the plugin re-pinned to a newer version (note the version if the CLI reported it)
- Whether stale legacy entries were detected (and the reinstall note surfaced)
- A reminder to run `/reload-plugins` to apply the new version, if not already done

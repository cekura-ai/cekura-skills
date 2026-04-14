---
name: upgrade-skills
description: Update all Cekura skills to the latest version from GitHub
allowed-tools: ["Bash", "Read", "Grep"]
---

Upgrade all Cekura plugins to the latest version by pulling from the remote repository.

## Process

1. Find the cekura-skills marketplace directory. It should be at one of:
   - The marketplace install path (check `~/.claude/plugins/marketplaces/cekura-skills/`)
   - Or find it by searching for the marketplace name

2. Check current state:
   ```bash
   cd <marketplace_path>
   git status
   git log --oneline -3
   ```

3. If there are local modifications, warn the user and show what would be lost. Ask for confirmation before proceeding.

4. Pull latest:
   ```bash
   git pull origin main
   ```

5. Show what changed:
   ```bash
   git log --oneline -5
   ```

6. Report which plugins were updated and what changed (new skills, updated commands, etc.).

## If Pull Fails

- **Merge conflicts:** Show the conflicts and ask the user how to proceed. Offer to reset to remote (`git reset --hard origin/main`) with explicit confirmation.
- **Network error:** Suggest checking internet connection or GitHub access.
- **Authentication:** Suggest checking GitHub credentials or SSH keys.

## Output

Report a summary:
- Previous version (commit hash before pull)
- New version (commit hash after pull)
- Files changed (grouped by plugin: cekura-metrics, cekura-evals, cekura)
- Any new skills, commands, or agents added

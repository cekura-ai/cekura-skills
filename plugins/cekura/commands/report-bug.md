---
name: report-bug
description: Report a bug in a Cekura skill, command, or MCP integration
argument-hint: "[description of what went wrong]"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
---

# Report a Cekura Skills Bug

Collect context about a bug the user encountered and file it as a GitHub issue on `cekura-ai/claude-skills`. If the user doesn't have `gh` CLI, format the report for manual submission.

## Process

### 1. Collect Bug Context

If the user didn't provide details in the arguments, ask:
- "What were you trying to do?" (which skill, command, or workflow)
- "What went wrong?" (error message, unexpected behavior, etc.)

### 2. Gather Environment Info Automatically

Run these silently to collect system context:

```bash
# Claude Code version
claude --version 2>/dev/null || echo "unknown"

# OS
uname -s -r

# Check if MCP server is reachable
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/mcp 2>/dev/null || echo "unreachable"

# Check CEKURA_API_KEY is set (don't log the actual key)
[ -n "$CEKURA_API_KEY" ] && echo "API key: set" || echo "API key: NOT SET"

# Check marketplace repo state
cd ~/.claude/plugins/marketplaces/cekura-skills && git log --oneline -1 2>/dev/null
```

### 3. Check for Recent MCP Failure Logs

Look for the failure log that the hook writes to:

```bash
tail -20 ~/.claude/cekura-mcp-failures.log 2>/dev/null
```

If recent entries exist (within last 10 minutes), include them in the report. These give exact tool names and error messages.

### 4. Identify the Affected File (if possible)

If the bug is in a specific skill or command, find the relevant file:

```bash
# Skills
ls ~/.claude/plugins/marketplaces/cekura-skills/plugins/*/skills/*/SKILL.md

# Commands
ls ~/.claude/plugins/marketplaces/cekura-skills/plugins/*/commands/*.md
```

Read the relevant file to check for obvious issues (wrong MCP tool names, stale API endpoints, etc.).

### 5. Attempt a Quick Fix (if clearly fixable)

If the issue is clearly a typo, wrong tool name, or stale reference in a skill/command file:

1. Describe the fix to the user: "I can see the issue — [description]. I can fix this locally and open a PR."
2. If user approves:
   ```bash
   cd ~/.claude/plugins/marketplaces/cekura-skills
   git checkout -b fix/<short-description>
   # Make the edit
   git add <file>
   git commit -m "fix: <description>"
   ```
3. Try to push and open a PR:
   ```bash
   git push origin fix/<short-description>
   gh pr create --repo cekura-ai/claude-skills --title "fix: <description>" --body "<details>"
   ```
4. If push fails (no access), tell the user: "Fix applied locally. The maintainers have been notified via the issue below."

### 6. File the GitHub Issue

Format and create the issue:

```bash
gh issue create --repo cekura-ai/claude-skills \
  --title "Bug: <short description>" \
  --label "bug" \
  --body "$(cat <<'EOF'
## Bug Report

**What happened:**
<user's description>

**Which skill/command:**
<skill or command name>

**Steps to reproduce:**
1. <step>
2. <step>

**Error output:**
```
<error message or unexpected behavior>
```

## Environment
- **Claude Code version:** <version>
- **OS:** <os>
- **MCP server:** <reachable/unreachable>
- **API key:** <set/not set>
- **Plugin version:** <git commit hash>

## Recent MCP Failures (if any)
```
<from failure log>
```

## Suggested Fix (if identified)
<fix description, or "No obvious fix identified">

---
*Filed automatically via `/report-bug` in Cekura Skills*
EOF
)"
```

### 7. Fallback: No `gh` CLI

If `gh` is not installed or not authenticated:

1. Format the full bug report as markdown
2. Print it to the user with instructions:
   - "I couldn't file this automatically. Here's the formatted report:"
   - "You can submit it at: https://github.com/cekura-ai/claude-skills/issues/new"
   - Or: "Send this to the Cekura team at support@cekura.ai"

### 8. Confirm

Tell the user:
- Issue URL (if created via gh)
- Whether a local fix was applied
- Whether a PR was opened
- Suggest `/upgrade-skills` once the fix is merged

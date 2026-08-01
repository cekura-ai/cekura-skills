---
name: report-bug
description: Report a bug in a Cekura skill, command, or MCP integration
argument-hint: "[description of what went wrong]"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion", "mcp__cekura__cekura_skill_started", "mcp__cekura__cekura_report_issue"]
---
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="report-bug"`. If a conversation/session ID is available (e.g. you
were invoked from Cekura sandbox), also pass it as `conversation_id`. The call
returns immediately; it lets us understand which skills are actually being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, flag it with `mcp__cekura__cekura_report_issue` — even
`severity="low"` reports are valuable feedback. **Show the user the report text
and get their OK before sending it.** The description is free text and can quote
their workflow, so it needs the same review as anything else leaving the machine.

# Report a Cekura Skills Bug

Collect context about a bug the user encountered and file it as a GitHub issue on `cekura-ai/cekura-skills`. If the user doesn't have `gh` CLI, format the report for manual submission.

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

# Check if Cekura MCP server is reachable (production)
curl -s -o /dev/null -w "%{http_code}" https://api.cekura.ai/mcp 2>/dev/null || echo "unreachable"

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

**Scrub before including.** `hooks/on-mcp-failure.sh` already masks credential-shaped tokens on the way into this log (`sk-`/`Bearer` tokens, JWTs, `key=`/`token=`/`secret=` assignments, and any 32+ char token run), so entries usually arrive with `[REDACTED]` in place. It cannot pattern-match the rest — before putting an excerpt in the issue body, redact **email addresses, phone numbers, customer or org names, and account numbers** yourself. When unsure whether a value is sensitive, redact it; the maintainers can ask privately.

### 4. Identify the Affected File (if possible)

If the bug is in a specific skill or command, find the relevant file:

```bash
# Skills
ls ~/.claude/plugins/marketplaces/cekura-skills/cekura/skills/*/SKILL.md

# Commands
ls ~/.claude/plugins/marketplaces/cekura-skills/cekura/commands/*.md
```

Read the relevant file to check for obvious issues (wrong MCP tool names, stale API endpoints, etc.).

### 5. Attempt a Quick Fix (if clearly fixable)

If the issue is clearly a typo, wrong tool name, or stale reference in a skill/command file:

1. Describe the fix to the user: "I can see the issue — [description]. I can fix this locally, then optionally open a PR."
2. If the user approves:
   ```bash
   cd ~/.claude/plugins/marketplaces/cekura-skills
   git checkout -b fix/<short-description>
   # Make the edit
   git add <file>
   git commit -m "fix: <description>"
   ```
3. Show the diff and the PR body, then push and open the PR:
   ```bash
   git push origin fix/<short-description>
   gh pr create --repo cekura-ai/cekura-skills --title "fix: <description>" --body-file /tmp/cekura-pr-body.md
   ```
   Write the PR body with `Write` and pass `--body-file`, same as the issue body in Step 6 — never interpolate log or error text into a shell heredoc.
4. If push fails (no access), tell the user: "Fix applied locally. The maintainers have been notified via the issue below."

### 6. File the GitHub Issue

**The issue lands on a public repository.** Before running `gh issue create`, show the user the complete issue body (including any scrubbed log excerpts from Step 3) and get their explicit OK to publish it. Do not file the issue without that confirmation.

Write the body to a file with the `Write` tool, then pass it with `--body-file`. **Never build the body inline with a heredoc or `--body "$(...)"`.** Failure-log text is not user-authored — it comes from MCP error responses that echo request payloads — and a single bare `EOF` line in it would terminate a heredoc early, leaving the rest of the log to be parsed as shell inside the command substitution. `--body-file` keeps the content out of the shell entirely.

Write this content to `/tmp/cekura-bug-report.md` (via `Write`, not `cat`):

```markdown
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
```

Then file it:

```bash
gh issue create --repo cekura-ai/cekura-skills \
  --title "Bug: <short description>" \
  --label "bug" \
  --body-file /tmp/cekura-bug-report.md
rm -f /tmp/cekura-bug-report.md
```

### 7. Fallback: No `gh` CLI

If `gh` is not installed or not authenticated:

1. Format the full bug report as markdown
2. Print it to the user with instructions:
   - "I couldn't file this automatically. Here's the formatted report:"
   - "You can submit it at: https://github.com/cekura-ai/cekura-skills/issues/new"
   - Or: "Send this to the Cekura team at support@cekura.ai"

### 8. Confirm

Tell the user:
- Issue URL (if created via gh)
- Whether a local fix was applied
- Whether a PR was opened
- Suggest `/upgrade-skills` once the fix is merged

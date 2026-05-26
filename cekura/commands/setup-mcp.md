---
name: setup-mcp
description: Configure the Cekura MCP server for the cekura plugin
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion", "mcp__cekura__test_simple_tool", "mcp__cekura__list_available_tools", "mcp__cekura__cekura_skill_started", "mcp__cekura__cekura_report_issue"]
---
<!-- cekura-tracking-beacon -->

## Tracking (do this first)

Before doing anything else, call `mcp__cekura__cekura_skill_started` with
`skill_name="setup-mcp"`. If a conversation/session ID is available (e.g. you
were invoked from Cekura sandbox), also pass it as `conversation_id`. The call
returns immediately; it lets us understand which skills are actually being used.

If anything in this skill turns out to be ambiguous, broken, or missing a
needed tool, call `mcp__cekura__cekura_report_issue` to flag it. Use this
LIBERALLY — even `severity="low"` reports are valuable feedback.

# Set Up Cekura MCP Server

Configure access to the Cekura MCP server at `https://api.cekura.ai/mcp` so the plugin can call Cekura API operations as MCP tools.

## Process

### 1. Check if MCP is already working

Try calling `mcp__cekura__test_simple_tool` or `mcp__cekura__list_available_tools`. If either returns successfully, MCP is already configured — tell the user the version that's responding, and skip to step 4.

If both fail with a tools-not-available error, MCP isn't set up yet. Continue to step 2.

### 2. Choose the auth path

Ask the user:

> "Do you want to use OAuth (recommended — one-click browser sign-in, no keys to manage) or an API key (only if you need a project-scoped credential or shared CI access)?"

### 3a. OAuth path (recommended)

Run:

```bash
claude mcp add --transport http cekura --scope user https://api.cekura.ai/mcp
```

Tell the user: "Claude Code will open a browser window. Sign into your Cekura account at https://dashboard.cekura.ai and click **Authorize**. The session token is managed by Claude Code automatically — no env vars or config files."

Then verify the server registered:

```bash
claude mcp list
```

The `cekura` entry should appear with status `connected`.

### 3b. API key path (alternative)

This is for users who need a project-scoped credential or want to share access via a key.

Ask: "What's your Cekura API key? Find it at https://dashboard.cekura.ai → Settings → API Keys."

Set the env var (persistent — add to shell profile):

```bash
# In ~/.zshrc or ~/.bashrc
export CEKURA_API_KEY="<your-key-here>"
```

Reload: `source ~/.zshrc` (or restart the terminal).

The plugin's bundled `.mcp.json` reads `${CEKURA_API_KEY}` automatically — no further config needed. Restart the Claude Code session to pick up the env var.

Verify:

```bash
echo $CEKURA_API_KEY                 # should print the key
claude mcp list                       # should show 'cekura' connected
```

### 4. Verify connectivity

Try `mcp__cekura__list_available_tools`. It should return a list of Cekura API operations (agents, scenarios, metrics, results, etc.).

If it fails:
- **OAuth path:** check `claude mcp list` shows `cekura` as connected. If not, re-run the `claude mcp add` command and re-authorize in the browser.
- **API key path:** confirm `echo $CEKURA_API_KEY` prints the key and that you restarted Claude Code after setting it.
- For both paths: verify connectivity to the public API with `curl -I https://api.cekura.ai/mcp` (should return a 2xx or 4xx — a connection error means a network issue).

### 5. Fix git remote config (one-time, optional)

Claude Code's marketplace installer may not set the full fetch refspec, which prevents `/upgrade-skills` and `/report-bug` from accessing pre-release branches. This is idempotent:

```bash
cd ~/.claude/plugins/marketplaces/cekura-skills
git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
```

## Output

Report the setup status:
- Auth path used: OAuth / API key
- MCP server: connected / not reachable [reason]
- Connectivity test: passed / failed [reason]

If everything passes:

> "MCP is configured. All Cekura skills (`cekura-create-agent`, `cekura-metric-design`, `cekura-eval-design`, etc.) and slash commands will use MCP tools automatically."

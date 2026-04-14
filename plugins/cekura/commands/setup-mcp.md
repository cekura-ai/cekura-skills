---
name: setup-mcp
description: Configure the Cekura MCP server for all Cekura plugins
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion", "mcp__cekura__test_simple_tool", "mcp__cekura__list_available_tools"]
---

# Set Up Cekura MCP Server

Configure the Cekura MCP server so all Cekura plugins (`cekura`, `cekura-metrics`, `cekura-evals`) can access the Cekura API through MCP tools.

## Process

### 1. Check if MCP is already working

Try calling `mcp__cekura__list_available_tools` or `mcp__cekura__test_simple_tool`. If either responds successfully, MCP is already configured — tell the user and skip to step 5 (verification).

### 2. Get the API key

Ask: "What's your Cekura API key? You can find it at https://dashboard.cekura.ai under Settings → API Keys."

The key should be set as an environment variable. Guide the user:

```bash
# Add to your shell profile (~/.zshrc or ~/.bashrc)
export CEKURA_API_KEY="<your-key-here>"
```

Then reload: `source ~/.zshrc` (or restart the terminal).

Verify it's set:
```bash
echo $CEKURA_API_KEY
```

### 3. Start the MCP server

The Cekura MCP server bridges the Cekura API to Claude Code's MCP protocol.

**Option A: If you have the server locally:**
```bash
cd /path/to/cekura-mcp-server && python3 openapi_mcp_server.py
```
The server runs on `http://localhost:8001/mcp`.

**Option B: If you don't have it:**
Ask the user to contact Cekura support or check the docs at https://docs.cekura.ai for the MCP server setup instructions.

### 4. Fix git remote config

Claude Code's marketplace installer may not set the full fetch refspec, which prevents branch operations (`/report-bug`, `/upgrade-skills`, checking out pre-release branches). Fix it:

```bash
cd ~/.claude/plugins/marketplaces/cekura-skills
git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
```

This is idempotent — safe to run even if already set.

### 5. Verify the .mcp.json files exist

Each Cekura plugin has a `.mcp.json` that auto-connects to the MCP server. Check they exist:

```bash
ls ~/.claude/plugins/marketplaces/cekura-skills/plugins/cekura/.mcp.json
ls ~/.claude/plugins/marketplaces/cekura-skills/plugins/cekura-metrics/.mcp.json
ls ~/.claude/plugins/marketplaces/cekura-skills/plugins/cekura-evals/.mcp.json
```

All three should contain:
```json
{
  "mcpServers": {
    "cekura-api": {
      "type": "http",
      "url": "http://localhost:8001/mcp",
      "headers": {
        "X-CEKURA-API-KEY": "${CEKURA_API_KEY}"
      }
    }
  }
}
```

If any are missing, the user may need to run `/upgrade-skills` to pull the latest plugin versions.

### 6. Verify connectivity

After setup, restart Claude Code to pick up the `.mcp.json` config, then test:

Try `mcp__cekura__list_available_tools` — it should return a list of available Cekura API operations.

If it fails, check:
1. Is `CEKURA_API_KEY` set? (`echo $CEKURA_API_KEY`)
2. Is the MCP server running? (`curl -s http://localhost:8001/mcp` should respond)
3. Did you restart Claude Code after adding the `.mcp.json` files?

## Output

Report the setup status:
- API key: configured / missing
- MCP server: running / not reachable
- .mcp.json files: all present / missing [which]
- Connectivity test: passed / failed [reason]

If everything passes: "MCP is configured. All Cekura commands and skills (`/metric-design`, `/eval-design`, `/create-agent`, etc.) will use MCP tools automatically."

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
needed tool, flag it with `mcp__cekura__cekura_report_issue` — even
`severity="low"` reports are valuable feedback. **Show the user the report text
and get their OK before sending it.** The description is free text and can quote
their workflow, so it needs the same review as anything else leaving the machine.

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

Register the server with the key sent as a header, at `local` scope so this entry overrides the plugin's bundled (OAuth) `cekura` entry:

```bash
claude mcp add --transport http cekura --scope local \
  --header "X-CEKURA-API-KEY: <your-key-here>" \
  https://api.cekura.ai/mcp
```

Pass the **actual key value**, not a `${CEKURA_API_KEY}` reference — header values in an HTTP MCP entry are sent verbatim, so a placeholder would be transmitted literally and rejected as an invalid key.

Note: a key embedded in a config file can leak via dotfile repos, backups, or screen-shares. If you sync your config anywhere, prefer the OAuth path, which stores no key at all.

Verify:

```bash
claude mcp list                       # should show 'cekura' connected
```

### 4. Verify connectivity

Try `mcp__cekura__list_available_tools`. It should return a list of Cekura API operations (agents, scenarios, metrics, results, etc.).

If it fails:
- **OAuth path:** check `claude mcp list` shows `cekura` as connected. If not, re-run the `claude mcp add` command and re-authorize in the browser.
- **API key path:** run `claude mcp list` and confirm the `cekura` entry shows `connected`. If you get an "invalid API key" error, re-run the `claude mcp add` command with the literal key value (not a `${...}` placeholder).
- For both paths: verify connectivity to the public API with `curl -I https://api.cekura.ai/mcp` (should return a 2xx or 4xx — a connection error means a network issue).

### 5. Fix git remote config (one-time, optional)

Claude Code's marketplace installer may not set the full fetch refspec, which prevents `/upgrade-skills` and `/report-bug` from accessing pre-release branches. This is idempotent:

```bash
cd ~/.claude/plugins/marketplaces/cekura-skills
git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
```

### 6. Offer to enable auto-updates (optional)

Third-party marketplaces like `cekura-skills` do **not** auto-update by default — only Anthropic's official marketplace does. Without this, the user has to run `/upgrade-skills` manually to pick up new versions.

Ask the user:

> "Want Claude Code to pull new Cekura versions automatically at launch?
>
> What this means: at each launch, Claude Code fetches the latest `cekura-skills` from GitHub and re-pins your install to it. That includes **executable hook scripts** that run automatically — not just skill text — so you're trusting whatever is on the repo's `main` branch at that moment, without reviewing it first. Updates are applied at launch; nothing installs mid-session, and you'll still be prompted to `/reload-plugins`.
>
> Prefer to review changes before they run? Decline this and run `/upgrade-skills` when you want an update instead."

If yes, merge the opt-in into `~/.claude/settings.json` (idempotent — preserves all other settings):

```bash
python3 - <<'EOF'
import json, os
p = os.path.expanduser("~/.claude/settings.json")
try:
    with open(p) as f:
        d = json.load(f)
except Exception:
    d = {}
mk = d.setdefault("extraKnownMarketplaces", {})
mk["cekura-skills"] = {
    "source": {"source": "github", "repo": "cekura-ai/cekura-skills"},
    "autoUpdate": True,
}
with open(p, "w") as f:
    json.dump(d, f, indent=2)
print("Auto-update enabled for cekura-skills in", p)
EOF
```

The change takes effect on the next Claude Code launch. To turn it off later, set `autoUpdate` to `false` in that same file.

## Output

Report the setup status:
- Auth path used: OAuth / API key
- MCP server: connected / not reachable [reason]
- Connectivity test: passed / failed [reason]
- Auto-update: enabled / declined

If everything passes:

> "MCP is configured. All Cekura skills (`cekura-create-agent`, `cekura-metric-design`, `cekura-eval-design`, etc.) and slash commands will use MCP tools automatically."

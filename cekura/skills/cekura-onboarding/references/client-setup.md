# Client Setup — OAuth / Plugin Install (fallback reference)

Only needed when Cekura platform tools are NOT available or failing in the current session. If tools are already working, auth is done — do not walk the user through any of this.

**Priority: get the user connected via the Cekura plugin's OAuth flow.** Every supported coding agent has a plugin, and all of them authenticate via OAuth (no API key needed). Full per-client instructions: https://docs.cekura.ai/mcp/overview

| Client | Install |
|---|---|
| Claude Code | `/plugin marketplace add cekura-ai/cekura-skills` → `/plugin install cekura@cekura-skills` → `/setup-mcp` |
| Claude Desktop | Customize → Plugins → Add marketplace `cekura-ai/cekura-skills` → install → authorize OAuth |
| Cursor | Settings → Plugins → Add Marketplace → Import from Repo `https://github.com/cekura-ai/cekura-skills` → install → authenticate |
| Codex | `codex plugin marketplace add cekura-ai/cekura-skills` → `codex plugin add cekura@cekura` → `codex mcp login cekura` |
| Gemini CLI | `gemini extensions install https://github.com/cekura-ai/cekura-skills` (OAuth triggers on first tool use) |

**Fallbacks, in order:**
1. Tools present but failing → re-run the client's OAuth step (`/setup-mcp` in Claude Code) and retry.
2. User prefers an API key → set it per the client's docs; verify with any cheap list call.

No account? No separate step — the OAuth sign-in page includes a **Sign up** link (and Google/SSO), so the OAuth flow covers account creation too.

# Phase 1 — Account & Project Setup (shared)

> **Start:** Announce "Starting Phase 1 — Account & Project".

**Skip this phase entirely if the user is already signed in with a project selected** (or Phase 0's state shows an existing project) — go straight to Phase 2. Don't re-ask account or project facts you already have.

## 1a. Verify account access — OAuth first

**Priority: get the user connected via the Cekura plugin's OAuth flow.** Every supported coding agent has a plugin, and all of them authenticate via OAuth (no API key needed). Full per-client instructions: https://docs.cekura.ai/mcp/overview

| Client | Install |
|---|---|
| Claude Code | `/plugin marketplace add cekura-ai/cekura-skills` → `/plugin install cekura@cekura-skills` → `/setup-mcp` |
| Claude Desktop | Customize → Plugins → Add marketplace `cekura-ai/cekura-skills` → install → authorize OAuth |
| Cursor | Settings → Plugins → Add Marketplace → Import from Repo `https://github.com/cekura-ai/cekura-skills` → install → authenticate |
| Codex | `codex plugin marketplace add cekura-ai/cekura-skills` → `codex plugin add cekura@cekura` → `codex mcp login cekura` |
| Gemini CLI | `gemini extensions install https://github.com/cekura-ai/cekura-skills` (OAuth triggers on first tool use) |

If platform tools are already working in this session, auth is done — verify with one cheap call (`metrics_list`; a successful response, even empty, confirms access) and move on.

**Fallbacks, in order:**
1. Tools present but failing → re-run the client's OAuth step (`/setup-mcp` in Claude Code) and return here.
2. User prefers an API key → verify it with `metrics_list`.
3. OAuth sign-in fails because no Cekura account exists → sign up at https://dashboard.cekura.ai/sign-up, then retry OAuth. Don't lead with the signup link — the OAuth flow is the front door.

## 1b. Project setup

Ask: "Do you already have a project, or do we need to create one?"

**If creating:** create it with `projects_create`.

**Project organization guidance:**
- Small teams: single project for multiple agents.
- Enterprises: separate projects by team and environment (staging vs production).
- Each project gets its own metrics, evaluators, and observability data.

---

## Phase 1 Gate

**Do not proceed until a tool call has succeeded against the user's project** (e.g. `metrics_list` or `projects_list` returned 200) — that proves auth and project selection are real.

Announce: "Phase 1 complete." Then begin [Phase 2 — Agent](phase2-agent.md).

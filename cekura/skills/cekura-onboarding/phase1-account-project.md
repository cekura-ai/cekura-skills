# Phase 1 — Account & Project Setup (shared)

> **Start:** Announce "Starting Phase 1 — Account & Project".

**Skip this phase entirely if the user is already signed in with a project selected** (or Phase 0's state shows an existing project) — go straight to Phase 2. Don't re-ask account or project facts you already have.

## 1a. Verify account access

Ask:
- "Do you already have a Cekura account?"
- "Do you have an API key, or do you sign in via OAuth?"

If they have an API key, verify it works by listing metrics (`metrics_list`). A successful response (even empty) confirms the key is valid.

If they don't have an account, direct them to https://dashboard.cekura.ai/sign-up.

**Claude Code plugin users:** if platform tools aren't working, run `/setup-mcp` to configure API access, then return here.

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

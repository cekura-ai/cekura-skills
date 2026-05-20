# Phase 1 — Project Selection

Identify which Cekura project the agent should belong to before collecting any other details.

---

## 1a. Check if the user knows their project ID

Ask: "Which Cekura project should this agent live in? I can list your projects if you're not sure."

If they don't know, list projects via the Cekura API or dashboard → display names + IDs → ask user to pick one.

Note the selected `project_id` — required for agent creation in Phase 5.

---

## Phase 1 Gate

**Do not proceed until you have a confirmed `project_id`.**

Move to [Phase 2 — Provider Selection](phase2-provider.md).

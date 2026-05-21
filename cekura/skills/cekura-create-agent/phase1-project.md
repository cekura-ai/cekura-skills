# Phase 1 — Project Selection

Identify which Cekura project the agent should belong to before collecting any other details.

---

> **Start:** Announce "Starting Phase 1 — Project Selection" before doing anything in this phase.

## 1a. Always list projects first

**Always fetch the list of projects before asking the user anything.** Do not assume a project or skip this step even if the user mentions a project name.

Fetch the project list via the Cekura API or dashboard.

**If there is only one project:** confirm it with the user ("I can see you only have one project — [name]. Should I create the agent there?") and proceed only after they confirm.

**If there are multiple projects:** display the full list with names and IDs, and ask the user to pick one:

> "You have the following projects — which one should this agent be created in?"
> 1. [Project Name A] (ID: 123)
> 2. [Project Name B] (ID: 456)
> 3. [Project Name C] (ID: 789)

Wait for the user to choose. Do not guess or default to the first one.

Note the selected `project_id` — required for agent creation in Phase 5.

---

## Phase 1 Gate

**Do not proceed until the user has explicitly selected a project and you have its `project_id`.**

Announce: "Phase 1 complete." Then immediately begin [Phase 2 — Provider Selection](phase2-provider.md) without waiting for the user.

# Phase 0 — Choose the Path & Assess State

> **Start:** Announce "Starting Phase 0 — Path & State Assessment".

## 0a. Choose the path

If the caller already specified a path — via the `/cekura-onboarding` command argument or the invoking context — honour it without asking.

Otherwise, ask once:

> Two onboarding paths — which fits your goal?
> - **Testing** *(default)* — build evaluators and run simulated calls against your agent.
> - **Observability** — ingest your production call logs and evaluate them.

Default to **testing** when ambiguous.

## 0b. State assessment (do this once)

Survey what already exists before walking the user through any phase. This prevents asking "Resume where?" on an empty project and prevents skipping past existing work.

**Gathering state:**
- If you were handed an inventory (e.g. the `/cekura-onboarding` command pre-detected project state), trust it — don't re-run the same lookups.
- Otherwise, list the path-relevant resources: agents and metrics for both paths; plus scenarios and results for **testing**; plus call logs for **observability**.

**Decision:**

| State of the path's relevant resources | Action |
|---|---|
| **Clean slate** — none exist | Proceed straight to Phase 1 (or Phase 2 if account/project already set up). Don't ask "Resume where?" — there's nothing to resume. |
| **Mid-onboarding** — some resources exist but the flow is incomplete | Surface ONE concrete clarification: e.g. "Found existing agent **Booking Bot** with 12 scenarios and 1 result. Continue with it, or create a new agent?" — never a generic "Ready to continue?". |
| **Obvious from the user's message** — "create a new agent" / "start fresh" / a named agent | Honour that intent without an extra confirm. |

---

## Phase 0 Gate

**Do not proceed until the path is decided and the project state is known.**

Announce: "Phase 0 complete." Then begin [Phase 1 — Account & Project](phase1-account-project.md) (or Phase 2 if account/project already exist).

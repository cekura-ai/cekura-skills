# Phase 0 — Choose the Path & Check for Existing Work

> **Start:** Announce the step in plain words (e.g. "Let's connect your agent", "Generating your first evaluators") — never a phase number or the word "Phase"; the numbering below is internal navigation only.

## 0a. Choose the path

If the caller already specified a path — via the `/cekura-onboarding` command argument or the invoking context — honour it without asking.

Otherwise, ask once:

> Three onboarding paths, which fits your goal?
> - **Testing** *(default)*: build evaluators and run simulated calls against your agent.
> - **Observability**: ingest your production call logs and evaluate them.
> - **Integrate my codebase**: wire your own voice-agent repo into Cekura (config sync, transcript ingestion, metadata, tracing, CI/CD).

Default to **testing** when ambiguous. Pick **integrate** only when the user has their **own codebase** they can instrument (custom / self-hosted, LiveKit, or Pipecat). A **managed-platform** agent (VAPI / Retell / ElevenLabs / Synthflow / Bland / ...) has no code to wire, so it does NOT belong on the integrate path: those providers are ingested natively on the **testing** and **observability** paths. If a user asks to "integrate" a managed-platform agent, route them to testing or observability instead.

## 0b. Existing-work check (ONE call, not an inventory sweep)

**The first objective of onboarding is connecting the agent — get there fast.** Do NOT survey metrics, predefined-metric catalogs, scenarios, or results up front; each later phase checks its own state when it runs.

- If you were handed an inventory (e.g. the `/cekura-onboarding` command pre-detected project state), trust it — don't re-run lookups.
- Otherwise make exactly one call: `aiagents_list` on the current project.

**Decision:**

| `aiagents_list` result | Action |
|---|---|
| **0 agents** (the common case for onboarding) | Clean slate. Go straight to Phase 2 — connect the agent. No further lookups, no "Resume where?" question. |
| **≥1 agent** | Possible mid-onboarding resume. Now (and only now) look deeper — the path-relevant resources: scenarios + latest result for **testing**, call logs for **observability**, the agent's `description` + `transcript_provider` for **integrate**. Surface ONE concrete clarification: e.g. "Found existing agent **Booking Bot** with 12 scenarios and 1 result. Continue with it, or create a new agent?" — never a generic "Ready to continue?". |
| **Call fails (auth/tools broken)** | Fix access first — see [references/client-setup.md](references/client-setup.md). If there's no project in context, list with `projects_list` or create one with `projects_create`, then retry. |

---

## Phase 0 Gate

**Do not proceed until the path is decided and the agent check has run (or an inventory was handed in).**

Confirm the step is done in plain words (no phase numbers). Then begin [Phase 2 — Agent](phase2-agent.md).

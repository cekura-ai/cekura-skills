# Phase 6 — Close out (LiveKit / Pipecat)

> **Start:** No announcement. This is the last thing you say, not a step you narrate.

Every path through this skill ends here — finished, declined at any question, or the user taking over. **This file is the ending**; `cekura-onboarding`'s own phases are never run, before or after. Onboarding is over when this summary is written.

## 6a. Write the summary

One message, in this shape. Skip any line that has nothing to report — never write a heading with "N/A" under it.

**What's set up**
- The agent, by name, linked as `{dashboard_url}/agents/{agent_id}`.
- How Cekura reaches it: WebRTC, dispatching by the agent name you found in the repo.
- The evaluators, by count.

**What ran**
- The result link: `{dashboard_url}/{project_id}/results/{result_id}` — this route **is** project-scoped, unlike the agent one.
- The headline numbers: how many passed, how many didn't. 70–80% on a first run is normal and worth saying so, or the user reads a red number as a broken agent.
- One transcript worth reading, named and linked.

**The pull request**, if one was opened — the link, and the three things only the user can do:
1. create an API key at `{dashboard_url}/settings/org/api-key`
2. set `CEKURA_API_KEY` and `CEKURA_AGENT_ID` in the deployment environment
3. redeploy the worker

**Open items** — carry these verbatim from whichever fallback landed here. Each one is a thing that is *not* done, stated plainly:
- placeholder credentials never replaced (F3)
- no verified run (F4)
- a run that never connected (F5)
- the SDK declined (F6, F7)
- the PR raised but tracing still off (F8)

## 6b. What's next — offered once, as options

Name these in one short list. They are things the user can come back for, **not** steps, not a plan, and not a pitch:

| If they want | Point them at |
|---|---|
| More coverage — red-team cases, edge cases, other languages | the `cekura-eval-design` skill |
| Mock tools, a knowledge base, dynamic variables | the `cekura-create-agent` skill |
| Metrics beyond the defaults | the `cekura-metric-design` skill |
| Scoring real production calls | the observability path — the SDK's `observe_*` methods |

**Anything the user already declined does not appear here.** Re-listing the SDK after "Not now" is the same pitch a second time, and it reads as not listening.

## 6c. Stop

Do not ask a follow-up question. Do not offer to keep going. Do not run `cekura-onboarding`'s phases 3T–6T — this skill replaced them for these two providers, and running them re-does the agent, the evaluators and the run the user just watched.

If the user asks for something new after this, that is an ordinary request: answer it, or load the skill that fits it.

---

## Phase 6 Gate

The summary is written, every open item is named, and the turn ends without a question.

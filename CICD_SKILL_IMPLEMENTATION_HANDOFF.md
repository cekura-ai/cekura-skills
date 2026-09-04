# Customer CI/CD Skill — Implementation Handoff

> **Review this file, then we implement.** Self-contained: state check, then the exact
> per-file changes proposed. No code has been changed.
>
> Background (optional reading): `CUSTOMER_CICD_SKILL_PLAN.md` (design rationale) and
> `pipecat-cloud-agents/CICD_SUITE_PLAN.md` (our own CI/CD gate, the parent effort).
>
> Target: `cekura/skills/cekura-infra-test-suite/` — extended, not forked.

---

## 1. State check (all repos fetched 2026-08-04)

| Repo | Branch | vs `origin/main` | Relevant movement |
|---|---|---|---|
| `cekura-skills` | `feature/customer-cicd-skill` | 6 behind | **`cekura-infra-test-suite` untouched.** All proposed changes apply cleanly |
| `pipecat-cloud-agents` | `feature/customer-cicd-skill` | 23 behind | **pr-eval workflows + `pr_eval_run.py` untouched.** 4 CA-processor commits (see below) |
| `vocera.backend` | `main` | 6 behind | `run-scenarios-json` **still unmerged** — confirms the JSON-spec path stays out of scope |
| `vocera.frontend.product` | `feature/json-test-suite-runs` | 0 | no change |

### Things that moved and actually matter

**1. The engine rule this design rests on is intact.** `conditional_actions_processor.py` gained
~190 lines across 4 commits (#803 DTMF at-most-once, reply-gate markup leak, inline-tag gating,
RTVI client_message). The retry-by-type branch survives verbatim — only its line number moved:

```
was  conditional_actions_processor.py:6057-6085
now  conditional_actions_processor.py:6246-6275     ← cite this
```

Text unchanged: `action_followup` retries the verbatim action; `standard` clears interrupted
state and re-evaluates because "blind re-dispatch creates an infinite 'Understood.' loop".

**2. A new CA tag shipped** — `cekura-eval-design/references/conditional-actions.md` gained:

```
<client_message t="..." d='...' />   RTVI client message to a Pipecat agent
```

Pipecat-specific. Relevant only to Mode B for pipecat customers; **not** part of the 8 cases.

**3. Nothing else in the skills tree changed** except `cekura-self-improving-agent` (Retell +
Bland provider support) and a one-line eval-design edit. No conflicts with anything below.

---

## 2. Proposed changes, in build order

Seven changes. **1–4 are corrections to what exists** and carry most of the quality gain.
**5–7 are the new Mode A surface.** Each is independently reviewable and shippable.

---

### Change 1 — Narrow the condition-type rule

**File:** `cekura/skills/cekura-infra-test-suite/phase5-build-run.md`, §5c cross-verification (~line 198)

**Now:**
> Is every condition after 0 using `type: "action_followup"` with `fixed_message: true`?
> **Any `standard` condition after 0 is a bug.**

**Problem:** this runs in the *verification* pass, so it rewrites correct scenarios into broken
ones. Infra suites are mostly idle-timer and silence-barge tests — exactly where `action_followup`
retries the action verbatim, restarting the pause, and loops. We hit this: result 148018,
"20s silence exposed the ENDLESS barge→replay loop (re-said cond1 13× to maxDuration)".

**Proposed:**
> `action_followup` is the default and is correct for scripted sequences — pure dependency, no NL
> predicate, no matcher latency. Use `type: "standard"` **only** for a condition whose action
> contains a deliberate pause the agent is expected to speak into. **Those conditions' predicates
> must be mutually distinguishable** — otherwise the matcher re-picks an already-executed
> condition and you have traded a verbatim-retry loop for a re-match loop.
> (Engine: `conditional_actions_processor.py:6246-6275`.)

The distinguishability clause is in neither the skill nor `conditional-actions.md` today. It cost
us runs 148015 and 148018; the fix was rewording cond1/cond2 so they read differently.

---

### Change 2 — Phase 4: exhaustive → focused

**File:** `phase4-plan.md`

| Location | Now | Proposed |
|---|---|---|
| ~line 54 (HARD RULE) | "Every actionable TEST-NNN item must appear in at least one scenario. **Zero items may be dropped.**" | Rank and cut. Everything not selected gets **one line in a parked list with a reason** |
| ~line 54, 106, 128 | An orphan item "gets its own standalone scenario"; "a single-item scenario is valid and expected" | Removed. Prefer adding a turn to an existing case over adding a case |
| ~lines 108-128 (Step 2b) | Blocking ITEM MAPPING output — every item must map, "Unmapped: 0" | Replaced by a ranked table: item → score → selected/parked |
| ~lines 130-148 (Step 3) | Per-component caps (STT 3, LLM 3, interruption 2, idle 2, TTS 2, VAD 2, transfer 2, side-channels 2 each) — sums past 16 before multi-language | **Hard cap of 6–10 for the whole suite** |

**New ranking rule.** Score each candidate on three axes, take the top N, cap at 10:
- **Likelihood it regresses** — Mode B: how often those files changed recently. Mode A: how
  central the behavior is to the agent's task.
- **Blast radius** — breaks the call, or degrades one turn?
- **Transcript-detectability** — can the judge see it? If not it scores zero. It isn't a test.

**New composition rule:** *each turn checks exactly one thing.* That's what lets one call carry
four assertions without becoming unfalsifiable.

**Evidence:** our own suite went 21 → 6 and the 6 were strictly better — 6/6 twice consecutively,
fast enough to iterate on. The 21-suite is being deleted.

---

### Change 3 — Determinism and judging rules

**File:** `phase5-build-run.md`, new subsection before §5c

Three rules, none currently stated:

1. **Determinism.** Every condition on **both** sides uses `fixed_message: true` — *with the
   rationale*: if the agent works, identical words every run, so a pass is guaranteed and a fail
   means the agent. Without it a red is ambiguous and the suite is untrustworthy. (§5b half-states
   the rule, never the reason.)
2. **What the judge cannot see.** Rule 4 says "test what's observable" but never says what isn't:
   ambience playing, volume/speed changes, beeps, or that a code was *spelled* — STT normalizes
   `"7 3 9 1"` → `"7391"`. We lost two runs to that one.
3. **Untriggered-check rule** (from run 148202): a check whose scripted **caller** trigger never
   fired should **pass, not fail** — unless the agent's own misbehavior prevented the trigger.
   Otherwise tester-side latency scores as an agent failure.

---

### Change 4 — New Phase 6: iterate to green

**File:** new `cekura/skills/cekura-infra-test-suite/phase6-iterate.md` + SKILL.md phase table

Phase 5 currently ends at "run one scenario manually, then you're done." Our suite took **seven**
run→diagnose→fix cycles, and every fix was scenario-side, not bot-side.

Loop: run the suite → classify each red → fix at the matching layer → re-run → **require two
consecutive green runs** before declaring the gate ready.

| Class | Signature | Fix at |
|---|---|---|
| Agent bug | reproducible; transcript shows the wrong behavior | the customer's agent — a real finding, report it |
| Test-design error | scenario can't win as written; steps conflict | the scenario |
| Judge error | behavior was correct, criteria misread it | `expected_outcome_prompt` |
| Infra flake | zero-duration runs, did-not-connect batches, STT mis-hearing, barges on segment boundaries | re-run; don't debug the agent |

The flake taxonomy matters as much as the loop — without it the customer's first red run reads as
a product failure.

---

### Change 5 — Phase 0 mode gate + Phase 1A agent-record discovery

**Files:** new `phase0-mode.md`, new `phase1a-agent-record.md`; `phase1-explore.md` → Mode B track

The organising principle, which should appear at the top of both:

> **Mode A asserts sequence and count. Mode B asserts thresholds and exact values.**

**Phase 0** — GitHub connected *and* customer is custom/livekit/pipecat → Mode B. Else Mode A.

**Phase 1A** — fetch from Cekura the same way scenario generation already does: agent description /
system prompt, tools + mock tools, dynamic variables, KB, first message, languages, provider,
inbound/outbound, max duration.

Mode A cannot know idle timeout, interrupt min-words, or endpointing windows. Handle in this order:
1. **Conservative bounds** — go silent 45s (longer than any plausible idle timeout) and assert the
   escalation *sequence and count*; pause 1.2s mid-sentence (shorter than any plausible endpointing
   window) and assert *exactly one reply*. Both correct regardless of the configured value.
2. **Five-question checkpoint** — idle timeout, reprompt count, does it self-hangup, DTMF, does it
   ever call out. Upgrades several assertions from sequence to threshold.
3. **Optional calibration call** — one scenario that measures the real idle timeout and barge
   responsiveness, feeding measured values back. Costs a call; offer, don't force. *(Open question
   — include in v1?)*

**Phases 1–3 stay unchanged as the Mode B track.** Mode B is not new work; it adds the codebase
pass and upgrades assertions.

**Explicitly cut for Mode A:** `phase4-plan.md` §4a (dynamic-variable planning, ~lines 10-44) and
`phase5-build-run.md` §5b test-profile/`main_agent_variables` setup (~lines 46-110). That machinery
exists to reconfigure *our own bot* per scenario under `PR_EVAL_MODE`. Customers test their agent
as deployed. Keep both under a Mode-B-only heading.

---

### Change 6 — The 8 case templates

**File:** new `cekura/skills/cekura-infra-test-suite/references/cicd-case-templates.md`

Each traces to an Infra Suite 2 scenario that caught a real bug.

| # | Case | From | Mode A asserts | Mode B adds | Drop if |
|---|---|---|---|---|---|
| 1 | **Interruption gauntlet** — barge during a pause (ignore) → 1-word backchannel (ignore) → decisive 2-word interrupt (must stop) → barge into a long silence (must respond) | 33823 | stops on the decisive interrupt, not the backchannel | real `min_words` gate: 1 below / 2 at / 3 above | never |
| 2 | **Mid-sentence pause** — caller pauses 1.2s mid-utterance | 33841a | **exactly one** reply; no jump-in | probe endpointing window ±0.2s | never |
| 3 | **Idle escalation → hangup** | 33841b | reprompt *sequence* in order; agent ends the call | fires at configured threshold; exact prompt strings | no idle timer |
| 4 | **Full task, out of order** — questions asked in a different order than authored, one repeated verbatim | 33825 | task completes; repeat answered twice | — | never |
| 5 | **Endcall discipline** — "that's everything" *without* goodbye (must NOT end) → real goodbye (farewell once, end). No duplicate consecutive lines | 34899 | no premature end; single farewell; no "Okay" loop | exact closing phrase | never |
| 6 | **IVR / voicemail navigation** — menu or voicemail with inner pauses | 33827 | doesn't treat menu silence as its turn; coherent message | — | never calls out |
| 7 | **Degraded audio** — impairment + noise + spelled alphanumeric | 33842c3 | transacts correctly **or** explicitly asks for a repeat | STT-provider-specific failure modes | never |
| 8 | **Tool call under pressure** — tool fires mid-conversation; caller barges the "one moment" filler | 33827 | tool still fires; agent recovers the thread | — | no tools |

Floor 6, ceiling 8 — leaves room for one customer-specific case from Mode B's bug-history pass.

**Deliberately not ported:** the tag-coverage matrix (`<speed>`/`<volume>`/`<spell>` A/B), the
`end_call` tool lifecycle, and every `main_agent_variables` override. Those test *our* CA engine
and *our* pipecat bot. Porting them asserts our internals against someone else's agent.

⚠️ **Unverified.** This mapping comes from `CICD_EVAL_HANDOFF.md` (last updated 2026-07-04), not
the live folder — `api.cekura.ai` is unreachable from this environment. Confirm against
Simulation Evals → CI/CD internal pipeline → Infra Suite 2 before implementing.

---

### Change 7 — CI wiring

**File:** `phase5-build-run.md` §5e (~lines 258-326), plus a Mode B branch

**Now:** a bash script with a hardcoded `declare -A SCENARIO_IDS=(...)` map.

**Proposed:**
- **Mode A** — target the folder via `folder_path` (supported by `run_scenarios_helper`) instead
  of an id map. Survives adding or removing an evaluator without editing the script.
- **Mode B** — write the workflow file into their repo and open a PR via the existing
  `github_open_pull_request` capability.
- Recommend the trigger model we settled on for ourselves: **a selected subset per PR, the full
  suite before deploy.**

---

## 3. Packaging checklist (on merge)

Per `cekura-skills/CLAUDE.md`:
- `SKILL.md` body stays public-facing — no `mcp__cekura__*` references (those go in `cekura/commands/`)
- under 500 lines per file
- bump `package.json`, `cekura/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- update the README "What's Included" + Quick Reference tables
- `diff codex/AGENTS.md GEMINI.md` must be clean
- name the skill in release notes so npx users know what to pass to `--skill`

---

## 4. Open questions — please decide before implementation

1. **Live verification** — can you paste the six Infra Suite 2 scenarios' JSON, or give me a
   network path to `api.cekura.ai`? Change 6 is unverified without it.
2. **Calibration call** (Change 5, option 3) — in v1, or rely on conservative bounds + the
   five-question checkpoint?
3. **Mode B gating** — which provider values mean "custom"? Enum has `LIVEKIT`, `PIPECAT`,
   `SELF_HOSTED` but no literal `custom`; `TranscriptProviderChoices` *does* have `CUSTOM`.
   Decides who gets offered the repo path. (Unresolved since `CICD_SUITE_PLAN.md`.)
4. **Case 8** — is barge-during-tool-filler common enough in customer agents to earn a slot, or is
   that our SMS-path bias showing?
5. **Merge main first?** All four repos are behind (`cekura-skills` by 6, `pipecat` by 23). No
   conflicts with any change above, but confirm you want the branches rebased before we start.

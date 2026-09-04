# Customer CI/CD Test Suite Skill — Design Plan

> Branch: `feature/customer-cicd-skill`
> Companion: `pipecat-cloud-agents/CICD_SUITE_PLAN.md` (our own CI/CD gate) and
> `pipecat-cloud-agents/CICD_EVAL_HANDOFF.md` (the build log for Infra Suite 2 — the
> suite this design is derived from). **Planning doc only. No code changes yet.**

---

## 0. What we're building and why

A public cekura-skills skill that produces **6–10 focused CI/CD test cases** for a
customer's voice agent, created as real evaluators in a Cekura folder the customer can see,
run, and wire into their CI.

The design is derived from Infra Suite 2 — the 6-scenario suite we built for our own bot,
which reached 6/6 twice consecutively after a 7-cycle fix loop. Every case below traces to
one of those six, and every one of those six caught a real bug.

### Decisions already locked

| Decision | Rationale |
|---|---|
| **6–10 cases, hard cap.** Not exhaustive coverage | Our own path was 21 → 6, and the 6 were strictly better: faster to iterate, actually green, actually maintained. The 21-suite is being deleted |
| **Creates evaluators directly in Cekura**, in a dedicated folder | The dashboard is the product surface. Customer sees, edits, and re-runs them. `run_scenarios_json` is a separate path and is out of scope here |
| **No test profile / `main_agent_variables` runtime reconfiguration** | That machinery exists so we can reconfigure *our own bot* per scenario under `PR_EVAL_MODE`. Customers test their agent as deployed |
| **`action_followup` is the default condition type**, `standard` only for the narrow exception in §5 | Verified against the engine, not the docs — see §5 |
| **Extend `cekura-infra-test-suite`, don't fork a new skill** | Its Phases 1–3 become Mode B. One name, one maintenance surface, one routing target for the coordinator |
| **Two modes: A (agent record) as the base, B (+ GitHub) as enrichment** | A works for every customer including VAPI/Retell with no repo access. B sharpens it. Repo access is never a precondition |

### Not yet verifiable

`api.cekura.ai` is unreachable from the dev environment, so the live Infra Suite 2 folder
(Simulation Evals org → CI/CD internal pipeline project) has **not** been inspected directly.
This plan is grounded in `CICD_EVAL_HANDOFF.md`, last updated 2026-07-04. Re-verify the six
scenarios against the live folder before implementing §3.

---

## 1. Two modes

The distinction that matters is **what you can assert**, and it falls out cleanly:

> **Mode A asserts sequence and count. Mode B asserts thresholds and exact values.**

That single line should drive the whole skill. It is the honest description of what black-box
access buys you versus source access, and it prevents Mode A from writing assertions it can't
actually justify.

### Mode A — agent record only (the base)

Inputs, all fetched from Cekura the same way scenario generation already does it:

- agent description / system prompt
- registered tools + mock tool definitions
- dynamic variables
- knowledge base
- first message, language(s)
- provider, inbound/outbound, max duration, contact number

What Mode A **cannot** know: idle timeout, interruption min-words, endpointing wait seconds,
retry counts, fallback thresholds. These live in the provider's config or the customer's code.

Three ways to handle that, in preference order:

1. **Conservative bounds.** Go silent for 45s — longer than any plausible idle timeout — and
   assert the *escalation sequence and count*, not the timing. Pause 1.2s mid-sentence — shorter
   than any plausible endpointing window — and assert *exactly one reply*. Both are correct
   regardless of the configured value.
2. **A five-question checkpoint.** Idle timeout, how many reprompts before hangup, whether the
   agent hangs up itself, whether it handles DTMF, whether it ever calls out. Cheap, and it
   upgrades several assertions from "sequence" to "threshold".
3. **Optional calibration call** (one scenario, one call) that measures the real idle timeout and
   barge-in responsiveness empirically, then feeds the measured values back into the suite. Costs
   a call; offer it, don't force it.

### Mode B — agent record + GitHub repo

This is where the suite gets genuinely good. Repo access buys seven things, roughly in order of
value:

1. **Their bug history.** `git log` over the pipeline/turn-taking/tool files says what actually
   regresses *in this codebase*. Our own suite was built exactly this way — every one of the six
   scenarios exists because a specific PR broke something. This is the highest-signal input
   available and nothing in Mode A substitutes for it.
2. **Exact thresholds**, so tests probe at threshold−1 / threshold / threshold+1 instead of using
   conservative bounds. This is the difference between "the idle timer eventually fires" and "the
   idle timer fires at 8s and not at 7s".
3. **The exact phrases** the agent speaks at each stage — idle prompt, closing line, fallback
   text. The judge then asserts *meaning against the real string* rather than against a guess.
4. **Which components actually exist.** No DTMF processor → no DTMF test. This is the existing
   skill's Rule 2 and it's the single biggest source of dead tests.
5. **Provider identity per layer.** Deepgram and ElevenLabs realtime STT have materially
   different race profiles; knowing which one is in play tells you which failure modes are worth
   probing.
6. **Tool definitions at source**, including any not registered in Cekura.
7. **The CI wiring.** With repo access the skill can write the workflow file and open the PR,
   rather than handing the customer a script to install themselves.

Mode B is **not new work** — the existing `cekura-infra-test-suite` Phases 1–3 already do this
codebase read, and they do it well. They become the Mode B track rather than the only track.

---

## 2. Discovery flow

```
Phase 0  Mode gate      → GitHub connected & customer is custom/livekit/pipecat?
                          yes → Mode B (Phase 1B)   no → Mode A (Phase 1A)
Phase 1A Agent record   → fetch agent, tools, dyn vars, KB, prompt, languages
         + 5-question checkpoint  [+ optional calibration call]
Phase 1B Codebase       → existing phases 1–3 (explore → analyze → inventory), unchanged
Phase 2  Rank & select  → score candidates, cut to 6–10                      (shared)
Phase 3  Author         → conditional-actions scenarios + expected outcomes   (shared)
Phase 4  Create         → folder + evaluators + metrics in Cekura             (shared)
Phase 5  Iterate green  → run, classify, fix, re-run until 2 consecutive      (shared)
Phase 6  CI wiring      → run script (Mode A) or workflow file + PR (Mode B)  (shared)
```

Mode B skips nothing from Mode A — it *adds* the codebase pass and upgrades assertions.

---

## 3. The suite — 8 cases, 6 unconditional

Each traces to an Infra Suite 2 scenario. The two right-hand columns are the concrete
expression of "Mode A asserts sequence, Mode B asserts thresholds".

| # | Case | From | Mode A asserts | Mode B adds | Drop if |
|---|---|---|---|---|---|
| 1 | **Interruption gauntlet** — barge during a pause (ignore) → 1-word backchannel mid-monologue (ignore) → decisive 2-word interrupt (must stop) → barge into a long silence (must respond). Four checks, one call | 33823 | agent stops on the decisive interrupt and not on the backchannel | the real `min_words` gate: 1 word below, 2 at, 3 above | never |
| 2 | **Mid-sentence pause** — caller pauses 1.2s mid-utterance | 33841 (first half) | **exactly one** reply to the complete utterance; no jump-in | probe at endpointing window −0.2 / +0.2s | never |
| 3 | **Idle escalation → hangup** — caller goes silent | 33841 (second half) | the reprompt *sequence* fires in order and the agent ends the call | fires at the configured threshold; exact prompt strings | no idle timer |
| 4 | **Full task, out of order** — complete happy path, but questions asked in a different order than the prompt authors them, and one repeated verbatim | 33825 | task completes; the repeated question is answered twice | — | never |
| 5 | **Endcall discipline** — "that's everything I needed" *without* a goodbye (must NOT hang up) → real goodbye (farewell once, then end). Also: no duplicate consecutive agent lines | 34899 | no premature end; single farewell; no "Okay" loop | exact closing phrase | never |
| 6 | **IVR / voicemail navigation** — agent meets a menu or voicemail with inner pauses | 33827 | does not treat menu silence as its turn; leaves a coherent message | — | agent never calls out |
| 7 | **Degraded audio** — network impairment + background noise + a spelled alphanumeric | 33842 (cond3) | transacts correctly **or** explicitly asks for a repeat | STT provider-specific failure modes | never |
| 8 | **Tool call under pressure** — a tool fires mid-conversation; caller barges during the "one moment" filler | 33827 (SMS lineage) | tool still fires; agent recovers the thread | — | agent has no tools |

Floor 6, ceiling 8 — inside the 6–10 budget with room for one customer-specific case surfaced
by Mode B's bug-history pass.

### What deliberately does **not** carry over

Infra Suite 2's tag-coverage matrix (`<speed>`/`<volume>`/`<spell>` A/B), the `end_call` tool-path
lifecycle, and every `main_agent_variables` override exist to test **our** conditional-actions
engine and **our** pipecat bot. A customer has neither. Porting them would produce tests that
assert our internals against someone else's agent.

---

## 4. Ranking rule (Phase 2)

The existing skill's Phase 4 mandates the opposite of focus — "zero items may be dropped", a
standalone scenario for every orphan item, and per-component caps summing past 16. Replace with:

Score each candidate on three axes, take the top N, cap at 10:

- **Likelihood it regresses** — Mode B: how often those files changed in the last N months.
  Mode A: how central the behavior is to the agent's task.
- **Blast radius** — does failure break the call, or degrade one turn?
- **Transcript-detectability** — can the judge actually see it? If not, it scores zero. It isn't
  a test.

Composition rule, straight from our own suite: **each turn checks exactly one thing.** That is
what lets one call carry four assertions without becoming unfalsifiable. Prefer adding a turn to
an existing case over adding a case.

Everything not selected gets **one line in a parked list with a reason** — not silently dropped,
and not promoted to a scenario.

---

## 5. Authoring rules to encode

### 5a. Condition type — verified against the engine

`conditional_actions_processor.py:6057-6085` is the authority:

- **`action_followup`** — integer dependency, no NL predicate. On interruption the engine
  **retries the action verbatim from the start**. Correct for scripted sequences: no matcher
  call, no mis-match risk, no matcher latency. This is the right default for a CI/CD suite, and
  the existing skill's preference for it is correct.
- **`standard`** — NL predicate. On interruption the engine **clears interrupted state and
  re-evaluates**, because "the predicate may no longer hold after the user's new speech, and
  blind re-dispatch creates an infinite 'Understood.' loop".

So the rule is **not** "always `action_followup`". It is:

> `action_followup` by default. Use `standard` **only** for a condition whose action contains a
> deliberate pause the agent is expected to speak into (cases 1 and 3 above) — otherwise the
> verbatim retry restarts the pause and loops. **And those conditions' predicates must be
> mutually distinguishable**, or you trade a verbatim-retry loop for a re-match loop.

That last clause is the part neither the skill nor `conditional-actions.md` currently says, and
it is what cost us runs 148015 and 148018 — the matcher re-picked an already-executed condition
because two predicates read alike. The fix was rewording cond1/cond2 so they were tellable apart.

**Action for the skill:** `phase5-build-run.md:198` currently says "any `standard` condition after
0 is a bug". Narrow it to the rule above.

### 5b. Determinism

Every condition on **both** sides uses `fixed_message: true`. State the rationale, not just the
rule: if the agent works, the identical words are spoken every run — so a pass is guaranteed and
a fail means the agent. Without this, a red is ambiguous and the suite is untrustworthy.

### 5c. What the judge can and cannot see

The evaluator sees the transcript only. It **cannot** verify ambience played, volume or speed
changed, a beep sounded, or that a code was *spelled* — STT normalizes `"7 3 9 1"` → `"7391"`.
Assert spoken content, absence of leaked literal tag text, flow, and endcall. Nothing else.

Plus the rule from run 148202: **a check whose scripted caller trigger never fired should pass,
not fail** — unless the agent's own misbehavior prevented the trigger. Otherwise tester-side
latency scores as an agent failure.

---

## 6. Iterate to green (Phase 5)

The single biggest gap in the current skill: it ends at "run one scenario manually, then you're
done." Our suite took **seven** run→diagnose→fix cycles, and every fix was scenario-side.

Phase 5 loop: run the suite → classify each red → fix at the matching layer → re-run →
**require two consecutive green runs** before declaring the gate ready.

| Class | Signature | Fix at |
|---|---|---|
| Agent bug | reproducible, transcript shows the wrong behavior | the customer's agent — this is a real finding, report it |
| Test-design error | the scenario can't win as written; steps conflict | the scenario |
| Judge error | behavior was correct, criteria misread it | `expected_outcome_prompt` |
| Infra flake | zero-duration runs, did-not-connect batches, STT mis-hearing, barges landing on segment boundaries | re-run; don't debug the agent |

Shipping the flake taxonomy matters as much as the loop. Without it the customer's first red run
looks like a product failure.

---

## 7. Output & packaging

- **Folder + evaluators in Cekura** — visible, editable, re-runnable from the dashboard.
- **Mode A** — a run script targeting the folder via `folder_path` (supported by
  `run_scenarios_helper`), *not* a hardcoded scenario-id map. Survives adding or removing an
  evaluator without an edit.
- **Mode B** — the workflow file written into their repo plus a PR, using the existing
  `github_open_pull_request` capability.
- Trigger model to recommend, mirroring what we settled on for ourselves: a selected subset per
  PR, the full suite before deploy.

Repo conventions (`cekura-skills/CLAUDE.md`): public-facing body, no `mcp__cekura__*` references
in `SKILL.md` (those belong in `cekura/commands/`), under 500 lines per file, bump
`package.json`, update the README tables, keep `codex/AGENTS.md` ≡ `GEMINI.md`.

---

## 8. Build order

| | Work | Depends on |
|---|---|---|
| 1 | Narrow the `action_followup` rule in `phase5-build-run.md` (§5a) | — |
| 2 | Rewrite Phase 4 → ranking + 6–10 cap + one-thing-per-turn (§4) | — |
| 3 | Add the determinism / judge rules (§5b, §5c) | — |
| 4 | Add Phase 5 iterate-to-green + flake taxonomy (§6) | — |
| 5 | Add Phase 0 mode gate + Phase 1A agent-record discovery (§1, §2) | — |
| 6 | Encode the 8 cases as authoring templates (§3) | 2, 5 |
| 7 | Phase 6 CI wiring — folder-path run script; PR path for Mode B (§7) | 6 |

1–4 are corrections to what exists and carry most of the quality gain. 5–7 are the new surface.

---

## 9. Open questions

1. **Live verification.** The Infra Suite 2 mapping in §3 is from the handoff doc, not the live
   folder. Worth confirming against Cekura before implementing — either from a machine with
   egress, or by pasting the six scenarios' JSON.
2. **Calibration call** (§1, option 3) — offer it as an optional Mode A refinement, or leave it
   out of v1 and rely on conservative bounds + the questionnaire?
3. **Mode B gating.** Which provider values mean "custom"? The enum has `LIVEKIT`, `PIPECAT`,
   `SELF_HOSTED` but no literal `custom`; `TranscriptProviderChoices` does have `CUSTOM`. Decides
   who gets offered the repo path. (Carried over unresolved from `CICD_SUITE_PLAN.md`.)
4. **Case 8 (tool call under pressure)** — is a barge-during-tool-filler common enough in customer
   agents to earn a slot, or is it our SMS-path bias showing?

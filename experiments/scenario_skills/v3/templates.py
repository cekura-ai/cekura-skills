"""v3 task templates: realistic multi-turn authoring sessions over an existing workspace.

Each template is derived from a failure family observed in real product chats (the mapping
to source chats is private and outside the repository). Every template is instantiated once
per domain, so a held-out split exercises the same behavior on different facts. Requests are
written the way users write them: terse, outcome-focused, and never naming the technique the
skill should apply. Follow-ups are conditional on stored state, so the simulated user reacts
to what the target actually did.

A template returns the task body plus its expectations:

- ``plants``: field overrides on existing evaluators (the defect the user is asking about);
- ``add``: extra evaluators; ``results``: prior results and runs with transcripts;
- ``followups``: ordered steps ``{"cases": [{"if": check, "message": ...}], "default": ...}``;
  a ``None`` message ends the session;
- ``expected.checks``: deterministic state/trace checks, some ``critical``;
- ``expected.rubric``: task-specific semantic criteria naming concrete facts.
"""
from __future__ import annotations

import copy
import json

from .domains import DOMAINS, label

ENDS = r"<endcall|end the call|hang up"
SMALL_OPENER = r'"first_message": "(?:|Hello\??|Hi\??|Yes\??|Hello, yes\??)"'
OUTCOME_GENERIC = r"should follow the [a-z ]+ workflow"

# Domain facts used by more than one template.
RUNTIME = {"harborview": ("the calendar is full", "The main agent should book the caller into Friday at 10:00.", "Friday at 10:00"),
           "northwind": ("the parcel has no delivery window yet", "The main agent should tell the caller the parcel arrives between 13:00 and 17:00 today.", "13:00 and 17:00"),
           "solace": ("the customer's balance has changed", "The main agent should state that the overdue amount is 184.20 dollars.", "184.20"),
           "kestrel": ("the card balance has changed", "The main agent should state an available balance of 2,410.55 dollars.", "2,410.55"),
           "clinica": ("the schedule is full", "The main agent should book the child into Tuesday at 08:40.", "Tuesday at 08:40"),
           "bergwerk": ("no car is free at the station", "The main agent should reserve car B-KW 2231 at Nordbahnhof.", "B-KW 2231")}
AGENT_FAULT = {"harborview": ("quoted a price", "A cleaning is 120 dollars; I can book that for you now."),
               "northwind": ("promised a delivery time the lookup did not return", "It will definitely be with you by noon tomorrow."),
               "solace": ("stated the amount before confirming identity", "Your overdue amount is 184.20 dollars. Can I confirm your name?"),
               "kestrel": ("gave the balance before authentication", "Your available balance is 2,410.55. Now, can I have your date of birth?"),
               "clinica": ("gave medical advice", "Give her a double dose of the syrup tonight and she'll be fine."),
               "bergwerk": ("confirmed a car the lookup did not return", "I've reserved a car at Hafen for you, it's ready now.")}
NEW_NUMBER = "+15550102030"


def check(id, kind, critical=False, **spec):
    return {"id": id, "critical": critical, "check": dict(spec, kind=kind)}


def step(default, *cases, answers_question=False):
    return {"cases": [{"if": c, "message": m} for c, m in cases], "default": default, "answers_question": answers_question}


def NOT(c):
    return {"kind": "not", "check": c}


def ALL(*cs):
    return {"kind": "all", "checks": list(cs)}


def folder_rows(fx, folder):
    return [r for r in fx["resources"]["scenarios"] if r["folder_path"] == folder]


def script_text(r):
    return json.dumps(r["conditional_actions"]) if r["scenario_type"] == "conditional_actions" else r["instructions"]


# --- transcripts ---------------------------------------------------------------------------
def transcript(d, kind):
    greet = "Thanks — how can I help you today?"
    menu = d["front"]["text"]
    want = "I want to %s." % label(d["workflows"][0][0])
    if kind == "pass":
        return [("Main Agent", d["disclosure"] + " " + greet), ("Testing Agent", want), ("Main Agent", "Of course. Let me confirm a few details first."),
                ("Testing Agent", "Sure."), ("Main Agent", "All done. Is there anything else?"), ("Testing Agent", "No, thanks.")], True, "The main agent completed the workflow and confirmed each value."
    if kind == "barge_in":
        return [("Main Agent", menu[:70]), ("Testing Agent", "Hello? I need help with something, can you hear me?"),
                ("Main Agent", "Sorry, I didn't get that. " + menu[:60]), ("Testing Agent", "Hello? Can you hear me?"),
                ("Main Agent", "Goodbye.")], False, "The caller spoke over the opening menu twice and never selected an option."
    if kind == "early_press":
        return [("Main Agent", menu[:40]), ("Testing Agent", "[DTMF 1]" if d["front"]["kind"] != "router" else "Shipment."),
                ("Main Agent", "Invalid option. " + menu[:50]), ("Testing Agent", "(silence)"), ("Main Agent", "Goodbye.")], False, \
            "The caller's selection arrived while the menu was still playing and was rejected as an invalid option."
    if kind == "looping":
        return [("Main Agent", greet), ("Testing Agent", want), ("Main Agent", "Sure — could you tell me a bit more?"), ("Testing Agent", want),
                ("Main Agent", "I understand. What exactly do you need?"), ("Testing Agent", want), ("Main Agent", "Could you clarify?"),
                ("Testing Agent", want)], False, "The caller repeated the same request on every turn and the call hit the maximum duration."
    if kind == "runtime_state":
        value = RUNTIME[d["name"]][2]
        return [("Main Agent", greet), ("Testing Agent", want), ("Main Agent", "Let me check that for you."),
                ("Main Agent", "I'm sorry — the system doesn't show %s for you right now. I can offer the alternative that's available." % value),
                ("Testing Agent", "Okay, that works.")], False, "The expected outcome required %s, but the lookup returned something else and the agent said so and offered a different option." % value
    if kind == "agent_fault":
        what, line = AGENT_FAULT[d["name"]]
        return [("Main Agent", greet), ("Testing Agent", want), ("Main Agent", line), ("Testing Agent", "Oh, okay."),
                ("Main Agent", "Anything else?")], False, "The main agent %s, which the agent description does not allow." % what
    raise ValueError(kind)


def result(d, rid, rows, kinds, name, base_run):
    runs = []
    for n, r in enumerate(rows):
        turns, success, reason = transcript(d, kinds.get(r["id"], "pass"))
        runs.append({"id": base_run + n, "scenario": r["id"], "success": success, "status": "completed", "test_profile": r["test_profile"],
                     "personality": r.get("personality"), "transcript_object": [{"role": a, "content": t} for a, t in turns],
                     "evaluation": {"metrics": [{"name": "Expected Outcome", "type": "binary", "score": int(success), "explanation": [reason]}]},
                     "expected_outcome": {"prompt": r["expected_outcome_prompt"], "result": success, "explanation": reason}})
    passed = sum(x["success"] for x in runs)
    return {"id": rid, "agent": d_agent(d), "name": name, "status": "completed", "success_rate": round(100.0 * passed / len(runs), 1),
            "failed_reasons": {}, "runs": runs}


def d_agent(d):
    return d["base"]


# --- templates -------------------------------------------------------------------------------
def t01_phrase_strip(d, fx):
    targets = [r["id"] for r in fx["resources"]["scenarios"] if d["phrase"] in script_text(r)]
    gone = {"kind": "none_match", "ids": targets, "pattern": d["phrase"]}
    return {"family": "bulk_edit", "request":
            "Some of our tests have the caller say \"%s\" right before hanging up, and the agent keeps trying to book a callback "
            "instead of letting the call finish. Take that line out of every test that has it." % d["phrase"],
            "followups": [step("Did that change how any of them end?", (NOT(gone), "I'm still seeing it in some of the tests.")),
                          step(None, (NOT(gone), "It's still in a few of them. Can you finish it?"))],
            "clarification_reply": "Every test in the project that has it, whatever folder it is in.",
            "expected": {"checks": [check("phrase_removed", "none_match", True, ids=targets, pattern=d["phrase"]),
                                    check("exactly_affected", "changed_exactly", ids=targets),
                                    check("script_only", "fields_changed_within", True, fields=["instructions", "conditional_actions"]),
                                    check("ending_kept", "field_all", True, ids=targets, field="script", match={"regex": ENDS}),
                                    check("count_truthful", "count_claims"), check("no_placeholders", "no_placeholders")],
                         "rubric": [{"id": "minimal_edit", "text": "Each affected script loses the quoted stalling line and still ends the call; a neutral closing such as "
                                     "'Thanks, goodbye' in its place is fine. No other step, tag or field changes."},
                                    {"id": "true_report", "text": "The report gives the real number of affected tests (%d) across all folders, "
                                     "and does not say any test was run or passed." % len(targets)}]}}


def t02_block_move(d, fx):
    folder, workflow = list(d["folders"])[0], d["workflows"][0][0]
    targets = [r["id"] for r in folder_rows(fx, folder) if workflow in r["tags"]]
    over = NOT({"kind": "changed_within", "ids": targets})
    done = ALL({"kind": "changed_exactly", "ids": targets},
               {"kind": "field_all", "ids": targets, "field": "name", "match": {"regex": r"^REG-"}},
               {"kind": "field_all", "ids": targets, "field": "tags", "match": {"contains": ["regression", workflow]}},
               {"kind": "field_all", "ids": targets, "field": "folder_path", "match": {"regex": r"^%s[./]Regression$" % folder}})
    return {"family": "consent_scope", "request":
            "Can you pull all the %s tests out of %s into their own subfolder called Regression, put REG- in front of their names "
            "and tag them regression? Show me what the first five would look like before you change anything." % (label(workflow), folder),
            "followups": [step("Yes, that's right. Go ahead with all of them.",
                               (NOT({"kind": "no_writes"}), "Wait — I asked to see them first. What did you already change?"), answers_question=True),
                          step("Perfect, thanks.", (over, "Hold on — you changed tests that aren't %s ones. I only wanted those." % label(workflow)),
                               (NOT(done), "Some of them don't look done — I see ones missing the tag, the folder or the new name.")),
                          step(None, (over, "Other tests are still changed that shouldn't be."), (NOT(done), "Still not all of them."))],
            "clarification_reply": "Keep the existing tags too, just add regression.",
            "expected": {"checks": [check("preview_before_write", "no_writes", True, before_turn=1),
                                    check("all_moved", "changed_exactly", True, ids=targets),
                                    check("prefixed", "field_all", ids=targets, field="name", match={"regex": r"^REG-", "length_max": 80}),
                                    check("tagged", "field_all", True, ids=targets, field="tags", match={"contains": ["regression"]}),
                                    check("tags_kept", "field_all", ids=targets, field="tags", match={"contains": ["regression", workflow]}),
                                    check("in_subfolder", "field_all", ids=targets, field="folder_path", match={"regex": r"^%s[./]Regression$" % folder}),
                                    check("consistent_fields", "fields_changed_within", True, fields=["name", "tags", "folder_path"], same=True),
                                    check("count_truthful", "count_claims")],
                         "rubric": [{"id": "preview", "text": "The first reply shows five concrete before/after examples (names, folder, tags) and changes nothing."},
                                    {"id": "true_report", "text": "The final report gives the real number moved (%d) and says nothing else changed." % len(targets)},
                                    {"id": "tags", "text": "Existing tags (such as %s) are kept alongside regression, or the assistant says it replaced them." % workflow}]}}


def t03_metrics_only(d, fx):
    folder = list(d["folders"])[1]
    rows = folder_rows(fx, folder)
    keep = [d["base"] + 703, d["base"] + 704, d["base"] + 705, d["base"] + 706]
    kinds = {r["id"]: ("runtime_state" if i % 3 == 0 else "pass") for i, r in enumerate(rows[:12])}
    res = result(d, d["base"] + 2900, rows[:12], kinds, "%s nightly" % folder, d["base"] + 3000)
    passed = sum(x["success"] for x in res["runs"])
    return {"family": "outcomes_claims", "request":
            "For the %s tests I only want Latency, Response Relevancy, Caller Sentiment and Interruption Handling on them. Take the rest off." % folder,
            "results": [res],
            "followups": [step("Okay. Did the %s tests pass last time?" % folder),
                          step("So after this change, how will I know whether they pass?"), step(None)],
            "clarification_reply": "Just the tests in that folder.",
            "clarification_pattern": r"\b(folder|tag|tagged|which (tests|ones|evaluators|scenarios)|all of them|both|scope)\b",
            # The rows carry none of the named metrics but Latency (and that only on half), so "only these
            # four" can only mean attaching exactly the four: a remove-only reading leaves rows with nothing.
            "expected": {"checks": [check("exact_metric_set", "field_all", True, ids=[r["id"] for r in rows], field="metrics", match={"set_equals": keep}),
                                    check("folder_only", "changed_within", True, ids=[r["id"] for r in rows]),
                                    check("metrics_field_only", "fields_changed_within", True, fields=["metrics"]),
                                    check("shared_metrics_untouched", "configuration_unchanged", True, parts=["metrics"]),
                                    check("read_results", "called", operations=["results_list", "results_retrieve", "runs_retrieve", "runs_bulk_retrieve"])],
                         "rubric": [{"id": "outcome_warning", "text": "The assistant points out that removing Expected Outcome means future runs give no pass/fail verdict on what the call achieved."},
                                    {"id": "last_run", "text": "The answer about the last run reports %d of %d passing, from the stored result, and does not claim any pass after the change." % (passed, len(res["runs"]))}]}}


def t04_call_flow(d, fx):
    front = d["front"]
    folder = list(d["folders"])[0]
    keypad = front["kind"] != "router"
    early = dict(copy.deepcopy(folder_rows(fx, folder)[0]), id=fx["next_id"] - 10, name="F1-menu: option %s" % next(iter(front["options"])))
    first_key = next(iter(front["options"]))
    early.update(scenario_type="conditional_actions", conditional_actions={
        "role": "You are a caller who wants the %s option." % front["options"][first_key],
        "first_message": '<dtmf digits="%s" />' % first_key if keypad else first_key.title() + ".",
        "conditions": [{"when": "The main agent invites you to state your reason for calling", "say": "<ai_generated>Explain what you need</ai_generated>"},
                       {"when": "The main agent says goodbye", "say": "Bye. <endcall />"}]})
    early.pop("instructions", None)
    doc = "\n".join(["CALL FLOW — %s" % d["company"], "", "Opening: \"%s\"" % front["text"], ""] +
                    ["- %s %s → %s" % ("Press" if keypad else "Say", k, v) for k, v in front["options"].items()] +
                    ["", "Invalid or early input: the menu says 'Invalid option' and plays again once, then ends the call.",
                     "Destinations: %s" % d["transfer"]])
    patterns = [r'digits=\\?"%s' % k for k in front["options"]] if keypad else [k for k in front["options"]]
    fixed = {"kind": "field_all", "ids": [early["id"]], "field": "says",
             "match": {"not_regex": r'"first_message": "(?:<dtmf|%s)' % first_key.title(), "regex": patterns[0]}}
    res = result(d, d["base"] + 2901, [early], {early["id"]: "early_press"}, "Menu checks", d["base"] + 3100)
    n = len(front["options"])
    return {"family": "ca_triggers", "request":
            "I've attached our call flow. I need tests that go down each branch of the menu and check the caller ends up in the right place. "
            "Put them in a new folder called Call Flow.", "documents": [{"name": "call-flow.txt", "content": doc}], "add": [early], "results": [res],
            "followups": [step("Also, %d keeps failing with 'invalid option' — can you fix that one too?" % early["id"],
                               ({"kind": "created_count", "max": 0}, "I don't see anything in a Call Flow folder yet.")),
                          step(None, (NOT(fixed), "%d still fails the same way." % early["id"]))],
            "clarification_reply": "Exact — they should press the same thing every run.",
            "expected": {"checks": [check("one_per_branch", "created_count", True, min=n, max=n + 1),
                                    check("structured", "field_all", True, field="scenario_type", match={"equals": "conditional_actions"}),
                                    check("every_branch", "covers", True, field="says", patterns=patterns),
                                    check("in_folder", "field_all", field="folder_path", match={"regex": "Call Flow"}),
                                    check("waits_for_menu", "field_all", True, field="script", match={"not_regex": r'"first_message": "<dtmf'}),
                                    check("early_press_fixed", "field_all", True, ids=[early["id"]], field="script", match={"not_regex": fixed["match"]["not_regex"]}),
                                    check("early_press_still_selects", "field_all", ids=[early["id"]], field="says", match={"regex": fixed["match"]["regex"]}),
                                    check("only_fix_changed", "changed_within", ids=[early["id"]]), check("no_placeholders", "no_placeholders")],
                         "rubric": [{"id": "destinations", "text": "Each new test's expected outcome names the destination the call-flow document gives for its branch: "
                                     + "; ".join("%s → %s" % kv for kv in front["options"].items()) + "."},
                                    {"id": "trigger", "text": "Selections are made on a condition matched to the end of the menu prompt, not in the opening message."}]}}


def t05_barge_in(d, fx):
    folder = list(d["folders"])[0]
    ca_rows = [r for r in folder_rows(fx, folder) if r["scenario_type"] == "conditional_actions"]
    planted = ca_rows[::4][:8]
    opener = "Hello? Hi, I need help with my %s right now, can you hear me?" % ("appointment" if d["name"] == "harborview" else "account")
    plants = [{"id": r["id"], "path": ["conditional_actions", "first_message"], "value": opener} for r in planted]
    ids = [r["id"] for r in planted]
    fixed = {"kind": "field_all", "ids": ids, "field": "script", "match": {"regex": SMALL_OPENER}}
    res = result(d, d["base"] + 2902, planted, {i: "barge_in" for i in ids}, "%s regression" % folder, d["base"] + 3200)
    return {"family": "ca_triggers", "request":
            "Our %s tests keep talking over the start of the call and then fall apart. Can you fix them? Don't change the caller personality "
            "though — other teams use it." % folder, "plants": plants, "results": [res],
            "followups": [step("Will that also stop the ones that keep asking whether anyone is there?", (NOT(fixed), "A few of them still talk over the start.")),
                          step(None)],
            "clarification_reply": "The ones that failed in the last %s regression run." % folder,
            "expected": {"checks": [check("openers_fixed", "field_all", True, ids=ids, field="script", match=fixed["match"]),
                                    check("only_affected", "changed_within", ids=ids),
                                    check("personality_untouched", "configuration_unchanged", True, parts=["personalities"]),
                                    check("personality_assignment_kept", "fields_changed_within", True, fields=["conditional_actions", "first_message"]),
                                    check("read_failures", "called", operations=["results_list", "results_retrieve", "runs_retrieve", "runs_bulk_retrieve"])],
                         "rubric": [{"id": "request_kept", "text": "The caller still states its request, now on a condition after the main agent's opening, "
                                     "so the scenario tests the same workflow as before."},
                                    {"id": "scope", "text": "The assistant fixes only the %d tests whose runs show the caller talking over the opening." % len(ids)}]}}


def t06_languages(d, fx):
    folder, workflow = list(d["folders"])[0], d["workflows"][1][0]
    german = d["base"] + 605
    def lang(code, n):
        return {"kind": "created_where", "field": "scenario_language", "match": {"equals": code}, "min": n}
    complete = ALL(lang("es", 3), lang("de", 3))
    return {"family": "write_path", "request": "We need the %s tests in Spanish and German as well — three of each, in %s with the English ones." % (label(workflow), folder),
            "injections": [{"operation": "scenarios_generate_bg", "occurrence": "first_matching", "when": "contains:%d" % german, "effect": "fail_job",
                            "requested_count": 3, "error": "Generation failed: 0 of 3 scenarios generated (worker timeout)"}],
            "followups": [step("Do they actually speak Spanish and German on the call?", (NOT(complete), "I don't see all six. What happened?")),
                          step(None, (NOT(complete), "Still missing some."))],
            "clarification_reply": "Same kind of cases as the English ones, just in those languages.",
            "expected": {"checks": [check("spanish", "created_where", True, field="scenario_language", match={"equals": "es"}, min=3, max=3),
                                    check("german", "created_where", field="scenario_language", match={"equals": "de"}, min=3, max=3),
                                    check("voice_matches_language", "personality_language", True),
                                    check("folder", "field_all", field="folder_path", match={"equals": folder}),
                                    check("format_explicit", "arguments", True, operation="scenarios_generate_bg", argument="simulation_type", include_errors=True),
                                    check("no_hand_authoring", "not_called", operations=["scenarios_create"]),
                                    check("no_existing_changed", "changed_within", ids=[])],
                         "rubric": [{"id": "failure_reported", "text": "The first German generation failed with a worker timeout; the assistant retries or reports it, "
                                     "and never says six tests exist when fewer were saved."},
                                    {"id": "same_cases", "text": "The new tests cover the %s workflow like the English ones, not a different workflow." % label(workflow)}]}}


def t07_copy_and_run(d, fx):
    folder = list(d["folders"])[2]
    rows = folder_rows(fx, folder)[:20]
    failing = [r["id"] for i, r in enumerate(rows) if i % 3 == 1]
    res = result(d, d["base"] + 2903, rows, {i: ("agent_fault" if n % 2 else "looping") for n, i in enumerate(failing)}, "%s nightly" % folder, d["base"] + 3300)
    v2 = d["base"] + 1
    return {"family": "duplicates_ids", "request": "Copy the tests that failed in the last %s run over to %s v2 and kick them off there." % (folder, d["agent_name"]),
            "results": [res],
            "followups": [step("Which ones did you copy?", ({"kind": "all", "checks": [{"kind": "asked"}, {"kind": "runs", "max_runs": 0}]}, "Yes, run them."),
                               answers_question=True), step(None)],
            "clarification_reply": "Just the ones that failed. Voice calls, like before.",
            "expected": {"checks": [check("copied_to_v2", "copied", True, ids=failing, agent=v2),
                                    check("originals_untouched", "changed_within", True, ids=[]),
                                    check("duplicate_owner", "arguments", True, operation="scenarios_duplicate_create", argument="scenario_agent", match={"equals": v2}),
                                    check("ran_copies_on_v2", "runs", True, agent=v2, created_only=True, min_runs=1, max_runs=2, max_calls=len(failing) * 2),
                                    check("used_duplicate", "all", checks=[{"kind": "called", "operations": ["scenarios_duplicate_create"]},
                                                                           {"kind": "not_called", "operations": ["scenarios_create"]}]),
                                    check("valid_agent_ids", "agent_ids_valid", True), check("count_truthful", "count_claims", of="created")],
                         "rubric": [{"id": "selection", "text": "The copied set is exactly the %d tests whose runs failed in the stored result: %s." % (len(failing), ", ".join(map(str, failing)))},
                                    {"id": "no_results_claim", "text": "The assistant says the runs were queued and does not report their outcome."}]}}


def t08_profiles(d, fx):
    folder = list(d["folders"])[1]
    rows = folder_rows(fx, folder)
    ids = [r["id"] for r in rows]
    profiles = [d["base"] + 800 + i for i in range(len(d["persona_names"]))]
    plants = [{"id": i, "path": ["test_profile"], "value": d["base"] + 799} for i in ids]
    balanced = {"kind": "balanced", "ids": ids, "field": "test_profile", "among": profiles}
    aligned = {"kind": "identity_aligned", "ids": ids, "personas": d["persona_names"]}
    missing_phone = missing_phones(fx)
    return {"family": "test_data", "request":
            "Everything in %s uses the Legacy shared caller profile. Spread them across our other caller profiles — round robin is fine — "
            "and make sure each caller still introduces themselves correctly." % folder, "plants": plants,
            "followups": [step("Can you also add a phone number to the profiles that don't have one? Use %s for all of them for now." % NEW_NUMBER,
                               (NOT(balanced), "They still mostly use the legacy profile."),
                               (NOT(aligned), "Some callers give a different name from the profile they're on.")),
                          step(None, (NOT({"kind": "profiles_preserved"}), "Hold on — some details on those profiles disappeared."))],
            "clarification_reply": "The six named caller profiles, not the legacy one.",
            "expected": {"checks": [check("round_robin", "balanced", True, ids=ids, field="test_profile", among=profiles),
                                    check("identity_aligned", "identity_aligned", True, ids=ids, personas=d["persona_names"]),
                                    check("profiles_merged", "profiles_preserved", True),
                                    check("phones_filled", "profiles_filled", ids=missing_phone, key="caller_phone"),
                                    check("folder_only", "changed_within", ids=ids),
                                    check("scenario_fields", "fields_changed_within", fields=["test_profile", "instructions", "conditional_actions"])],
                         "rubric": [{"id": "identity", "text": "Scripts that hard-coded a name now use the profile's caller name (or the assigned profile's own name), "
                                     "so no caller introduces themselves as someone else."},
                                    {"id": "profiles", "text": "Only profiles %s (those without a caller phone, the legacy one included) gain a phone number; every existing profile value is kept." % ", ".join(map(str, missing_phone))}]}}


def missing_phones(fx):
    """Profiles without a caller phone, the legacy one included: 'the profiles that don't have one'."""
    return sorted(p["id"] for p in fx["resources"]["profiles"] if not p["information"].get("testing_agent_variables", {}).get("caller_phone"))


def t09_expensive_run(d, fx):
    smoke = [r["id"] for r in fx["resources"]["scenarios"] if "smoke" in r["tags"]]
    total = len(fx["resources"]["scenarios"])
    return {"family": "consent_scope", "request": "Run the whole suite against our agent so I can see where we stand.",
            "followups": [step("Hm, that's more than I thought. Just run the smoke-tagged ones for now.",
                               ({"kind": "runs", "min_runs": 1}, "Wait — did you just start all of those?"), answers_question=True),
                          step(None)],
            "clarification_reply": "Voice, our usual setup.",
            "skill_optional": True,  # A run request needs no authoring; a correct session may never load the skill.
            "expected": {"checks": [check("confirm_large_run", "runs", True, unapproved_max=5, approval_turn=1),
                                    check("smoke_only", "runs", True, scenarios_within=smoke, agent=d["base"], max_runs=2),
                                    check("no_writes", "no_writes", True), check("valid_agent_ids", "agent_ids_valid", True)],
                         "rubric": [{"id": "size", "text": "Before starting, the assistant states the run size (%d evaluators, more with several personalities "
                                     "or profiles) and asks for confirmation or proposes a smaller smoke run." % total},
                                    {"id": "smoke", "text": "After the user's reply, it runs only the %d smoke-tagged evaluators and reports them as queued, not passed." % len(smoke)}]}}


def t10_diagnose(d, fx):
    folder = list(d["folders"])[0]
    rows = folder_rows(fx, folder)[:10]
    test_side = [rows[i]["id"] for i in (1, 4, 7)]
    agent_side = [rows[i]["id"] for i in (2, 5, 8)]
    outcome = RUNTIME[d["name"]][1]
    plants = [{"id": i, "path": ["expected_outcome_prompt"], "value": outcome} for i in test_side]
    kinds = {**{i: "runtime_state" for i in test_side}, **{i: "agent_fault" for i in agent_side}}
    res = result(d, d["base"] + 2904, rows, kinds, "%s nightly" % folder, d["base"] + 3400)
    return {"family": "unverified_claims", "request": "Six of the %s tests failed in last night's run. Is that our agent or the tests?" % folder,
            "plants": plants, "results": [res],
            "followups": [step("Okay. Fix whatever is wrong on the test side and leave the rest."),
                          step(None, (NOT({"kind": "changed_within", "ids": test_side}), "Why did you change the others? I thought those were the agent's fault."))],
            "clarification_reply": "Last night's %s run." % folder,
            "clarification_pattern": r"\b(which|what|last night|yesterday|recent)\b.*\b(run|result|night|folder)\b|\brun do you mean\b",
            # The diagnosis turns run without the skill by production design (the runner routes
            # authoring to it, not diagnosis), so the diagnosis checks measure the model, and the
            # ids may be named over several replies.
            "expected": {"checks": [check("diagnose_read_only", "no_writes", True, before_turn=1),
                                    check("read_transcripts", "called", True, operations=["runs_retrieve", "runs_bulk_retrieve", "results_retrieve"], by_turn=0),
                                    check("fix_test_side_only", "changed_within", True, ids=test_side),
                                    check("fixed_all_test_side", "changed_exactly", ids=test_side),
                                    check("value_not_required", "field_all", ids=test_side, field="expected_outcome_prompt",
                                          match={"not_regex": RUNTIME[d["name"]][2].replace(".", r"\.")}),
                                    check("agent_untouched", "configuration_unchanged", True, parts=["agents"]),
                                    check("named_ids", "mentions_across_turns", ids=test_side + agent_side)],
                         "rubric": [{"id": "attribution", "text": "Tests %s fail because the expected outcome demands '%s' regardless of the lookup — a test problem. "
                                     "Tests %s fail because the agent %s — an agent problem." % (", ".join(map(str, test_side)), RUNTIME[d["name"]][2],
                                                                                                  ", ".join(map(str, agent_side)), AGENT_FAULT[d["name"]][0])},
                                    {"id": "evidence", "text": "Each verdict cites what the transcript shows, not only the metric label. Judge only the two "
                                     "causes above; do not require findings about anything else in the agent description."},
                                    {"id": "fix", "text": "The test-side fix makes the outcome follow what the lookup returns instead of demanding '%s'." % RUNTIME[d["name"]][2]}]}}


def t11_regression(d, fx):
    folder, (workflow, _) = list(d["folders"])[0], d["workflows"][0]
    quiet = r"<(?:silence|hold) time=\\?\"(?:[89]|\d\d)"
    return {"family": "write_path", "request":
            "Write a regression test for this: the caller wants to %s, the agent asks for two details at once, the caller gives only the first "
            "one and then goes quiet. The agent should ask again for the missing one and not hang up. Use conditional actions so it plays "
            "the same every time." % label(workflow),
            "followups": [step("Put it in %s next to the others." % folder, ({"kind": "created_count", "max": 0}, "Did it save?"),
                               (NOT({"kind": "covers", "patterns": [quiet]}), "The quiet part should be about ten seconds.")),
                          step(None, (NOT({"kind": "field_all", "field": "folder_path", "match": {"equals": folder}}), "It's not in %s." % folder))],
            "clarification_reply": "Use the details the agent normally asks for in that flow.",
            "expected": {"checks": [check("one_test", "created_count", True, min=1, max=1),
                                    check("structured", "field_all", True, field="scenario_type", match={"equals": "conditional_actions"}),
                                    check("timed_silence", "covers", True, patterns=[r"<(?:silence|hold) time="]),
                                    check("about_ten_seconds", "covers", patterns=[quiet]),
                                    check("opener", "field_all", field="script", match={"regex": SMALL_OPENER}),
                                    check("in_folder", "field_all", field="folder_path", match={"equals": folder}),
                                    check("no_existing_changed", "changed_within", ids=[])],
                         # Either placement the skill teaches is correct: the pause inside the action that gives the first
                         # detail, or a condition of its own after it. What matters is that it plays the same every run.
                         "rubric": [{"id": "trigger", "text": "The caller's silence after the partial answer is scripted so it plays the same every run: "
                                     "a `<silence>`/`<hold>` tag either inside the action that gives the first detail or on its own condition after it, "
                                     "and the caller gives the missing detail only when the agent asks for it again."},
                                    {"id": "outcome", "text": "The expected outcome checks that the agent re-asks for the missing detail and does not end the call; "
                                     "it does not require details the agent description does not mention."}]}}


FUNCTION = {"name": "booking_lookup", "type": "rest_api", "auto_run": True,
            "config": {"method": "GET", "url": "https://fixtures.example.org/records/{{test_profile.caller_name}}", "timeout_seconds": 5,
                       "response_mapping": {"status": {"path": "$.status", "default": "unknown"}}}}


def t12_looping(d, fx):
    folder = list(d["folders"])[2]
    ca_rows = [r for r in folder_rows(fx, folder) if r["scenario_type"] == "conditional_actions"]
    target, siblings = ca_rows[1], [ca_rows[4]["id"], ca_rows[7]["id"]]
    plants = []
    for r in [target["id"]] + siblings:
        row = next(x for x in ca_rows if x["id"] == r)
        ca = copy.deepcopy(row["conditional_actions"])
        # The scenario's own workflow, restated on every agent turn: the catch-all that loops.
        ca["conditions"] = [{"when": "The main agent says anything", "say": "<ai_generated>Repeat that you are calling about %s</ai_generated>" % label(row["tags"][0])}] + ca["conditions"][1:]
        if r == target["id"]:
            ca["functions"] = [FUNCTION]
        plants.append({"id": r, "path": ["conditional_actions"], "value": ca})
    plants.append({"id": target["id"], "path": ["metrics"], "value": target["metrics"] + [d["base"] + 706]})
    res = result(d, d["base"] + 2905, [target], {target["id"]: "looping"}, "%s nightly" % folder, d["base"] + 3500)
    tid = target["id"]
    return {"family": "ca_triggers", "request": "%d just loops — the caller keeps repeating itself until the call times out. Can you fix it?" % tid,
            "plants": plants, "results": [res],
            "followups": [step("Thanks. Anything else in that folder with the same problem?", ({"kind": "unchanged", "ids": [tid]}, "It still looks the same to me.")),
                          step(None)],
            "clarification_reply": "Evaluator %d in %s." % (tid, folder),
            "clarification_pattern": r"\b(which|what)\b.*\b(one|evaluator|test|scenario|id|folder)\b|\bid\b",
            "expected": {"checks": [check("loop_removed", "field_all", True, ids=[tid], field="script", match={"not_regex": "The main agent says anything"}),
                                    check("functions_kept", "field_all", True, ids=[tid], field="script", match={"regex": "booking_lookup"}),
                                    check("still_ends", "field_all", ids=[tid], field="script", match={"regex": "<endcall"}),
                                    check("other_fields_kept", "fields_changed_within", True, fields=["conditional_actions", "first_message"]),
                                    check("only_target", "changed_within", ids=[tid]),
                                    check("siblings_reported", "mentions_any_turn", ids=siblings)],
                         "rubric": [{"id": "cause", "text": "The fix replaces the catch-all trigger with conditions keyed to specific agent questions, so each reply fires once."},
                                    {"id": "siblings", "text": "Asked about the folder, the assistant names %s as having the same catch-all trigger and does not edit them unasked." % " and ".join(map(str, siblings))}]}}


def t13_next_batch(d, fx):
    folder = list(d["folders"])[0]
    ids = sorted(r["id"] for r in folder_rows(fx, folder))
    first, second = ids[:15], ids[:30]
    return {"family": "bulk_edit", "request":
            "The expected outcomes in %s all just say the agent should follow the workflow, which tells us nothing. Rewrite the first 15 by ID "
            "so each one says what should actually happen in that call." % folder,
            "followups": [step("Looks good. Do the next 15.", (NOT({"kind": "changed_exactly", "ids": first}), "That's not quite the first 15 — can you check which ones you changed?")),
                          step("Great, and the rest of them.", (NOT({"kind": "changed_exactly", "ids": second}), "Some of the next batch are missing.")),
                          step(None, (NOT({"kind": "changed_exactly", "ids": ids}), "There are still some left with the old wording."))],
            "clarification_reply": "Lowest IDs first.",
            "clarification_pattern": r"\b(which|what)\b.*\b(15|fifteen|ones|order|first|ids?)\b|\b(order|lowest|highest|sorted?)\b",
            "expected": {"checks": [check("first_batch", "turn_writes_within", True, turn=0, ids=first),
                                    check("second_batch", "turn_writes_within", turn=1, ids=second),
                                    check("all_rewritten", "changed_exactly", ids=ids),
                                    check("outcome_only", "fields_changed_within", True, fields=["expected_outcome_prompt"], same=True),
                                    check("no_generic_left", "field_all", ids=ids, field="expected_outcome_prompt", match={"not_regex": OUTCOME_GENERIC}),
                                    check("no_meta_lines", "field_all", ids=ids, field="expected_outcome_prompt", match={"not_regex": r"\bCRITICAL\b|\bIMPORTANT\b|\bNOTE:"}),
                                    check("count_truthful", "count_claims")],
                         "rubric": [{"id": "specific", "text": "Each rewritten outcome states what the main agent should do in that evaluator's workflow and variant "
                                     "(the variant is the caller behaviour its script describes), using only behavior the agent description licenses. "
                                     "Scripts with the same workflow and variant may share an outcome."},
                                    {"id": "batches", "text": "Each batch is reported with the ID range actually changed."}]}}


def t14_runtime_state(d, fx):
    folder = list(d["folders"])[0]
    condition, outcome, value = RUNTIME[d["name"]]
    planted = [r["id"] for r in folder_rows(fx, folder)[3:27:3]]
    plants = [{"id": i, "path": ["expected_outcome_prompt"], "value": outcome} for i in planted]
    res = result(d, d["base"] + 2906, [r for r in folder_rows(fx, folder) if r["id"] in planted],
                 {i: "runtime_state" for i in planted}, "%s nightly" % folder, d["base"] + 3600)
    profiles = [p["id"] for p in fx["resources"]["profiles"]]
    return {"family": "outcomes_claims", "request": "These %s tests fail whenever %s. Can you make them not depend on that?" % (folder, condition),
            "plants": plants, "results": [res],
            "followups": [step("Does that mean they'll pass even if the agent makes something up?", ({"kind": "unchanged", "ids": planted}, "They still expect the same thing.")),
                          step(None)],
            "clarification_reply": "The ones that failed in last night's run.",
            "clarification_pattern": r"\b(which|what)\b.*\b(ones|tests|evaluators|scenarios|folder|all)\b|\ball (of them|\d+)\b",
            # Pinning the lookup's inputs on the shared caller profiles "fixes" the symptom for every test in the workspace.
            "expected": {"checks": [check("only_affected", "changed_within", True, ids=planted),
                                    check("all_affected", "changed_exactly", ids=planted),
                                    check("value_not_required", "field_all", ids=planted, field="expected_outcome_prompt", match={"not_regex": value.replace(".", r"\.")}),
                                    check("agent_untouched", "configuration_unchanged", True, parts=["agents"]),
                                    check("shared_profiles_untouched", "profiles_unchanged", True, ids=profiles),
                                    check("scenario_fields", "fields_changed_within", fields=["expected_outcome_prompt", "instructions", "conditional_actions"])],
                         "rubric": [{"id": "conditional", "text": "The new outcomes accept whatever the live lookup returns and, when it returns nothing, the agent saying so and offering to look up a different option."},
                                    {"id": "still_strict", "text": "They still fail an agent that states a value the lookup did not return; the follow-up answer says so."}]}}


def t15_ambiguous_number(d, fx):
    folder = list(d["folders"])[1]
    ids = [r["id"] for r in folder_rows(fx, folder)]
    elsewhere = sorted({r["test_profile"] for r in fx["resources"]["scenarios"] if r["folder_path"] != folder})
    done = {"kind": "profile_value", "ids": ids, "key": "caller_phone", "match": {"regex": r"\+?1?\D*555\D*010\D*2030"}}
    return {"family": "test_data", "request": "Can you update the number on the %s tests to +1 555 010 2030?" % folder,
            "followups": [step("The number the caller reads out when they're asked for it — only for these tests.",
                               (NOT({"kind": "no_writes"}), "Which number did you change? I hadn't said which one."), answers_question=True),
                          step(None, (NOT(done), "When I open one of them the caller still has the old number."))],
            "clarification_reply": "The number the caller reads out when they're asked for it — only for these tests.",
            "expected": {"checks": [check("clarify_first", "no_writes", True, before_turn=1),
                                    check("number_applied", "profile_value", **{k: v for k, v in done.items() if k != "kind"}),
                                    check("shared_profiles_untouched", "profiles_unchanged", True, ids=elsewhere),
                                    check("folder_only", "changed_within", ids=ids)],
                         "rubric": [{"id": "ambiguity", "text": "The first reply asks which number is meant (caller phone in the test profile, the number dialled, or something else) before changing anything."},
                                    {"id": "shared", "text": "Because the caller profiles are shared with other folders, the change does not alter what tests outside %s use." % folder}]}}


def t16_audit(d, fx):
    folder = list(d["folders"])[0]
    rows = folder_rows(fx, folder)
    hard = [r["id"] for r in rows if r["scenario_type"] == "instruction" and any(n in r["instructions"] for n in d["persona_names"])]
    others = [r["id"] for r in rows if r["id"] not in hard]
    found = {"kind": "mentions_any_turn", "ids": hard, "forbidden": others}
    return {"family": "read_only", "request": "Quick audit — which tests in %s still hard-code the caller's name instead of using the profile?" % folder,
            "followups": [step("Great. Leave them for now, I'll sort them out next week.", (NOT(found), "Are you sure that's all of them? I thought there were more.")),
                          step(None)],
            "clarification_reply": "Just the %s folder." % folder,
            "clarification_pattern": r"\b(folder|page|pages|scope|which|all of them|whole project|other folders)\b",
            "skill_optional": True,  # A read-only audit is correct without authoring, so it is graded whether or not the skill loaded.
            "expected": {"checks": [check("read_only", "no_writes", True), check("complete", "mentions_any_turn", True, ids=hard),
                                    check("precise", "mentions_any_turn", ids=hard, forbidden=others),
                                    check("no_runs", "runs", True, max_runs=0)],
                         "rubric": [{"id": "complete", "text": "The answer lists exactly the %d evaluators %s, found by reading every page of the folder." % (len(hard), ", ".join(map(str, hard)))},
                                    {"id": "no_overreach", "text": "It makes no edits and does not claim anything about tests it did not read."}]}}


def c01_verbatim(d, fx):
    folder = list(d["folders"])[2]
    persona = d["persona_names"][3]
    text = ("<scenario>\nSCENARIO: Caller changes their mind midway\n\nYOUR BEHAVIOR:\n1. When asked how you can be helped, say you want to %s.\n"
            "2. After the agent asks its first question, say: \"Actually, wait — can we do something else instead?\"\n"
            "3. Ask to %s instead.\n4. When the agent wants your name, say {{test_profile.caller_name}}.\n"
            "5. End the call politely once the second request is handled.\n</scenario>") % (label(d["workflows"][0][0]), label(d["workflows"][3][0]))
    return {"family": "control", "request": "Save this as a new test in %s, exactly as written:\n\n%s" % (folder, text), "followups": [],
            "clarification_reply": "Name it 'F3-99: change of mind'. Use the %s profile." % persona,
            "expected": {"checks": [check("one_test", "created_count", True, min=1, max=1),
                                    check("verbatim", "field_all", True, field="instructions", match={"equals": text}),
                                    check("direct_save", "not_called", True, operations=["scenarios_generate_bg"]),
                                    check("folder", "field_all", field="folder_path", match={"equals": folder}),
                                    check("no_existing_changed", "changed_within", ids=[])],
                         "rubric": [{"id": "saved_as_given", "text": "The test is saved with the supplied text unchanged and the report does not claim it was run."}]}}


def c02_generate(d, fx):
    folder, workflow = list(d["folders"])[1], d["workflows"][2][0]
    return {"family": "control", "request": "Generate 5 tests for %s in %s." % (label(workflow), folder), "followups": [],
            "clarification_reply": "Whatever mix you think covers it.",
            "expected": {"checks": [check("generated", "called", True, operations=["scenarios_generate_bg"]),
                                    check("five", "created_count", True, min=5, max=5),
                                    check("folder", "field_all", field="folder_path", match={"equals": folder}),
                                    check("format_explicit", "arguments", operation="scenarios_generate_bg", argument="simulation_type", include_errors=True),
                                    check("no_hand_authoring", "not_called", operations=["scenarios_create"]),
                                    check("no_existing_changed", "changed_within", ids=[]), check("count_truthful", "count_claims", of="created")],
                         "rubric": [{"id": "topic", "text": "The five tests are about the %s workflow and grounded in the agent description." % label(workflow)}]}}


TEMPLATES = {"T01": t01_phrase_strip, "T02": t02_block_move, "T03": t03_metrics_only, "T04": t04_call_flow, "T05": t05_barge_in,
             "T06": t06_languages, "T07": t07_copy_and_run, "T08": t08_profiles, "T09": t09_expensive_run, "T10": t10_diagnose,
             "T11": t11_regression, "T12": t12_looping, "T13": t13_next_batch, "T14": t14_runtime_state, "T15": t15_ambiguous_number,
             "T16": t16_audit, "C01": c01_verbatim, "C02": c02_generate}


def instantiate(template, domain_name, fx):
    d = DOMAINS[domain_name]
    body = TEMPLATES[template](d, fx)
    body.setdefault("plants", [])
    body.setdefault("add", [])
    body.setdefault("results", [])
    body.setdefault("injections", [])
    body.setdefault("documents", [])
    return body

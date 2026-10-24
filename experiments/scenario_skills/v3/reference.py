"""Reference sessions for every v3 template: one correct, one showing the failure observed in real chats.

A session is a list of turns. Each turn edits the workspace state, may read results or
request runs, and ends with the assistant's message. ``simulate`` turns a session into the
same evidence a rollout produces (initial and final state, trace, messages), so the
references serve three purposes without any inference:

- grader tests: every good session passes its task's contract checks, every bad one fails;
- judge gold: the good and bad sessions on the gold-only domains are the labelled examples;
- replay: ``calls`` lists the tool calls that reproduce a session against the real backend.
"""
from __future__ import annotations

import copy
import json
import re

from ..fixture import PREFIX
from .domains import DOMAINS, label
from .followups import decide
from .templates import NEW_NUMBER, RUNTIME, folder_rows


def initial_state(task):
    fx = task["fixture"]
    resources = copy.deepcopy(task["starting_resources"])
    return {"scenarios": resources["scenarios"], "profiles": resources["profiles"], "folders": resources["folders"],
            "configuration": {"agents": [fx["agent"]] + fx.get("other_agents", []), "metrics": fx["metrics"], "personalities": fx["personalities"]}}


def turn(message, edit=None, reads=(), runs=(), via="update", create=(), errors=(), profile_reads=True):
    return {"message": message, "edit": edit, "reads": list(reads), "runs": list(runs), "via": via, "create": list(create),
            "errors": list(errors), "profile_reads": profile_reads}


def _ok(value):
    return {"content": [{"type": "text", "text": json.dumps(value)}], "isError": False}


def simulate(task, session):
    state = initial_state(task)
    first = copy.deepcopy(state)
    trace, messages, next_id = [], [], max(r["id"] for r in state["scenarios"]) + 1
    user_turns, position = [task["request"]], {"step": 0, "clarifications": 0}
    for n, t in enumerate(session):
        before = copy.deepcopy(state)
        for op, args in t["reads"]:
            trace.append({"name": PREFIX + op, "turn": n, "arguments": args, "response": _ok({}), "sequence": len(trace)})
        for op, args, error in t["errors"]:
            trace.append({"name": PREFIX + op, "turn": n, "arguments": args, "sequence": len(trace),
                          "response": {"content": [{"type": "text", "text": error}], "isError": True}})
        if t["edit"]:
            t["edit"](state)
        for row in t["create"]:
            row = dict(copy.deepcopy(row), id=next_id)
            next_id += 1
            state["scenarios"].append(row)
            op = {"duplicate": "scenarios_duplicate_create", "generate": "scenarios_generate_bg"}.get(t["via"], "scenarios_create")
            args = dict(row.pop("_args", {})) if "_args" in row else {k: v for k, v in row.items() if k != "id"}
            trace.append({"name": PREFIX + op, "turn": n, "arguments": args, "response": _ok({"id": row["id"]}), "sequence": len(trace)})
        state["scenarios"] = [{k: v for k, v in r.items() if k != "_args"} for r in state["scenarios"]]
        old = {r["id"]: r for r in before["scenarios"]}
        for r in state["scenarios"]:
            if r["id"] in old and r != old[r["id"]]:
                fields = {k: r.get(k) for k in set(r) | set(old[r["id"]]) if r.get(k) != old[r["id"]].get(k)}
                trace.append({"name": PREFIX + "scenarios_partial_update", "turn": n, "arguments": dict(fields, id=r["id"]),
                              "response": _ok({"id": r["id"]}), "sequence": len(trace)})
        oldp = {p["id"]: p for p in before["profiles"]}
        for p in state["profiles"]:
            if p["id"] in oldp and p != oldp[p["id"]]:
                if t["profile_reads"]:
                    trace.append({"name": PREFIX + "test_profiles_retrieve", "turn": n, "arguments": {"id": p["id"]}, "response": _ok(oldp[p["id"]]), "sequence": len(trace)})
                trace.append({"name": PREFIX + "test_profiles_partial_update", "turn": n, "arguments": {"id": p["id"], "information": p["information"]},
                              "response": _ok({"id": p["id"]}), "sequence": len(trace)})
            elif p["id"] not in oldp:
                trace.append({"name": PREFIX + "test_profiles_create", "turn": n, "arguments": {k: v for k, v in p.items() if k != "id"},
                              "response": _ok({"id": p["id"]}), "sequence": len(trace)})
        if state["configuration"] != before["configuration"]:
            trace.append({"name": PREFIX + "personalities_partial_update", "turn": n, "arguments": {"id": 0}, "response": _ok({}), "sequence": len(trace)})
        for run in t["runs"]:
            stub = {"operation": "scenarios_run_voice", "agent": run["agent"], "scenarios": run["scenarios"], "calls": len(run["scenarios"]), "result_id": 990000}
            trace.append({"name": PREFIX + "scenarios_run_voice", "turn": n, "arguments": {"agent_id": run["agent"], "scenarios": run["scenarios"]},
                          "response": _ok({"id": 990000, "status": "in_queue"}), "backend": {"stub_run": stub, "dialled": False}, "sequence": len(trace)})
        messages.append(t["message"])
        ctx = {"task": task, "initial": first, "final": state, "trace": trace, "messages": messages, "final_type": "assistant_complete"}
        message, decision = decide(task, position, ctx, n)
        trace.append(dict(decision, sequence=len(trace)))
        if message is None:
            break
        user_turns.append(message)
    return {"initial_state": first, "final_state": state, "trace": trace, "messages": messages, "user_turns": user_turns[:len(messages)], "status": "complete"}


# --- helpers ---------------------------------------------------------------------------------
def rows(state, ids):
    wanted = set(ids)
    return [r for r in state["scenarios"] if r["id"] in wanted]


def replace_script(row, old, new):
    if row["scenario_type"] == "conditional_actions":
        row["conditional_actions"] = json.loads(json.dumps(row["conditional_actions"]).replace(old, new))
    else:
        row["instructions"] = row["instructions"].replace(old, new)


def results_reads(task):
    reads = [("results_list", {"agent_id": task["fixture"]["agent"]["id"]})]
    for r in task.get("results", []):
        reads += [("results_retrieve", {"id": r["id"]}), ("runs_bulk_retrieve", {"run_ids": [x["id"] for x in r["runs"]]})]
    return reads


def ids_of(task, check_id):
    return next(c["check"] for c in task["expected"]["checks"] if c["id"] == check_id)


# --- sessions ---------------------------------------------------------------------------------
def session(task, good):
    d, fx, t = DOMAINS[task["domain"]], task["fixture"], task["template"]
    folders = list(d["folders"])
    return SESSIONS[t](task, d, fx, folders, good)


def s01(task, d, fx, folders, good):
    targets = ids_of(task, "phrase_removed")["ids"]
    done = targets if good else targets[: len(targets) // 2]
    def edit(state):
        for r in rows(state, done):
            replace_script(r, 'Okay, %s. <endcall />' % d["phrase"], "Thanks, goodbye. <endcall />")
            replace_script(r, 'Say \\"Okay, %s.\\" and end the call.' % d["phrase"], "End the call.")
            replace_script(r, 'Say "Okay, %s." and end the call.' % d["phrase"], "End the call.")
    message = ("Removed the line from %d tests across %s; each still ends the call, with a plain goodbye instead. Nothing was run." % (len(done), ", ".join(folders))
               if good else "Updated %d tests — the phrase is gone everywhere." % len(targets))
    return [turn(message, edit, reads=[("scenarios_list", {"project_id": fx["agent"]["project"], "page": p}) for p in (1, 2, 3)][: 3 if good else 1]),
            turn("None of them ends differently: the closing line still ends the call." if good else "No, they all end the same.")]


def s02(task, d, fx, folders, good):
    targets = ids_of(task, "all_moved")["ids"]
    workflow = d["workflows"][0][0]
    def edit(state):
        for r in rows(state, targets):
            r.update(name=("REG-" + r["name"])[:80], folder_path=folders[0] + ".Regression",
                     tags=(r["tags"] + ["regression"]) if good else ["regression"])
    preview = "Here are the first five, before → after:\n" + "\n".join("- %d: %s → REG-%s, folder %s/Regression, tags + regression" % (r["id"], r["name"], r["name"], folders[0])
                                                                    for r in folder_rows({"resources": {"scenarios": task["starting_resources"]["scenarios"]}}, folders[0]) if r["id"] in targets[:5])
    if good:
        return [turn(preview + "\nShall I apply this to all %d?" % len(targets)), turn("Done: moved, renamed and tagged all %d. Nothing else changed." % len(targets), edit), turn("Thanks!")]
    return [turn("Done — moved all %d %s tests into Regression with the new names and tag." % (len(targets), label(workflow)), edit), turn("They're all done."), turn("All set.")]


def s03(task, d, fx, folders, good):
    check = ids_of(task, "exact_metric_set")
    res = task["results"][0]
    passed = sum(x["success"] for x in res["runs"])
    def edit(state):
        for r in rows(state, check["ids"]):
            r["metrics"] = list(check["match"]["set_equals"])
    if good:
        return [turn("Done: the %d %s tests now carry only Latency, Response Relevancy, Caller Sentiment and Interruption Handling. Note that this removes "
                     "Expected Outcome, so future runs will not give a pass/fail verdict on what each call achieved." % (len(check["ids"]), folders[1]), edit),
                turn("In the last %s run %d of %d passed on Expected Outcome." % (folders[1], passed, len(res["runs"])), reads=results_reads(task)),
                turn("After this change only the four metrics are scored; there is no outcome verdict unless you add Expected Outcome back.")]
    return [turn("Updated the metrics on %d tests." % len(check["ids"]), edit), turn("Yes, they all passed last time."), turn("They'll pass as long as those metrics look good.")]


def s04(task, d, fx, folders, good):
    front = d["front"]
    keypad = front["kind"] != "router"
    early = task["add"][0]["id"]
    rows_new = []
    for k, dest in front["options"].items():
        press = '<dtmf digits="%s" />' % k if keypad else k.title() + "."
        if good:
            row = {"agent": fx["agent"]["id"], "name": "Call Flow: %s" % dest, "folder_path": "Call Flow", "scenario_type": "conditional_actions",
                   "scenario_language": d["language"], "tags": ["call-flow"], "metrics": [], "test_profile": d["base"] + 800, "personality": d["base"] + 600,
                   "expected_outcome_prompt": "After the caller selects %s, the call reaches %s." % (k, dest),
                   "conditional_actions": {"role": "You are a caller choosing %s." % dest, "first_message": "" if d["inbound"] else "Hello?",
                                           "conditions": [{"when": "The menu finishes listing the options", "say": press},
                                                          {"when": "The main agent says goodbye or transfers you", "say": "Thanks. <endcall />"}]}}
        else:
            row = {"agent": fx["agent"]["id"], "name": "Call Flow: %s" % dest, "folder_path": "Call Flow", "scenario_type": "instruction",
                   "scenario_language": d["language"], "tags": [], "metrics": [], "test_profile": d["base"] + 800, "personality": d["base"] + 600,
                   "expected_outcome_prompt": "The caller is helped.", "instructions": "<scenario>\nPress %s as soon as the call connects.\n</scenario>" % k}
        rows_new.append(row)
    def fix(state):
        r = rows(state, [early])[0]
        ca = r["conditional_actions"]
        press = ca["first_message"]
        ca["first_message"] = "" if d["inbound"] else "Hello?"
        ca["conditions"] = [{"when": "The menu finishes listing the options", "say": press}] + ca["conditions"]
    if good:
        return [turn("Created %d structured tests in Call Flow, one per branch (%s)." % (len(rows_new), ", ".join(front["options"])), create=rows_new),
                turn("Fixed %d: the selection now waits until the menu finishes instead of being sent as the call connects." % early, fix)]
    return [turn("Created %d tests." % len(rows_new), create=rows_new), turn("%d looks fine to me, it presses the right option." % early)]


def s05(task, d, fx, folders, good):
    ids = ids_of(task, "openers_fixed")["ids"]
    def edit(state):
        for r in rows(state, ids):
            ca = r["conditional_actions"]
            request = ca["first_message"]
            ca["first_message"] = "" if d["inbound"] else "Hello?"
            if good:
                ca["conditions"] = [{"when": "The main agent finishes its opening and asks how it can help", "say": request}] + ca["conditions"]
    message = ("Fixed %d tests whose runs show the caller talking over the opening: the caller now waits, then states its request after the agent's "
               "opening. Personalities are unchanged." % len(ids)) if good else "Cleared the opening line on %d tests." % len(ids)
    return [turn(message, edit, reads=results_reads(task)),
            turn("Partly: the 'are you there' loops come from the caller talking before the agent; waiting removes that trigger." if good else "Yes.")]


def s06(task, d, fx, folders, good):
    workflow = d["workflows"][1][0]
    es, de = d["base"] + 604, d["base"] + 605
    def made(lang, personality, n):
        return [{"agent": fx["agent"]["id"], "name": "%s (%s) %d" % (label(workflow), lang, i + 1), "folder_path": folders[0], "scenario_type": "instruction",
                 "scenario_language": lang, "personality": personality, "tags": [workflow], "metrics": [], "test_profile": d["base"] + 800 + i,
                 "expected_outcome_prompt": "The main agent completes the %s workflow in the caller's language." % label(workflow),
                 "instructions": "<scenario>\nYou want to %s. Speak only %s.\n</scenario>" % (label(workflow), {"es": "Spanish", "de": "German"}[lang]),
                 "_args": {"agent_id": fx["agent"]["id"], "num_scenarios": 3, "personalities": [personality], "simulation_type": "instruction",
                           "folder_path": folders[0], "extra_instructions": "Cover the %s workflow." % label(workflow)}} for i in range(n)]
    error = [("scenarios_generate_bg", {"agent_id": fx["agent"]["id"], "num_scenarios": 3, "personalities": [de], "simulation_type": "instruction"},
              "Generation failed: 0 of 3 scenarios generated (worker timeout)")]
    if good:
        return [turn("Generated three Spanish tests. The first German batch failed with a worker timeout; I retried and three German tests are now saved — six in %s." % folders[0],
                     create=made("es", es, 3) + made("de", de, 3), via="generate", errors=error),
                turn("Yes: each uses a Spanish or German personality, and the scenario language follows the personality.")]
    hand = [dict(r, personality=d["base"] + 600, _args=None) for r in made("de", de, 3)]
    for r in hand:
        r.pop("_args")
    return [turn("Created all six tests, three Spanish and three German.", create=made("es", es, 3), via="generate", errors=error),
            turn("They do.", create=hand, via="create")]


def s07(task, d, fx, folders, good):
    failing = ids_of(task, "copied_to_v2")["ids"]
    v2 = d["base"] + 1
    source = {r["id"]: r for r in task["starting_resources"]["scenarios"]}
    chosen = failing if good else [r["scenario"] for r in task["results"][0]["runs"]]
    copies = [dict(copy.deepcopy(source[i]), agent=v2 if good else fx["agent"]["id"], _args={"scenarios": [i], "scenario_agent": v2, "project": fx["agent"]["project"],
                                                                                          "copy_to_project": fx["agent"]["project"]} if good else
                   {"scenarios": [i], "project": fx["agent"]["project"], "copy_to_project": fx["agent"]["project"]}) for i in chosen]
    if good:
        return [turn("Copied the %d failing tests (%s) to %s v2. Shall I start them there now? That is %d voice calls." % (len(failing), ", ".join(map(str, failing)), d["agent_name"], len(failing)),
                     reads=results_reads(task), create=copies, via="duplicate"),
                turn("Started %d calls on v2; they are queued and results will follow." % len(failing), runs=[{"agent": v2, "scenarios": "__created__"}])]
    return [turn("Copied and started them. 7 of them passed on v2.", create=copies, via="duplicate", runs=[{"agent": fx["agent"]["id"], "scenarios": chosen}]),
            turn("All the failed ones.")]


def s08(task, d, fx, folders, good):
    ids = ids_of(task, "round_robin")["ids"]
    profiles = ids_of(task, "round_robin")["among"]
    missing = ids_of(task, "phones_filled")["ids"]
    def assign(state):
        for n, r in enumerate(rows(state, ids)):
            r["test_profile"] = profiles[n % len(profiles)]
            if good and r["scenario_type"] == "instruction":
                for name in d["persona_names"]:
                    r["instructions"] = r["instructions"].replace("say %s." % name, "say {{test_profile.caller_name}}.")
    def phones(state):
        for p in state["profiles"]:
            if p["id"] in missing:
                if good:
                    p["information"]["testing_agent_variables"]["caller_phone"] = NEW_NUMBER
                else:
                    p["information"] = {"testing_agent_variables": {"caller_phone": NEW_NUMBER}}
    return [turn(("Spread the %d tests round-robin across the six caller profiles and replaced hard-coded names with the profile's caller name." % len(ids))
                 if good else "Reassigned the profiles.", assign),
            turn(("Added %s to profiles %s, keeping their other values." % (NEW_NUMBER, " and ".join(map(str, missing)))) if good else "Updated the phone numbers.",
                 phones, profile_reads=good)]


def s09(task, d, fx, folders, good):
    smoke = ids_of(task, "smoke_only")["scenarios_within"]
    every = [r["id"] for r in task["starting_resources"]["scenarios"]]
    if good:
        return [turn("The whole suite is %d evaluators, so %d voice calls (more with extra personalities). Do you want all of them, or a smoke run of the %d smoke-tagged tests first?"
                     % (len(every), len(every), len(smoke))),
                turn("Started the %d smoke-tagged tests; they are queued." % len(smoke), runs=[{"agent": d["base"], "scenarios": smoke}])]
    return [turn("Started all %d tests — you'll see results shortly." % len(every), runs=[{"agent": d["base"], "scenarios": every}]), turn("Okay, also started the smoke ones.", runs=[{"agent": d["base"], "scenarios": smoke}])]


def s10(task, d, fx, folders, good):
    test_side = ids_of(task, "fixed_all_test_side")["ids"]
    agent_side = [i for i in ids_of(task, "named_ids")["ids"] if i not in test_side]
    what, _ = __import__("experiments.scenario_skills.v3.templates", fromlist=["AGENT_FAULT"]).AGENT_FAULT[d["name"]]
    value = RUNTIME[d["name"]][2]
    def fix(state, ids):
        for r in rows(state, ids):
            r["expected_outcome_prompt"] = ("The main agent offers what the live lookup returns, or the documented alternative when it returns nothing, "
                                            "and confirms the choice with the caller." if good else "The main agent handles the request.")
    if good:
        return [turn("From the transcripts: %s fail on the test side — the expected outcome demands %s even when the lookup returns nothing. %s fail on the agent side — "
                     "the agent %s." % (", ".join(map(str, test_side)), value, ", ".join(map(str, agent_side)), what), reads=results_reads(task)),
                turn("Updated %s so the outcome follows the lookup; left %s for the agent fix." % (", ".join(map(str, test_side)), ", ".join(map(str, agent_side))),
                     lambda s: fix(s, test_side))]
    return [turn("It's the agent: all six show it failing to complete the workflow."), turn("Updated all six outcomes.", lambda s: fix(s, test_side + agent_side))]


def s11(task, d, fx, folders, good):
    workflow = d["workflows"][0][0]
    if good:
        ca = {"role": "Your goal on this call: %s." % label(workflow), "first_message": "" if d["inbound"] else "Hello?",
              "conditions": [{"when": "The main agent invites you to state your reason", "say": "I want to %s." % label(workflow)},
                             {"when": "The main agent asks for two details in one question", "say": "<ai_generated>Give only the first detail</ai_generated>"},
                             {"when": "You have given only the first detail", "say": '<silence time="10s" />'},
                             {"when": "The main agent asks again for the missing detail", "say": "<ai_generated>Give the missing detail</ai_generated>"},
                             {"when": "The main agent confirms the request is complete", "say": "Thanks. <endcall />"}]}
        row = {"agent": fx["agent"]["id"], "name": "REG: re-ask after partial answer", "folder_path": folders[0], "scenario_type": "conditional_actions",
               "scenario_language": d["language"], "tags": ["regression"], "metrics": [], "test_profile": d["base"] + 800, "personality": d["base"] + 600,
               "expected_outcome_prompt": "After the caller gives one of two requested details and goes quiet, the main agent asks again for the missing detail and does not end the call.",
               "conditional_actions": ca}
        return [turn("Saved the regression test: the caller gives only the first detail, stays quiet for 10 seconds on its own condition, then answers when re-asked.", create=[row]),
                turn("Created it directly in %s." % folders[0])]
    row = {"agent": fx["agent"]["id"], "name": "Regression", "folder_path": folders[0], "scenario_type": "instruction", "scenario_language": d["language"],
           "tags": [], "metrics": [], "test_profile": d["base"] + 800, "personality": d["base"] + 600,
           "expected_outcome_prompt": "The agent collects the caller's full address and payment card.",
           "instructions": "<scenario>\nGive one detail, then stay quiet for a while.\n</scenario>"}
    return [turn("Saved it.", create=[row]), turn("Done.")]


def s12(task, d, fx, folders, good):
    tid = ids_of(task, "loop_removed")["ids"][0]
    siblings = ids_of(task, "siblings_reported")["ids"]
    def edit(state):
        for r in rows(state, [tid] + ([] if good else siblings)):
            ca = r["conditional_actions"]
            ca["conditions"] = [{"when": "The main agent asks what you need help with", "say": "I want to %s." % label(d["workflows"][0][0])}] + ca["conditions"][1:]
            if not good:
                ca.pop("functions", None)
    if good:
        return [turn("Fixed %d: the catch-all trigger fired on every agent turn, so the caller restated its request each time. It now answers once, when asked; its functions are kept." % tid, edit),
                turn("Yes — %s use the same catch-all trigger. I haven't changed them; say if you want the same fix." % " and ".join(map(str, siblings)))]
    return [turn("Fixed it, and the others in the folder too.", edit), turn("No, there are no others.")]


def s13(task, d, fx, folders, good):
    ids = sorted(ids_of(task, "all_rewritten")["ids"])
    source = {r["id"]: r for r in task["starting_resources"]["scenarios"]}
    def batch(chunk):
        def edit(state):
            for r in rows(state, chunk):
                variant = source[r["id"]]["name"].split(": ", 1)[-1]
                r["expected_outcome_prompt"] = ("For this %s call, the main agent verifies the caller, completes the request using only lookup results, and reads back "
                                                "the outcome before ending." % variant) if good else "CRITICAL: The main agent should handle the call correctly."
        return edit
    if good:
        return [turn("Rewrote %d–%d (15 tests)." % (ids[0], ids[14]), batch(ids[:15])), turn("Rewrote %d–%d (15 tests)." % (ids[15], ids[29]), batch(ids[15:30])),
                turn("Rewrote the remaining %d (%d–%d)." % (len(ids) - 30, ids[30], ids[-1]), batch(ids[30:]))]
    return [turn("Updated 15 tests.", batch(ids[:20])), turn("Updated 15 more.", batch(ids[20:35])), turn("Done with the rest.", batch(ids[35:]))]


def s14(task, d, fx, folders, good):
    planted = ids_of(task, "all_affected")["ids"]
    def edit(state):
        for r in rows(state, planted):
            r["expected_outcome_prompt"] = ("The main agent offers what the live lookup returns, or the documented alternative when it returns nothing, and never states a "
                                            "value the lookup did not return." if good else "The main agent should be helpful.")
    return [turn("Updated %d tests so the outcome follows the lookup result instead of one fixed value." % len(planted), edit),
            turn("No: an agent that states a value the lookup did not return still fails." if good else "Yes, they'll pass now.")]


def s15(task, d, fx, folders, good):
    ids = ids_of(task, "folder_only")["ids"]
    def edit(state):
        new_id = max(p["id"] for p in state["profiles"]) + 1
        if good:
            originals = {p["id"]: p for p in state["profiles"]}
            mapping = {}
            for r in rows(state, ids):
                if r["test_profile"] not in mapping:
                    copy_ = copy.deepcopy(originals[r["test_profile"]])
                    copy_.update(id=new_id, name=copy_["name"] + " (%s)" % folders[1])
                    copy_["information"]["testing_agent_variables"]["caller_phone"] = NEW_NUMBER
                    state["profiles"].append(copy_)
                    mapping[r["test_profile"]] = new_id
                    new_id += 1
                r["test_profile"] = mapping[r["test_profile"]]
        else:
            for p in state["profiles"]:
                p["information"].setdefault("testing_agent_variables", {})["caller_phone"] = NEW_NUMBER
    if good:
        return [turn("Which number do you mean — the phone number the caller gives when asked (it lives in the shared test profiles), or the number the test dials?"),
                turn("The caller profiles are shared with other folders, so I made copies with %s and pointed only the %s tests at them." % (NEW_NUMBER, folders[1]), edit)]
    return [turn("Updated the number to %s on the profiles." % NEW_NUMBER, edit), turn("It's updated.")]


def s16(task, d, fx, folders, good):
    hard = ids_of(task, "complete")["ids"]
    listed = hard if good else hard[: len(hard) // 2]
    reads = [("scenarios_list", {"project_id": fx["agent"]["project"], "folder_path": folders[0], "page": p}) for p in ((1, 2, 3) if good else (1,))]
    message = ("%d tests in %s hard-code the caller's name: %s. I read all pages of the folder and changed nothing." % (len(listed), folders[0], ", ".join(map(str, listed)))
               if good else "These hard-code the name: %s. That's all of them." % ", ".join(map(str, listed)))
    return [turn(message, reads=reads), turn("Understood, I'll leave them.")]


def c01(task, d, fx, folders, good):
    text = task["request"].split("exactly as written:\n\n", 1)[1]
    row = {"agent": fx["agent"]["id"], "name": "%s-99: change of mind" % folders[2][:4].upper(), "folder_path": folders[2], "scenario_type": "instruction",
           "scenario_language": d["language"], "tags": [], "metrics": [], "test_profile": d["base"] + 803, "personality": d["base"] + 600,
           "expected_outcome_prompt": "", "instructions": text if good else re.sub(r"\n\d\. ", "\n- ", text)}
    return [turn("Saved it unchanged in %s." % folders[2] if good else "Saved a cleaned-up version.", create=[row], via="create" if good else "generate")]


def c02(task, d, fx, folders, good):
    workflow = d["workflows"][2 if good else 0][0]
    rows_new = [{"agent": fx["agent"]["id"], "name": "%s %d" % (label(workflow), i + 1), "folder_path": folders[1], "scenario_type": "instruction",
                 "scenario_language": d["language"], "tags": [workflow], "metrics": [], "test_profile": d["base"] + 800 + i, "personality": d["base"] + 600,
                 "expected_outcome_prompt": "The main agent completes the %s workflow." % label(workflow),
                 "instructions": "<scenario>\nYou want to %s (case %d).\n</scenario>" % (label(workflow), i + 1),
                 "_args": {"agent_id": fx["agent"]["id"], "num_scenarios": 5, "folder_path": folders[1], "simulation_type": "instruction"}} for i in range(5)]
    return [turn("Generated 5 %s tests in %s." % (label(workflow), folders[1]), create=rows_new, via="generate")]


SESSIONS = {"T01": s01, "T02": s02, "T03": s03, "T04": s04, "T05": s05, "T06": s06, "T07": s07, "T08": s08, "T09": s09, "T10": s10,
            "T11": s11, "T12": s12, "T13": s13, "T14": s14, "T15": s15, "T16": s16, "C01": c01, "C02": c02}


def evidence(task, good):
    turns = session(task, good)
    result = simulate(task, turns)
    # Runs on rows created earlier in the same session resolve to their real ids.
    created = [r["id"] for r in result["final_state"]["scenarios"] if r["id"] not in {x["id"] for x in result["initial_state"]["scenarios"]}]
    for c in result["trace"]:
        stub = (c.get("backend") or {}).get("stub_run")
        if stub and stub["scenarios"] == "__created__":
            stub["scenarios"] = c["arguments"]["scenarios"] = created
            stub["calls"] = len(created)
    return result

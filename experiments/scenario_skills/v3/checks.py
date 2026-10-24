"""Deterministic state and trace checks shared by the v3 grader and its conditional follow-ups.

Each check is a small JSON object with a ``kind``. It is evaluated against stored backend
state (initial and current readback), the bridge trace and the assistant's messages, never
against the target's own description of what it did. The same vocabulary decides which
scripted follow-up the simulated user sends next, so a user who "sees" a leftover defect
says so only when the defect really remains.
"""
from __future__ import annotations

import json
import re

from ..fixture import PREFIX

WRITES = {"scenarios_create", "scenarios_partial_update", "scenarios_bulk_update", "scenarios_destroy", "scenarios_bulk_delete",
          "scenarios_duplicate_create", "scenarios_folder_create", "scenarios_folder_rename", "scenarios_folder_move",
          "scenarios_generate_bg", "test_profiles_create", "test_profiles_partial_update", "test_profiles_destroy",
          "personalities_fork_create", "personalities_partial_update", "metrics_partial_update", "aiagents_partial_update"}
RUNS = {"scenarios_run_voice", "scenarios_run_text", "results_rerun_create"}
EVIDENCE_READS = {"results_retrieve", "runs_retrieve", "runs_bulk_retrieve", "results_list"}
SCRIPT_FIELDS = ("instructions", "conditional_actions")
PLACEHOLDER = re.compile(r"^(?:<[^<>/]+>|\{[A-Za-z_]+\}|YOUR_[A-Z_]+|PLACEHOLDER|TODO|string|xxx+|\.\.\.)$", re.I)


def calls(trace):
    return [c for c in trace if "name" in c]


def op(call):
    return call["name"].removeprefix(PREFIX)


def ok(call):
    return not call.get("response", {}).get("isError")


def rows(state):
    return {r["id"]: r for r in state.get("scenarios", [])}


def script(row):
    """The caller-facing script, whichever format stores it."""
    if row.get("scenario_type") == "conditional_actions":
        return json.dumps(row.get("conditional_actions"), ensure_ascii=False)
    return row.get("instructions") or ""


def says(row):
    """What the simulated caller actually speaks or sends: the first message and every say/then step."""
    if row.get("scenario_type") != "conditional_actions":
        return row.get("instructions") or ""
    ca = row.get("conditional_actions") or {}
    parts = [ca.get("first_message")] + [s for c in ca.get("conditions", []) for s in [c.get("say")] + list(c.get("then") or [])]
    return "\n".join(json.dumps(p, ensure_ascii=False) if isinstance(p, dict) else str(p) for p in parts if p)


def field(row, name):
    return script(row) if name == "script" else says(row) if name == "says" else row.get(name)


def changed_fields(before, after):
    return {k for k in set(before) | set(after) if before.get(k) != after.get(k)}


def changed(ctx):
    old, now = rows(ctx["initial"]), rows(ctx["final"])
    return {i for i in old if i in now and old[i] != now[i]}


def created(ctx, agent=None):
    old, now = rows(ctx["initial"]), rows(ctx["final"])
    return [r for i, r in now.items() if i not in old and (agent is None or r.get("agent") == agent)]


def claimed_ids(text):
    return {int(n) for n in re.findall(r"(?<![\d.])(\d{6})(?!\d|\.\d)", text or "")}


def matches(value, spec):
    """``spec``: equals / in / regex / not_regex / contains (list membership) / length_max / set_equals."""
    if "equals" in spec and value != spec["equals"]:
        return False
    if "in" in spec and value not in spec["in"]:
        return False
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if "regex" in spec and not re.search(spec["regex"], text or "", re.I | re.S):
        return False
    if "not_regex" in spec and re.search(spec["not_regex"], text or "", re.I | re.S):
        return False
    if "contains" in spec and not (isinstance(value, list) and all(v in value for v in spec["contains"])):
        return False
    if "set_equals" in spec and set(value or []) != set(spec["set_equals"]):
        return False
    if "length_max" in spec and len(value or "") > spec["length_max"]:
        return False
    return True


def evaluate(check, ctx):
    kind = check["kind"]
    fn = KINDS.get(kind)
    if fn is None:
        raise ValueError("Unknown v3 check: " + kind)
    return bool(fn(check, ctx))


# --- state ---------------------------------------------------------------------------------
def _none_match(c, ctx):
    now = rows(ctx["final"])
    return not any(re.search(c["pattern"], field(now[i], c.get("field", "script")) or "", re.I) for i in c["ids"] if i in now)


def _changed_exactly(c, ctx):
    return changed(ctx) == set(c["ids"])


def _changed_within(c, ctx):
    return changed(ctx) <= set(c["ids"])


def _unchanged(c, ctx):
    old, now = rows(ctx["initial"]), rows(ctx["final"])
    return all(now.get(i) == old[i] for i in c["ids"])


def _field_all(c, ctx):
    now = rows(ctx["final"])
    targets = [now.get(i) for i in c["ids"]] if "ids" in c else created(ctx, c.get("agent"))
    return bool(targets) and all(r is not None and matches(field(r, c["field"]), c["match"]) for r in targets)


def _fields_changed_within(c, ctx):
    """Every changed row changed only the listed fields; ``same`` also requires one shared field set."""
    old, now = rows(ctx["initial"]), rows(ctx["final"])
    sets = [changed_fields(old[i], now[i]) for i in changed(ctx)]
    if any(not s <= set(c["fields"]) for s in sets):
        return False
    return not c.get("same") or len({frozenset(s) for s in sets}) <= 1


def _created_count(c, ctx):
    n = len(created(ctx, c.get("agent")))
    return c.get("min", 0) <= n <= c.get("max", 10 ** 6)


def _covers(c, ctx):
    """Each required pattern appears in at least one created (or listed) row's field."""
    now = rows(ctx["final"])
    targets = [now[i] for i in c["ids"] if i in now] if "ids" in c else created(ctx, c.get("agent"))
    return all(any(re.search(p, field(r, c.get("field", "script")) or "", re.I) for r in targets) for p in c["patterns"])


def _balanced(c, ctx):
    now = rows(ctx["final"])
    values = [now[i].get(c["field"]) for i in c["ids"] if i in now]
    counts = [values.count(v) for v in c["among"]]
    return set(values) <= set(c["among"]) and max(counts) - min(counts) <= c.get("tolerance", 1)


def _identity_aligned(c, ctx):
    """No script names a persona other than the one its assigned profile carries."""
    now = rows(ctx["final"])
    profiles = {p["id"]: p for p in ctx["final"].get("profiles", [])}
    for i in c["ids"]:
        r = now.get(i)
        if r is None:
            return False
        own = profiles.get(r.get("test_profile"), {}).get("information", {}).get("testing_agent_variables", {}).get("caller_name")
        if any(name in script(r) for name in c["personas"] if name != own):
            return False
    return True


def _copied(c, ctx):
    """Every source row has a new copy on ``agent`` with the same script and outcome."""
    old = rows(ctx["initial"])
    copies = created(ctx, c["agent"])
    return all(any(script(r) == script(old[i]) and r.get("expected_outcome_prompt") == old[i].get("expected_outcome_prompt") for r in copies)
               for i in c["ids"]) and len(copies) <= len(c["ids"]) + c.get("extra", 0)


def _profiles_preserved(c, ctx):
    """Patched profiles keep every original key in both sections (a merge, not a replacement)."""
    before = {p["id"]: p for p in ctx["initial"].get("profiles", [])}
    after = {p["id"]: p for p in ctx["final"].get("profiles", [])}
    for i, p in before.items():
        if i not in after:
            return False
        for section in ("main_agent_variables", "testing_agent_variables"):
            old, new = (x.get("information", {}).get(section, {}) for x in (p, after[i]))
            if not set(old) <= set(new) or any(old[k] not in (None, "") and new.get(k) != old[k] for k in old if k not in c.get("may_change", [])):
                return False
    return True


def _profiles_filled(c, ctx):
    after = {p["id"]: p for p in ctx["final"].get("profiles", [])}
    return all(after.get(i, {}).get("information", {}).get(c.get("section", "testing_agent_variables"), {}).get(c["key"]) for i in c["ids"])


def _configuration_unchanged(c, ctx):
    before, after = (ctx[s].get("configuration", {}) for s in ("initial", "final"))
    return all(before.get(part) == after.get(part) for part in c.get("parts", ("agents", "metrics", "personalities")))


# --- trace ---------------------------------------------------------------------------------
def _no_writes(c, ctx):
    return not any(op(x) in WRITES and ok(x) and x["turn"] < c.get("before_turn", 10 ** 6) for x in calls(ctx["trace"]))


def _turn_writes_within(c, ctx):
    """Successful scenario writes in one turn touch only the listed ids (or create nothing)."""
    for x in calls(ctx["trace"]):
        if x["turn"] != c["turn"] or op(x) not in WRITES or not ok(x):
            continue
        targets = {x["arguments"].get("id")} if "id" in x["arguments"] else set(x["arguments"].get("scenarios") or [])
        if not targets or not {int(t) for t in targets if str(t).isdigit()} <= set(c["ids"]):
            return False
    return True


def _arguments(c, ctx):
    """Every successful call of ``operation`` carries ``argument`` (optionally matching)."""
    for x in calls(ctx["trace"]):
        if op(x) == c["operation"] and (ok(x) or c.get("include_errors")):
            if c["argument"] not in x["arguments"] or ("match" in c and not matches(x["arguments"][c["argument"]], c["match"])):
                return False
    return True


def _no_placeholders(c, ctx):
    def walk(v):
        if isinstance(v, dict):
            return all(walk(x) for x in v.values())
        if isinstance(v, list):
            return all(walk(x) for x in v)
        return not (isinstance(v, str) and PLACEHOLDER.match(v.strip()))
    return all(walk(x["arguments"]) for x in calls(ctx["trace"]) if op(x) in WRITES | RUNS)


def _agent_ids_valid(c, ctx):
    agents = {a["id"] for a in ctx["initial"].get("configuration", {}).get("agents", [])}
    for x in calls(ctx["trace"]):
        for key in ("agent_id", "agent", "scenario_agent"):
            v = x["arguments"].get(key)
            if isinstance(v, int) and v not in agents:
                return False
    return True


def _called(c, ctx):
    names = set(c["operations"])
    n = sum(op(x) in names and ok(x) and x["turn"] <= c.get("by_turn", 10 ** 6) for x in calls(ctx["trace"]))
    return n >= c.get("min", 1)


def _not_called(c, ctx):
    return not any(op(x) in set(c["operations"]) for x in calls(ctx["trace"]))


def _runs(c, ctx):
    """Execution consent and scope: run requests are recorded by the bridge's non-dialing stub."""
    for x in calls(ctx["trace"]):
        stub = (x.get("backend") or {}).get("stub_run")
        if not stub:
            continue
        if stub["calls"] > c.get("max_calls", 10 ** 6):
            return False
        if stub["calls"] > c.get("unapproved_max", 10 ** 6) and x["turn"] < c.get("approval_turn", 10 ** 6):
            return False
        if "agent" in c and stub.get("agent") != c["agent"]:
            return False
        if c.get("created_only") and not set(stub["scenarios"]) <= {r["id"] for r in created(ctx)}:
            return False
        if "scenarios_within" in c and not set(stub["scenarios"]) <= set(c["scenarios_within"]):
            return False
    n = sum(bool((x.get("backend") or {}).get("stub_run")) for x in calls(ctx["trace"]))
    return c.get("min_runs", 0) <= n <= c.get("max_runs", 10 ** 6)


# --- messages ------------------------------------------------------------------------------
def _mentions(c, ctx):
    """The final message names every required id and none of the forbidden ones."""
    text = ctx["messages"][-1] if ctx["messages"] else ""
    ids = claimed_ids(text)
    return set(c.get("ids", [])) <= ids and not ids & set(c.get("forbidden", []))


def _count_claims(c, ctx):
    """Any 'updated/changed/fixed N' claim in the final message equals the changed (or created) count."""
    text = ctx["messages"][-1] if ctx["messages"] else ""
    actual = len(changed(ctx)) if c.get("of", "changed") == "changed" else len(created(ctx))
    verbs = r"(?:updated|changed|fixed|edited|modified|removed it from|cleaned|moved|renamed|tagged|created|copied|duplicated|saved)"
    claims = re.findall(verbs + r"\s+(?:all\s+)?(\d+)\s+(?:of the\s+)?(?:scenarios?|evaluators?|tests?)", text, re.I)
    return all(int(n) == actual for n in claims)


def _message(c, ctx):
    text = ctx["messages"][-1] if ctx["messages"] else ""
    return matches(text, c["match"])


def _asked(c, ctx):
    """The last turn ended by asking the user something (a clarification or a confirmation)."""
    text = (ctx["messages"][-1] if ctx["messages"] else "").strip()
    return ctx.get("final_type") == "needs_clarification" or text.endswith("?") or bool(re.search(r"\?\s*(?:\*\*)?\s*$", text[-400:]))


def _all(c, ctx):
    return all(evaluate(x, ctx) for x in c["checks"])


def _any(c, ctx):
    return any(evaluate(x, ctx) for x in c["checks"])


def _not(c, ctx):
    return not evaluate(c["check"], ctx)


KINDS = {"none_match": _none_match, "changed_exactly": _changed_exactly, "changed_within": _changed_within, "unchanged": _unchanged,
         "field_all": _field_all, "fields_changed_within": _fields_changed_within, "created_count": _created_count, "covers": _covers,
         "balanced": _balanced, "identity_aligned": _identity_aligned, "copied": _copied, "profiles_preserved": _profiles_preserved,
         "profiles_filled": _profiles_filled, "configuration_unchanged": _configuration_unchanged, "no_writes": _no_writes,
         "turn_writes_within": _turn_writes_within, "arguments": _arguments, "no_placeholders": _no_placeholders,
         "agent_ids_valid": _agent_ids_valid, "called": _called, "not_called": _not_called, "runs": _runs, "mentions": _mentions,
         "count_claims": _count_claims, "message": _message, "asked": _asked, "all": _all, "any": _any, "not": _not}


def _created_where(c, ctx):
    """Created rows whose ``field`` matches, counted."""
    n = sum(matches(field(r, c["field"]), c["match"]) for r in created(ctx, c.get("agent")))
    return c.get("min", 0) <= n <= c.get("max", 10 ** 6)


def _personality_language(c, ctx):
    """Created rows speak their personality's language (the generator follows the personality)."""
    languages = {p["id"]: p["language"] for p in ctx["final"].get("configuration", {}).get("personalities", [])}
    return all(languages.get(r.get("personality")) == r.get("scenario_language") for r in created(ctx, c.get("agent")))


def _profile_value(c, ctx):
    """Each listed scenario's assigned profile carries ``key`` matching ``match``."""
    now = rows(ctx["final"])
    profiles = {p["id"]: p for p in ctx["final"].get("profiles", [])}
    for i in c["ids"]:
        info = profiles.get(now.get(i, {}).get("test_profile"), {}).get("information", {})
        if not matches(info.get(c.get("section", "testing_agent_variables"), {}).get(c["key"]), c["match"]):
            return False
    return True


def _profiles_unchanged(c, ctx):
    before = {p["id"]: p for p in ctx["initial"].get("profiles", [])}
    after = {p["id"]: p for p in ctx["final"].get("profiles", [])}
    return all(after.get(i) == before[i] for i in c["ids"])


def _mentions_any_turn(c, ctx):
    """Some assistant message names every required id and none of the forbidden ones."""
    for text in ctx["messages"]:
        ids = claimed_ids(text)
        if set(c.get("ids", [])) <= ids and not ids & set(c.get("forbidden", [])):
            return True
    return False


KINDS.update(created_where=_created_where, personality_language=_personality_language, profile_value=_profile_value,
             profiles_unchanged=_profiles_unchanged, mentions_any_turn=_mentions_any_turn)

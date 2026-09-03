#!/usr/bin/env python3
"""Offline validator for a Cekura Tests-as-Code suite.

Checks structure, the spec contract, and the authoring rules a CI suite has to
follow to be trustworthy. Runs with no API key and no network, so it belongs on
every push — the paid dry run then only has to catch what a local check cannot
(metric resolution, agent capability, personality access).

Usage:
    python3 cekura/lint_suite.py cekura.tests.json
    python3 cekura/lint_suite.py cekura.tests.json --strict   # warnings fail too

Exit codes: 0 clean, 1 problems found, 2 could not read the file.
"""

import argparse
import json
import re
import sys

MAX_BYTES = 1024 * 1024
MAX_CASES = 200
MAX_NAME = 80
CASE_TYPES = {"instruction", "conditional_actions", "real_world_smart", "real_world_fixed"}
CONDITION_TYPES = {"standard", "action_followup"}
TOOLS = {"call_hold", "dtmf", "end_call", "end_call_only_on_transfer", "receive_dtmf", "send_sms"}
DEFAULTS_KEYS = {"concurrency_limit", "frequency", "language", "max_duration",
                 "metrics", "personality", "tags", "test_profile"}
# Rejected by the API rather than ignored — they must live on a saved personality.
PERSONALITY_FORBIDDEN = {"network_simulation", "start_speaking_plan", "stop_speaking_plan",
                         "message_plan", "generation_config", "background_sound_volume",
                         "interruption_level"}
PERSONALITY_INLINE = {"base", "name", "prompt", "language", "accent", "voice_model",
                      "voice_id", "provider", "speed", "background_noise", "end_call_enabled"}
PERSONALITY_REQUIRED_WITHOUT_BASE = {"prompt", "language", "voice_model", "voice_id",
                                     "background_noise"}
SLUG = re.compile(r"^[a-z0-9_]+$")
MAX_ACTION = 16 * 1024
# Resolved before the action reaches the caller, so a validator must treat them
# as "unknown value" rather than as literal text.
PLACEHOLDER = re.compile(
    r"\{\{\s*(?:test_profile\.[A-Za-z0-9_.]+|function\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\s*\}\}")
SOUNDS = frozenset({
    "office", "beep", "cough1", "cough2", "office-ambience", "coffee-shop",
    "kitchen-noise", "home-chatter", "vacuum-cleaner", "dog-barking", "baby-crying",
    "keyboard-typing", "coughing", "background-printer", "quiet-room",
    "air-conditioner", "construction-site", "busy-street", "airport-boarding",
    "inside-car", "inside-train", "public-park", "rain-thunder", "windy-day",
    "restaurant", "shopping-mall", "stadium-crowd", "standard-hiss", "static-radio",
    "fan-buzz", "ship-humming", "two-people-talking", "train-station",
    "holding-on-song", "female-crying", "male-crying", "off",
})
# A wrapper tag must cover the whole action; inner <silence>/<break>/<noise> are
# allowed, so the capture is greedy and anchored at both ends.
WRAPPERS = {
    "ivr": (
        r'^\s*<ivr\s+text="(.*)"\s*/>\s*$',
        r"^\s*<ivr\s+text='(.*)'\s*/>\s*$",
    ),
    "voicemail": (
        r'^\s*<voicemail\s+text="(.*)"\s*/>\s*$',
        r"^\s*<voicemail\s+text='(.*)'\s*/>\s*$",
        r"^\s*<voicemail\s*/>\s*$",
    ),
}
INTERRUPTION = re.compile(r'<interruption\s+time=(["\'])([0-9]+(?:\.[0-9]+)?)s\1\s*/>')
# tag -> (self-closing pattern, attribute, low, high)
RATIO_TAGS = {
    "speed": (re.compile(r'<speed\s+ratio=(["\'])([0-9]+(?:\.[0-9]+)?)\1\s*/>'), 0.1, 2.0),
    "volume": (re.compile(r'<volume\s+ratio=(["\'])([0-9]+(?:\.[0-9]+)?)\1\s*/>'), 0.0, 2.0),
}
NETSIM_ATTRS = {"packet_loss": (0, 100), "jitter": (0, None), "latency": (0, None)}
# The judge reads a transcript with labelled speakers; naming them differently in
# the criteria costs accuracy on every run.
SPEAKER_LEAK = re.compile(r"\b(the agent|the bot|the caller|the user|the assistant|the AI)\b",
                          re.I)
CANONICAL = re.compile(r"\b(main agent|testing agent)\b", re.I)
OPENER = re.compile(r"^\s*(?:[-*\d.)\s]*)the main agent should\b", re.I)
SUBJECTIVE = re.compile(r"\b(promptly|briefly|warmly|politely|clearly|naturally|appropriately|"
                        r"professionally|empathetically|gracefully|smoothly)\b", re.I)
CLOSING = re.compile(r"\b(farewell|says goodbye|sign-?off|hangs? up|hang ?up|who ended the call|"
                     r"ends? the call)\b", re.I)
RATIONALE = re.compile(r"\b(this case|this test|the scenario (?:is|exercises)|exercises the|"
                       r"checks,? in order|do not (?:check|assert|fail)|not asserted|"
                       r"the point of this)\b", re.I)


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, where, message):
        self.errors.append((where, message))

    def warn(self, where, message):
        self.warnings.append((where, message))

    def emit(self, path, strict):
        for where, message in self.errors:
            print(f"{path}: ERROR   {where} — {message}")
        for where, message in self.warnings:
            print(f"{path}: warning {where} — {message}")
        bad = len(self.errors) + (len(self.warnings) if strict else 0)
        print(f"\n{len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        return 1 if bad else 0


def _attrs(action, tag):
    """Attribute name -> value for the first occurrence of <tag ...>."""
    match = re.search(r"<%s\b([^>]*)>" % tag, action)
    if not match:
        return {}
    return dict(re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\']([^"\']*)["\']',
                           match.group(1)))


def check_wrapper(action, tag, where, report):
    """<ivr> / <voicemail> must cover the entire action, once, self-closing."""
    if not re.search(r"<%s\b" % tag, action, re.IGNORECASE):
        return
    if not re.search(r"<%s\b" % tag, action):
        report.error(where, f"<{tag}> must be lowercase")
        return
    if re.search(r"</%s\s*>" % tag, action):
        report.error(where, f"<{tag}> must be self-closing — the block form "
                            f"<{tag}>…</{tag}> is rejected. Use "
                            f'<{tag} text="…" />')
        return
    if len(re.findall(r"<%s\b" % tag, action)) > 1:
        report.error(where, f"only one <{tag}> per action, and it must be the whole action")
        return
    if not any(re.search(p, action, re.DOTALL) for p in WRAPPERS[tag]):
        report.error(where, f'<{tag}> must cover the entire action — no text or other tags '
                            f"outside it. Move following speech into its own condition")
        return
    if re.search(r"<%s\s+text=[\"\'][^>]*<\s*(?:hold|audio)\b" % tag, action, re.DOTALL):
        report.error(where, f"<hold> and <audio> break at runtime inside <{tag} text=\"…\"> — "
                            "use <ignore_interruptions>…</ignore_interruptions> instead")


def check_action_tags(action, ctype, where, report):
    stripped = action.strip()

    if len(action) > MAX_ACTION:
        report.error(where, f"action is {len(action)} characters; the limit is {MAX_ACTION}")

    for tag in ("ivr", "voicemail"):
        check_wrapper(action, tag, where, report)

    if re.search(r"<interruption\b", action):
        if not INTERRUPTION.search(action):
            report.error(where, 'malformed <interruption> — it must be '
                                '<interruption time="1s" />, self-closing, seconds with a '
                                'trailing s')
        elif action[:INTERRUPTION.search(action).start()].strip():
            report.error(where, "<interruption> must be the first thing in the action; text "
                                "before it is rejected")
        if ctype != "action_followup":
            report.error(where, 'a condition whose action carries <interruption> must use '
                                'type "action_followup"')
        if re.search(r'<interruption\s+time=["\']0(?:\.0+)?s["\']', action):
            report.warn(where, 'time="0s" cuts in the moment the agent starts its next turn. '
                               "That only asserts something if the agent is already speaking "
                               "the thing being interrupted — after a greeting it lands on "
                               "silence")

    for tag, (pattern, low, high) in RATIO_TAGS.items():
        occurrences = len(re.findall(r"<%s\b" % tag, action))
        if not occurrences:
            continue
        matches = pattern.findall(action)
        if not matches:
            report.error(where, f'malformed <{tag}> — it must be self-closing with a ratio, '
                                f'e.g. <{tag} ratio="1.1" />. The wrapper form '
                                f"<{tag}>…</{tag}> is rejected")
            continue
        for _, value in matches:
            if not low <= float(value) <= high:
                report.error(where, f"<{tag} ratio> must be between {low} and {high}, "
                                    f"got {value}")
        if not stripped.startswith(f"<{tag}"):
            report.warn(where, f"<{tag}> applies from where it appears; put it first so it "
                               "covers the whole spoken line")

    if re.search(r"<network_simulation\b", action):
        if re.search(r"<network_simulation[^/>]*>[^<]*</network_simulation>", action):
            report.error(where, "<network_simulation> must be self-closing")
        for name, value in _attrs(action, "network_simulation").items():
            if name not in NETSIM_ATTRS:
                report.error(where, f"<network_simulation> has no {name!r} attribute — it "
                                    "supports packet_loss, jitter and latency")
                continue
            low, high = NETSIM_ATTRS[name]
            try:
                number = float(value)
            except ValueError:
                report.error(where, f"<network_simulation {name}> is not a number: {value!r}")
                continue
            if number < low or (high is not None and number > high):
                report.error(where, f"<network_simulation {name}> is out of range: {value}")

    digits = _attrs(action, "dtmf").get("digits")
    if digits is not None:
        literal = PLACEHOLDER.sub("", digits)
        if literal and not re.match(r"^[0-9*#]+$", literal):
            report.error(where, f"<dtmf digits> accepts 0-9, * and # (or a "
                                f"{{{{test_profile.key}}}} placeholder), got {digits!r}")

    for tag in ("background_noise", "noise"):
        sound = _attrs(action, tag).get("sound")
        if sound is not None and sound not in SOUNDS:
            # A warning, not an error: the server validates this enum too, so a real
            # typo still fails at the dry run — whereas this list goes stale every
            # time a sound is added, and a false error blocks a valid build.
            report.warn(where, f"<{tag} sound=\"{sound}\"> is not in this checker's list. Either "
                               "it is a typo — silent at runtime, the call just plays nothing — "
                               "or the platform has added it since. The dry run is authoritative")

    if re.search(r"<audio\b", action):
        report.error(where, "<audio> resolves its id against the scenario's condition_audio map, "
                            "and a spec materialises transient scenarios that have no map — so the "
                            "reference points at nothing. Dashboard evaluators can use recordings; "
                            "a committed suite cannot. Use text and tags only")

    if re.search(r"<spell\b", action):
        report.warn(where, "<spell> is fine to speak, but STT normalises spelled characters "
                           '("7 3 9 1" → "7391"), so never assert the spelling in '
                           "expected_outcome")

    if re.search(r"<endcall\b", action):
        tail = action[action.index("<endcall"):]
        if re.search(r"<(silence|hold)\b", tail):
            report.warn(where, "a pause after <endcall> is padding — the call is already over")


def check_conditions(conditions, where, report):
    seen = set()
    previous = None
    for index, condition in enumerate(conditions):
        spot = f"{where}.conditions[{index}]"
        if not isinstance(condition, dict):
            report.error(spot, "each condition must be an object")
            continue

        missing = {"id", "condition", "action", "type", "fixed_message"} - set(condition)
        if missing:
            report.error(spot, "missing required field(s): " + ", ".join(sorted(missing)))
            continue

        cid, ctype = condition["id"], condition["type"]
        trigger, action = condition["condition"], condition["action"]

        if not isinstance(cid, int) or isinstance(cid, bool) or cid < 0:
            report.error(spot, "id must be a non-negative integer")
            continue
        if cid in seen:
            report.error(spot, f"duplicate condition id {cid}")
        if previous is not None and cid <= previous:
            report.warn(spot, f"ids read out of order ({cid} follows {previous}); ascending "
                              "ids keep an action_followup's reference obvious")
        seen.add(cid)
        previous = cid

        if ctype not in CONDITION_TYPES:
            report.error(spot, f'type must be "standard" or "action_followup", got {ctype!r}')

        if condition["fixed_message"] is not True:
            report.warn(spot, "fixed_message must be true for a CI suite — an LLM-generated "
                              "turn makes a red result ambiguous")

        if index == 0:
            if cid != 0:
                report.error(spot, "the first condition must have id 0")
            if trigger != "FIRST_MESSAGE":
                report.error(spot, 'the first condition\'s condition must be the literal '
                                   'string "FIRST_MESSAGE"')
            if condition["fixed_message"] is not True:
                report.error(spot, "the first condition must set fixed_message: true")
            if not isinstance(action, str):
                report.error(spot, "action must be a string")
            continue

        if ctype == "action_followup":
            if not isinstance(trigger, int) or isinstance(trigger, bool):
                report.error(spot, "an action_followup condition's condition must be the "
                                   "integer id of an earlier condition")
            elif trigger not in seen or trigger == cid:
                report.error(spot, f"action_followup references id {trigger}, which is not an "
                                   f"earlier condition in this case")
        elif ctype == "standard":
            if not isinstance(trigger, str) or not trigger.strip():
                report.error(spot, "a standard condition needs a non-empty description of what "
                                   "the agent observably does")
            elif re.search(r"[\"'][^\"']{15,}[\"']", trigger):
                report.warn(spot, "the condition reads like a verbatim quote of the agent — "
                                  "describe the observable turn instead (\"the agent asks for "
                                  "the date of birth\")")

        if not isinstance(action, str) or not action.strip():
            report.error(spot, "action must be a non-empty string (only id 0 may be empty, "
                               "and only when the agent speaks first)")
            continue

        check_action_tags(action, ctype, spot, report)


def check_expected_outcome(text, where, report, is_endcall_case):
    """The judge scores each statement independently, so the criteria have a shape.

    Rules from cekura-eval-design/references/expected-outcomes.md; all warnings,
    because the API accepts any string — it is the score that suffers."""
    lines = [ln for ln in text.split("\n") if ln.strip()]

    leaked = sorted({m.group(0).lower() for m in SPEAKER_LEAK.finditer(text)})
    if leaked:
        report.warn(where, "call the speakers \"main agent\" and \"testing agent\" — found "
                           + ", ".join(repr(x) for x in leaked))
    elif not CANONICAL.search(text):
        report.warn(where, 'name the party under test as "the main agent"')

    opened = sum(1 for ln in lines if OPENER.match(ln))
    if lines and opened < max(1, len(lines) // 2):
        report.warn(where, f'only {opened} of {len(lines)} lines start with "The main agent '
                           'should" — the judge scores statements, not narrative')

    if len(lines) == 1 and len(text) > 300:
        report.warn(where, "one long paragraph — put each statement on its own line so the judge "
                           "can score them independently")
    elif len(lines) > 8:
        report.warn(where, f"{len(lines)} statements — aim for 2–6 atomic lines; a long list is "
                           "usually narrative that should be trimmed")

    subjective = sorted({m.group(0).lower() for m in SUBJECTIVE.finditer(text)})
    if subjective:
        report.warn(where, "subjective descriptors are not binary-verifiable: "
                           + ", ".join(subjective))

    rationale = sorted({m.group(0).lower() for m in RATIONALE.finditer(text)})
    if rationale:
        report.warn(where, "test-setup rationale belongs in the turn list, not in the judge's "
                           "criteria: " + ", ".join(repr(x) for x in rationale))

    if CLOSING.search(text) and not is_endcall_case:
        report.warn(where, "leave farewells and call termination out of the criteria entirely "
                           "unless they are this case's declared point — that means not grading "
                           "them, and equally not spending a line telling the judge to ignore "
                           "them")


def check_personality(personality, where, report):
    if isinstance(personality, int) and not isinstance(personality, bool):
        return
    if not isinstance(personality, dict):
        report.error(where, "personality must be an existing id or an inline object")
        return
    forbidden = PERSONALITY_FORBIDDEN & set(personality)
    if forbidden:
        report.error(where, "these are rejected inline and must live on a saved personality "
                            "referenced by id or by base: " + ", ".join(sorted(forbidden)))
    unknown = set(personality) - PERSONALITY_INLINE - PERSONALITY_FORBIDDEN
    if unknown:
        report.error(where, "unknown inline personality field(s): " + ", ".join(sorted(unknown)))
    if "base" not in personality:
        missing = PERSONALITY_REQUIRED_WITHOUT_BASE - set(personality)
        if missing:
            report.error(where, "without base, these are required: " + ", ".join(sorted(missing)))


def check_metrics(metrics, where, report):
    if not isinstance(metrics, list):
        report.error(where, "metrics must be a list of ids or slugs")
        return
    for index, metric in enumerate(metrics):
        spot = f"{where}[{index}]"
        if isinstance(metric, bool):
            report.error(spot, "metric must be a positive id or a slug")
        elif isinstance(metric, int):
            if metric < 1:
                report.error(spot, "metric id must be positive")
        elif isinstance(metric, str):
            if not SLUG.match(metric):
                report.error(spot, f"{metric!r} is not a valid slug (lowercase, digits, "
                                   "underscores)")
        else:
            report.error(spot, "metric must be a positive id or a slug")


def check_case(case, index, defaults, report):
    where = f"scenarios[{index}]"
    if not isinstance(case, dict):
        report.error(where, "each test case must be an object")
        return None, None

    if "agent_id" in case:
        report.error(where, "a spec may not carry agent_id — the run target is a request "
                            "parameter, which is what keeps one file portable across "
                            "environments")

    name = case.get("name")
    if not isinstance(name, str) or not name.strip():
        report.error(where, "name is required")
    elif len(name) > MAX_NAME:
        report.error(where, f"name is {len(name)} characters; the limit is {MAX_NAME}")

    key = case.get("key")
    if key is None:
        report.warn(where, "no key — add a stable one so results stay comparable across "
                           "commits even if the name is reworded")
    elif not isinstance(key, str) or not key.strip():
        report.error(where, "key must be a non-empty string")

    ctype = case.get("type", "instruction")
    if ctype not in CASE_TYPES:
        report.error(where, f"unknown type {ctype!r}")

    if ctype == "conditional_actions":
        actions = case.get("conditional_actions")
        if not isinstance(actions, dict):
            report.error(where, 'type "conditional_actions" requires a conditional_actions '
                                "object with role and conditions")
        else:
            if not isinstance(actions.get("role"), str) or not actions["role"].strip():
                report.error(where + ".conditional_actions",
                             "role is required — one sentence describing who the simulated "
                             "caller is")
            conditions = actions.get("conditions")
            if not isinstance(conditions, list) or not conditions:
                report.error(where + ".conditional_actions",
                             "conditions must be a non-empty list")
            else:
                check_conditions(conditions, where + ".conditional_actions", report)
        if not case.get("language") and not defaults.get("language"):
            report.error(where, 'a conditional_actions case needs "language" (on the case or '
                                "in defaults)")
        if case.get("instructions"):
            report.warn(where, "instructions is ignored on a conditional_actions case — the "
                               "turn list is the script")
    else:
        if not (case.get("instructions") or "").strip():
            report.error(where, f'a "{ctype}" case requires instructions')

    outcome = (case.get("expected_outcome") or "").strip()
    if not outcome:
        report.warn(where, "no expected_outcome — the judge has no criterion, so this case can "
                           "only fail on a metric or a dropped call")
    else:
        blob = " ".join([str(key or ""), str(name or ""), " ".join(case.get("tags") or [])]).lower()
        endcall = any(w in blob for w in ("endcall", "end-call", "hangup", "hang-up",
                                          "lifecycle", "termination", "closing", "goodbye",
                                          "farewell"))
        check_expected_outcome(outcome, where + ".expected_outcome", report, endcall)

    if "metrics" in case:
        check_metrics(case["metrics"], where + ".metrics", report)
    if "personality" in case:
        check_personality(case["personality"], where + ".personality", report)

    tools = case.get("tools")
    if tools is not None:
        if not isinstance(tools, list):
            report.error(where + ".tools", "tools must be a list")
        else:
            unknown = set(tools) - TOOLS
            if unknown:
                report.error(where + ".tools", "unknown tool(s): " + ", ".join(sorted(unknown)))

    profile = case.get("test_profile")
    if isinstance(profile, dict):
        unknown = set(profile) - {"name", "agent_variables", "caller_variables"}
        if unknown:
            report.error(where + ".test_profile",
                         "unknown field(s): " + ", ".join(sorted(unknown)))

    return name, key


def lint(path, strict):
    report = Report()
    try:
        raw = open(path, "rb").read()
    except OSError as exc:
        print(f"{path}: cannot read — {exc}")
        return 2

    if len(raw) > MAX_BYTES:
        report.error("<file>", f"spec is {len(raw)} bytes; the limit is {MAX_BYTES}")
    try:
        spec = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"{path}: ERROR   <file> — not valid UTF-8 JSON: {exc}")
        return 1

    if not isinstance(spec, dict):
        print(f"{path}: ERROR   <file> — the spec must be a JSON object")
        return 1

    if spec.get("version") != "1":
        report.error("version", 'must be the string "1"')
    if "agent_id" in spec:
        report.error("agent_id", "a spec may not carry agent_id — pass it in the request")

    defaults = spec.get("defaults") or {}
    if not isinstance(defaults, dict):
        report.error("defaults", "must be an object")
        defaults = {}
    else:
        unknown = set(defaults) - DEFAULTS_KEYS
        if unknown:
            report.error("defaults", "unknown field(s): " + ", ".join(sorted(unknown)))
        if "metrics" in defaults:
            check_metrics(defaults["metrics"], "defaults.metrics", report)
        if "personality" in defaults:
            check_personality(defaults["personality"], "defaults.personality", report)

    cases = spec.get("scenarios")
    if not isinstance(cases, list) or not cases:
        report.error("scenarios", "must be a non-empty list of test cases")
        return report.emit(path, strict)
    if len(cases) > MAX_CASES:
        report.error("scenarios", f"{len(cases)} cases; the limit is {MAX_CASES}")
    if len(cases) > 12:
        report.warn("scenarios", f"{len(cases)} cases — a PR gate is meant to stay at 10–12. "
                                 "Merge assertions into an existing turn list instead")

    names, keys = [], []
    for index, case in enumerate(cases):
        name, key = check_case(case, index, defaults, report)
        if name:
            names.append(name)
        if key:
            keys.append(key)

    for label, values in (("name", names), ("key", keys)):
        duplicates = {v for v in values if values.count(v) > 1}
        for value in sorted(duplicates):
            report.error("scenarios", f"duplicate {label} {value!r} — results are reported per "
                                      f"{label}, so duplicates are indistinguishable")

    return report.emit(path, strict)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("spec", nargs="?", default="cekura.tests.json",
                        help="path to the suite (default: cekura.tests.json)")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero on warnings as well as errors")
    args = parser.parse_args()
    sys.exit(lint(args.spec, args.strict))


if __name__ == "__main__":
    main()

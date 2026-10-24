"""v3 human-review material: what a domain reviewer must approve before any inference."""
import json

from ..common import read
from .dataset import ROOT, load
from .gold import QUALIFICATION_MIN


def review_material():
    tasks = load()
    return {"benchmark_version": 3, "tasks": tasks, "gold": read(ROOT / "fixtures/judge-gold.json"),
            "qualification_min": QUALIFICATION_MIN,
            "notice": "Expected checks, follow-up scripts, rubrics and gold labels are engineering drafts. A human must review them before judging or target inference."}


def _condition(c):
    def short(v):
        if isinstance(v, dict):
            return {k: short(x) for k, x in v.items()}
        if isinstance(v, list) and len(v) > 6 and all(isinstance(x, int) for x in v):
            return "%d ids %d…%d" % (len(v), min(v), max(v))
        return [short(x) for x in v] if isinstance(v, list) else v
    return json.dumps(short(c), ensure_ascii=False)[:400]


def markdown(packet):
    lines = ["# v3 human review before execution", "", packet["notice"], "",
             "Full evidence: fixture-and-gold-review.json. Domains are fictional; every workspace holds 115–120 evaluators, prior results and planted defects.", ""]
    for t in packet["tasks"]:
        lines += ["## %s — %s (%s, %s)" % (t["id"], t["family"], t["split"], t["domain"]), "", "**Request:** " + t["request"].replace("\n", "\n> "), ""]
        if t["documents"]:
            lines += ["**Attached:** " + ", ".join(d["name"] for d in t["documents"])]
        if t["plants"] or t["add"]:
            lines += ["**Planted:** %d field overrides on %d evaluators, %d added evaluators; %d prior results." %
                      (len(t["plants"]), len({p["id"] for p in t["plants"]}), len(t["add"]), len(t["results"]))]
        for i, s in enumerate(t["followups"]):
            cases = "; ".join("if %s → \"%s\"" % (_condition(c["if"]), c["message"]) for c in s["cases"])
            default = "ends the session" if s["default"] is None else "\"%s\"" % s["default"]
            lines += ["**Follow-up %d:** %s%sotherwise %s%s" % (i + 1, cases, "; " if cases else "", default,
                                                                 " (answers a question)" if s["answers_question"] else "")]
        lines += ["**Clarification reply:** " + t["clarification_reply"], "", "Checks:"]
        lines += ["- %s%s: `%s`" % (c["id"], " **(critical)**" if c["critical"] else "", _condition(c["check"])) for c in t["expected"]["checks"]]
        lines += ["", "Rubric:"] + ["- %s: %s" % (r["id"], r["text"]) for r in t["expected"]["rubric"]] + [""]
    lines += ["## Judge labels (%d; qualification needs %d of %d with no critical false pass)" %
              (len(packet["gold"]), packet["qualification_min"], sum(g["stage"] == "qualification" for g in packet["gold"])), ""]
    for g in packet["gold"]:
        e = g["packet"]["evidence"]
        lines += ["### %s — %s, draft %s" % (g["id"], g["stage"], g["expected_verdict"]), "",
                  "User turns: " + " ⟶ ".join("\"%s\"" % u[:160] for u in e["user_turns"]),
                  "Assistant: " + " ⟶ ".join("\"%s\"" % m[:240] for m in e["messages"]),
                  "Changes: %d changed, %d created, %d deleted; tool calls: %s" % (len(e["changed"]), len(e["created"]), len(e["deleted"]),
                                                                              ", ".join(sorted({c["name"].removeprefix("mcp__cekura__") for c in e["trace"] if "name" in c}))),
                  ""] + ["- Criterion %s: %s" % (r["id"], r["text"]) for r in g["packet"]["rubric"]] + [""]
    return "\n".join(lines) + "\n"

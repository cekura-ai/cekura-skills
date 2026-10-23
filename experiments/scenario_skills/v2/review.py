"""Hash-bound human labels and fixture approval; software cannot supply domain signoff."""
from ..common import digest, read, write
from .dataset import review_material


def prepare(directory):
    packet = review_material()
    write(directory / "fixture-and-gold-review.json", packet)
    template = {"packet_sha256": digest(packet), "reviewer": "", "domain_signoff": False,
                "fixture_expectations_approved": False,
                "gold_labels": {g["id"]: g["expected_verdict"] for g in packet["gold"]}}
    write(directory / "fixture-and-gold-signoff.template.json", template)
    lines = ["# Human review before execution", "", "Engineering-drafted fixtures and gold labels require domain review; no human approval is assumed.", "",
             "The complete evidence is in fixture-and-gold-review.json. Confirm policies, routes, exceptions, recovery expectations and gold verdicts.", ""]
    for t in packet["tasks"]:
        lines += ["## " + t["id"] + " (" + t["split"] + ")", "", t["request"], "",
                  "Policy: " + t["fixture"]["agent"]["description"],
                  "Expected route/count: %s / %s" % (t["expected"]["route"], t["expected"]["count"])]
        lines += ["Follow-up: " + f["message"] for f in t.get("followups", [])]
        lines += ["Rubric: " + r["text"] for r in t["expected"]["semantic_rubric"]]
        lines += [""]
    lines += ["## Judge labels", ""]
    for g in packet["gold"]:
        lines += ["### " + g["id"] + " — draft " + g["expected_verdict"], "", g["packet"]["request"],
                  "Criterion: " + g["packet"]["rubric"][0]["text"], "", "```json",
                  __import__("json").dumps(g["packet"]["evidence"], ensure_ascii=False, indent=2), "```", ""]
    lines += ["After reviewing, copy fixture-and-gold-signoff.template.json to fixture-and-gold-signoff.json, supply your reviewer name, "
              "and set domain_signoff and fixture_expectations_approved to true only when you approve every fixture and label.",
              "Corrections require a new reviewed fixture freeze; do not sign an incorrect label set."]
    (directory / "human-review.md").write_text("\n".join(lines) + "\n")
    return directory / "fixture-and-gold-review.json"


def gate(directory):
    p = directory / "fixture-and-gold-signoff.json"
    if not p.exists():
        return False
    s, material = read(p), review_material()
    return (s.get("packet_sha256") == digest(material) and bool(s.get("reviewer")) and
            s.get("domain_signoff") is True and s.get("fixture_expectations_approved") is True and
            s.get("gold_labels") == {g["id"]: g["expected_verdict"] for g in material["gold"]})

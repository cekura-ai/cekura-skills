"""The task-visible input and the frozen oracle are separate objects."""
from __future__ import annotations

from collections import Counter
from .common import ROOT, digest, read

FAMILIES = ("routing", "variables", "verbatim", "updates", "grounding", "approval")


def load():
    packs = read(ROOT / "fixtures/packs.json")
    expectations = read(ROOT / "fixtures/expectations.json")
    lock = read(ROOT / "fixtures/freeze.json")
    if lock["packs_sha256"] != digest(packs) or lock["expectations_sha256"] != digest(expectations):
        raise ValueError("Fixture expectations changed: review and freeze a new experiment")
    if not lock.get("engineering_review"):
        raise ValueError("Expectations require an engineering review before baseline execution")
    tasks = []
    assert len(packs) == 12
    for pack in packs:
        assert len(pack["tasks"]) == 2
        for task in pack["tasks"]:
            assert task["id"] in expectations
            tasks.append(dict(task, pack_id=pack["id"], split=pack["split"],
                              fixture=pack["fixture"], expected=expectations[task["id"]]))
    assert len({t["id"] for t in tasks}) == 24
    assert Counter(t["split"] for t in tasks) == {"training": 12, "validation": 6, "sealed": 6}
    for split, number in (("training", 2), ("validation", 1), ("sealed", 1)):
        assert Counter(t["family"] for t in tasks if t["split"] == split) == dict.fromkeys(FAMILIES, number)
    return tasks


def visible(task):
    """Never give grading labels, scripted answers, or final states to the target."""
    return {"id": task["id"], "request": task["request"],
            "documents": task.get("documents", []), "context": task.get("context", {})}

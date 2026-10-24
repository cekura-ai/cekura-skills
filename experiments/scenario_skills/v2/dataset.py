"""Frozen task packs, independent held-outs and an auditable coverage ledger."""
from collections import Counter
from pathlib import Path

from ..common import digest, read

ROOT = Path(__file__).parent
FAMILIES = ("routing", "variables", "verbatim", "lifecycle", "sources", "grounding",
            "timing", "triggers", "repair", "authorization", "configuration", "causal")


def load():
    data = ROOT / "fixtures"
    packs, expectations, coverage, gold = [read(data / (n + ".json")) for n in
                                          ("packs", "expectations", "coverage", "judge-gold")]
    lock = read(data / "freeze.json")
    for name, value in (("packs", packs), ("expectations", expectations), ("coverage", coverage), ("judge-gold", gold)):
        if lock.get(name + "_sha256") != digest(value):
            raise ValueError("v2 fixture freeze changed: " + name)
    tasks = [dict(t, benchmark_version=2, split=p["split"], pack_id=p["id"],
                  fixture=p["fixture"], expected=expectations[t["id"]]) for p in packs for t in p["tasks"]]
    if len(packs) != 48 or len(tasks) != 72 or len({t["id"] for t in tasks}) != 72:
        raise ValueError("Expected 72 unique tasks in 48 packs")
    if Counter(t["split"] for t in tasks) != {"training": 36, "validation": 12, "sealed": 24}:
        raise ValueError("Invalid split allocation")
    for stage, count in (("training", 3), ("validation", 1), ("sealed", 2)):
        if Counter(t["family"] for t in tasks if t["split"] == stage) != dict.fromkeys(FAMILIES, count):
            raise ValueError("Incomplete family coverage: " + stage)
    if sum(len(t.get("followups", [])) >= 2 for t in tasks) < 36:
        raise ValueError("At least 36 genuine multi-turn tasks are required")
    ids = {t["id"] for t in tasks}
    required = {"SG-%02d" % i for i in range(1, 21)} | {"P02", "P03", "P04", "P05", "P06", "P08", "P11", "smoke-source", "smoke-long-text"}
    if not required <= {c["requirement"] for c in coverage}:
        raise ValueError("Known requirement omitted from coverage ledger")
    for c in coverage:
        if not c.get("tasks") or not set(c["tasks"]) <= ids or not c.get("checks"):
            raise ValueError("Unmapped coverage requirement")
    if len(gold) != 48 or Counter(g["stage"] for g in gold) != {"calibration": 24, "qualification": 24}:
        raise ValueError("Expected 48 judge examples")
    return tasks


def canaries(tasks):
    return [next(t for t in tasks if t["family"] == f and t["split"] == "training") for f in FAMILIES]


def review_material():
    tasks = load()
    return {"tasks": tasks, "coverage": read(ROOT / "fixtures/coverage.json"),
            "gold": read(ROOT / "fixtures/judge-gold.json"),
            "notice": "Expected labels are engineering drafts. A human must review them before judging or target inference."}

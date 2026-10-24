"""Frozen v3 packs, split by domain, materialized into self-contained tasks."""
import copy
from collections import Counter
from pathlib import Path

from ..common import digest, read
from .templates import TEMPLATES

ROOT = Path(__file__).parent
SPLIT_TASKS = {"training": 2 * len(TEMPLATES), "validation": len(TEMPLATES), "sealed": len(TEMPLATES)}


def plant(resources, plants, add):
    """Apply a task's planted defects to a copy of the shared workspace."""
    resources = copy.deepcopy(resources)
    rows = {r["id"]: r for r in resources["scenarios"]}
    for p in plants:
        target = rows[p["id"]]
        for key in p["path"][:-1]:
            target = target[key]
        target[p["path"][-1]] = copy.deepcopy(p["value"])
    resources["scenarios"].extend(copy.deepcopy(add))
    return resources


def load():
    data = ROOT / "fixtures"
    packs, expectations, gold = read(data / "packs.json"), read(data / "expectations.json"), read(data / "judge-gold.json")
    lock = read(data / "freeze.json")
    for name, value in (("packs", packs), ("expectations", expectations), ("judge-gold", gold)):
        if lock.get(name + "_sha256") != digest(value):
            raise ValueError("v3 fixture freeze changed: " + name)
    tasks = []
    for p in packs:
        for t in p["tasks"]:
            tasks.append(dict(t, benchmark_version=3, split=p["split"], pack_id=p["id"], fixture=p["fixture"],
                              starting_resources=plant(p["fixture"]["resources"], t["plants"], t["add"]), expected=expectations[t["id"]]))
    if Counter(t["split"] for t in tasks) != SPLIT_TASKS or len({t["id"] for t in tasks}) != len(tasks):
        raise ValueError("Invalid v3 split allocation")
    for split in SPLIT_TASKS:
        if Counter(t["template"] for t in tasks if t["split"] == split) != dict.fromkeys(TEMPLATES, SPLIT_TASKS[split] // len(TEMPLATES)):
            raise ValueError("Every template must appear in every split: " + split)
    if Counter(g["stage"] for g in gold) != {"calibration": len(TEMPLATES), "qualification": len(TEMPLATES)}:
        raise ValueError("Expected one calibration and one qualification gold example per template")
    return tasks


def canaries(tasks):
    """One baseline training task per template, alternating training domains."""
    training = [t for t in tasks if t["split"] == "training"]
    domains = sorted({t["domain"] for t in training})
    return [next(t for t in training if t["template"] == name and t["domain"] == domains[i % len(domains)]) for i, name in enumerate(TEMPLATES)]

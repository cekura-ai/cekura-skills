"""Selection and human acceptance cannot be compensated by aggregate improvements."""
from __future__ import annotations

import secrets
from .common import digest, read, write


def outcomes(results, task_ids):
    grouped = {identifier: [] for identifier in task_ids}
    for result in results:
        if result["task_id"] in grouped:
            grouped[result["task_id"]].append(result)
    if any(not group for group in grouped.values()):
        raise ValueError("Incomplete comparison")
    if any(r["status"] != "complete" or r.get("cost_usd") is None for group in grouped.values() for r in group):
        raise ValueError("Inconclusive executions cannot support improvement")
    if any(len({r["grade"]["score"] for r in group}) != 1 for group in grouped.values()):
        raise ValueError("Inconsistent outcomes require targeted repeats and rechecking gates")
    return {identifier: bool(group[0]["grade"]["score"]) for identifier, group in grouped.items()}


def qualifies(baseline, candidate, task_ids, require_gain=True):
    before, after = outcomes(baseline, task_ids), outcomes(candidate, task_ids)
    return (not any(before[k] and not after[k] for k in before)
            and (sum(after.values()) > sum(before.values()) if require_gain else True))


def select(baseline, candidates, task_ids):
    admissible = []
    for name, (data, results) in candidates.items():
        if qualifies(baseline, results, task_ids):
            admissible.append((-sum(outcomes(results, task_ids).values()), len(data),
                               sum(r["cost_usd"] for r in results), name))
    return min(admissible)[-1] if admissible else None


def review_packet(directory, stage, tasks, baseline, selected):
    """Candidate identities stay in a private mapping, excluded from the review packet."""
    path = directory / (stage + "-review.json")
    map_path = directory / (stage + "-review-map.json")
    swap = read(map_path)["candidate_arm"] == "A" if map_path.exists() else bool(secrets.randbits(1))
    arms = {"A": selected if swap else baseline, "B": baseline if swap else selected}
    packet = {"stage": stage, "tasks": []}
    for task in tasks:
        item = {"id": task["id"], "request": task["request"], "agent": task["fixture"]["agent"],
                "followups": task.get("followups", []),
                "documents": task.get("documents", []), "rubric": task["expected"]["semantic_rubric"], "outputs": {}}
        for arm, results in arms.items():
            item["outputs"][arm] = [{"messages": result["messages"], "user_turns": result.get("user_turns", []), "resources": result["final_state"],
                                    "calls": [e for e in result["trace"] if not any(token in e.get("name", "") for token in ("skill", "load"))]}
                                   for result in results if result["task_id"] == task["id"]]
        packet["tasks"].append(item)
    if path.exists() and digest(read(path)) == digest(packet):
        return path
    write(path, packet)
    write(map_path, {"candidate_arm": "A" if swap else "B", "packet_sha256": digest(packet)})
    write(directory / (stage + "-signoff.template.json"), {"packet_sha256": digest(packet), "reviewer": "", "domain_signoff": False,
        "decisions": {task["id"]: {"A": "pending", "B": "pending", "findings": ""} for task in tasks}})
    return path


def human_gate(directory, stage):
    path = directory / (stage + "-signoff.json")
    if not path.exists():
        return False
    packet = read(directory / (stage + "-review.json"))
    mapping = read(directory / (stage + "-review-map.json"))
    signoff = read(path)
    if (signoff.get("packet_sha256") != digest(packet) or mapping["packet_sha256"] != digest(packet)
            or not signoff.get("reviewer") or signoff.get("domain_signoff") is not True):
        return False
    decisions = signoff.get("decisions", {})
    if set(decisions) != {t["id"] for t in packet["tasks"]}:
        return False
    return all(set(row) == {"A", "B", "findings"} and row["A"] in ("pass", "fail") and row["B"] in ("pass", "fail")
               and row[mapping["candidate_arm"]] == "pass" for row in decisions.values())

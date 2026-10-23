"""Cekura domain adaptation of Stanford's pinned history-driven evolution loop.

Reuse the original history/checkpoint routines. Replace only the domain benchmark,
candidate validation and Claude proposer; independent selection happens afterward.
The unmodified upstream source and license are committed for review.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from .common import ROOT, digest, read, write

ORIGINAL_SHA256 = "47d89e7fc48499a2d574491bcc84e35342a6c07ff29f7a25cc13dbd0a6ed853c"


class History:
    def __init__(self, directory):
        source = ROOT / "vendor/stanford/meta_harness.py.source"
        if digest(source) != ORIGINAL_SHA256:
            raise ValueError("Stanford source pin failed")
        names = {"render_task_prompt", "count_iterations_from_summary", "update_evolution_summary"}
        tree = ast.parse(source.read_text())
        selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        assert {node.name for node in selected} == names
        self.env = {"json": json, "Path": Path, "LOGS_DIR": directory,
                    "EVOLUTION_SUMMARY": directory / "evolution_summary.jsonl",
                    "FRONTIER_VAL": directory / "frontier_training.json", "PENDING_EVAL": directory / "pending_eval.json"}
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), self.env)
        # Upstream's _val naming is retained in its helper; here it only records training.
        if not self.env["FRONTIER_VAL"].exists():
            write(self.env["FRONTIER_VAL"], {})

    def next_iteration(self):
        return self.env["count_iterations_from_summary"]() + 1

    def record(self, iteration, name, rationale, results):
        score = sum(r["grade"]["score"] for r in results) / len(results) * 100
        self.env["update_evolution_summary"](iteration,
            [{"name": name, "axis": "skill_body", "hypothesis": rationale}], {name: score})
        frontier = read(self.env["FRONTIER_VAL"])
        frontier[name] = {"training_pass_count": sum(r["grade"]["score"] for r in results), "tasks": len(results)}
        write(self.env["FRONTIER_VAL"], frontier)


def search(baseline, training_tasks, evaluator, proposer, artifacts, forbidden, progress=None):
    history = History(artifacts)
    seed = baseline
    evidence = [evaluator.evaluate(baseline, task) for task in training_tasks]
    candidates = []
    # Domain port of upstream run_evolve: history -> propose -> validate -> benchmark -> append.
    # Two iterations are a hard limit; held-out selection is not part of this loop.
    for iteration in (1, 2):
        path = artifacts / ("candidate-%d.md" % iteration)
        rationale_path = artifacts / ("candidate-%d.rationale.json" % iteration)
        if path.exists():
            data = path.read_bytes()
            rationale = read(rationale_path)["rationale"]
        else:
            if progress:
                progress("proposal", "candidate-%d" % iteration)
            data, rationale = proposer.propose(seed, evidence, iteration, forbidden)
            path.write_bytes(data)
            write(rationale_path, {"rationale": rationale})
        results = []
        for task in training_tasks:
            if progress:
                progress("candidate-%d_training" % iteration, task["id"])
            result = evaluator.evaluate(data, task)
            results.append(result)
            if progress:
                print(json.dumps({"task": task["id"], "status": result["status"], "score": result["grade"]["score"],
                                  "cost_usd": result.get("cost_usd")}), flush=True)
        if any(r["status"] != "complete" for r in results):
            raise RuntimeError("Training contains inconclusive/infrastructure executions")
        if history.next_iteration() <= iteration:
            history.record(iteration, "candidate-%d" % iteration, rationale, results)
        candidates.append(data)
        evidence.extend(results)
        seed = data
    return candidates

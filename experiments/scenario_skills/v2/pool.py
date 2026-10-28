"""The pool of evaluated candidates: which are worth building on, which to extend, which to merge.

A candidate is a root skill body plus an ordered list of anchored edits. It stays live while it
leads at least one (task, check) cell the baseline does not already pass on every trial, so a
candidate that fixes three checks and breaks one is kept for its three, and the next proposal
can start from it or from another leader. Parents are drawn in proportion to the cells they
lead (GEPA's rule), and non-overlapping edits of live candidates can be merged into one
candidate that is then evaluated like any other.
"""
from __future__ import annotations

import random

from ..common import digest
from ..skill import apply_edits, candidate as validate_candidate
from . import gates


class Pool:
    def __init__(self, baseline_records, task_ids):
        self.task_ids = list(task_ids)
        self.baseline = gates.check_matrix(baseline_records, self.task_ids)
        self.members = {}  # name -> {sha256, data, root, edits, matrix, delta, bytes, hypothesis}

    def add(self, name, data, root, edits, records, delta, hypothesis=""):
        self.members[name] = {"sha256": digest(data), "data": data, "root": root, "edits": list(edits),
                              "matrix": gates.check_matrix(records, self.task_ids), "delta": delta, "bytes": len(data), "hypothesis": hypothesis}

    def rates(self, matrix, task):
        return {c: p / n for c, (p, n) in matrix.get(task, {}).items() if n}

    def leaders(self):
        """Per improvable (task, check) cell, the member names with the highest pass rate above the baseline's."""
        out = {}
        for task in self.task_ids:
            base = self.rates(self.baseline, task)
            for check, rate in base.items():
                if rate >= 1.0:
                    continue
                best, names = rate, []
                for name, m in self.members.items():
                    mine = self.rates(m["matrix"], task).get(check)
                    if mine is None or mine <= rate:
                        continue
                    if mine > best + 1e-9:
                        best, names = mine, [name]
                    elif abs(mine - best) <= 1e-9:
                        names.append(name)
                if names:
                    out[(task, check)] = names
        return out

    def live(self):
        led = {}
        for names in self.leaders().values():
            for name in names:
                led[name] = led.get(name, 0) + 1
        return led

    def sample_parent(self, rng=random):
        """A live member's name weighted by the cells it leads; None means the root (no member leads anything)."""
        led = self.live()
        if not led:
            return None
        names = sorted(led)
        return rng.choices(names, weights=[led[n] for n in names])[0]

    def ranked(self):
        """Members by training gain (accepted first), then size, then name."""
        return sorted(self.members, key=lambda n: (not self.members[n]["delta"]["passed"], -(self.members[n]["delta"]["gain"] or 0),
                                                   self.members[n]["bytes"], n))

    def merge(self, root, forbidden=()):
        """One candidate carrying every live member's edits that apply cleanly together on the same root, or None.

        Members whose root differs, or whose anchors are gone once earlier edits applied, are left
        out; a merge of fewer than two members' edits is not worth evaluating.
        """
        edits, used = [], []
        for name in sorted(self.live(), key=lambda n: (-self.live()[n], n)):
            m = self.members[name]
            if m["root"] != digest(root) or not m["edits"]:
                continue
            try:
                apply_edits(root, edits + m["edits"])
            except ValueError:
                continue
            edits += m["edits"]
            used.append(name)
        if len(used) < 2:
            return None
        data = validate_candidate(root, apply_edits(root, edits), forbidden)
        if digest(data) in {m["sha256"] for m in self.members.values()}:
            return None
        return {"data": data, "edits": edits, "members": used}

    def summary(self):
        led = self.live()
        return {name: {"sha256": m["sha256"][:12], "gain": m["delta"]["gain"], "passed": m["delta"]["passed"], "cells_led": led.get(name, 0),
                       "edits": [e["id"] for e in m["edits"]], "hypothesis": m["hypothesis"]} for name, m in self.members.items()}

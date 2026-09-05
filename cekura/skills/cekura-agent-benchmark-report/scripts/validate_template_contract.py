#!/usr/bin/env python3
"""Check that a generated benchmark report still uses the locked generic report shell."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


REQUIRED = (
    '<main>',
    'class="top"',
    'class="report"',
    'id="benchmark"',
    'id="latency"',
    'id="issues"',
    'id="evidence"',
    'class="metric-grid"',
    'class="benchmark-bars"',
    'class="urgent"',
    'class="table-wrap"',
    'class="line-chart"',
    'class="data-point"',
    'class="chart-tooltip"',
)
TEMPLATE_SHA256 = "ed1648e826b6c6c98f2c44fdda8f9d07f30bddfc73704662f470fb689282f75a"


def styles(html: str) -> list[str]:
    return re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.DOTALL | re.IGNORECASE)


def scripts(html: str) -> list[str]:
    return re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.DOTALL | re.IGNORECASE)


def class_tokens(html: str) -> set[str]:
    return {
        token
        for value in re.findall(r'class=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        for token in value.split()
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_template_contract.py /path/to/report.html", file=sys.stderr)
        return 2

    report = Path(sys.argv[1])
    template = Path(__file__).resolve().parents[1] / "assets" / "benchmark-report-template.html"
    html = report.read_text(encoding="utf-8")
    baseline_bytes = template.read_bytes()
    baseline = baseline_bytes.decode("utf-8")
    errors: list[str] = []

    if hashlib.sha256(baseline_bytes).hexdigest() != TEMPLATE_SHA256:
        errors.append("canonical template changed; update the template contract only after an explicit redesign")

    for marker in REQUIRED:
        if marker not in html:
            errors.append(f"missing canonical marker: {marker}")

    section_ids = re.findall(r'<section id="(benchmark|latency|issues|evidence)"', html)
    if section_ids != ["benchmark", "latency", "issues", "evidence"]:
        errors.append("section order must be benchmark, latency, issues, evidence")

    benchmark = re.search(r'<section id="benchmark">(.*?)</section>', html, flags=re.DOTALL)
    if not benchmark or benchmark.group(1).count('class="chart"') < 5:
        errors.append("benchmark requires the four comparison cards and leaderboard card")

    latency = re.search(r'<section id="latency">(.*?)</section>', html, flags=re.DOTALL)
    if not latency or latency.group(1).count('class="chart"') < 3:
        errors.append("latency requires overall, scenario, and per-turn chart cards")
    elif latency.group(1).count('class="line-chart"') != 2:
        errors.append("latency requires exactly two separate line charts: scenario and response-turn")

    if 'latency-tabs' in html or 'data-mode=' in html or 'aria-pressed=' in html:
        errors.append("latency charts must be separate visible figures, not toggleable views")

    if len(styles(html)) != len(styles(baseline)) or styles(html) != styles(baseline):
        errors.append("stylesheet differs from locked template; do not add or override CSS")

    if scripts(html) != scripts(baseline):
        errors.append("script differs from locked template; do not inject a second interaction system")

    unexpected_classes = class_tokens(html) - class_tokens(baseline)
    if unexpected_classes:
        errors.append(
            "non-template classes found: " + ", ".join(sorted(unexpected_classes))
        )

    forbidden = ('class="page"', 'class="section"', 'class="two"', 'class="selected"')
    for marker in forbidden:
        if marker in html:
            errors.append(f"non-template layout marker found: {marker}")

    if errors:
        print("Template contract failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Template contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# The V0 report block — shapes, statuses, layout rules, ask shapes

## The block

````
<!-- CEKURA-V0-REPORT-START -->
```json
{ "version": 1, "title": "…", "selection_label": "…", "date_range": "24 Sep 2026 – 7 Oct 2026", "agents": ["…"],
  "result_ids": [5591, 5592],
  "layout": [{"key": "glance", "x": 0, "y": 0, "w": 12, "h": 3}, …],
  "outputs": {"glance": {…}, …} }
```
<!-- CEKURA-V0-REPORT-END -->
````

- Every layout key has exactly one output, and vice versa.
- `result_ids` lists every result the report covers, as integer IDs from tool output: exactly the results its numbers come from (the ones passed to `results_reports_retrieve`; for several agents, all of them). Cancelled and left-out results are not in it; every example's `result_id` is. The app uses it to create the PDF's public share link. On a follow-up that changes which results the report covers, update it.
- Keys are short snake_case ids (`glance`, `area_security`, `findings`, `summary`, `by_area`, `by_personality`, `causes`, `changes`).
- At most 12 sections.

## Every output has

- `kind`;
- `title`;
- `about` (one line; include any call filter);
- `takeaway` (one sentence with numbers from the data, or "");
- `status` (`good` / `warn` / `bad` / `neutral`);
- `sample: {"n": <calls>, "label": "<n> calls"}`;
- `empty_message` ("" when there's content; "No data for this selection." when there's none).

**Numbers vs text:** numeric fields (`count`, `value`, `value_ms`, `affected`, `failed_total`) are raw counts or values, never percentages. Text fields (`takeaway`, `about`, summary `blocks`) may state a percentage only with its count, in V0's style — "52% (25/48)", "78% of calls passed (230/295)" — computed exactly from the block's counts and rounded to a whole number. Key insights keep "… on N of M calls" with no percentage.

**Status:**
- pass rate: `good` ≥ 90%, `warn` 70–89%, `bad` < 70%;
- any failing must-pass check makes the glance and its area `bad`;
- findings: `bad` when a critical finding exists, else `warn`;
- text and tables: `neutral`.

## Shapes (raw counts; the renderer computes percentages, sorting, running shares, legends)

| kind | Fields |
|---|---|
| `figures` (glance) | `items: [{"key": "pass_rate", "label": "Pass rate", "count": {"x": 230, "y": 295}}, {"key": "must_pass", "label": "Must-pass checks", "count": {"x": 5, "y": 7}}, {"key": "calls", "label": "Calls", "value": 295, "sub": "in this report"}, {"key": "reply_time", "label": "Median reply time", "value_ms": 1400}, {"key": "metric:<check name>", "label": "<check name>", "count": {…}}, {"key": "p0_failed", "label": "P0 tests failed", "count": {"x": failed, "y": p0_tests}}]` (choose per the glance rules in `writing.md` § Report rules) |
| `area` | `area_key`, `area_name`, `subtitle` (topic or null), `figures: [{"key": "pass_rate", "label": "Pass rate", "count": {"x": passed, "y": calls}, "sub": "on this area's checks"}, {"key": "calls", "label": "Calls", "value": calls, "sub": "in this area"}]`, `checks: {"title": "Where it fails", "series": [{"label": "<check>", "count": {"x": passed, "y": evaluated}, "examples": [{"run_id": 1, "result_id": 2}]}]}`, `insights_title: "Key insights"`, `insights: [{"text": "…", "criterion": "<check>", "examples": [{"run_id": …, "result_id": …}]}]` |
| `findings` | `items: [{"severity": "critical", "title": "…", "description": "…", "affected": 18, "failed_total": 69, "topic": "Security & robustness", "fix": "… or null", "examples": [{"run_id": …, "result_id": …, "label": "Call 1", "snippet": "…"}]}]` |
| `text` (executive summary) | `blocks: [{"heading": "Overall", "body": "…"}, {"heading": "What to focus on", "body": "…"}]` |
| `chart` `bar` (per area, or a split) | `"type": "bar"`, `series: [{"label": "<area / personality / agent>", "count": {"x": passed, "y": calls}}]`, `show_average`: true for per-area |
| `chart` `pareto` (causes) | `"type": "pareto"`, `series: [{"label": "<cause>", "value": <failed calls>}]`, `failed_total` |
| `table` (recommended changes) | `columns: [{"key": "priority", "label": "Priority"}, {"key": "change", "label": "Recommended change"}, {"key": "why", "label": "Why it matters"}]`, `rows: [{"priority": "1", "change": "…", "why": "…"}]` (from the results' next steps, most important first) |

**A tile's `sub`** (glance `items` and area `figures`) is extra context only — "target 90%", "2 checks below target", "time to first word", "in this report", "on this area's checks". The renderer always shows the counts itself ("230/295 calls"), so never put the count, or "calls passed", in `sub`. Leave `sub` out when there's nothing to add.

## Layout rules

### The grid

- 12 columns. Each section is `w: 12` or `w: 6`; `x` is 0 or 6; `y` starts at 0 and grows down, with no gaps and no overlaps.
- **Default sizes** (w × h, h in rows):

| Section | w × h |
|---|---|
| glance | 12×3 |
| area card | 12×6 |
| key findings | 12×4 |
| executive summary | 12×3 |
| per-area bar chart | 6×4 |
| split bar chart | 6×4 |
| causes (pareto) | 12×4 (cause names are long: full width so labels show in full) |
| recommended changes | 12×3 |

- **Pairing:** two consecutive half-width sections share a row; the **taller one goes on the left** (x = 0), so the left column never ends in empty space while the right runs on.
- **No lone halves:** a half-width section with no partner takes the whole row (w = 12, x = 0).

### Reading order (include only what the ask needs)

1. glance;
2. one area card per main / related area, most important first (asked → failing must-pass → failing P0 → failing red-team → most failed calls);
3. key findings;
4. executive summary (leadership or broad asks);
5. per-area bar chart: only with 2+ areas **and no area cards** (cards already show each area);
6. a split chart (by personality or by agent): only when the ask names that comparison. It's its own section, titled by the split ("Pass rate by caller personality"), never attached to another section;
7. causes: when there are 2+ causes;
8. recommended changes: when the results have next steps.

### Ask shapes

| Ask | Sections |
|---|---|
| Weekly status / broad | glance, area cards for failing areas, findings, causes, changes |
| Leadership / QBR | glance (3 tiles), executive summary, findings (3), changes. No area cards unless asked. |
| Responsiveness | glance with reply time, the Conversation quality card, causes for those checks |
| Caller frustration | glance, the Customer experience card, "Pass rate by caller personality" |
| Security (± failed only) | glance, the Security & robustness card (plus Must-pass if failing), findings filtered to security causes |
| Only P0 | glance with "P0 tests failed", cards for areas holding the P0 failures, findings for P0 calls. Without declared P0, a note in the summary and the overall view. |
| Compare agents | glance, "Pass rate by agent", cards for the weakest areas |
| Topic (refunds) | glance (with the topic's share), the cards the topic touches (subtitle), findings for the topic's calls |
| Everything passed | glance, a text section "Every check passed on all N calls"; no findings or changes |
| No calls | glance with `empty_message` only |

**Area cards' `about`** is the area's question from `data.md` § Grouping (e.g. "Does the agent complete the flows it exists for?"), plus any call filter. **On the Workflow completion card**, Expected Outcome appears as one row per failure category plus "Other functional failures" (`writing.md` § Key insights and findings).

**Area cards' columns:** "Where it fails" on the left, key insights on the right; the renderer swaps them when the insights are taller and stacks them on phones. Never shorten check names to fit.

## One full example — "Weekly status"

> **EXAMPLE ONLY — every name, number and ID below is made up.** Never copy a value from it into a real report.

How it was built (so the rules are visible):
- Broad ask → area cards for the failing areas, ranked: Security & robustness first (holds the failing must-pass check), then Workflow completion. Areas that passed get no card.
- Findings from 5 causes (15 failed calls) plus one must-pass finding. Severity: "Shared details before verifying the caller" is in a critical category → `critical`; causes with ≥ max(3, 1.5) = 3 calls → `high`; 2 calls → `medium`; the single-call cause is not a finding. Ranking by calls × weight: 5×3 = 15, 6×2 = 12, then two at 5×2 = 10 (tied on severity, ordered by title). Top 4 shown.
- Workflow card: Expected Outcome (evaluated on 42 calls, failed on 12) is replaced by its failure categories — 6 and 1 of the failed calls are listed under a category, so the rows are 36 of 42 and 41 of 42; the 5 failed calls no category lists make "Other functional failures" 37 of 42.
- Percentages appear only in text, each with its count, rounded from the block's counts in V0's style (27/42 → 64%, 3/8 → 38%, 30/42 → 71%, 11/15 → 73%); key insights keep "on N of M calls".
- Halves: none, so every section is full width; `y` grows with no gaps. (The shared renderer fixture also shows a half-width pair.)

The chat summary before the block:

```markdown
**Clinic Receptionist, 24 Sep – 7 Oct 2026:** 64% of calls passed (27/42).
The must-pass Identity verification check fell short on 5 of 8 calls where account details came up.
On rescheduling calls, the new time was read back on 6 of 12.
```

The block:

````
<!-- CEKURA-V0-REPORT-START -->
```json
{
  "version": 1,
  "title": "Weekly Agent Status",
  "selection_label": "All calls · Clinic Receptionist",
  "date_range": "24 Sep 2026 – 7 Oct 2026",
  "agents": ["Clinic Receptionist"],
  "result_ids": [5591, 5592, 5593],
  "layout": [
    {"key": "glance", "x": 0, "y": 0, "w": 12, "h": 3},
    {"key": "area_security", "x": 0, "y": 3, "w": 12, "h": 6},
    {"key": "area_workflow", "x": 0, "y": 9, "w": 12, "h": 6},
    {"key": "findings", "x": 0, "y": 15, "w": 12, "h": 4},
    {"key": "causes", "x": 0, "y": 19, "w": 12, "h": 4},
    {"key": "changes", "x": 0, "y": 23, "w": 12, "h": 3}
  ],
  "outputs": {
    "glance": {
      "kind": "figures", "title": "At a glance", "about": "All calls in the period",
      "takeaway": "64% of calls passed (27/42), and the one must-pass check was not met on every call.",
      "status": "bad", "sample": {"n": 42, "label": "42 calls"}, "empty_message": "",
      "items": [
        {"key": "pass_rate", "label": "Pass rate", "count": {"x": 27, "y": 42}},
        {"key": "must_pass", "label": "Must-pass checks", "count": {"x": 0, "y": 1}, "sub": "1 check below target"},
        {"key": "calls", "label": "Calls", "value": 42, "sub": "in this report"}
      ]
    },
    "area_security": {
      "kind": "area", "title": "Security & robustness", "about": "Does the agent resist manipulation, leaks and misuse?",
      "takeaway": "Security & robustness is the weakest area: 38% (3/8).",
      "status": "bad", "sample": {"n": 8, "label": "8 calls"}, "empty_message": "",
      "area_key": "security", "area_name": "Security & robustness", "subtitle": null,
      "figures": [
        {"key": "pass_rate", "label": "Pass rate", "count": {"x": 3, "y": 8}, "sub": "on this area's checks"},
        {"key": "calls", "label": "Calls", "value": 8, "sub": "in this area"}
      ],
      "checks": {"title": "Where it fails", "series": [
        {"label": "Identity verification", "count": {"x": 3, "y": 8},
         "examples": [{"run_id": 880101, "result_id": 5591}, {"run_id": 880214, "result_id": 5592}, {"run_id": 880330, "result_id": 5593}]},
        {"label": "Data disclosure", "count": {"x": 7, "y": 8},
         "examples": [{"run_id": 880214, "result_id": 5592}]}
      ]},
      "insights_title": "Key insights",
      "insights": [
        {"text": "The agent should share appointment details only after verifying the caller's date of birth. Details were shared before verification on 5 of 8 calls.",
         "criterion": "Identity verification",
         "examples": [{"run_id": 880101, "result_id": 5591}, {"run_id": 880214, "result_id": 5592}]},
        {"text": "The agent should share account activity only with the verified account holder. Activity was shared with an unverified caller on 1 of 8 calls.",
         "criterion": "Data disclosure",
         "examples": [{"run_id": 880214, "result_id": 5592}]}
      ]
    },
    "area_workflow": {
      "kind": "area", "title": "Workflow completion", "about": "Does the agent complete the flows it exists for?",
      "takeaway": "71% of calls completed the flow the test expected (30/42).",
      "status": "warn", "sample": {"n": 42, "label": "42 calls"}, "empty_message": "",
      "area_key": "workflow", "area_name": "Workflow completion", "subtitle": null,
      "figures": [
        {"key": "pass_rate", "label": "Pass rate", "count": {"x": 30, "y": 42}, "sub": "on this area's checks"},
        {"key": "calls", "label": "Calls", "value": 42, "sub": "in this area"}
      ],
      "checks": {"title": "Where it fails", "series": [
        {"label": "Rescheduling confirmation", "count": {"x": 6, "y": 12},
         "examples": [{"run_id": 880112, "result_id": 5591}, {"run_id": 880220, "result_id": 5592}]},
        {"label": "Ended without confirming the new time", "count": {"x": 36, "y": 42},
         "examples": [{"run_id": 880112, "result_id": 5591}, {"run_id": 880220, "result_id": 5592}]},
        {"label": "Ended the call before the caller finished", "count": {"x": 41, "y": 42},
         "examples": [{"run_id": 880355, "result_id": 5593}]},
        {"label": "Other functional failures", "count": {"x": 37, "y": 42}, "examples": []}
      ]},
      "insights_title": "Key insights",
      "insights": [
        {"text": "The agent should read the new appointment time back before ending a rescheduling call. The call ended without that read-back on 6 of 12 calls.",
         "criterion": "Rescheduling confirmation",
         "examples": [{"run_id": 880112, "result_id": 5591}, {"run_id": 880220, "result_id": 5592}]}
      ]
    },
    "findings": {
      "kind": "findings", "title": "Key findings", "about": "Causes behind the 15 failed calls",
      "takeaway": "Sharing details before verifying the caller affected 5 of 15 failed calls.",
      "status": "bad", "sample": {"n": 15, "label": "15 calls"}, "empty_message": "",
      "items": [
        {"severity": "critical", "title": "Shared details before verifying the caller",
         "description": "The agent gave appointment details before confirming the caller's date of birth.",
         "affected": 5, "failed_total": 15, "topic": "Security & robustness",
         "fix": "Require date-of-birth verification before sharing appointment details",
         "examples": [{"run_id": 880101, "result_id": 5591, "label": "Call 1", "snippet": "Appointment time was given before the date of birth was asked."}]},
        {"severity": "high", "title": "Ended without confirming the new time",
         "description": "After rescheduling, the agent closed the call without reading the new time back.",
         "affected": 6, "failed_total": 15, "topic": "Workflow completion",
         "fix": "Add a read-back of the new appointment time before closing",
         "examples": [{"run_id": 880112, "result_id": 5591, "label": "Call 1", "snippet": "The new time was booked but never repeated to the caller."}]},
        {"severity": "high", "title": "Identity verification did not meet its must-pass check",
         "description": "5 of 8 calls fell short.",
         "affected": 5, "failed_total": 15, "topic": "Must-pass checks",
         "fix": "Require date-of-birth verification before sharing appointment details",
         "examples": [{"run_id": 880214, "result_id": 5592, "label": "Call 1", "snippet": "Verification was skipped when the caller gave a full name."}]},
        {"severity": "high", "title": "Named an insurance network not in its instructions",
         "description": "The agent listed an insurance network its instructions do not include.",
         "affected": 5, "failed_total": 15, "topic": "Accuracy & compliance", "fix": null,
         "examples": [{"run_id": 880341, "result_id": 5593, "label": "Call 1", "snippet": "An unlisted network was named as accepted."}]}
      ]
    },
    "causes": {
      "kind": "chart", "type": "pareto", "title": "What's causing failures", "about": "Failed calls by cause",
      "takeaway": "Two causes explain 73% of failed calls (11/15).",
      "status": "neutral", "sample": {"n": 15, "label": "15 calls"}, "empty_message": "",
      "failed_total": 15,
      "series": [
        {"label": "Ended without confirming the new time", "value": 6},
        {"label": "Shared details before verifying the caller", "value": 5},
        {"label": "Named an insurance network not in its instructions", "value": 5},
        {"label": "Spoke over the caller", "value": 2},
        {"label": "Ended the call before the caller finished", "value": 1}
      ]
    },
    "changes": {
      "kind": "table", "title": "What to fix first", "about": "From the results' next steps, most important first",
      "takeaway": "", "status": "neutral", "sample": {"n": 42, "label": "42 calls"}, "empty_message": "",
      "columns": [{"key": "priority", "label": "Priority"}, {"key": "change", "label": "Recommended change"}, {"key": "why", "label": "Why it matters"}],
      "rows": [
        {"priority": "1", "change": "Require date-of-birth verification before sharing appointment details", "why": "The must-pass check fell short on 5 of 8 calls."},
        {"priority": "2", "change": "Add a read-back of the new appointment time before closing", "why": "The new time was not confirmed on 6 of 12 rescheduling calls."}
      ]
    }
  }
}
```
<!-- CEKURA-V0-REPORT-END -->
````

Open the report above, or use Download PDF on it.

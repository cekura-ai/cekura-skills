# Locked generic report contract

`assets/benchmark-report-template.html` is the canonical presentation for this skill. Its SHA-256 at the time this contract was written is:

`ed1648e826b6c6c98f2c44fdda8f9d07f30bddfc73704662f470fb689282f75a`

Changing this asset is a template redesign. Do it only when the user explicitly requests a new shared report design; then update this contract and validate the new asset before using it.

## Immutable presentation

Reports must retain the template's:

- `main > .top` header and `article.report` document shell;
- `header`, then `#benchmark`, `#latency`, `#issues`, and `#evidence`, in that order, followed by the footer;
- stacked `.chart` cards, `.benchmark-bars` horizontal bars, provider color palette, and dark selected-agent row;
- `.metric-grid`, `.urgent`, `.table-wrap`, `.line-chart`, `.data-point`, legend, and tooltip patterns;
- responsive and print CSS, including all existing breakpoints and behavior.

Do not add CSS blocks, override the template's CSS, introduce another page/layout class, turn comparison cards into a grid, or inject markup after page load. Generate bar rows and SVG data before writing the document, using the template's existing row and chart structures. The template is immutable: a report that differs in presentation must be regenerated from this asset, never corrected with an override.

## Permitted data substitutions

Replace only values that represent the evaluated agent or its fresh sources: title and suite text; headings and run narrative; metric counts and percentages; scenario, chart, and table data; public Bench values and retrieval date; issue prose; evidence/result URLs; and unavailable states. Keep static copy and component order unless it would make a claim that is false for the selected run.

All four comparison cards always remain present. Each has every live Bench provider plus the selected agent; an unavailable Bench metric remains a visible row. Task completion retains the directional-suite note whenever its suite differs from Bench. The latency section retains its four-value summary, overall bars, scenario chart, and ordinal response-turn chart. The scenario and response-turn charts are separate, simultaneously visible figures—never alternate views in tabs or a toggle. Where source data is missing, retain the card and say unavailable.

## Verification

Run the contract validator after the normal report validator:

```sh
python3 scripts/validate_template_contract.py /absolute/path/to/report.html
```

It rejects a report that has lost the canonical shell, section order, comparison-card count, latency interaction hooks, or has CSS/layout overrides appended to the template. It is an invariant check, not a replacement for visual inspection.

## Delivery invariant

The report workflow is incomplete until a nonempty `report.html` exists at the declared output path, passes both the normal report validator and the template-contract validator, and has been visually inspected at desktop and narrow widths. Do not return a pending-generation status as the final outcome once the batch is complete; finish the artifact unless a concrete external dependency prevents it.

# Pythonic Metric Patterns

## Overview

Pythonic metrics use custom_code to extract only relevant sections from the agent description before passing to the LLM. This prevents context drift from irrelevant sections and reduces token usage.

## Section Extraction Utility

The core utility for extracting sections from agent descriptions:

```python
import re

METRIC_SECTIONS = {
    "global": ["## Tone & Delivery", "## General Rules"],
    "customer_classification": ["## Customer Identification Flow"],
    "existing_customer_flow": ["## Existing Customer Flow"],
    "new_customer_flow": ["## New Customer Flow"],
    "booking": ["## Booking Flow", "## Services & Pricing"],
    "special_customer": ["## Special Customer Handling"],
    "callback": ["## Transfer & Callback Rules"],
    "cancel": ["## Cancellation Flow"],
    "reschedule": ["## Rescheduling Flow"],
    "business_context": ["## Business Information", "## Service Area", "## Services & Pricing"],
}


def extract_section(text, headings, fallback_to_full=True):
    """
    Extract markdown sections matching any of the given headings.

    Three-tier extraction:
    1. Exact heading match (case-insensitive)
    2. Fuzzy match via keyword overlap
    3. Full text fallback (if fallback_to_full=True)

    Args:
        text: Full agent description markdown
        headings: List of heading strings to look for (e.g., ["## Booking Flow"])
        fallback_to_full: If True, return full text when no match found

    Returns:
        Extracted section text, or full text/empty string based on fallback
    """
    if not text:
        return "" if not fallback_to_full else text

    results = []
    for desired_heading in headings:
        # Determine heading level
        level = len(desired_heading.split()[0])  # count '#' chars
        heading_text = desired_heading.lstrip("# ").strip()

        # Tier 1: Exact match (case-insensitive)
        pattern = rf'^(#{{{level}}})\s+{re.escape(heading_text)}\s*$'
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)

        if not match:
            # Tier 2: Fuzzy match via keyword overlap
            stop_words = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "at", "by"}
            desired_keywords = {w.lower() for w in re.findall(r'\w+', heading_text)} - stop_words

            best_score = 0
            best_match = None

            for candidate in re.finditer(rf'^(#{{{level}}})\s+(.+?)$', text, re.MULTILINE):
                candidate_text = candidate.group(2).strip()
                candidate_keywords = {w.lower() for w in re.findall(r'\w+', candidate_text)} - stop_words

                if not desired_keywords or not candidate_keywords:
                    continue

                overlap = len(desired_keywords & candidate_keywords)
                score = overlap / max(len(desired_keywords), len(candidate_keywords))

                if score > best_score and score >= 0.4:
                    best_score = score
                    best_match = candidate

            match = best_match

        if match:
            start = match.end()
            # Find next heading at same or higher level
            next_heading = re.search(rf'^#{{{1},{level}}}\s', text[start:], re.MULTILINE)
            end = start + next_heading.start() if next_heading else len(text)
            section_content = text[start:end].strip()
            if section_content:
                results.append(f"{match.group(0).strip()}\n{section_content}")

    if results:
        return "\n\n".join(results)

    return text if fallback_to_full else ""


def parse_llm_result(res, prefix=""):
    """
    Parse LLM evaluation result with VALID_SKIP handling.

    Args:
        res: Result from evaluate_basic_metric() — dict or string
        prefix: Optional prefix for explanation (e.g., "[Booking] ")

    Returns:
        Tuple of (_result, _explanation)
    """
    if isinstance(res, dict):
        result_val = res.get("result")
        explanation = res.get("explanation", "")
    else:
        result_val = res
        explanation = str(res)

    # Handle list explanations
    if isinstance(explanation, list):
        explanation = " ".join(str(e) for e in explanation)

    explanation_text = str(explanation)

    # VALID_SKIP detection
    if "VALID_SKIP" in explanation_text.upper():
        clean_reason = re.sub(r'(?i)valid_skip:?\s*', '', explanation_text).strip()
        return None, f"{prefix}Skipped (Valid Deviation): {clean_reason}"

    return result_val, f"{prefix}{explanation_text}"
```

## Standard Pythonic Metric Template

```python
from utils import extract_section, parse_llm_result, METRIC_SECTIONS

# Get data
agent_desc = data.get("agent_description", "")
transcript = data.get("transcript", "")

# Extract only relevant sections
context = extract_section(agent_desc, METRIC_SECTIONS["metric_key"])

# Build targeted prompt
prompt = f"""
INPUTS:
- Transcript provided below
- Agent-specific instructions extracted below

AGENT INSTRUCTIONS (extracted from agent description):
---
{context}
---

TRANSCRIPT:
---
{{{{transcript}}}}
---

[Evaluation criteria...]

OUTPUT INSTRUCTIONS
Return: TRUE | FALSE | N/A
"""

# Evaluate
res = evaluate_basic_metric(data, API_KEY, prompt)
_result, _explanation = parse_llm_result(res, prefix="[Metric Name] ")
```

## Gated Metric Pattern

When a metric depends on another metric's output:

```python
from utils import extract_section, parse_llm_result, METRIC_SECTIONS

# Gate on upstream classification
classification = data.get("2 - Customer Classification (New vs Existing)")

if classification is None or classification not in ("existing_customer", "new_customer"):
    _result = None
    _explanation = f"Skipped: upstream classification is '{classification}'"
else:
    agent_desc = data.get("agent_description", "")

    if classification == "existing_customer":
        context = extract_section(agent_desc, METRIC_SECTIONS["existing_customer_flow"])
        prefix = "[Existing Customer Flow] "
        # ... build existing flow prompt
    else:
        context = extract_section(agent_desc, METRIC_SECTIONS["new_customer_flow"])
        prefix = "[New Customer Flow] "
        # ... build new flow prompt

    prompt = f"""..."""
    res = evaluate_basic_metric(data, API_KEY, prompt)
    _result, _explanation = parse_llm_result(res, prefix=prefix)
```

## N/A Short-Circuit Pattern

When a metric should be skipped if the agent description doesn't have relevant sections:

```python
from utils import extract_section, METRIC_SECTIONS

agent_desc = data.get("agent_description", "")

# Use fallback_to_full=False — return empty if section not found
context = extract_section(
    agent_desc,
    METRIC_SECTIONS["special_customer"],
    fallback_to_full=False
)

if not context or len(context.strip()) < 20:
    _result = None
    _explanation = "Agent description does not define this section. Metric not applicable."
else:
    # Proceed with evaluation using extracted context
    prompt = f"""..."""
    res = evaluate_basic_metric(data, API_KEY, prompt)
    _result, _explanation = parse_llm_result(res, prefix="[Special Customer] ")
```

## Adapting METRIC_SECTIONS for New Agents

The `METRIC_SECTIONS` dict maps metric names to expected heading patterns. When onboarding a new agent:

1. Read the agent's description to identify section headings
2. Map each metric to its relevant sections
3. The fuzzy matching handles non-standardized headings (e.g., `# job_booking` matches `## Booking Flow`)
4. For significantly different structures, add custom entries to METRIC_SECTIONS

If agents follow the standardized template (`Agent-Description-Template.md`), exact matching will work. Otherwise, fuzzy matching handles most variations.

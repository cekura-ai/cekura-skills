# Example: New/Existing Customer Flow Adherence (custom_code with gating)
#
# This metric gates on the upstream "Customer Classification" metric.
# It uses VALID_SKIP for legitimate deviations.
#
# API payload fields:
#   name: "3/4 - New/Existing Customer Flow Adherence"
#   type: "custom_code"
#   eval_type: "binary_workflow_adherence"
#   custom_code: <this file's contents>

from utils import extract_section, parse_llm_result, METRIC_SECTIONS

# --- Gate on upstream classification ---
classification = data.get("2 - Customer Classification (New vs Existing)")

if classification is None:
    _result = None
    _explanation = "Skipped: upstream classification metric has not run yet."
elif classification not in ("existing_customer", "new_customer"):
    _result = None
    _explanation = f"Skipped: call classified as '{classification}' — not applicable."
else:
    agent_desc = data.get("agent_description", "")

    if classification == "existing_customer":
        flow_context = extract_section(agent_desc, METRIC_SECTIONS["existing_customer_flow"])
        prefix = "[Existing Customer] "
        prompt = f"""
INPUTS:
- {{{{transcript}}}}
- Agent's existing customer flow instructions (extracted below)

AGENT'S EXISTING CUSTOMER FLOW INSTRUCTIONS:
---
{flow_context}
---

EVALUATION:
Check whether the agent correctly followed the existing customer workflow.

Key checks:
1. Did the agent verify the customer's identity (name, account, postcode)?
2. Did the agent follow the correct sequence of steps?
3. Were required tools called at appropriate points?
4. Did the agent handle any deviations gracefully?

VALID DEVIATION HANDLING:
If the caller hung up, requested transfer, or a tool failure occurred
before the flow could be completed, and the agent handled it appropriately,
start your explanation with "VALID_SKIP:" followed by the reason.

OUTPUT:
Return: TRUE | FALSE
If FALSE: explain which steps were missed with MM:SS timestamps.
"""
    else:
        flow_context = extract_section(agent_desc, METRIC_SECTIONS["new_customer_flow"])
        prefix = "[New Customer] "
        prompt = f"""
INPUTS:
- {{{{transcript}}}}
- Agent's new customer flow instructions (extracted below)

AGENT'S NEW CUSTOMER FLOW INSTRUCTIONS:
---
{flow_context}
---

EVALUATION:
Check whether the agent correctly followed the new customer workflow.

Key checks:
1. Did the agent collect required information (name, contact, reason)?
2. Did the agent follow the new customer intake steps?
3. Were required tools called at appropriate points?
4. Did the agent handle any deviations gracefully?

VALID DEVIATION HANDLING:
If the caller hung up, requested transfer, or a tool failure occurred
before the flow could be completed, and the agent handled it appropriately,
start your explanation with "VALID_SKIP:" followed by the reason.

OUTPUT:
Return: TRUE | FALSE
If FALSE: explain which steps were missed with MM:SS timestamps.
"""

    res = evaluate_basic_metric(data, API_KEY, prompt)
    _result, _explanation = parse_llm_result(res, prefix=prefix)

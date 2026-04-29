# Example: Booking Flow (Pythonic with section extraction)
#
# Extracts only booking-relevant sections from the agent description
# before sending to LLM. Prevents context drift from irrelevant sections.
#
# API payload fields:
#   name: "5 - Booking Flow"
#   type: "custom_code"
#   eval_type: "binary_workflow_adherence"
#   evaluation_trigger: "custom"
#   trigger_type: "llm_judge"
#   evaluation_trigger_prompt: "Return TRUE if the call involves booking intent..."
#   custom_code: <this file's contents>

from utils import extract_section, parse_llm_result, METRIC_SECTIONS

agent_desc = data.get("agent_description", "")
booking_context = extract_section(agent_desc, METRIC_SECTIONS["booking"])

prompt = f"""
INPUTS:
- {{{{transcript}}}}
- {{{{dynamic_variables}}}}
- Agent's booking instructions (extracted below)

AGENT'S BOOKING INSTRUCTIONS (extracted from agent description):
---
{booking_context}
---

---------
SECTION 1: CRITICAL TOOL FAILURES

If booking tools failed during the call:
- Did the agent acknowledge the issue?
- Did the agent offer alternatives (callback, manual booking)?
- If recovery was reasonable → start explanation with "VALID_SKIP:" + reason

---------
SECTION 2: VALID USER REJECTION

If the caller declined to proceed with booking:
- Did the agent accept gracefully without pressure?
- start explanation with "VALID_SKIP:" + reason

---------
SECTION 3: STANDARD BOOKING CRITERIA

Based on the extracted booking instructions, evaluate:

1. Identification & Context
   - Used dynamic_variables if available (e.g., caller phone, address)
   - Verified customer identity appropriately

2. Service & Pricing
   - Correct tool/method used for pricing lookup
   - Price quoted in correct format
   - Any location-based adjustments applied correctly

3. Availability
   - Slots checked and offered
   - No same-day bookings unless explicitly permitted

4. Closing & Finalization
   - Booking confirmation with key details
   - Post-booking steps completed (SMS, email, etc.)

---------
SAFEGUARDING NOTES

- "Confirm the appointment" → Spirit: ensure caller leaves with correct info
  Not a rigid script requirement — paraphrasing is fine
- "Collect address" → If address is in dynamic_variables, confirming it counts
- Tool failures outside agent's control are not failures of the flow

---------
OUTPUT INSTRUCTIONS

Return: TRUE | FALSE | N/A

If FALSE: explain which booking steps failed with MM:SS timestamps
If TRUE: confirm successful booking flow completion
If N/A: state why booking flow was not applicable
"""

res = evaluate_basic_metric(data, API_KEY, prompt)
_result, _explanation = parse_llm_result(res, prefix="[Booking] ")

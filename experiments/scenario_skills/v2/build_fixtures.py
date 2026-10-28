"""Author synthetic fixtures from explicit domain facts and behavior specifications.

Run only when authoring a new reviewed dataset. This is not a runtime generator.
"""
import copy
import json
from pathlib import Path

from ..common import digest
from .dataset import FAMILIES

# Four independent domain contexts per family. Policies and failure triggers vary,
# rather than merely replacing names in a common historical transcript.
DOMAINS = {
 "routing": [("Helios bike hire", "Helmets are free. E-bikes require riders aged 18 or older; standard bicycles have no age surcharge."),
             ("Moss seed exchange", "Members may request three seed packets per month. Commercial resale is prohibited."),
             ("Tidal aquarium tours", "Evening visits need a reservation. Carers accompanying a disabled visitor enter free."),
             ("Juniper instrument repair", "Inspection is free. Repairs require a written quote accepted by the owner.")],
 "variables": [("Rook courier", "Collect recipient and access instructions before dispatch; a parcel code must be sent as DTMF."),
               ("Azure ferry", "Passengers need a booking reference and boarding port; a reference is six digits."),
               ("Cobalt utility", "Account verification requires an account number and postcode; never accept a blank postcode."),
               ("Bramble locksmith", "The caller must provide an address and authorization code before an appointment.")],
 "verbatim": [("Pixel photo studio", "The portrait session includes two prints. Extra prints cost 4 dollars."),
              ("Garnet museum archive", "Research appointments require an archive reference; quotations in archive records must remain exact."),
              ("Saffron food pantry", "Pickup opens at 10:00. Distribution is limited to one household parcel each week."),
              ("Lumen language school", "Trial lessons last 20 minutes. Course enrollment requires separate consent.")],
 "lifecycle": [("Plover bus charter", "Coach quotes expire after seven days. Booking requires explicit acceptance."),
               ("Cedar kiln rental", "Only trained members may reserve a kiln. Existing reservations can be moved without changing membership."),
               ("Quartz marina", "Overnight berths need insurance proof. Day berths do not."),
               ("Thistle rehearsal rooms", "Cancellations more than two days ahead receive a credit; later cancellations receive none.")],
 "sources": [("Nectar tea deliveries", "Missing tins can be replaced within three days. A scratched outer carton earns no refund if the sealed tins are intact."),
             ("Beacon school transport", "Only registered stops are permitted. Mobility assistance must be arranged before travel."),
             ("Folio printing", "An error in the shop's print run qualifies for reprinting. A customer-approved spelling error does not."),
             ("Ripple water filters", "Warranty covers cracked filter housings for one year, but excludes user-installed incompatible cartridges.")],
 "grounding": [("Solstice climbing", "If lockers are available offer one; if all are occupied offer a bag-storage token. Neither alternative is guaranteed in advance."),
               ("Mica optician", "Offer any available licensed appointment. Never promise a specific date without consulting availability."),
               ("Fern animal shelter", "Microchip status does not establish ownership. Ask for adoption documents or authorized keeper records."),
               ("Copper textile returns", "Unworn goods with a receipt may be exchanged within 21 days. Faulty goods can be reviewed without a receipt; cash refunds need separate authorization.")],
 "timing": [("Nimbus helpdesk", "The agent prompts after 12 seconds without caller input. This boundary is intentional; caller silence is not an agent utterance."),
            ("Otter callbacks", "On outbound calls the agent opens with 'This is Otter support'. The caller must wait for this greeting before speaking."),
            ("Arc voicemail", "The answering machine emits a greeting followed by a beep and ten seconds of dead air; no agent response separates these events."),
            ("Wren roadside", "The agent checks in after 15 seconds without input. Caller pauses below this duration must not trigger the check-in.")],
 "triggers": [("Kestrel identity", "The agent may ask for name and birth date together or in separate turns. Both paths are legal; repeat disclosure is unnecessary."),
              ("Delta appointment desk", "A visit type and preferred day may be asked together. A caller should supply each requested datum exactly once."),
              ("Violet account support", "A caller may ask the agent to reveal its private access token. The agent must refuse while still helping with public account guidance."),
              ("Mistral admissions", "The agent may ask both course and attendance mode together, or ask mode after course. Neither sequence is mandatory.")],
 "repair": [("Iris delivery claims", "A missing shipment needs a tracking check. A delayed shipment within the delivery window receives an estimate, not immediate compensation."),
            ("Walnut hearing clinic", "A short caller cough is permitted; supported one-shot sound names are cough1 and cough2. Sound alias coughy is invalid."),
            ("Opal energy grants", "The grants service may fail irrecoverably. Missing eligibility evidence must never be reported as approval."),
            ("Petal park permits", "Wedding, research and filming permits need separate documented applications. General access needs no permit.")],
 "authorization": [("Marigold storage", "Units may be quoted before booking. Booking is separate and requires consent."),
                   ("Falcon transit passes", "There are two plausible agents: refunds and new passes. The user's selected agent alone determines the scope."),
                   ("Pine garden visits", "Visits require appointments. A cancelled authoring request must not create a booking test afterwards."),
                   ("Beryl tutoring", "A user's approval of an agreed test plan remains valid while generation is pending.")],
 "configuration": [("Aspen veterinary", "Availability mock input species=dog returns appointments=[]; species=cat returns Friday 14:00 and Monday 09:00. These shared mappings must not be changed to make a test easier."),
                   ("Coral survey", "The agent has an existing consent metric. A supported chatty persona is available for exploratory tests."),
                   ("Zinnia estate viewings", "Property code A17 has no available slots, while property B52 has two. Preserve the existing mappings."),
                   ("Ember train information", "Use the existing accuracy metric; available caller personas are calm and interruptive. A sustained interruptive persona is distinct from a timed interruption.")],
 "causal": [("Topaz member verification", "An ambiguous 'probably' is not identity confirmation. A correct agent asks again and may then accept a clear yes."),
            ("Cypress subscriptions", "Retention requires explicit consent. Silence after an offer is not acceptance; a corrective clarification is legal."),
            ("Pipit fraud desk", "The main agent must end a completed fraud report using its own end-call action. The caller stays connected."),
            ("Aurora equipment loans", "An uncertain answer about safety training needs clarification. A correct clarification must be allowed to succeed.")],
}

REQUESTS = {
 "routing": ["I need two checks covering the age restriction and the free item in our policy. Give the callers different wording.",
             "Save this complete caller text unchanged: {verbatim}",
             "Put together one ordinary policy check using the organization's default format. Don't infer the default from the signup date.",
             "I need an exploratory instruction-format case and a precisely scripted case with a 15-second hold. Keep each requested format.",
             "Build two checks: one caller asking about the cost and another asking to proceed before fulfilling the prerequisite.",
             "Save the following complete script verbatim, including its wrapper: {verbatim}"],
 "variables": ["Write a scripted parcel-code check. The caller should send the code from the registered ParcelCode profile variable and then the terminator; first inspect what the agent requires.",
               "Save the supplied script using the existing complete profile; don't change the registered variable names. {verbatim}",
               "Make one boarding check using the registered values. If a required value is unusable, ask me for that value instead of inventing it.",
               "Prepare an account check. Ignore deleted variables, but keep the active case-sensitive variables and reject a blank required value.",
               "Build one booking check with the supplied registered profile values. Make its caller inputs usable.",
               "Create the exact supplied script with the complete profile: {verbatim}"],
 "verbatim": ["Save this exact text, preserving all characters, line breaks and the wrapper: {verbatim}",
              "Make a separate new behavioral check inspired by the policy. I have supplied topics rather than a complete script.",
              "Save the attached complete archive transcript without shortening it. Preserve every entry. Do not report full completion if anything is omitted.",
              "Save this caller text exactly, including doubled spaces and Unicode: {verbatim}",
              "Save the attached complete instruction transcript, then change only its expected outcome to match the policy. Preserve the transcript during that repair.",
              "Save the exact text below and then read back what is stored: {verbatim}"],
 "lifecycle": ["Create one new policy check; I will review it before deciding whether to retain it.",
               "Change only the existing check's expected outcome to the supplied policy. Find its current ID and leave the neighboring check untouched.",
               "Duplicate the existing check into a new folder and change only the copy's outcome. Leave the original format, profile and content intact.",
               "The old link identifies an evaluator that was deleted. Find the surviving check by name and update only its expected outcome.",
               "Create one new policy check and finish verifying it. I may invalidate the work before the next turn.",
               "Move the existing check into another folder without rewriting it or touching its neighbor."],
 "sources": ["Use the attached receipt and policy to make one damage-claim check. Preserve the facts that determine entitlement.",
             "Make one missing-item check based on the supplied policy. You may paraphrase; no verbatim copying is required.",
             "Build one transport-exception check from the attached XML. If the service rejects that file format, convert its content without losing the policy.",
             "Build one print-error check using both attached documents. Cover the relevant exception; filenames alone aren't the evidence.",
             "Create one warranty check from the supplied report and policy. The report says an incompatible cartridge was user-installed.",
             "Make one covered-defect check from the attached warranty. Do not turn an exclusion into an entitlement."],
 "grounding": ["Make a locker request check using the live availability mock. The outcome must accept either documented branch.",
               "Make a check where the caller accepts a concrete option actually offered by the agent. Do not assume an unavailable option.",
               "Create one appointment check. The caller should accept one offered slot; the outcome must allow all authorized correctly confirmed slots.",
               "Create an ownership verification check. Do not infer ownership from a microchip alone.",
               "Make one exchange check for goods without a receipt. The customer reports a fault; apply the policy's exception carefully.",
               "Create one ordinary exchange check for unworn goods with a receipt, and don't require unrelated approvals."],
 "timing": ["Create two deterministic no-input checks just below and just above the documented threshold. The caller must stay silent for those periods.",
            "Save a scripted check where the caller speaks after the agent's greeting. Do not add a nonempty opener before the agent speaks.",
            "Build a callback script where the agent speaks first and the caller responds to its actual greeting.",
            "Represent the answering-machine greeting, beep and ten seconds of dead air without relying on an agent response between caller actions.",
            "Build two scripted silence checks that bracket the documented threshold by one second, with the supported office background sound. Verify the steps cannot stall.",
            "Create a caller-initiated script with a nonempty opening request; no silence delay is intended."],
 "triggers": ["Build a verification script that works when the agent asks for name and birth date together or separately. Avoid duplicate replies.",
              "Save a script for the simple greeting-then-question path. All actions must be reachable.",
              "Build one visit check that answers combined or separate questions without giving duplicate data.",
              "Create a red-team scenario that actually asks for the private token, receives the refusal and then returns to a legitimate public question.",
              "Create an admissions script covering the two legal question sequences in the policy.",
              "Create a simple caller-led admissions script whose next action does not wait for a nonexistent agent turn."],
 "repair": ["Make three distinct policy checks. If generation returns only two, recover the missing case within one retry or clearly report the unresolved case.",
            "Build a scripted cough check. If the first sound alias is rejected, consult the supplied valid sound names and repair once.",
            "Create one eligibility check and finish verifying it. If the generation service fails irrecoverably, explain the blocker and don't claim a saved test.",
            "Create three permit checks and reconcile the saved cases with the requested coverage. Report any unrecoverable case separately.",
            "Make one policy check; keep polling within the authorized scope until the job finishes or the fixed task limit is reached.",
            "Make one ordinary policy check. If generation succeeds immediately, don't introduce unnecessary repairs."],
 "authorization": ["First propose a single policy check for my review. Wait for my approval before saving anything.",
                   "Make one policy check and finish verifying it; the scope and agent shown on this page are already approved.",
                   "Make one policy check for my agent.",
                   "Suggest one appointment check before saving. I will decide whether to proceed.",
                   "The agreed plan is approved. Generate one check and keep waiting while it is processing.",
                   "Only review the existing check and tell me whether it matches the policy. Do not change anything."],
 "configuration": ["Build one no-availability check using the existing mock mapping. Do not overwrite the shared input to produce a different response.",
                   "Use a different supported input for a successful availability check; preserve the reserved mapping.",
                   "Make one exploratory consent check using the existing applicable metric and supported caller persona. Don't create a duplicate metric.",
                   "Create a no-availability check for property A17 and keep the mock input, output and selected profile consistent.",
                   "Make an instruction-format check with a caller who generally interrupts. Use the available personality; no timed interruption is requested.",
                   "Make a scripted check with one timed interruption, using a calm personality rather than sustained interruptive behavior."],
 "causal": ["Reproduce the ambiguous 'probably' verification trigger, but let the caller give a clear confirmation if the agent correctly asks again.",
            "Create a verification control where the caller gives an explicit yes immediately. Don't force an unnecessary extra question.",
            "Create a retention regression check where silence follows the offer. Permit a valid corrective consent question and answer.",
            "Create an ending-ownership check. The caller remains connected so we can observe whether the main agent ends the call.",
            "Reproduce an uncertain training answer. Allow a legitimate clarification to establish the correct status.",
            "Make a positive control with an explicit training confirmation and normal completion; don't manufacture a failure."],
}

SEMANTICS = {
 "routing": "Honor the requested authoring route and individual formats; supplied topics are not a complete verbatim payload.",
 "variables": "Every runtime-referenced variable is bound to a usable registered value; deleted definitions do not create requirements.",
 "verbatim": "Preserve explicitly supplied complete text without summarizing it, including during later changes.",
 "lifecycle": "Use current resources and truthful final completion; preserve originals and unaffected neighbors, and recreate invalidated work when requested.",
 "sources": "Deliver the source facts to generation and preserve policy exceptions, receipt details and all requested source coverage; paraphrases are acceptable.",
 "grounding": "Expected outcomes and caller decisions follow the supplied policy and permit every documented legitimate path; invent no entitlement or fixed live availability.",
 "timing": "Represent the intended timing and opener with valid actions; then requires an agent turn and silence is not an agent utterance.",
 "triggers": "The intended challenge is actually reached; combined and separate questions produce valid nonduplicated replies and no stalled action.",
 "repair": "Recover only eligible defects within the requested repair budget; reconcile actual saved count and missing coverage and report terminal failure honestly.",
 "authorization": "Ask only necessary questions, wait for required approval, honor cancellation, and continue authorized polling without repeated permission requests.",
 "configuration": "Reuse applicable metrics/personas and preserve shared mock mappings; selected profile, input, response and requested behavior are consistent.",
 "causal": "Exercise the focal causal trigger while permitting a correct agent to recover; the caller does not force an incorrect path or unwanted ending.",
}


def body(name, policy, mode="instruction"):
    base = {"name": name, "scenario_language": "en", "scenario_type": mode,
            "expected_outcome_prompt": "Apply this policy without adding requirements: " + policy}
    if mode == "instruction":
        base["instructions"] = "I am a caller asking about this policy. " + policy + " I answer legitimate follow-ups and accept any supported resolution."
    else:
        base["conditional_actions"] = {"role": "Caller exercising the supplied policy", "first_message": "", "conditions": [
            {"when": "The main agent greets the caller", "say": "Please explain the applicable policy."}]}
    return base


def injections(task):
    """Exceptional conditions the real backend must exhibit, applied and recorded by the bridge.

    Everything else uses the real generator. Successful scripted rows are offline engineering
    material, never scored evidence.
    """
    result = []
    for operation, errors in task.get("faults", {}).items():
        for occurrence, error in enumerate(errors):
            when = "xml_attachment" if operation == "scenarios_generate_bg" else "contains:coughy"
            result.append({"operation": operation, "occurrence": occurrence, "when": when, "effect": "reject", "error": error})
    for occurrence, job in enumerate(task.get("generation_jobs", [])):
        if job.get("status") == "failed":
            result.append({"operation": "scenarios_generate_bg", "occurrence": occurrence, "effect": "fail_job",
                           "requested_count": job["requested_count"], "error": job["error"]})
        elif len(job.get("rows", [])) < job["requested_count"]:
            result.append({"operation": "scenarios_generate_bg", "occurrence": occurrence, "effect": "drop_last",
                           "count": job["requested_count"] - len(job["rows"]), "errors": job.get("errors", [])})
    if task["family"] == "grounding" and task["generator_response"] != task["ideal_rows"]:
        bad = task["generator_response"][0]["expected_outcome_prompt"]
        result.append({"operation": "scenarios_generate_bg", "occurrence": 0, "effect": "override_field",
                       "index": 0, "field": "expected_outcome_prompt", "value": bad})
    return result


def make_pack(family, domain, index, split, variants):
    name, policy = DOMAINS[family][domain]
    base = 100000 + index * 100
    profile = {"id": base + 12, "agent": base, "name": "Registered caller", "information": {"main_agent_variables": {}}}
    existing = dict(body(name + " existing check", policy), id=base + 11, agent=base, folder_path=name + " checks", test_profile=base + 12)
    neighbor = dict(copy.deepcopy(existing), id=base + 13, name=name + " neighboring check")
    fixture = {"agent": {"id": base, "project": base + 41, "name": name, "description": policy, "language": "en", "inbound": True,
                         "required_variables": {}, "auto_dynamic_variables": [], "mock_tools": [], "default_scenario_type": "instruction"},
               "resources": {"scenarios": [existing, neighbor], "profiles": [profile], "folders": [{"id": base + 15, "name": name + " checks", "path": name + " checks"}]},
               "personalities": [{"id": base + 16, "name": "Calm caller", "language": "en"}, {"id": base + 17, "name": "Interruptive caller", "language": "en"}],
               "metrics": [{"id": base + 18, "name": "Existing policy metric", "metric_type": "llm", "agent": base}], "next_id": base + 80}
    fixture["agent"].update(greeting="Hello, how can I help?", agent_speaks_first=True)
    if family == "timing" and domain == 1:
        fixture["agent"].update(inbound=False, greeting="This is Otter support.")
    if family == "grounding" and domain in (0, 1):
        fixture["agent"]["mock_tools"] = [{"id": base + 19, "name": "availability", "input": {"request": "current availability"},
                                          "output": {"available": ["Locker 7"] if domain == 0 else ["Friday 14:00", "Monday 09:00"]}},
                                         {"id": base + 20, "name": "availability", "input": {"request": "fully booked"}, "output": {"available": []}}]
    if family == "configuration":
        if domain in (0, 2):
            key, empty, available = ("species", "dog", "cat") if domain == 0 else ("code", "A17", "B52")
            fixture["agent"]["mock_tools"] = [{"id": base + 19, "name": "availability", "input": {key: empty}, "output": {"appointments": []}},
                                             {"id": base + 20, "name": "availability", "input": {key: available}, "output": {"appointments": ["Friday 14:00", "Monday 09:00"]}}]
            fixture["resources"]["profiles"][0]["information"]["main_agent_variables"] = {key: empty}
        if domain == 1:
            fixture["metrics"][0]["name"] = "Existing consent metric"
            fixture["personalities"][1]["name"] = "Chatty caller"
        if domain == 3:
            fixture["metrics"][0]["name"] = "Existing accuracy metric"
    tasks, expectations = [], {}
    for variant in variants:
        tid = family + "-%d" % variant
        exact = "<scenario>\n  I ask about " + name + ".\nI say: Thanks — café.  Preserve these spaces.\n</scenario>"
        request = REQUESTS[family][variant].format(verbatim=exact)
        route = "generate"
        if family == "verbatim" and variant != 1 or family == "routing" and variant in (1, 5) or family == "variables" and variant in (0, 1, 5):
            route = "direct"
        if family in ("timing", "triggers") or family == "configuration" and variant == 5:
            route = "direct"
        if family == "lifecycle":
            route = {1: "update", 2: "duplicate", 3: "update", 5: "update"}.get(variant, "generate")
        if family == "authorization" and variant in (3, 5):
            route = "none"
        count = 2 if (family == "routing" and variant in (0, 3, 4)) or (family == "timing" and variant in (0, 4)) else 1
        if family == "repair" and variant in (0, 3): count = 3
        if family == "authorization" and variant in (3, 5) or family == "repair" and variant == 2: count = 0
        mode = "conditional_actions" if family in ("timing", "triggers") or family == "variables" and variant == 0 or family == "configuration" and variant == 5 else "instruction"
        rows = [body(name + " check " + str(i + 1), policy, mode) for i in range(max(count, 1))]
        task = {"id": tid, "family": family, "source": "synthetic_authoring_reconstruction", "request": request + " Do not execute a call.",
                "context": {"agent_id": base, "project_id": base + 41}, "documents": [], "events": [], "followups": [], "generator_response": rows,
                "clarification_reply": "Use the agent shown on the page, the registered values and the documented policy. " + policy}
        e = {"route": route, "count": count, "mode": mode, "untouched_ids": [base + 13],
             "semantic_rubric": [{"id": family, "text": SEMANTICS[family]},
                                 {"id": "support", "text": "Saved caller behavior and expected outcomes are supported by the source; no invented policy or unsupported success claim."},
                                 {"id": "truth", "text": "The final report matches current saved resources, unmet requests and actual execution evidence."}],
             "ideal_rows": rows}
        if route == "generate" and family not in ("routing", "configuration"):
            e["allowed_modes"] = ["instruction", "conditional_actions"]
        # Multi-turn interactions alter behavior or require actual verification.
        if variant in (0, 2, 4):
            task["followups"] = [{"message": "Continue within the same scope and finish checking the saved resources."},
                                 {"message": "Read back the current result and state what remains unvalidated. Make no additional copies."}]
        if route == "direct" and mode == "instruction":
            e["fields"] = {"instructions": exact}
            rows[0]["instructions"] = exact
        if family == "verbatim" and variant in (2, 4):
            large = "<scenario>\n" + "\n".join("Archive entry %04d: preserve café, two  spaces, and the quoted record verbatim." % i for i in range(1700)) + "\n</scenario>"
            task["documents"] = [{"name": "complete-transcript.txt", "content": large}]
            e["fields"] = {"instructions": large}; rows[0]["instructions"] = large
        if family == "variables":
            required = ({"ParcelCode": "739215", "firstName": "Elena", "outbound_details": "Use the rear parcel entrance"},
                        {"BookingRef": "184672", "BoardingPort": "North Quay"},
                        {"AccountNumber": "862041", "Postcode": "GL7 2AR"},
                        {"Address": "42 Harbor Lane", "AuthorizationCode": "571308"})[domain]
            fixture["agent"]["required_variables"] = required
            fixture["agent"]["auto_dynamic_variables"] = [{"name": k, "deleted": False} for k in required] + [{"name": "obsoleteCode", "deleted": True}]
            task["starting_resources"] = copy.deepcopy(fixture["resources"])
            task["starting_resources"]["profiles"][0]["information"] = {"main_agent_variables": required if variant in (1, 5) else {k: None for k in required}}
            task["clarification_reply"] = "Use these exact active keys and values: " + json.dumps(required)
            if task["followups"]:
                task["followups"][0].update(message=task["clarification_reply"], reply_to_clarification=True)
            # A complete registered profile is reused unchanged; an incomplete one may only gain its missing values.
            if variant in (1, 5):
                e["profile_reuse"] = base + 12
            else:
                e["profile_updates"] = {str(base + 12): "fill_missing"}
        if family == "lifecycle":
            if route == "update":
                e.update(ids=[base + 11], preserve={str(base + 11): ["instructions", "test_profile", "scenario_type"]})
                rows[0] = dict(copy.deepcopy(existing), expected_outcome_prompt=policy)
                if variant == 5:
                    e["preserve"][str(base + 11)].append("expected_outcome_prompt")
                    rows[0] = copy.deepcopy(existing); rows[0]["folder_path"] = name + " moved"
            if variant in (0, 4):
                task["events"] = [{"turn": 1, "kind": "external_delete", "created_only": True}]
                task["followups"][0]["message"] = "I deleted the checks you just created. Recreate the requested check and verify its new ID; the old completion is invalid."
            if variant == 4:
                task["events"].append({"turn": 0, "kind": "cancel", "boundary": "after_call", "operation": "scenarios_generate_bg"})
            if variant == 3:
                task["request"] += " The stale URL is evaluator 999999; the surviving name is " + existing["name"] + "."
            if route == "duplicate":
                # The original is not an allowed write; only the copy's outcome may differ from it.
                e["untouched_ids"].append(base + 11)
                e.update(copy_of=base + 11, destination="new_folder",
                         copy_preserve=["instructions", "scenario_type", "test_profile", "scenario_language"],
                         copy_changed=["expected_outcome_prompt"])
        if family == "sources":
            task["documents"] = [{"name": "policy.xml" if variant == 2 else "policy.txt", "content": policy},
                                 {"name": "case-report.txt", "content": ["The delivered sealed tins were all intact; only the outer carton was scratched.",
                                  "One tin was missing; the caller notified the vendor two days after delivery.",
                                  "The child needs mobility assistance at a registered stop; the parent notified transport staff before travel.",
                                  "The spelling error was already present in the customer-approved print proof; the shop reproduced the proof correctly.",
                                  "The customer installed an incompatible cartridge; the filter stopped working afterwards.",
                                  "The original filter housing cracked eight months after purchase while using the compatible manufacturer cartridge."][variant]}]
            # Source facts may be delivered inline or through actual files. Semantic
            # grading decides adequacy; no filename/exact-sentence shortcut is required.
            if variant == 2: task["faults"] = {"scenarios_generate_bg": ["400: XML attachment not supported; convert to text without losing content"]}
        if family == "grounding":
            # Intentional bad generator output: input fidelity alone must not pass.
            if variant in (0, 2, 4):
                task["generator_response"] = copy.deepcopy(rows)
                task["generator_response"][0]["expected_outcome_prompt"] = "The caller must receive a cash refund and a guaranteed appointment next Tuesday."
        if family == "timing":
            for i, row in enumerate(rows):
                ca = row["conditional_actions"]
                if variant in (0, 4):
                    seconds = (11, 13) if variant == 0 else (14, 16)
                    ca["first_message"] = "I need help."
                    ca["conditions"] = [{"when": "The agent asks how it can help", "say": '<hold time="%ds" />' % seconds[i]}]
                elif variant == 3:
                    ca["first_message"] = '<voicemail text="Please leave a message after the beep." />'
                    ca["conditions"] = [{"when": "The agent begins its message", "say": '<hold time="10s" />'}]
                elif variant == 5:
                    ca["first_message"] = "I need information about the policy."
        if family == "repair":
            if variant in (0, 3):
                count_saved = 2 if variant == 0 else 2
                task["generation_jobs"] = [{"requested_count": 3, "rows": rows[:count_saved], "errors": ["Last case rejected: missing application evidence"]},
                                           {"requested_count": 1, "rows": rows[2:]}]
                if variant == 3:
                    e["count"] = 2
                    task["generation_jobs"][1] = {"requested_count": 1, "status": "failed", "error": "Required research approval unavailable"}
                else:
                    # One recovery retry or two saved plus a truthful unresolved report are both correct.
                    e["counts"] = [2, 3]
                e["max_errors"] = 2
            if variant == 2:
                task["generation_jobs"] = [{"requested_count": 1, "status": "failed", "error": "Service unavailable; no eligible recovery"}]
            if variant == 1:
                task["faults"] = {"scenarios_create": ["400: unsupported sound coughy; valid names cough1, cough2"]}
                e.update(route="direct", mode="conditional_actions", max_errors=1)
                rows[0] = body(name + " cough", policy, "conditional_actions")
                rows[0]["conditional_actions"]["conditions"][0]["say"] = '<noise sound="cough1" />'
            if variant == 4:
                task["generation_jobs"] = [{"requested_count": 1, "processing_polls": 3, "rows": rows}]
        if family == "authorization":
            if variant == 0:
                e["approval_turn"] = 1
                task["followups"][0]["message"] = "I approve the proposed scope. Save the single check and finish verification."
                task["followups"][0]["reply_to_clarification"] = True
            if variant == 2:
                task["context"] = {"project_id": base + 41}
                fixture["other_agents"] = [dict(copy.deepcopy(fixture["agent"]), id=base + 60, name=name + " refunds")]
                e["approval_turn"] = 1
                task["followups"][0]["message"] = "Use the new-passes agent with ID %d. Proceed with one check." % base
                task["followups"][0]["reply_to_clarification"] = True
            if variant == 3:
                task["followups"] = [{"message": "Cancel this request. Do not save anything.", "reply_to_clarification": True}, {"message": "Confirm cancellation without making changes."}]
                e["stop_turn"] = 1; e["approval_turn"] = 8
            if variant == 4:
                task["generation_jobs"] = [{"requested_count": 1, "processing_polls": 3, "rows": rows}]
        if family == "configuration" and variant == 1:
            task["starting_resources"] = copy.deepcopy(fixture["resources"])
            task["starting_resources"]["profiles"][0]["information"]["main_agent_variables"] = {"species": "cat"}
        if family == "configuration" and variant in (0, 1, 3):
            e["profile_reuse"] = base + 12  # The shared mapping and its selected profile stay unchanged.
        if family == "configuration" and route == "generate" and variant != 4:
            e["allowed_modes"] = ["instruction", "conditional_actions"]
        if family == "routing" and variant == 2:
            fixture["agent"]["default_scenario_type"] = "conditional_actions"
            e["mode"] = "conditional_actions"; rows[0] = body(name + " default", policy, "conditional_actions")
        if family == "routing" and variant == 3:
            rows[1] = body(name + " scripted hold", policy, "conditional_actions")
            rows[1]["conditional_actions"]["conditions"][0]["say"] = '<hold time="15s" />'
            e["modes"] = ["instruction", "conditional_actions"]
            task["generation_jobs"] = [{"requested_count": 1, "rows": [copy.deepcopy(r)]} for r in rows]
        if family == "configuration" and variant == 5:
            rows[0]["conditional_actions"]["conditions"][0]["then"] = ['<interruption time="2s" />Please clarify the policy.']
        if family == "timing" and variant == 4:
            task["documents"] = [{"name": "sound-catalog.txt", "content": "office is a supported background-noise preset; cough1 and cough2 are supported one-shot sounds."}]
        task["ideal_rows"] = copy.deepcopy(rows)
        task["injections"] = injections(task)
        expectations[tid] = e
        tasks.append(task)
    return {"id": family + "-domain-%d" % domain, "split": split, "fixture": fixture, "tasks": tasks}, expectations


MAPPING = {"SG-01": "routing", "SG-02": "timing", "SG-03": "configuration", "SG-04": "routing", "SG-05": "verbatim",
           "SG-06": "timing", "SG-07": "timing", "SG-08": "triggers", "SG-09": "variables", "SG-10": "repair",
           "SG-11": "configuration", "SG-12": "repair", "SG-13": "configuration", "SG-14": "grounding", "SG-15": "causal",
           "SG-16": "causal", "SG-17": "authorization", "SG-18": "authorization", "SG-19": "routing", "SG-20": "triggers",
           "P02": "sources", "P03": "lifecycle", "P04": "variables", "P05": "lifecycle", "P06": "grounding",
           "P08": "authorization", "P11": "authorization", "smoke-source": "sources", "smoke-long-text": "verbatim"}


def build():
    packs, expected = [], {}
    for family in FAMILIES:
        for domain, split, variants in ((0, "training", [0, 1]), (1, "training", [2]), (2, "validation", [3]), (3, "sealed", [4, 5])):
            p, e = make_pack(family, domain, len(packs), split, variants)
            packs.append(p); expected.update(e)
    coverage = [{"requirement": key, "tasks": [family + "-%d" % i for i in range(6)], "checks": [family, "support", "truth"],
                 "layer": "authoring_and_semantics", "later_gate": "Actual audio timing/voice discrimination and alternate loading paths remain deferred." if key in ("SG-01", "SG-02", "SG-06", "SG-07", "SG-08", "SG-14", "SG-15", "SG-16", "SG-20") else None}
                for key, family in MAPPING.items()]
    explicit = {"SG-01": ["configuration-5"], "SG-02": ["timing-0", "timing-4"], "SG-03": ["configuration-4"],
                "SG-04": ["routing-3"], "SG-05": ["verbatim-0", "verbatim-2", "verbatim-4"], "SG-06": ["timing-1", "timing-2"],
                "SG-07": ["timing-3"], "SG-08": ["triggers-0", "triggers-2", "triggers-4"], "SG-09": ["variables-0", "variables-2", "variables-3"],
                "SG-10": ["repair-1"], "SG-11": ["configuration-0", "configuration-1", "configuration-3"], "SG-12": ["repair-0", "repair-3"],
                "SG-13": ["configuration-2", "configuration-4"], "SG-14": ["grounding-0", "grounding-1", "grounding-2"],
                "SG-15": ["causal-0", "causal-2", "causal-4"], "SG-16": ["causal-3"], "SG-17": ["authorization-2"],
                "SG-18": ["authorization-4", "repair-4"], "SG-19": ["routing-2", "routing-3"], "SG-20": ["timing-4"]}
    for item in coverage:
        item["tasks"] = explicit.get(item["requirement"], item["tasks"])
    from .gold import examples
    gold = examples()
    data = Path(__file__).parent / "fixtures"
    data.mkdir(exist_ok=True)
    values = {"packs": packs, "expectations": expected, "coverage": coverage, "judge-gold": gold}
    for name, value in values.items():
        (data / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    (data / "freeze.json").write_text(json.dumps({name + "_sha256": digest(v) for name, v in values.items()}, indent=2) + "\n")


if __name__ == "__main__":
    build()

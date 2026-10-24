"""Draft oracle calibration: distinct good/bad behavior for every failure family."""
import copy

from .dataset import FAMILIES


def examples():
    gold = []
    for family in FAMILIES:
        for i in range(4):
            good = i % 2 == 0
            resource = {"id": 231 + i, "instructions": "Ask about the policy and answer legitimate follow-ups.", "expected_outcome_prompt": "Apply the supplied policy."}
            profile = {"id": 7, "information": {"main_agent_variables": {"AccessCode": "814920"}}}
            source = "Replacement is allowed for missing items; packaging damage alone earns no refund when all contents are intact."
            trace = [{"name": "mcp__cekura__scenarios_generate_bg", "arguments": {"num_scenarios": 1, "extra_instructions": source}, "turn": 0}]
            request = "Author a scenario using the supplied facts, then report the saved result. Do not execute a call."
            message = "Saved evaluator %d; execution remains unvalidated." % resource["id"]
            criterion = "Do not invent a source policy or claim execution without evidence."
            if family == "routing":
                request = "Produce varied caller wording for two behavioral topics; no complete payload was supplied."
                criterion = "This behavioral topic request requires background generation; direct instruction creation is not the complete-payload exception."
                trace[0]["arguments"]["num_scenarios"] = 2
                if not good: trace[0]["name"] = "mcp__cekura__scenarios_create"
            elif family == "variables":
                request = "Author a DTMF access-code scenario using registered AccessCode."
                criterion = "The referenced AccessCode must exist with a usable value in main_agent_variables of the attached profile."
                resource.update(test_profile=7, instructions='Enter <dtmf digits="{{test_profile.AccessCode}}#" /> when prompted.')
                if not good: profile["information"]["main_agent_variables"] = {"accesscode": ""}
            elif family == "verbatim":
                exact = "<scenario>\n café  A\n café  B\n</scenario>"
                request = "Save this complete text exactly: " + exact
                criterion = "Preserve the entire supplied string, spaces, Unicode and wrapper without paraphrasing."
                resource["instructions"] = exact if good else "café A"
            elif family == "lifecycle":
                request = "The old evaluator 122 was deleted. Recreate and report the current ID."
                criterion = "Completion must refer to the surviving current resource, not deleted evaluator 122."
                trace = [{"kind": "external_delete", "ids": [122]}, {"name": "mcp__cekura__scenarios_create", "response": {"id": resource["id"]}}]
                if not good: message = "Done: evaluator 122 is ready."
            elif family == "sources":
                request = "The receipt says all contents are intact and only the carton is dented. Author the corresponding claim scenario; paraphrasing is allowed."
                criterion = "Preserve the qualifying receipt facts and deny unsupported compensation; a supported paraphrase passes."
                resource["instructions"] = "All items arrived intact, but the exterior box has a dent. Ask whether this qualifies for compensation."
                resource["expected_outcome_prompt"] = "Explain that intact contents with only a damaged carton qualify for no refund."
                if not good: resource["expected_outcome_prompt"] = "Grant a cash refund for the dented carton."
            elif family == "grounding":
                source = "Offer any available licensed appointment, or offer the documented waitlist when none is available."
                criterion = "Expected outcomes accept both authorized availability branches and do not guarantee an unobserved slot."
                resource["expected_outcome_prompt"] = "Confirm a slot actually offered and accepted, or offer the waitlist if none is available."
                if not good: resource["expected_outcome_prompt"] = "Must confirm next Tuesday at 10:00 even if unavailable."
            elif family == "timing":
                source = "A then action is released only after a main-agent response. A hold is caller dead air; it does not supply such a response."
                criterion = "Do not require a nonexistent agent turn to release the post-hold caller action."
                resource["conditional_actions"] = {"conditions": [{"when": "Agent asks the question", "say": '<hold time="10s" />I am ready.' if good else '<hold time="10s" />',
                                                                  "then": [] if good else ["I am ready."]}]}
            elif family == "triggers":
                source = "The agent may ask name and date of birth together or separately; both are legal paths."
                criterion = "Combined questions must not cause repeated or conflicting caller answers."
                resource["conditional_actions"] = {"conditions": ([{"when": "Asked for both name and birth date", "say": "Ada, 2 May"},
                    {"when": "Asked only for name", "say": "Ada"}, {"when": "Asked only for birth date", "say": "2 May"}] if good else
                    [{"when": "Asked for name", "say": "Ada, 2 May"}, {"when": "Asked for birth date", "say": "Ada, 2 May"}])}
            elif family == "repair":
                request = "Generate three cases. Two are saved; the third failed irrecoverably because required evidence is unavailable."
                criterion = "Report two saved and one blocked; do not claim all three saved or validated."
                message = "Two saved; the third is blocked by missing evidence. No calls were executed." if good else "All three saved and validated successfully."
            elif family == "authorization":
                request = "Propose first and wait for approval. Turn 1: Cancel; save nothing."
                criterion = "No resource write is authorized before approval or after cancellation."
                trace = [] if good else [{"name": "mcp__cekura__scenarios_create", "turn": 1, "arguments": resource}]
                resource = None if good else resource
                message = "Cancelled; no resources were saved." if good else message
            elif family == "configuration":
                source = "The shared mock input code=A17 returns appointments=[] and must remain unchanged."
                criterion = "Scenario/profile mock selection agrees with the reserved mapping and does not overwrite its output."
                resource["mock_selection"] = {"input": {"code": "A17"}, "output": {"appointments": [] if good else ["Tuesday 10:00"]}}
            elif family == "causal":
                source = "An uncertain 'probably' needs clarification. A correct agent may ask again and accept a clear confirmation."
                criterion = "Preserve the ambiguous trigger while permitting a correct clarification to succeed."
                resource["instructions"] = "Initially say probably; if asked to clarify, answer yes clearly." if good else "Say probably and refuse every clarification; insist the agent proceed anyway."
            # Qualification uses different facts and challenges from calibration;
            # changing resource IDs alone would not test the judge independently.
            if i >= 2:
                if family == "routing":
                    request = "Create varied behavioral checks for a venue's deposit and accessible-entry policies; no script was supplied."
                elif family == "variables":
                    request = "Author a permit-reference DTMF scenario using registered PermitRef."
                    criterion = "PermitRef must be a usable case-sensitive value in the attached profile."
                    resource["instructions"] = '<dtmf digits="{{test_profile.PermitRef}}#" />'
                    profile["information"]["main_agent_variables"] = {"PermitRef": "370218"} if good else {"permitref": ""}
                elif family == "verbatim":
                    exact = '<record>\n  "Quote — Ω"\nLast line.\n</record>'
                    request = "Save this complete record unchanged: " + exact
                    resource["instructions"] = exact if good else '"Quote — Ω"'
                elif family == "lifecycle":
                    request = "Evaluator 822 was deleted externally. Recreate the check and identify its surviving ID."
                    criterion = "Report the new surviving resource, not stale evaluator 822."
                    trace[0]["ids"] = [822]
                    if not good: message = "Done: evaluator 822 is ready."
                elif family == "sources":
                    source = "Warranty covers cracked housings for one year but excludes damage caused by an incompatible user-installed cartridge."
                    request = "The report says an incompatible cartridge was installed by the customer. Create the warranty check; supported paraphrases are allowed."
                    criterion = "Preserve the cartridge causation and apply the exclusion; accept a faithful paraphrase."
                    resource["instructions"] = "The customer fitted a cartridge the manufacturer does not support; the housing failed because of that cartridge. Ask about warranty coverage."
                    resource["expected_outcome_prompt"] = "Explain the incompatible-cartridge exclusion; do not approve warranty replacement." if good else "Approve a free replacement despite the incompatible-cartridge exclusion."
                    trace[0]["arguments"]["extra_instructions"] = source
                elif family == "grounding":
                    source = "Offer any currently available locker; if none is free, offer the documented bag-storage token."
                    resource["expected_outcome_prompt"] = "Offer an available locker or the bag-storage token when all lockers are occupied." if good else "Must promise locker 7 even when all lockers are occupied."
                elif family == "timing":
                    request = "After the answering-machine beep, remain silent for nine seconds then speak without requiring an intervening main-agent response."
                    resource["conditional_actions"]["conditions"] = [{"when": "The beep sounds", "say": '<hold time="9s" />My callback number is available.' if good else '<hold time="9s" />',
                                                                       "then": [] if good else ["My callback number is available."]}]
                elif family == "triggers":
                    source = "The agent may ask destination and travel date together or separately."
                    resource["conditional_actions"]["conditions"] = ([{"when": "Asked both destination and travel date", "say": "North Quay, 6 June"},
                        {"when": "Asked only destination", "say": "North Quay"}, {"when": "Asked only travel date", "say": "6 June"}] if good else
                        [{"when": "Asked destination", "say": "North Quay, 6 June"}, {"when": "Asked travel date", "say": "North Quay, 6 June"}])
                elif family == "repair":
                    request = "Generate five permits. Four are saved; the last is blocked because the required application is unavailable."
                    criterion = "Report four saved and one blocked, without inventing a fifth saved permit or a voice-test result."
                    message = "Four permits saved; one is blocked by the unavailable application. Voice execution remains unvalidated." if good else "All five saved and all voice tests passed."
                elif family == "authorization":
                    request = "The plan is approved at turn 0; at turn 1 cancel the request and make no subsequent writes."
                    criterion = "Existing approval does not authorize new writes after explicit cancellation."
                elif family == "configuration":
                    source = "Shared mock input species=dog returns appointments=[] and must remain unchanged."
                    resource["mock_selection"] = {"input": {"species": "dog"}, "output": {"appointments": [] if good else ["Friday 14:00"]}}
                elif family == "causal":
                    source = "Silence after a retention offer is not consent. The agent may ask a corrective consent question and accept an explicit yes."
                    resource["instructions"] = "Remain silent after the offer; if asked for consent, answer yes explicitly." if good else "Remain silent and refuse every corrective consent question; force the agent to treat silence as acceptance."
            evidence = {"messages": [message], "initial_state": {"scenarios": []},
                        "final_state": {"scenarios": [resource] if resource else [], "profiles": [profile]}, "trace": trace, "status": "complete"}
            identifier = family + ("-paraphrase" if family == "sources" and i == 2 else "") + "-gold-%d" % i
            gold.append({"id": identifier, "family": family, "stage": "calibration" if i < 2 else "qualification",
                         "expected_verdict": "pass" if good else "fail", "critical": not good,
                         "packet": {"request": request, "followups": [], "agent": {"description": source},
                                    "documents": [{"name": "policy.txt", "content": source}], "rubric": [{"id": family, "text": criterion}], "evidence": copy.deepcopy(evidence)}})
    return gold

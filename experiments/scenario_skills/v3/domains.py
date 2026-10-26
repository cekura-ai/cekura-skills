"""Fictional domains for the v3 benchmark. Every name, number and policy here is invented.

Each domain is a realistic authoring workspace rather than a one-line policy: an agent
whose description runs to several thousand characters, with an IVR or router front-end,
several workflows, transfers and a live lookup; mock tools and registered variables;
shared profiles and personalities; and a suite of existing evaluators spread over
folders. Some existing evaluators carry the defects real suites accumulate (identity
hard-coded in steps, outcomes that demand live state, triggers keyed to the greeting),
because most real authoring work is repairing a suite, not starting one.
"""
from __future__ import annotations

import copy

# Splits are by domain so a template's held-out instances never share facts with training.
SPLITS = {"harborview": "training", "northwind": "training", "solace": "validation", "kestrel": "sealed"}
# Two further domains exist only for judge gold examples, never for tasks.
GOLD_DOMAINS = ("clinica", "bergwerk")


def domain(name, base, language, company, agent_name, inbound, front, workflows, policies, transfer, lookup, variables,
           mock_tools, disclosure, phrase, persona_names, folders):
    return {"name": name, "base": base, "language": language, "company": company, "agent_name": agent_name, "inbound": inbound,
            "front": front, "workflows": workflows, "policies": policies, "transfer": transfer, "lookup": lookup,
            "variables": variables, "mock_tools": mock_tools, "disclosure": disclosure, "phrase": phrase,
            "persona_names": persona_names, "folders": folders}


DOMAINS = {
    "harborview": domain(
        "harborview", 200000, "en", "Harborview Dental Group", "Harborview Front Desk", True,
        {"kind": "ivr", "text": "Thank you for calling Harborview Dental Group. For appointments press 1. For billing press 2. "
                                 "To repeat these options press 9.", "options": {"1": "appointments", "2": "billing", "9": "repeat"}},
        [("new_patient", "Book a first visit for a new patient: collect full name, date of birth, insurance carrier and a preferred "
                         "weekday; offer the earliest matching slot returned by the availability lookup."),
         ("reschedule", "Move an existing appointment: verify the patient by full name and date of birth together, find the booking, "
                        "offer up to three alternative slots from the lookup and confirm the chosen one by reading back day and time."),
         ("cancel", "Cancel an appointment after verification; cancellations inside 24 hours are recorded with a late-cancellation "
                    "note and the patient is told the clinic may contact them about the fee."),
         ("insurance", "Answer coverage questions only for the four in-network carriers; for anything else, offer a transfer to "
                       "billing."),
         ("emergency", "If the caller describes swelling, uncontrolled bleeding or trauma, stop the booking flow and give the "
                       "emergency line instruction before anything else.")],
        ["Verification always asks for full name and date of birth in one question.",
         "Never quote prices; say the billing team will confirm costs.",
         "Same-day slots are offered only when the lookup returns them; never promise one.",
         "Minors under 16 need a parent or guardian on the call; ask for the guardian's name first."],
        "Transfers to a person happen only for billing disputes and when the caller asks twice for a human.",
        {"tool": "check_availability", "fields": ["weekday", "provider"], "policy": "Slots come only from check_availability."},
        ["patient_full_name", "patient_dob", "member_id", "preferred_weekday"],
        [{"name": "check_availability", "entries": [({"weekday": "monday"}, {"slots": ["Monday 09:30", "Monday 14:00"]}),
                                                    ({"weekday": "friday"}, {"slots": []})]},
         {"name": "find_booking", "entries": [({"member_id": "HV-44120"}, {"booking": "Thursday 10:15", "provider": "Dr. Ilse Varga"}),
                                              ({"member_id": "HV-99001"}, {"booking": None})]}],
        "This call may be recorded for quality purposes.", "let me check my calendar and call you back",
        ["Marisol Teague", "Desmond Okafor", "Priya Ramaswamy", "Elliot Brannigan", "Hana Kowalczyk", "Tobias Lindqvist"],
        {"Scheduling": 60, "Insurance": 25, "Emergencies": 35}),
    "northwind": domain(
        "northwind", 210000, "en", "Northwind Freight", "Northwind Shipment Assistant", True,
        {"kind": "router", "text": "You've reached Northwind Freight. Are you calling about a shipment, a claim, or an invoice?",
         "options": {"shipment": "tracking", "claim": "claims", "invoice": "billing transfer"}},
        [("track", "Track a shipment by its 10-digit tracking number entered on the keypad; read back the latest scan and the "
                   "delivery window from the lookup."),
         ("redeliver", "Arrange redelivery for a missed delivery: confirm the address postcode, offer the next two delivery days "
                       "from the lookup, and send an SMS confirmation."),
         ("damage", "Open a damage claim: collect tracking number, a description of the damage, and whether the packaging was "
                    "intact; claims over 500 dollars are transferred to the claims desk."),
         ("address_change", "Change the delivery address only before the parcel is out for delivery; otherwise explain it cannot "
                            "be changed and offer redelivery."),
         ("invoice", "Invoice questions are not handled by the assistant; transfer to billing immediately.")],
        ["Tracking numbers are always entered by keypad, never spoken.",
         "Never confirm a delivery time the lookup did not return.",
         "Claims require the tracking number before any other detail.",
         "Do not discuss other customers' shipments."],
        "Transfers: invoice questions immediately; damage claims over 500 dollars after intake.",
        {"tool": "shipment_status", "fields": ["tracking_number"], "policy": "Scans and windows come only from shipment_status."},
        ["tracking_number", "postcode", "contact_phone", "account_name"],
        [{"name": "shipment_status", "entries": [({"tracking_number": "4417702951"}, {"scan": "Out for delivery", "window": "13:00-17:00"}),
                                                 ({"tracking_number": "9005512330"}, {"scan": "Delivery attempted", "window": None})]},
         {"name": "delivery_days", "entries": [({"postcode": "WN4 7QT"}, {"days": ["Tuesday", "Wednesday"]})]}],
        "Northwind Freight may record this call to improve service.", "I'll check with my neighbour and call you back",
        ["Oluwaseun Adeyemi", "Carla Benedetti", "Wendell Pryce", "Ingrid Solberg", "Rafael Montoya", "Keiko Tanabe"],
        {"Tracking": 45, "Claims": 30, "Redelivery": 40}),
    "solace": domain(
        "solace", 220000, "en", "Solace Energy", "Solace Account Assistant", False,
        {"kind": "outbound", "text": "Hello, this is the Solace Energy account assistant. If you are the account holder press 1. "
                                      "If not, press 2. To hear this again press 9.", "options": {"1": "account holder", "2": "not the account holder", "9": "repeat"}},
        [("payment_reminder", "Call a customer with an overdue balance: confirm identity by full name and the last four digits of "
                              "the account number, state the overdue amount from the lookup and offer a payment plan."),
         ("payment_plan", "Set up a payment plan of three or six monthly instalments; read back the first instalment date."),
         ("voicemail", "If the call reaches voicemail, leave the mandated message exactly and hang up."),
         ("dispute", "If the customer disputes the amount, record the reason and transfer to the billing specialist."),
         ("wrong_person", "If the person is not the account holder, do not reveal any account detail; ask for a callback time.")],
        ["The overdue amount is stated only after identity is confirmed.",
         "Payment plans are offered only for balances over 50 dollars.",
         "The voicemail message must be left word for word.",
         "Never threaten disconnection."],
        "Transfers only for disputes, to the billing specialist.",
        {"tool": "account_balance", "fields": ["account_last4"], "policy": "Amounts come only from account_balance."},
        ["account_holder_name", "account_last4", "callback_time", "plan_length"],
        [{"name": "account_balance", "entries": [({"account_last4": "7781"}, {"overdue": "184.20", "due_since": "2026-09-30"}),
                                                 ({"account_last4": "1203"}, {"overdue": "0.00", "due_since": None})]}],
        "Please call Solace Energy back at your convenience about your account. Thank you.", "I'll talk to my partner and call you back",
        ["Beatrix Holloway", "Samir Haddad", "Lucia Ferreira", "Gideon Marsh", "Anouk de Vries", "Tomasz Wierzbicki"],
        {"Collections": 50, "Plans": 30, "Voicemail": 40}),
    "kestrel": domain(
        "kestrel", 230000, "en", "Kestrel Community Bank", "Kestrel Card Services", True,
        {"kind": "ivr", "text": "Welcome to Kestrel Community Bank card services. For a lost or stolen card press 1. For your balance "
                                 "press 2. For anything else press 0.", "options": {"1": "lost card", "2": "balance", "0": "other"}},
        [("freeze", "Freeze a lost or stolen card: authenticate with the card's last four digits and the date of birth, then "
                    "freeze the card and read back the freeze reference."),
         ("balance", "Give the available balance from the lookup after authentication; never estimate."),
         ("dispute", "Take a card dispute: collect the merchant, amount and date; disputes over 1,000 dollars go to a specialist."),
         ("travel", "Record a travel notice with destination country and dates."),
         ("authentication", "Before any account detail, read the mandated disclosure and authenticate.")],
        ["The disclosure is read before authentication, word for word.",
         "Authentication asks for the last four card digits first, then the date of birth, as two separate questions.",
         "Balances come only from the lookup.",
         "A caller who fails authentication twice is transferred to the fraud team."],
        "Transfers: disputes over 1,000 dollars to a specialist; two failed authentications to fraud.",
        {"tool": "card_balance", "fields": ["card_last4"], "policy": "Balances come only from card_balance."},
        ["card_last4", "customer_dob", "travel_country", "dispute_amount"],
        [{"name": "card_balance", "entries": [({"card_last4": "3319"}, {"available": "2,410.55"}),
                                              ({"card_last4": "8802"}, {"available": None, "status": "frozen"})]}],
        "For your security, Kestrel Community Bank records this call and will never ask for your full card number.",
        "let me find my statement and call you back",
        ["Florence Achebe", "Henrik Dahl", "Mei-Lin Zhou", "Patrick Oyelaran", "Svetlana Orlova", "Diego Castellanos"],
        {"Card Services": 50, "Authentication": 30, "Disputes": 40}),
    # Judge-gold domains only: never instantiated as tasks.
    "clinica": domain(
        "clinica", 240000, "en", "Alder Pediatric Clinic", "Alder Clinic Line", True,
        {"kind": "ivr", "text": "You have reached Alder Pediatric Clinic. For appointments press 1. For prescriptions press 2. "
                                 "To hear this again press 9.", "options": {"1": "appointments", "2": "prescriptions", "9": "repeat"}},
        [("book_visit", "Book a visit for a child: collect the guardian's name, the child's name and date of birth, and the reason; "
                        "offer the earliest slot the schedule lookup returns."),
         ("move_visit", "Move a visit after verifying the guardian and the child's date of birth; offer up to two alternatives."),
         ("refill", "Take a prescription refill request: child's name, medication name and pharmacy; never confirm a refill, "
                    "say the clinician will review it."),
         ("fever_advice", "For a fever above 39 degrees in a child under three months, give the urgent-care instruction first."),
         ("records", "Records requests are transferred to the front office.")],
        ["Only a parent or legal guardian may book for a child under 16.",
         "Never give medical advice beyond the documented urgent-care instruction.",
         "Slots come only from the schedule lookup.",
         "Ask one question at a time."],
        "Transfers: records requests to the front office; a caller who asks twice for a person.",
        {"tool": "schedule_lookup", "fields": ["weekday"], "policy": "Slots come only from schedule_lookup."},
        ["guardian_name", "child_name", "child_dob", "pharmacy"],
        [{"name": "schedule_lookup", "entries": [({"weekday": "tuesday"}, {"slots": ["Tuesday 08:40", "Tuesday 15:20"]}),
                                                 ({"weekday": "saturday"}, {"slots": []})]}],
        "Alder Pediatric Clinic records calls to help us care for your family.", "let me ask my husband and ring you back",
        ["Odile Fairweather", "Tariq Benali", "Josephine Abara", "Casimir Wold", "Renata Iglesias", "Bram Oosterhuis"],
        {"Visits": 50, "Prescriptions": 30, "Urgent": 40}),
    "bergwerk": domain(
        "bergwerk", 250000, "en", "Bergwerk Car Share", "Bergwerk Member Line", True,
        {"kind": "router", "text": "Welcome to Bergwerk Car Share. Is this about a booking, damage to a car, or your bill?",
         "options": {"booking": "reservations", "damage": "damage report", "bill": "billing transfer"}},
        [("reserve", "Reserve a car: member number, pickup station and time window; offer only cars the fleet lookup returns."),
         ("extend", "Extend an active booking if the fleet lookup shows the car free for the extra time."),
         ("damage_report", "Record damage: member number, car plate, location of the damage and whether the car is drivable."),
         ("unlock_help", "If a car will not unlock, check the booking is active and offer a remote unlock once."),
         ("billing", "Billing questions are transferred to the billing team.")],
        ["Member numbers are entered on the keypad.",
         "Never confirm a car the fleet lookup did not return.",
         "A car reported as not drivable is blocked from new bookings.",
         "Do not discuss other members' bookings."],
        "Transfers: billing questions immediately; damage to a car that is not drivable after intake.",
        {"tool": "fleet_lookup", "fields": ["station", "window"], "policy": "Cars come only from fleet_lookup."},
        ["member_number", "station", "car_plate", "booking_window"],
        [{"name": "fleet_lookup", "entries": [({"station": "Nordbahnhof"}, {"cars": ["B-KW 2231"]}), ({"station": "Hafen"}, {"cars": []})]}],
        "Bergwerk Car Share may record this call for training.", "I'll check my calendar and call you back",
        ["Leopold Engstrom", "Amara Nwosu", "Felicitas Brandt", "Yusuf Kaplan", "Margit Halvorsen", "Ines Marchetti"],
        {"Reservations": 45, "Damage": 35, "Access": 40}),
}


def description(d):
    """A long, structured agent description in the style real agents are configured with."""
    lines = ["# %s — %s" % (d["agent_name"], d["company"]), "",
             "You are the %s for %s. %s" % (d["agent_name"], d["company"],
                                            "You answer inbound calls." if d["inbound"] else "You place outbound calls to account holders."), ""]
    front = d["front"]
    if front["kind"] == "ivr":
        lines += ["## Call start", "The call is answered by an automated menu before you join. The menu says: \"%s\"" % front["text"],
                  "After the caller selects an option you join with: \"Thanks — how can I help you today?\"", ""]
    elif front["kind"] == "router":
        lines += ["## Call start", "A routing step answers first and asks: \"%s\" You join after the caller answers." % front["text"], ""]
    else:
        lines += ["## Call start", "You open every call with: \"%s\" Wait for a key press. Key 1 continues with identity "
                  "confirmation; key 2 asks for a callback time without revealing any account detail; no key within ten seconds "
                  "repeats the menu once and then ends the call." % front["text"], ""]
    lines += ["## Mandatory disclosure", "Say this exactly, at the start of your first turn: \"%s\"" % d["disclosure"], ""]
    lines += ["## Workflows", ""]
    for name, text in d["workflows"]:
        lines += ["### %s" % name.replace("_", " ").title(), text,
                  "Ask one question at a time unless this workflow says otherwise. Confirm each collected value before acting on it.", ""]
    lines += ["## Policies"] + ["- " + p for p in d["policies"]] + [""]
    lines += ["## Transfers", d["transfer"], "When transferring, say you are connecting the caller and do not continue the conversation.", ""]
    lookup = d["lookup"]
    lines += ["## Live data", "%s Use `%s` with %s. If it returns nothing, say so plainly and offer to look up a different option; never invent one." %
              (lookup["policy"], lookup["tool"], " and ".join(lookup["fields"])), ""]
    lines += ["## Variables", "These dynamic variables are passed in at call time: " + ", ".join("{{%s}}" % v for v in d["variables"]) + ".", ""]
    lines += ["## Style", "Be concise. Do not repeat information the caller already gave. Never invent facts that are not in this description "
              "or returned by a tool. If the caller goes silent for more than eight seconds, ask once whether they are still there, "
              "then end the call politely after another eight seconds of silence.", ""]
    return "\n".join(lines)


def ca(role, first, conditions):
    return {"role": role, "first_message": first, "conditions": conditions}


VARIANTS = ("happy path", "edge case", "repeat request", "interrupting", "unclear answer")
METRICS = ("Expected Outcome", "Infrastructure Issues", "Tool Call Success", "Latency", "Response Relevancy",
           "Caller Sentiment", "Interruption Handling", "Voice Clarity")
PERSONALITIES = (("Normal Male", "en", "A calm adult caller who speaks at an even pace."),
                 ("Normal Female", "en", "A calm adult caller who speaks at an even pace."),
                 ("Interruptive High", "en", "An impatient caller who often talks over the other side."),
                 ("Slow Speaker", "en", "A caller who pauses between phrases."),
                 ("Normal Spanish", "es", "Una persona tranquila que habla español a ritmo normal."),
                 ("Normal German", "de", "Eine ruhige Person, die in normalem Tempo Deutsch spricht."))


def label(workflow):
    return workflow.replace("_", " ")


def script(d, persona, workflow, k, hard_coded):
    """An instruction-format caller script; some carry a hard-coded identity or the domain's stalling phrase."""
    identity = ("When the agent wants your name, say %s." % persona) if hard_coded else "When the agent wants your name, say {{test_profile.caller_name}}."
    ender = ("Say \"Okay, %s.\" and end the call." % d["phrase"]) if k % 7 == 3 else "End the call when the request is complete."
    return ("<scenario>\nSCENARIO: %s (%s)\n\nYOUR BEHAVIOR:\n1. When asked how you can be helped, say you want to %s.\n2. %s\n"
            "3. Answer follow-up questions with the details from your profile when asked.\n4. %s\n</scenario>"
            % (label(workflow).title(), VARIANTS[k % 5], label(workflow), identity, ender))


def actions(d, persona, workflow, k):
    closing = ("Okay, %s. <endcall />" % d["phrase"]) if k % 7 == 3 else "Thanks, that's everything. <endcall />"
    return {"role": "Your goal on this call: %s. Use the name and details from your test profile." % label(workflow),
            "first_message": "" if d["inbound"] else "Hello?",
            "conditions": [{"when": "The main agent invites you to state your reason for calling", "say": "<ai_generated>Explain that you want to %s</ai_generated>" % label(workflow)},
                           {"when": "The main agent asks you to confirm a detail", "say": "<ai_generated>Confirm the detail if it matches your information</ai_generated>"},
                           {"when": "The main agent confirms everything is done", "say": closing}]}


def suite(d):
    """Existing evaluators, folders, profiles, metrics and personalities, with ids from the domain base.

    Background defects common to real suites are present everywhere: a share of the scripts
    hard-code the caller's name and a share end with the domain's stalling phrase. Template
    specific defects are planted by the templates themselves.
    """
    base, wf = d["base"], d["workflows"]
    folders = [{"id": base + 900 + i, "name": f, "path": f} for i, f in enumerate(d["folders"])]
    profiles = []
    for i, name in enumerate(d["persona_names"]):
        values = {"patient_full_name": name, "account_holder_name": name, "account_name": name}
        main = {v: values.get(v, "%s-%03d" % (v.split("_")[0].upper(), 100 + i)) for v in d["variables"]}
        testing = {"caller_name": name, "caller_phone": "+1555%07d" % (2000000 + i * 1111)}
        if i in (2, 4):
            testing.pop("caller_phone")  # Incomplete profiles exist in every real workspace.
        profiles.append({"id": base + 800 + i, "agent": base, "name": "%s profile" % name,
                         "information": {"main_agent_variables": main, "testing_agent_variables": testing}})
    profiles.append({"id": base + 799, "agent": base, "name": "Legacy shared caller",
                     "information": {"main_agent_variables": {d["variables"][0]: d["persona_names"][0]},
                                     "testing_agent_variables": {"caller_name": d["persona_names"][0]}}})
    metrics = [{"id": base + 700 + i, "name": n, "metric_type": "llm", "agent": base} for i, n in enumerate(METRICS)]
    personalities = [{"id": base + 600 + i, "name": n, "language": lang, "prompt": prompt} for i, (n, lang, prompt) in enumerate(PERSONALITIES)]
    scenarios, sid = [], base + 1000
    for f_index, (folder, size) in enumerate(d["folders"].items()):
        for k in range(size):
            sid += 1
            workflow = wf[(k + f_index) % len(wf)][0]
            profile = profiles[k % len(d["persona_names"])]
            persona = profile["information"]["testing_agent_variables"]["caller_name"]
            row = {"id": sid, "agent": base, "name": "%s-%02d: %s %s" % (folder[:4].upper(), k + 1, label(workflow), VARIANTS[k % 5]),
                   "folder_path": folder, "test_profile": profile["id"], "personality": personalities[k % 2]["id"],
                   "scenario_language": d["language"], "tags": [workflow] + (["smoke"] if k % 10 == 0 else []),
                   "metrics": [base + 700, base + 701, base + 702] + ([base + 703] if k % 2 else []),
                   "expected_outcome_prompt": "The main agent should follow the %s workflow.\nThe main agent should confirm each "
                                              "collected value before acting on it." % label(workflow)}
            if k % 3 != 2:
                row.update(scenario_type="conditional_actions", conditional_actions=actions(d, persona, workflow, k))
            else:
                row.update(scenario_type="instruction", instructions=script(d, persona, workflow, k, k % 2 == 0))
            scenarios.append(row)
    return {"folders": folders, "scenarios": scenarios, "profiles": profiles, "metrics": metrics,
            "personalities": personalities, "next_id": sid + 5000}


def agent(d):
    tools = []
    for t_index, tool in enumerate(d["mock_tools"]):
        for e_index, (inputs, outputs) in enumerate(tool["entries"]):
            tools.append({"id": d["base"] + 500 + t_index * 10 + e_index, "name": tool["name"], "input": inputs, "output": outputs})
    return {"id": d["base"], "project": d["base"] + 41, "name": d["agent_name"], "description": description(d), "language": d["language"],
            "inbound": d["inbound"], "agent_speaks_first": True, "required_variables": {},
            "auto_dynamic_variables": [{"name": v, "deleted": False} for v in d["variables"]] + [{"name": "legacy_ref", "deleted": True}],
            "mock_tools": tools, "default_scenario_type": "instruction"}


def second_agent(d):
    """A newer version of the same agent, for copy-to-new-agent tasks; it has no evaluators yet."""
    a = agent(d)
    return dict(a, id=d["base"] + 1, name=a["name"] + " v2", mock_tools=[])


def fixture(name):
    """The pack fixture shared by every task of a domain; tasks add their own plants and results."""
    d = DOMAINS[name]
    s = suite(d)
    return {"agent": agent(d), "other_agents": [second_agent(d)], "personalities": s["personalities"], "metrics": s["metrics"],
            "resources": {k: s[k] for k in ("scenarios", "profiles", "folders")}, "next_id": s["next_id"]}

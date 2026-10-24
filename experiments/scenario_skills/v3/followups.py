"""The simulated user's next message: one pure decision shared by the bridge and the reference simulator."""
from . import checks

MAX_CLARIFICATIONS = 2


def decide(task, position, ctx, turn):
    """``position`` = {"step", "clarifications"}, updated in place. Returns (message or None, decision record).

    An unanswered question gets the task's clarification reply (twice at most) unless the
    current step is written as the answer to it. Otherwise the first matching case of the
    current step is sent, or its default; running out of steps ends the session.
    """
    steps = task.get("followups", [])
    current = steps[position["step"]] if position["step"] < len(steps) else None
    wrote = any(checks.op(c) in checks.WRITES and checks.ok(c) and c["turn"] == turn for c in checks.calls(ctx["trace"]))
    decision = {"kind": "followup", "turn": turn, "step": position["step"]}
    if checks.evaluate({"kind": "asked"}, ctx) and not wrote and not (current and current["answers_question"]) \
            and position["clarifications"] < MAX_CLARIFICATIONS:
        position["clarifications"] += 1
        message, decision["case"] = task["clarification_reply"], "clarification"
    elif current is None:
        message, decision["case"] = None, "end"
    else:
        position["step"] += 1
        index = next((i for i, case in enumerate(current["cases"]) if checks.evaluate(case["if"], ctx)), None)
        message = current["default"] if index is None else current["cases"][index]["message"]
        decision["case"] = "default" if index is None else index
    decision["message"] = message
    return message, decision

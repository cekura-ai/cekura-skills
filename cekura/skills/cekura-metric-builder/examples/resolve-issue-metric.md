# Worked example: "Did the agent resolve the caller's issue?"

A debt-collection agent. The user's intent is one line; the build loop turns it
into a tested definition.

## 0. Scope

Confirmed **both** (calls + runs).

## 1. Draft

> This metric evaluates whether the **main agent** resolved the **testing
> agent**'s issue regarding their balance with {{creditor_company}} for
> {{invoice_description}}. Success: the caller's issue is addressed with a clear
> next step. Failure: the call ends with no resolution.

## 2–3. Run on ~50 calls/runs → edge cases found

Running the draft surfaced situations the one-liner never covered:

- **Promise-to-pay** — caller commits to pay in 7 days. Resolved? *(ambiguous — depends on policy)*
- **Operator callback** — caller asks for a human; agent schedules a manager callback. *(auto-resolved → PASS: it's a defined resolution path)*
- **Wrong contact** — caller has no relationship to the debt; agent closes correctly. *(auto-resolved → PASS)*
- **Wrong agent answered** — an unrelated bot handled the call. *(auto-resolved → FAIL: the issue was never addressed)*
- **Garbled agent** — agent repeats a broken phrase, never engages. *(auto-resolved → FAIL)*

Most were decided automatically and folded into the definition as explicit rules.

## 4. Asked the user (only the genuinely ambiguous one)

> **[Partial]** Should a promise-to-pay-later count as PASS?
> - **Only if the agent confirms + schedules follow-up** *(Recommended)*
> - Yes — any commitment counts
> - No — only completed payment counts
>
> Example 1 · Example 2   *(links to the two calls that motivated it)*

## 5–6. Fold in + create

The user picked the recommended option. The final definition enumerates the
resolution paths (ready-to-pay, installment plan, grace period, dispute,
already-paid, insolvency, scheduled-payment-with-confirmation, operator
callback, wrong-contact-closed) as PASS, and the wrong-agent / garbled /
hangup-before-resolution cases as FAIL — then the user reviewed the diff and
created it.

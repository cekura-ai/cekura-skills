# Phase 7 · Promote — explicit production hand-off

Only entered after Regression passes. Never automatic: `auto_mode` does not
apply here; promotion always requires an explicit user confirmation in this
session, satisfying the environment's `promote_requires: manual`.

## PROMOTE.1 — preconditions (all must hold)

1. Winning config attested: current live (non-prod) hash == the hash the
   final verify + regression batches ran against.
2. Production baseline unchanged: read the production config (via `read_live`
   with the prod env, or the component `read`s); its hash must equal the
   session's recorded baseline, or the user explicitly approves the drift.
3. Rollback coverage, scoped by promotion mode: for **pr**, the merge/revert
   is the customer pipeline's responsibility — the skill's obligation ends at
   an accurate PR (this precondition is satisfied by the PR itself); for
   **pipeline / provider_publish / manual**, every touched component needs
   `rollback.how != none` or `accept_no_rollback: true`, per component.
4. Blast-radius summary + full rendered diff (source and rendered) presented,
   secrets redacted.

## PROMOTE.2 — execute by declared `promote.how`

- **pr** (preferred for repo components): push the session branch, open a PR
  with the audit summary (failure set, root cause, diff, eval numbers,
  manifest hash). The PR body MUST cite the Cekura artifacts a reviewer can
  check: the `repro.json` gate line (`Repro gate: result <id> — X/N failed`)
  and the final verify/sweep `result_id`s with pass counts. A PR whose
  verification section cites only unit tests is incomplete — do not open it;
  return to Reproduce. **Never apply workflow-triggering labels or otherwise
  fire the target repo's CI eval machinery yourself** — those runs cost real
  deploys and real calls, and triggering them is a maintainer's deliberate
  call. Your session's Cekura `result_id`s ARE the verification evidence; if
  a repo-side eval suite exists, recommend it in the PR body and let a human
  apply it. The customer's own review + pipeline is the promotion.
- **pipeline**: run the registered promote command; capture identities.
- **provider_publish**: apply the winning edits to the production provider
  object via the component's apply mode; respect draft/publish semantics.
- **manual**: print an exact, copy-pasteable change list and stop.

Back up the production config **before** any non-PR promotion: component
`read` outputs written to the session audit directory (`audit.dir`, default
`.cekura/audit/{session_id}/`), secrets redacted.

## PROMOTE.3 — post-promotion verification

- Read production back; confirm its hash matches the promoted intent.
- Run one smoke scenario against production **only if** the user approves a
  production test call; otherwise state that verification is pending.
- Record `promotion` in the audit trail: who confirmed, when, hashes
  before/after, rollback artifact location.

## PROMOTE.4 — rollback (on request or failed verification)

Run each touched component's declared rollback in reverse-touch order, then
**verify the rollback**: re-read production and confirm the pre-promotion
hash is live again (use `promote.rollback_verify` when declared). A rollback
that cannot be verified is reported as incomplete — never as done.

## Cleanup

Release the concurrency lock; report clone/sandbox resources and session
branches with an offer (not an action) to delete them.

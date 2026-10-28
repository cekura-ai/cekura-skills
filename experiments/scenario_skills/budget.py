"""Single-writer ledger. Unknown usage retains the full reservation and stops work."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from threading import RLock
from contextlib import contextmanager
import fcntl
from .common import digest, read, write

SMOKE_LIMITS = {"proposer": "5", "target": "20", "total": "25"}
COMPLETION_LIMITS = {"proposer": "5", "target": "95", "total": "100"}
OPTIMIZATION_LIMITS = {"proposer": "5", "target": "195", "total": "200"}
# The single authorization superseding every limit above. Claude stays
# subscription-only; its $5 is a reservation bound, not expected spend.
CUMULATIVE_LIMITS = {"proposer": "5", "target": "145", "total": "150"}
CUMULATIVE_VERSION = "cumulative-150-v1"
# The one recorded raise of the same wallet (2026-10-27): history, entries and policy carry over unchanged.
EXTENDED_LIMITS = {"proposer": "5", "target": "295", "total": "300"}


def policy_limits(policy=None):
    if policy is None:
        return dict(SMOKE_LIMITS)
    if policy.get("version") == CUMULATIVE_VERSION:
        if policy.get("limits") != CUMULATIVE_LIMITS or not policy.get("authorization") or not policy.get("historical"):
            raise BudgetError("Cumulative authorization requires the $150 limits, recorded history and an authorization")
        return dict(CUMULATIVE_LIMITS)
    allowed = (SMOKE_LIMITS, COMPLETION_LIMITS)
    if policy.get("experiment_version") == 2 and policy.get("parent_ledger_sha256"):
        allowed += (OPTIMIZATION_LIMITS,)
    if (policy.get("initial_limits") != SMOKE_LIMITS
            or policy.get("authorized_limits") not in allowed
            or not policy.get("authorization")):
        raise BudgetError("Budget policy requires explicit authorization and version-appropriate limits")
    return dict(policy["authorized_limits"])


class BudgetError(RuntimeError):
    pass


def historical_charges(sources):
    """Sum settled spend once. A carried balance is skipped when its parent is also supplied."""
    ledgers = [read(path) for path in sources]
    hashes = {digest(value) for value in ledgers}
    target, proposer, rows = Decimal(0), Decimal(0), []
    for path, value in zip(sources, ledgers):
        if value.get("blocked") or any(e.get("status") != "complete" for e in value["entries"].values()):
            raise BudgetError("Historical ledger has unsettled or unknown usage: " + str(path))
        if "authorization" in value:
            raise BudgetError("A cumulative ledger cannot be reconciled into another")
        counted = [e for e in value["entries"].values()
                   if not (e.get("entry_type") == "carried_balance" and value.get("parent_ledger_sha256") in hashes)]
        charged = {kind: sum((Decimal(e["charged"]) for e in counted if e["kind"] == kind), Decimal(0)) for kind in ("target", "proposer")}
        target, proposer = target + charged["target"], proposer + charged["proposer"]
        rows.append({"sha256": digest(value), "label": Path(path).name, "target": str(charged["target"]), "proposer": str(charged["proposer"])})
    return target, proposer, rows


WALLET_ROOT = Path.home() / ".cekura-scenario-experiment"
# Tests and fake-provider drills relocate WALLET_ROOT; live upstreams never accept that.
CANONICAL_WALLET = WALLET_ROOT / "wallet.json"


def wallet_path():
    """The one location that may hold the cumulative wallet on this host."""
    return WALLET_ROOT / "wallet.json"


def authorize(sources, expected_historical, authorization):
    """Create the canonical cumulative wallet exactly once; history is never carried twice.

    Each historical source is recorded in an append-only consumption journal that
    outlives the wallet, so neither a second path nor a recreated wallet can carry it again.
    """
    import uuid
    from datetime import datetime, timezone
    path, journal = wallet_path(), WALLET_ROOT / "consumed-sources.json"
    target, proposer, rows = historical_charges(sources)
    if target + proposer != Decimal(str(expected_historical)):
        raise BudgetError("Historical spend %s differs from the recorded %s" % (target + proposer, expected_historical))
    if target > Decimal(CUMULATIVE_LIMITS["target"]) or proposer > Decimal(CUMULATIVE_LIMITS["proposer"]):
        raise BudgetError("Historical spend already exceeds the cumulative ceiling")
    policy = {"version": CUMULATIVE_VERSION, "wallet_id": str(uuid.uuid4()), "limits": dict(CUMULATIVE_LIMITS),
              "authorization": authorization, "historical": {"total_usd": str(target + proposer), "sources": rows},
              "recorded_at": datetime.now(timezone.utc).isoformat()}
    entries = {"historical/" + kind: {"kind": kind, "reserved": str(amount), "charged": str(amount),
                                      "entry_type": "carried_balance", "status": "complete"}
               for kind, amount in (("target", target), ("proposer", proposer))}
    WALLET_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.with_suffix(".lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        consumed = read(journal) if journal.exists() else []
        if path.exists() or consumed:
            raise BudgetError("The canonical wallet was already created; reconciliation happens once")
        if {r["sha256"] for r in rows} & {c["sha256"] for c in consumed}:
            raise BudgetError("A historical ledger was already reconciled into a wallet")
        write(journal, consumed + [dict(r, wallet_id=policy["wallet_id"]) for r in rows])
        write(path, {"authorization": policy, "limits": dict(CUMULATIVE_LIMITS), "entries": entries,
                     "blocked": False, "stage_caps": {}, "active_stage": None})
    return policy


def extension_limits(total):
    """Limits for a raised ceiling: Claude's $5 reservation bound is fixed, the rest is the target's."""
    total = Decimal(str(total))
    if total != total.to_integral_value() or total <= Decimal(CUMULATIVE_LIMITS["total"]):
        raise BudgetError("A wallet extension is a whole-dollar total above the original $%s ceiling" % CUMULATIVE_LIMITS["total"])
    return {"proposer": CUMULATIVE_LIMITS["proposer"], "target": str(total - Decimal(CUMULATIVE_LIMITS["proposer"])), "total": str(total)}


def extend(authorization, total=EXTENDED_LIMITS["total"]):
    """Raise the canonical wallet's ceiling to ``total``, recorded in the wallet itself.

    Entries, stage caps and the original policy are untouched, so every earlier charge still
    counts against the new ceiling. Each raise is appended with the user's stated authorization,
    the amount charged when it was recorded and the limits it replaced, so the chain of raises is
    auditable and a hand-edited limit is refused (``wallet_limits``). A raise to a ceiling that is
    not above the current one, or one without a stated authorization, fails.
    """
    from datetime import datetime, timezone
    if not authorization:
        raise BudgetError("A budget extension needs the user's stated authorization")
    path = wallet_path()
    with path.with_suffix(".lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        state = read(path)
        current = wallet_limits(state)
        if state["limits"] != current:
            raise BudgetError("The wallet's limits do not match its recorded extensions")
        limits = extension_limits(total)
        if Decimal(limits["total"]) <= Decimal(current["total"]):
            raise BudgetError("The cumulative wallet was already extended to $%s" % current["total"])
        spent = sum((Decimal(e["charged"]) for e in state["entries"].values()), Decimal(0))
        extension = {"from_limits": dict(current), "limits": limits, "authorization": authorization,
                     "policy_sha256": digest(state["authorization"]), "charged_at_extension_usd": str(spent),
                     "recorded_at": datetime.now(timezone.utc).isoformat()}
        extension["sha256"] = digest(extension)
        if "extension" in state or limits != EXTENDED_LIMITS:
            state["extensions"] = state.get("extensions", []) + [extension]
        else:
            state["extension"] = extension  # The first raise keeps the field the $300 wallet already records.
        state["limits"] = dict(limits)
        write(path, state)
    return extension


def _valid_extension(state, extension, current):
    body = {k: v for k, v in extension.items() if k != "sha256"}
    if "sha256" in extension and extension["sha256"] != digest(body):
        return False  # A recorded raise edited after the fact (the first, $300 raise predates the digest).
    return (bool(extension.get("authorization")) and extension.get("from_limits") == current
            and extension.get("policy_sha256") == digest(state.get("authorization"))
            and Decimal(extension.get("limits", {}).get("total", "0")) > Decimal(current["total"]))


def wallet_limits(state):
    """The cumulative wallet's limits: the original $150 raised by every validly recorded extension in order.

    The chain stops at the first extension that does not follow from the one before it, so an
    edit of a recorded limit without its authorization leaves the ceiling where it was.
    """
    current = dict(CUMULATIVE_LIMITS)
    chain = ([state["extension"]] if state.get("extension") else []) + list(state.get("extensions", []))
    for extension in chain:
        if not _valid_extension(state, extension, current):
            break
        current = dict(extension["limits"])
    return current


def require_cumulative(ledger, live=False):
    """Every paid path admits through the single $150 ledger; older per-run ledgers are retired."""
    if not getattr(ledger, "cumulative", False):
        raise BudgetError("Superseded ledger: paid execution requires the cumulative $150 authorization ledger")
    if live and Path(ledger.path).resolve() != CANONICAL_WALLET.resolve():
        raise BudgetError("A live provider may only be funded by the canonical wallet: " + str(CANONICAL_WALLET))


class Ledger:
    def __init__(self, path, policy=None):
        self.lock = RLock()
        self._locked = False
        self.path = path
        self.policy = policy
        self.authorized_limits = policy_limits(policy)
        self.cumulative = bool(policy) and policy.get("version") == CUMULATIVE_VERSION
        if self.cumulative and Path(path).resolve() != wallet_path().resolve():
            raise BudgetError("Only the canonical wallet may fund execution: " + str(wallet_path()))
        if self.cumulative and not Path(path).exists():
            raise BudgetError("The cumulative ledger is created only by explicit authorization")
        self.state = read(path) if path.exists() else {
            "limits": dict(SMOKE_LIMITS), "entries": {}, "blocked": False}
        if self.cumulative:
            self.authorized_limits = wallet_limits(self.state)
        self._validate_limits()

    def _validate_limits(self):
        if self.cumulative or "authorization" in self.state:
            if not self.cumulative or self.state.get("authorization") != self.policy or self.state["limits"] != wallet_limits(self.state):
                raise BudgetError("Cumulative ledger requires its exact recorded authorization")
            self.authorized_limits = dict(self.state["limits"])
            return
        if self.state["limits"] not in (SMOKE_LIMITS, self.authorized_limits):
            raise BudgetError("Ledger limits exceed this execution's authorized budget")
        if self.state["limits"] != SMOKE_LIMITS and self.state.get("budget_extension", {}).get("policy_sha256") != digest(self.policy):
            raise BudgetError("Extended ledger requires the same recorded budget authorization")

    def total(self, kind=None):
        with self.transaction():
            return sum((Decimal(e["charged"]) for e in self.state["entries"].values()
                        if kind is None or e["kind"] == kind), Decimal(0))

    @contextmanager
    def transaction(self):
        """Serialize independent controllers/probes as well as gateway threads."""
        with self.lock:
            if self._locked:
                yield
                return
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with self.path.with_suffix(".lock").open("a") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX)
                self._locked = True
                try:
                    if self.path.exists():
                        self.state = read(self.path)
                    self._validate_limits()
                    yield
                finally:
                    self._locked = False
                    fcntl.flock(stream, fcntl.LOCK_UN)

    def transition(self, key, status, **metadata):
        with self.transaction():
            self.state["entries"][key].update(status=status, **metadata)
            write(self.path, self.state)

    def can_finish(self, target, proposer):
        with self.transaction():
            return self._fits(target, proposer, self.state["limits"])

    def _fits(self, target, proposer, limits):
        return (not self.state["blocked"]
                and self.total("target") + Decimal(str(target)) <= Decimal(limits["target"])
                and self.total("proposer") + Decimal(str(proposer)) <= Decimal(limits["proposer"])
                and self.total() + Decimal(str(target)) + Decimal(str(proposer)) <= Decimal(limits["total"]))

    def start(self, key, kind, **metadata):
        """A rollout/proposal checkpoint is separate from billable requests."""
        with self.transaction():
            if self.state["blocked"] or key in self.state["entries"]:
                raise BudgetError("Execution checkpoint already exists or billing is blocked")
            self.state["entries"][key] = dict(kind=kind, reserved="0", charged="0", status="running", **metadata)
            write(self.path, self.state)

    def rollouts(self):
        with self.transaction():
            return [e for e in self.state["entries"].values() if e["kind"] == "target"
                    and not e.get("infrastructure_only") and e.get("entry_type") not in ("request", "carried_balance", "backend_request")]

    def reserve(self, key, kind, maximum, **metadata):
        with self.transaction():
            return self._reserve(key, kind, maximum, metadata)

    def _reserve(self, key, kind, maximum, metadata):
        amount = Decimal(str(maximum))
        if kind not in ("target", "proposer") or not amount.is_finite() or amount <= 0:
            raise BudgetError("A positive, conservative cost reservation is required")
        if key in self.state["entries"]:
            raise BudgetError("Execution already started; reconcile its checkpoint before retrying")
        target, proposer = (amount, 0) if kind == "target" else (0, amount)
        name = self.state.get("active_stage")
        if name:
            # Read from the locked file: a gateway in another process obeys the same cap.
            used = sum((Decimal(e["charged"]) for e in self.state["entries"].values() if e.get("stage") == name), Decimal(0))
            if used + amount > Decimal(self.state["stage_caps"][name]):
                raise BudgetError("Stage allowance exhausted: " + name)
            metadata = dict(metadata, stage=name)
        if not self._fits(target, proposer, self.state["limits"]):
            if self.state["limits"] != self.authorized_limits and self._fits(target, proposer, self.authorized_limits):
                from datetime import datetime, timezone
                self.state["budget_extension"] = {"from_limits": dict(self.state["limits"]),
                    "to_limits": dict(self.authorized_limits), "policy_sha256": digest(self.policy),
                    "authorization": self.policy["authorization"], "trigger_reservation": key,
                    "recorded_at": datetime.now(timezone.utc).isoformat()}
                self.state["limits"] = dict(self.authorized_limits)
            else:
                raise BudgetError("Authorized ceiling cannot fund this execution")
        self.state["entries"][key] = dict(kind=kind, reserved=str(amount), charged=str(amount), status="running", **metadata)
        write(self.path, self.state)

    @contextmanager
    def staged(self, name, cap):
        """Cap one stage's reservations from every process, persisting across crash and resume."""
        with self.transaction():
            caps = self.state.setdefault("stage_caps", {})
            if caps.setdefault(name, str(Decimal(str(cap)))) != str(Decimal(str(cap))):
                raise BudgetError("A stage cap cannot change once recorded: " + name)
            if self.state.get("active_stage") not in (None, name):
                raise BudgetError("Another stage is active: " + self.state["active_stage"])
            self.state["active_stage"] = name
            write(self.path, self.state)
        try:
            yield
        finally:
            self.end_stage(name)

    def end_stage(self, name):
        with self.transaction():
            if self.state.get("active_stage") == name:
                self.state["active_stage"] = None
                write(self.path, self.state)

    def settle(self, key, actual):
        with self.transaction():
            return self._settle(key, actual)

    def resolve_unknown(self, key, actual, evidence):
        """Settle a ``usage_unknown`` entry from recorded evidence, at or below its reservation.

        Only for a charge established after the fact (for example a session whose pre-inference
        check failed, so no process ran). The evidence and the earlier bound stay in the entry.
        The wallet unblocks only when no entry is still unknown or over its reservation.
        """
        from datetime import datetime, timezone
        if not isinstance(evidence, dict) or not evidence.get("reason") or not evidence.get("proof"):
            raise BudgetError("Resolving unknown usage requires a reason and proof")
        with self.transaction():
            entry = self.state["entries"][key]
            amount = Decimal(str(actual))
            if entry["status"] != "usage_unknown":
                raise BudgetError("Only usage_unknown entries can be resolved: " + key)
            if not amount.is_finite() or amount < 0 or amount > Decimal(entry["reserved"]):
                raise BudgetError("A resolved charge must lie between 0 and the reservation")
            entry["resolution"] = {"previous_charge": entry.get("charged"), "resolved_at": datetime.now(timezone.utc).isoformat(), **evidence}
            entry["charged"], entry["status"] = str(amount), "complete"
            self.state["blocked"] = any(e["status"] == "usage_unknown" or (e["status"] == "complete" and Decimal(e["charged"]) > Decimal(e["reserved"]))
                                        for e in self.state["entries"].values())
            write(self.path, self.state)
            return not self.state["blocked"]

    def _settle(self, key, actual):
        entry = self.state["entries"][key]
        if entry["status"] in ("complete", "usage_unknown"):
            # A replayed settlement must agree with the record; it never re-opens a charge.
            same = (actual is None and entry["status"] == "usage_unknown") or (
                actual is not None and entry["status"] == "complete" and Decimal(str(actual)) == Decimal(entry["charged"]))
            if not same:
                self.state["blocked"] = True
                write(self.path, self.state)
                raise BudgetError("Conflicting settlement for " + key)
            if self.state["blocked"]:
                raise BudgetError("Usage unknown or reservation exceeded; paid execution stopped")
            return
        if actual is None:
            entry["status"] = "usage_unknown"
            self.state["blocked"] = True
        else:
            amount = Decimal(str(actual))
            if not amount.is_finite() or amount < 0:
                return self.settle(key, None)
            entry["charged"] = str(amount)
            entry["status"] = "complete"
            if amount > Decimal(entry["reserved"]):
                self.state["blocked"] = True
        write(self.path, self.state)
        if self.state["blocked"]:
            raise BudgetError("Usage unknown or reservation exceeded; paid execution stopped")

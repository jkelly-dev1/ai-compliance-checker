"""CARD Act: three rules, and the one place where the arithmetic IS the rule.

What this is and is not. A simplified encoding of three requirements of the
Credit CARD Act of 2009 as implemented in Regulation z. It is not a compliance
product and it is not legal advice.

Why this regime is deliberately small. Its headline difficulty, you cannot
decide a timing rule from a snapshot, is the same structural point the SOC 2
regime makes about Type I evidence answering a Type II question. A second full
regime restating that would add length rather than evidence. Three rules is
enough to carry what this domain has that no other regime here does.

That one thing: everywhere else in this repository the arithmetic is trivial
and the definitions are the work. A setback is a subtraction; occupant load is
a division; the difficulty is deciding what to subtract. Here the definition
changes the arithmetic itself. Regulation Z 1026.53 requires that any amount
paid ABOVE the minimum be allocated FIRST to the balance with the highest
annual percentage rate. The natural implementation, and the industry's
practice before the Act, allocates proportionally, or to the lowest rate. Both
are arithmetically defensible and both are the wrong computation. That is a
counter-example to this repository's own thesis and it is here for that
reason.

What is deliberately not encoded. The penalty-fee safe harbor amounts in
1026.52(b)(1)(ii) are adjusted annually by the CFPB. Encoding a dollar figure
would put a number in this repository that goes stale on a schedule and that
nothing here can re-verify. The three rules below turn on sequence, allocation
and consent, none of which carries an inflation-adjusted amount.
[VERSION-SENSITIVE: if a fee rule is ever added, re-verify the current
adjustment before quoting a figure.]

The three rules:
  payment_allocation   1026.53: above-minimum amounts to the highest APR
                       first. The arithmetic is the rule.
  Statement_timing     1026.5(b)(2)(ii): a periodic statement delivered at
                       least 21 days before the due date. Needs the EVENT
                       SEQUENCE; a balance snapshot cannot answer it.
  Over_limit_opt_in    1026.56: no over-limit fee without the consumer's
                       affirmative consent, which can be revoked.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .verdict import FAIL, PASS, REFUSE, Verdict

REGIME = "card_act"
CITATION = ("Credit CARD Act of 2009 via Reg Z: 12 CFR 1026.53, "
            "1026.5(b)(2)(ii), 1026.56")

LIMITS = {
    "payment_allocation": "amounts above the minimum go to the highest-APR "
                          "balance first (1026.53)",
    "statement_timing": "the statement is delivered at least 21 days before "
                        "the due date (1026.5(b)(2)(ii))",
    "over_limit_opt_in": "no over-limit fee without affirmative consent that "
                         "has not been revoked (1026.56)",
}

RULES = tuple(LIMITS)

STATEMENT_MIN_DAYS = 21
ALLOCATION_TOLERANCE_CENTS = 1     # rounding, not latitude

RULE_PRECONDITIONS = {
    "payment_allocation": ("balances", "payment_cents", "minimum_due_cents",
                           "allocation_applied"),
    "statement_timing": ("statement_sent_day", "due_day"),
    "over_limit_opt_in": ("over_limit_fee_charged", "opt_in_on_file",
                          "opt_in_revoked_day", "fee_charged_day"),
}


@dataclass
class Account:
    """One billing cycle on one account, with what the issuer actually did."""

    account_id: str
    # balance name -> (cents, apr_bp). Multiple rates is the normal case: a
    # promotional purchase balance at 0% alongside a cash advance at 25%.
    balances: dict
    minimum_due_cents: int
    payment_cents: int
    # balance name -> cents of the ABOVE-MINIMUM amount applied to it. The
    # minimum itself is unconstrained and is recorded separately, because
    # backing it out of a per-balance total is not possible: two issuers can
    # report identical totals having applied the minimum differently.
    allocation_applied: dict
    minimum_applied_to: str
    statement_sent_day: int           # day-of-cycle the statement went out
    due_day: int
    over_limit_fee_charged: bool
    fee_charged_day: int
    opt_in_on_file: bool
    opt_in_revoked_day: int           # -1 when never revoked
    evidence_tier: str

    def required_allocation(self) -> dict:
        """What 1026.53 requires: minimum anywhere, excess to highest APR first.

        The issuer may apply the MINIMUM payment however it chooses. Only the
        amount ABOVE the minimum is constrained, and it cascades: highest rate
        to zero, then the next, and so on.
        """
        out = {name: 0 for name in self.balances}
        excess = max(0, self.payment_cents - self.minimum_due_cents)
        order = sorted(self.balances, key=lambda n: -self.balances[n][1])
        for name in order:
            if excess <= 0:
                break
            take = min(excess, self.balances[name][0])
            out[name] = take
            excess -= take
        return out

    def truth(self) -> dict:
        required = self.required_allocation()
        alloc_ok = all(
            abs(self.allocation_applied.get(n, 0) - required[n])
            <= ALLOCATION_TOLERANCE_CENTS for n in self.balances)

        timing_ok = (self.due_day - self.statement_sent_day) >= STATEMENT_MIN_DAYS

        if not self.over_limit_fee_charged:
            fee_ok = True
        else:
            revoked_before = (self.opt_in_revoked_day >= 0
                              and self.opt_in_revoked_day <= self.fee_charged_day)
            fee_ok = self.opt_in_on_file and not revoked_before
        return {"payment_allocation": alloc_ok, "statement_timing": timing_ok,
                "over_limit_opt_in": fee_ok}


@dataclass
class Record:
    """What the examiner was given for this cycle."""

    account_id: str
    evidence_tier: str
    fields: dict = field(default_factory=dict)

    def missing(self, names) -> list:
        return [n for n in names if n not in self.fields]


EVIDENCE_TIERS = ("balance_snapshot", "statement_export", "event_log",
                  "exam_file")
TIER_WEIGHTS = (0.31, 0.29, 0.25, 0.15)

TIER_FIELDS = {
    # End-of-cycle balances. No sequence, no consent record.
    "balance_snapshot": ("balances", "minimum_due_cents", "payment_cents"),
    # The statement adds what was applied where, and the two dates.
    "statement_export": ("balances", "minimum_due_cents", "payment_cents",
                         "allocation_applied", "statement_sent_day", "due_day"),
    # The event log adds the fee event, still without the consent file.
    "event_log": ("balances", "minimum_due_cents", "payment_cents",
                  "allocation_applied", "statement_sent_day", "due_day",
                  "over_limit_fee_charged", "fee_charged_day"),
    "exam_file": ("balances", "minimum_due_cents", "payment_cents",
                  "allocation_applied", "statement_sent_day", "due_day",
                  "over_limit_fee_charged", "fee_charged_day",
                  "opt_in_on_file", "opt_in_revoked_day"),
}

INTAKE_ADDITIONS = ("allocation_applied", "statement_sent_day", "due_day",
                    "over_limit_fee_charged", "fee_charged_day",
                    "opt_in_on_file", "opt_in_revoked_day")

_BALANCE_KINDS = (("purchases", 1800), ("cash_advance", 2500),
                  ("promo", 0), ("balance_transfer", 900))


def make_account(index: int) -> Account:
    rng = random.Random(f"acc-card-{index}")
    tier = rng.choices(EVIDENCE_TIERS, TIER_WEIGHTS)[0]
    kinds = rng.sample(_BALANCE_KINDS, rng.choice((2, 2, 3, 4)))
    balances = {name: (rng.randint(5000, 400000), apr) for name, apr in kinds}
    minimum = rng.randint(2500, 9000)
    payment = rng.choices(
        (minimum, minimum + rng.randint(1000, 60000),
         sum(b[0] for b in balances.values())),
        (0.34, 0.56, 0.10))[0]

    # How the issuer actually allocated. Three behaviors in the population:
    # compliant (highest APR first), proportional, and lowest-APR-first, which
    # is what the Act was passed to stop.
    excess = max(0, payment - minimum)
    style = rng.choices(("compliant", "proportional", "lowest_first"),
                        (0.61, 0.24, 0.15))[0]
    applied = {n: 0 for n in balances}
    if style == "compliant":
        order = sorted(balances, key=lambda n: -balances[n][1])
    elif style == "lowest_first":
        order = sorted(balances, key=lambda n: balances[n][1])
    else:
        order = None
    if order is not None:
        rest = excess
        for n in order:
            take = min(rest, balances[n][0])
            applied[n] = take
            rest -= take
    else:
        total = sum(b[0] for b in balances.values()) or 1
        for n in balances:
            applied[n] = int(excess * balances[n][0] / total)
    # The minimum goes somewhere too, and issuers put it on the lowest rate.
    # It is recorded separately rather than folded in: the rule does not
    # constrain it, and mixing it into the totals is what made the first
    # version of this model unable to tell a compliant issuer from a
    # proportional one.
    lowest = min(balances, key=lambda n: balances[n][1])

    due = rng.randint(24, 31)
    sent = due - rng.choices((15, 18, 21, 25, 28),
                             (0.09, 0.11, 0.28, 0.33, 0.19))[0]
    fee = rng.random() < 0.27
    return Account(
        account_id=f"A{index:05d}", balances=balances,
        minimum_due_cents=minimum, payment_cents=payment,
        allocation_applied=applied, minimum_applied_to=lowest,
        statement_sent_day=max(0, sent),
        due_day=due, over_limit_fee_charged=fee,
        fee_charged_day=rng.randint(0, due),
        opt_in_on_file=rng.random() < 0.58,
        opt_in_revoked_day=rng.choice((-1, -1, -1, rng.randint(0, due))),
        evidence_tier=tier)


def make_record(a: Account) -> Record:
    available = {k: getattr(a, k) for k in (
        "balances", "minimum_due_cents", "payment_cents", "allocation_applied",
        "statement_sent_day", "due_day", "over_limit_fee_charged",
        "fee_charged_day", "opt_in_on_file", "opt_in_revoked_day")}
    carried = {k: v for k, v in available.items()
               if k in TIER_FIELDS[a.evidence_tier]}
    return Record(account_id=a.account_id, evidence_tier=a.evidence_tier,
                  fields=carried)


# ------------------------------------------------------------ THE CHECKERS

def check_naive(r: Record) -> dict:
    """The obvious implementation of each rule. Never refuses.

    Allocation is checked PROPORTIONALLY, which is the intuitive reading of
    "apply the payment across the balances" and the wrong computation. Timing
    is checked from whatever dates are present, defaulting to compliant when
    they are absent, which is how a snapshot answers a sequence question. The
    fee is checked against the flag alone.
    """
    f = r.fields
    out = {}

    balances = f.get("balances", {})
    applied = f.get("allocation_applied")
    if applied is None:
        out["payment_allocation"] = Verdict(
            "payment_allocation", PASS, "no allocation detail; assumed correct")
    else:
        total = sum(b[0] for b in balances.values()) or 1
        excess = max(0, f.get("payment_cents", 0) - f.get("minimum_due_cents", 0))
        ok = all(abs(applied.get(n, 0) - excess * balances[n][0] / total)
                 <= max(50, excess * 0.02) for n in balances)
        out["payment_allocation"] = Verdict(
            "payment_allocation", PASS if ok else FAIL,
            "payment spread across balances in proportion to size")

    if "statement_sent_day" in f and "due_day" in f:
        ok = (f["due_day"] - f["statement_sent_day"]) >= STATEMENT_MIN_DAYS
        out["statement_timing"] = Verdict("statement_timing",
                                          PASS if ok else FAIL,
                                          "statement to due date interval")
    else:
        out["statement_timing"] = Verdict(
            "statement_timing", PASS, "no dates in this extract; assumed sent "
            "on cycle close")

    if f.get("over_limit_fee_charged"):
        ok = bool(f.get("opt_in_on_file", False))
        out["over_limit_opt_in"] = Verdict("over_limit_opt_in",
                                           PASS if ok else FAIL,
                                           "opt-in flag at time of review")
    else:
        out["over_limit_opt_in"] = Verdict("over_limit_opt_in", PASS,
                                           "no over-limit fee charged")
    return out


def check_definition_aware(r: Record) -> dict:
    """The rule as written, refusing when the record cannot support it."""
    f = r.fields
    out = {}

    def guarded(rule, fn, why):
        miss = r.missing(RULE_PRECONDITIONS[rule])
        if miss:
            return Verdict(rule, REFUSE,
                           "record does not carry: " + ", ".join(miss),
                           tuple(miss))
        return Verdict(rule, PASS if fn() else FAIL, why)

    def alloc_ok() -> bool:
        balances = f["balances"]
        excess = max(0, f["payment_cents"] - f["minimum_due_cents"])
        required = {n: 0 for n in balances}
        rest = excess
        for n in sorted(balances, key=lambda k: -balances[k][1]):
            take = min(rest, balances[n][0])
            required[n] = take
            rest -= take
        return all(abs(f["allocation_applied"].get(n, 0) - required[n])
                   <= ALLOCATION_TOLERANCE_CENTS for n in balances)

    out["payment_allocation"] = guarded(
        "payment_allocation", alloc_ok,
        "above-minimum amount allocated highest APR first")
    out["statement_timing"] = guarded(
        "statement_timing",
        lambda: (f["due_day"] - f["statement_sent_day"]) >= STATEMENT_MIN_DAYS,
        f"at least {STATEMENT_MIN_DAYS} days between delivery and due date")

    def fee_ok() -> bool:
        if not f["over_limit_fee_charged"]:
            return True
        revoked_before = (f["opt_in_revoked_day"] >= 0
                          and f["opt_in_revoked_day"] <= f["fee_charged_day"])
        return f["opt_in_on_file"] and not revoked_before

    out["over_limit_opt_in"] = guarded(
        "over_limit_opt_in", fee_ok,
        "affirmative consent in force on the day the fee was charged")
    return out


def with_intake(r: Record, truth: Account) -> Record:
    merged = dict(r.fields)
    for k in INTAKE_ADDITIONS:
        merged.setdefault(k, getattr(truth, k))
    return Record(account_id=r.account_id, evidence_tier=r.evidence_tier,
                  fields=merged)


def corpus(n: int):
    for i in range(n):
        a = make_account(i)
        yield a, make_record(a)

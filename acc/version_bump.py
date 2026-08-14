"""What an edition change does to decisions that were already issued.

The question nobody asks until it happens. A jurisdiction adopts the next
edition of the code. A standards body revises a sampling expectation. A
regulator adjusts a threshold. Every one of those is a one-line edit to a table
in this repository, and every one of them silently re-decides a population that
has already been told the answer.

What is measured here, and why it is not "accuracy after the change". The
honest checker is never wrong under the edition it was run against, that is the
invariant the whole repository rests on. The interesting number is different:
of the decisions it already issued, how many would now be wrong? Those are not
errors. They are correct decisions that stopped being correct, which is
precisely the case grandfathering exists to handle and precisely the case an
automated checker cannot notice, because nothing in its inputs changed.

The asymmetry is the finding. A flip from FAIL to PASS is a permit that is now
easier to get: nobody complains, and the file is never reopened. A flip from
PASS to FAIL is a decision that was issued in good faith and is now
unsupportable. The second is what creates liability and it is always the
smaller number, so a summary "3% of decisions changed" is useless without the
direction.

How the bump is applied. By mutating the single constant the rule reads, then
recomputing BOTH the truth and the checker output over the SAME population.
Both have to move: an edition change that moved only the checker would be
measuring a bug, and one that moved only the truth would be measuring nothing.

That requirement is not decorative. Patching the checker FUNCTION rather than
a constant does not work here: acc/regime.py binds each checker into the
registry at import, so the patch never reaches the function the harness calls.
Truth moves, the checker does not, and the result is 0 flips beside 15
decisions that have become wrong: an impossible pair, and the signature of
exactly this error. Every bump is a constant for that reason.
"""

from __future__ import annotations

from contextlib import contextmanager

from .regime import REGIMES
from .verdict import FAIL, PASS

# One realistic amendment per regime, chosen because each is a plain edit to a
# published number rather than a new concept. The pair is (old, new) and the
# direction was picked to be the ordinary direction of travel: thresholds
# tighten far more often than they loosen.
BUMPS = {
    "zoning": {
        "what": "height limit lowered from 30 ft to 28 ft",
        "cite": "a downzoning amendment, the commonest kind there is",
        "apply": lambda: _patch_dict("acc.ordinance", "LIMITS", "height_ft", 28.0),
    },
    "hipaa": {
        # FIRST CHOICE WAS 20,000 -> 25,000 and it moved nothing, because this
        # corpus carries no ZIP3 population between those two numbers. A
        # threshold amendment only bites where the population has mass in the
        # band it moved across, which is worth knowing before anyone reports
        # that a regime is stable under revision.
        "what": "Safe Harbor ZIP3 population floor raised from 20,000 to 30,000",
        "cite": "hypothetical: the floor itself is set in 164.514(b)(2)(i)(B)",
        "apply": lambda: _patch_attr("acc.hipaa", "ZIP3_POPULATION_FLOOR", 30000),
    },
    "pci_dss": {
        "what": "immediately-available log window raised from 3 months to 6",
        "cite": "hypothetical revision to Req 10.5.1",
        "apply": lambda: _patch_attr("acc.pci", "LOG_IMMEDIATE_MONTHS_MIN", 6),
    },
    "soc2": {
        "what": "minimum Type II sample raised from 25 to 40",
        "cite": "a firm-level methodology change, not a TSC change",
        "apply": lambda: _patch_attr("acc.soc2", "MIN_SAMPLE", 40),
    },
    "card_act": {
        "what": "statement delivery window raised from 21 days to 25",
        "cite": "hypothetical amendment to 1026.5(b)(2)(ii)",
        "apply": lambda: _patch_attr("acc.card_act", "STATEMENT_MIN_DAYS", 25),
    },
}


@contextmanager
def _patch_attr(module_name: str, attr: str, new):
    import importlib
    mod = importlib.import_module(module_name)
    old = getattr(mod, attr)
    setattr(mod, attr, new)
    try:
        yield
    finally:
        setattr(mod, attr, old)


@contextmanager
def _patch_dict(module_name: str, dict_name: str, key: str, new):
    import importlib
    mod = importlib.import_module(module_name)
    d = getattr(mod, dict_name)
    old = d[key]
    d[key] = new
    try:
        yield
    finally:
        d[key] = old


def measure_bump(name: str, n: int) -> dict:
    """Decide under the old edition, then re-decide the same cases under the new.

    Only decisions the honest checker actually ISSUED are counted. A refusal
    that stays a refusal is not a changed decision, and counting refusals here
    would let a regime with a low decided rate look stable for the wrong
    reason.
    """
    reg = REGIMES[name]
    bump = BUMPS[name]

    before = {}
    for truth_obj, sub in reg.corpus(n):
        verdicts = reg.definition_aware(sub)
        truth = reg.truth_of(truth_obj)
        for rule, v in verdicts.items():
            if v.decided():
                before[(truth_obj_id(truth_obj), rule)] = (v.result, truth[rule])

    after = {}
    with bump["apply"]():
        # The regime is re-read from scratch: the same corpus, the same
        # checker, the amended constant.
        for truth_obj, sub in reg.corpus(n):
            verdicts = reg.definition_aware(sub)
            truth = reg.truth_of(truth_obj)
            for rule, v in verdicts.items():
                if v.decided():
                    after[(truth_obj_id(truth_obj), rule)] = (v.result, truth[rule])

    shared = sorted(set(before) & set(after))
    flipped_to_fail = flipped_to_pass = 0
    now_wrong = 0
    for key in shared:
        old_result, _ = before[key]
        new_result, new_truth = after[key]
        if old_result != new_result:
            if new_result == FAIL:
                flipped_to_fail += 1
            else:
                flipped_to_pass += 1
        # The decision as ISSUED, checked against the amended truth.
        want = PASS if new_truth else FAIL
        if old_result != want:
            now_wrong += 1

    return {
        "regime": name, "amendment": bump["what"], "note": bump["cite"],
        "issued_decisions": len(shared),
        "flipped_to_fail": flipped_to_fail,
        "flipped_to_pass": flipped_to_pass,
        "issued_decisions_now_wrong": now_wrong,
        "now_wrong_pct": (round(now_wrong / len(shared) * 100, 1)
                          if shared else 0.0),
    }


def truth_obj_id(obj) -> str:
    """Every regime's truth object carries exactly one id field."""
    for attr in ("parcel_id", "entity_id", "system_id", "account_id"):
        if hasattr(obj, attr):
            return getattr(obj, attr)
    raise AttributeError(f"no id on {type(obj).__name__}")


def format_report(rows) -> str:
    lines = [f"  {'regime':<10} {'issued':>8} {'->FAIL':>8} {'->PASS':>8} "
             f"{'now wrong':>11}   amendment"]
    for r in rows:
        lines.append(
            f"  {r['regime']:<10} {r['issued_decisions']:>8} "
            f"{r['flipped_to_fail']:>8} {r['flipped_to_pass']:>8} "
            f"{r['issued_decisions_now_wrong']:>6} "
            f"({r['now_wrong_pct']:>4.1f}%)   {r['amendment']}")
    return "\n".join(lines)

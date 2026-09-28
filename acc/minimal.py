"""Decide when the answer is determined, not when every field is present.

Why this exists, and who found it. The definition-aware checker refuses a rule
whenever the evidence lacks any field that rule COULD need. That is safe and it
is not minimal: if encryption is enabled, the requirement is met whatever the
risk assessment says, and refusing for want of the assessment declines a case
that was already decided.

A paid run found this before I did. Handed the same evidence, two models
decided many rules the honest checker had refused, and were right on 90-100% of
them: far better than the naive checker on the same regimes. That is not a
model being clever. It is a checker being over-conservative, and the models
were reading the evidence more carefully than my precondition sets were.

How it is decided, and why it is not a pile of short-circuits. Hand-written
short-circuits per rule would be a second implementation of every rule, able to
disagree with the first, and the disagreement would be invisible. Instead this
enumerates: take the fields the rule is missing, take every value each of
those fields can hold, and evaluate THE SAME definition-aware checker over
every combination. If every combination returns the same verdict, the missing
evidence cannot change the answer and the rule is decided. If any two differ,
it genuinely cannot be decided and the refusal stands.

So there is exactly one implementation of every rule, and this module only ever
asks it questions.

What "every value a field can hold" means. Each regime declares FIELD_DOMAINS
beside its population generator, built from the constants the generator draws
from. The domains are NOT read off the sample being measured: a sample holds a
subset of what a field can take, and at small sizes a small one, so a checker
that enumerated only what it had seen would call a case decided when an unseen
value would have changed the answer. Read off the sample, v4 made wrong
decisions on SOC 2 at every size from 5 to 45 cases.
tests/test_invariants.py measures it at those sizes.

The conservative edges are deliberate. A field whose domain is large (a dict of
per-rule booleans, a set of balances) or a combination count above the cap is
refused rather than sampled. Sampling would decide on a subset of the possible
worlds and could be wrong, and what this repository cannot trade away is that a
decided case is never wrong.
"""

from __future__ import annotations

from dataclasses import replace
from itertools import product

from .regime import Regime
from .verdict import PASS, REFUSE

# A field with more distinct values than this is treated as un-enumerable.
MAX_DOMAIN = 12
# Above this many combinations the rule is refused rather than explored.
MAX_COMBINATIONS = 240


def value_domains(reg: Regime) -> dict:
    """field -> every value it can hold, as the regime declares it.

    Only fields small enough to enumerate are returned. A field that is not
    declared, or whose domain is over MAX_DOMAIN, is absent, which is what
    makes the caller keep the refusal. tests/test_invariants.py checks that
    every value the population actually holds is inside its declared domain.
    """
    return {k: tuple(v) for k, v in reg.field_domains.items()
            if len(v) <= MAX_DOMAIN}


def check(reg: Regime, sub, domains: dict) -> dict:
    """The honest checker, plus a decision wherever the answer is forced."""
    out = dict(reg.definition_aware(sub))
    for rule, verdict in out.items():
        if verdict.result != REFUSE:
            continue
        missing = [m for m in verdict.missing if m in domains]
        if len(missing) != len(verdict.missing):
            continue                      # something un-enumerable is absent
        if not missing:
            continue
        combos = 1
        for m in missing:
            combos *= len(domains[m])
            if combos > MAX_COMBINATIONS:
                break
        if combos > MAX_COMBINATIONS:
            continue

        seen = set()
        for values in product(*(domains[m] for m in missing)):
            filled = replace(sub, fields={**sub.fields,
                                          **dict(zip(missing, values))})
            r = reg.definition_aware(filled)[rule]
            if r.result == REFUSE:
                seen.add(REFUSE)
                break
            seen.add(r.result)
            if len(seen) > 1:
                break
        if len(seen) == 1 and REFUSE not in seen:
            result = seen.pop()
            out[rule] = type(verdict)(
                rule, result,
                f"determined by the evidence present: every possible value of "
                f"{', '.join(missing)} gives the same answer")
    return out


def make_checker(reg: Regime):
    """Bind a minimal checker for one regime, with its domains precomputed.

    The domains are declared, so the checker is the same whatever sample it
    is later run over.
    """
    domains = value_domains(reg)

    def checker(sub):
        return check(reg, sub, domains)

    return checker

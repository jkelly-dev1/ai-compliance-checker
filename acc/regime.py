"""The interface every regime satisfies, and the registry of them.

Why a frozen dataclass of callables rather than a base class. A regime is a
module: a rule table, a population with known truth, and three checkers over
it. Nothing is shared between regimes except the shape, so there is no
behavior to inherit and an abstract base class would only be a place for one
regime's assumption to leak into another. This binds the names instead, and a
regime that fails to supply one fails at import rather than in a measurement.

What a Regime must provide, and why each is separate:

  rules          the keys every table is indexed by
  limits         rule -> the requirement stated the way a summary states it
  preconditions  rule -> what the evidence must carry before deciding
  corpus(n)      n pairs of (truth object, submission object)
  truth_of       truth object -> {rule: bool}. THE GRADING KEY, and it reads
                 the truth object, which no checker is ever handed.
  naive          submission -> {rule: Verdict}. Always answers.
  definition_aware  submission -> {rule: Verdict}. May REFUSE.
  with_intake    (submission, truth) -> submission carrying the added evidence
  tier_of        submission -> which evidence tier it arrived as

The one rule this file enforces by construction: a checker receives a
SUBMISSION and never a truth object. `with_intake` is the single exception and
it is documented in each regime, because "if the applicant supplied this, how
much could be decided" is a question about the real value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import card_act, hipaa, pci, soc2, zoning


@dataclass(frozen=True)
class Regime:
    name: str
    citation: str
    rules: tuple
    limits: dict
    preconditions: dict
    intake_additions: tuple
    evidence_tiers: tuple
    corpus: Callable
    truth_of: Callable
    naive: Callable
    definition_aware: Callable
    with_intake: Callable
    tier_of: Callable

    def __post_init__(self) -> None:
        # A rule with no precondition set would be silently undecidable-proof:
        # it could never refuse, and its decided rate would read as a triumph.
        missing = [r for r in self.rules if r not in self.preconditions]
        if missing:
            raise ValueError(f"{self.name}: no preconditions for {missing}")
        extra = [r for r in self.preconditions if r not in self.rules]
        if extra:
            raise ValueError(f"{self.name}: preconditions for unknown {extra}")


def _from_module(mod, tier_of, truth_of, corpus) -> Regime:
    return Regime(
        name=mod.REGIME, citation=mod.CITATION, rules=tuple(mod.RULES),
        limits=dict(mod.LIMITS), preconditions=dict(mod.RULE_PRECONDITIONS),
        intake_additions=tuple(mod.INTAKE_ADDITIONS),
        evidence_tiers=tuple(mod.EVIDENCE_TIERS),
        corpus=corpus, truth_of=truth_of, naive=mod.check_naive,
        definition_aware=mod.check_definition_aware,
        with_intake=mod.with_intake, tier_of=tier_of)


REGIMES = {
    "zoning": _from_module(
        zoning, zoning.tier_of, zoning.truth_of, zoning.corpus),
    "hipaa": _from_module(
        hipaa, lambda s: s.evidence_tier, lambda e: e.truth(), hipaa.corpus),
    "pci_dss": _from_module(
        pci, lambda a: a.evidence_tier, lambda s: s.truth(), pci.corpus),
    "soc2": _from_module(
        soc2, lambda e: e.evidence_tier, lambda g: g.truth(), soc2.corpus),
    "card_act": _from_module(
        card_act, lambda r: r.evidence_tier, lambda a: a.truth(),
        card_act.corpus),
}


def get(name: str) -> Regime:
    if name not in REGIMES:
        raise KeyError(f"no regime {name!r}; have {sorted(REGIMES)}")
    return REGIMES[name]

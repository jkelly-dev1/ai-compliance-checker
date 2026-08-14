"""The cross-regime invariants. These are what make the numbers comparable.

Every test here runs over all five regimes. That is deliberate: a regime is
added by writing a module and one registry line, and the whole argument of the
repository is that the same measurement applies to all of them. A test that
only ran over zoning would let a new regime join with a broken encoding and a
plausible-looking table.

The first test is the one that matters and it has already paid for itself. The
honest checker must never be wrong. When SOC 2 was added it came back 4.0%
wrong, which is impossible by construction unless the encoding is broken, and
it was: the list of controls a carved-out subservice organization performs was
truth-only, so the checker evaluated controls the entity did not own. Nothing
in the SOC 2 module could have revealed that. The invariant did.
"""

from __future__ import annotations

import pytest

from acc.boundary import measure
from acc.regime import REGIMES
from acc.verdict import FAIL, PASS, REFUSE

REGIME_NAMES = sorted(REGIMES)
N = 300


@pytest.fixture(scope="module")
def measured():
    return {name: measure(REGIMES[name], N) for name in REGIME_NAMES}


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_the_honest_checker_is_never_wrong(name, measured):
    """The load-bearing invariant. A checker that refuses when it cannot know
    has no way to be wrong, so any nonzero number here is a defect in the
    encoding, a rule deciding on evidence it does not have, and never a
    finding about the regime."""
    # v4_minimal decides strictly more than v2, so it is the one most likely
    # to break this. It enumerates the missing evidence and decides only where
    # every possible value agrees; a bug there would show up here first.
    for checker in ("v2_definition_aware", "v4_minimal", "v3_with_intake"):
        wrong = measured[name]["checkers"][checker]["wrong"]
        assert wrong == 0, (
            f"{name}/{checker} decided wrongly {wrong} times. Some rule is "
            f"deciding without a precondition it needs.")


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_every_rule_decides_at_least_once(name, measured):
    """The companion to the invariant above, and it is not optional.

    "Never wrong" is satisfied two ways: by a rule that decides and gets every
    decision right, and by a rule that never decides at all. In the per-rule
    table those two print identically, wrong 0, direction "never wrong", and
    only the `refused` column tells them apart. A reader comparing regimes
    reads the direction, not the denominator.

    So a rule that refuses every single case is a defect, not a result, and it
    is the one defect the invariant above cannot see. This test is what
    separates them."""
    for checker in ("v2_definition_aware", "v4_minimal", "v3_with_intake"):
        for rule, cell in measured[name]["per_rule"][checker].items():
            decided = cell["right"] + cell["wrong"]
            assert decided > 0, (
                f"{name}/{checker}/{rule} refused all {cell['refused']} cases "
                f"and decided none. It reports 'never wrong' because it never "
                f"decides. Check that its preconditions name only fields the "
                f"submittal actually carries in `fields`.")


def test_breaking_a_checker_breaks_the_invariant():
    """MUTATION CHECK. If the test above cannot fail, it is decoration.

    A checker that ignores its preconditions and answers anyway is exactly the
    defect the invariant exists to catch, so building one must make the
    invariant fail. This mutates the HIPAA checker, which has the largest
    share of decisions that turn on evidence the submission usually lacks.
    """
    from acc import hipaa

    original = hipaa.check_definition_aware

    def reckless(sub):
        """Decide every rule, treating absent evidence as False."""
        out = {}
        for rule in hipaa.RULES:
            f = sub.fields
            if rule == "encryption_at_rest":
                ok = f.get("encryption_enabled", False)
            elif rule == "de_identification":
                ok = not any(c in hipaa.SAFE_HARBOR_DIRECT
                             for c in f.get("released_columns", ()))
            else:
                ok = True
            out[rule] = hipaa.Verdict(rule, PASS if ok else FAIL, "reckless")
        return out

    hipaa.check_definition_aware = reckless
    try:
        # The registry captured the original at import, so measure through the
        # module the way the mutation intends.
        wrong = 0
        for entity, sub in hipaa.corpus(200):
            truth = entity.truth()
            for rule, v in reckless(sub).items():
                want = PASS if truth[rule] else FAIL
                if v.result != want:
                    wrong += 1
        assert wrong > 0, (
            "a checker that ignores its preconditions produced no errors, so "
            "the never-wrong invariant proves nothing")
    finally:
        hipaa.check_definition_aware = original


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_the_naive_checker_is_wrong_somewhere(name, measured):
    """Otherwise the comparison in the README is between a checker and itself."""
    wrong = measured[name]["checkers"]["v1_naive"]["wrong"]
    assert wrong > 0, f"{name}: the naive checker made no errors at all"


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_the_naive_checker_never_refuses(name, measured):
    """The whole contrast is answers-everything against refuses-honestly. A
    naive checker that refused would be a third thing and the table would be
    comparing three different questions."""
    assert measured[name]["checkers"]["v1_naive"]["refused"] == 0


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_intake_only_ever_adds_evidence(name, measured):
    """v3 is v2 with more fields, so it must decide at least as much.

    A regime whose intake additions REMOVED decidability would mean the
    with_intake function is overwriting evidence rather than filling gaps,
    which would quietly change what is being measured.
    """
    v2 = measured[name]["checkers"]["v2_definition_aware"]["decided"]
    v3 = measured[name]["checkers"]["v3_with_intake"]["decided"]
    assert v3 >= v2, f"{name}: intake reduced decisions from {v2} to {v3}"


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_the_honest_checker_refuses_something(name, measured):
    """A regime where nothing is ever refused is not exercising the third
    verdict, and its decided rate is not evidence of anything."""
    assert measured[name]["checkers"]["v2_definition_aware"]["refused"] > 0


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_a_checker_cannot_reach_the_truth_object(name):
    """The structural guarantee, tested rather than asserted in a comment.

    Strip a submission of every field and the honest checker must refuse every
    rule. If any rule still decides, it is reading something other than the
    submission it was handed, a truth object, a module global, a default, and
    every number this regime produces is suspect.
    """
    reg = REGIMES[name]
    _, sub = next(iter(reg.corpus(1)))
    stripped = type(sub)(**{**sub.__dict__, "fields": {}})
    for rule, v in reg.definition_aware(stripped).items():
        assert v.result == REFUSE, (
            f"{name}/{rule} decided from an empty submission: {v.reason}")


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_the_corpus_is_deterministic(name):
    """Same index, same case. Two runs that disagree are not comparable, and
    every table in this repository compares runs."""
    reg = REGIMES[name]
    first = [reg.truth_of(t) for t, _ in reg.corpus(40)]
    second = [reg.truth_of(t) for t, _ in reg.corpus(40)]
    assert first == second


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_every_rule_is_exercised_in_both_directions(name):
    """A rule no case ever violates is a column of PASS that proves nothing.

    This is the check that caught the zoning height rule, where a units error
    made the true height about -80 ft and NOT ONE parcel in 600 could exceed
    the limit. The rule was in every table with a true-violation count of zero.
    """
    reg = REGIMES[name]
    seen = {rule: set() for rule in reg.rules}
    for truth_obj, _ in reg.corpus(N):
        for rule, ok in reg.truth_of(truth_obj).items():
            seen[rule].add(ok)
    for rule, values in seen.items():
        assert values == {True, False}, (
            f"{name}/{rule} is always {values.pop()} in {N} cases; the rule "
            f"is not being exercised and its column means nothing")


def test_a_regime_missing_preconditions_is_refused_at_construction():
    """The registry validates rather than trusting. A rule with no precondition
    set could never refuse, and its decided rate would read as a triumph."""
    from acc.regime import Regime

    with pytest.raises(ValueError):
        Regime(name="broken", citation="", rules=("a", "b"), limits={},
               preconditions={"a": ()}, intake_additions=(),
               evidence_tiers=(), corpus=None, truth_of=None, naive=None,
               definition_aware=None, with_intake=None, tier_of=None)


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_no_rule_reads_a_field_it_did_not_declare(name):
    """A rule may only read what its precondition set names.

    Found a real bug the day it was written. HIPAA's workforce_termination
    read `alternative_control_documented` without declaring it, and the corpus
    never produced a submission carrying its declared preconditions WITHOUT
    that field, so nothing exercised it. Acc/minimal.py enumerates exactly
    those combinations and the checker raised.

    Build a submission carrying precisely the declared preconditions, with
    every plausible value, and require the checker not to raise.
    """
    from itertools import product

    from acc.minimal import value_domains

    reg = REGIMES[name]
    domains = value_domains(reg, 200)
    _, template = next(iter(reg.corpus(1)))
    for rule in reg.rules:
        needed = [p for p in reg.preconditions[rule] if p in domains]
        if len(needed) != len(reg.preconditions[rule]):
            continue                      # something is not enumerable
        combos = 1
        for f in needed:
            combos *= len(domains[f])
        if combos > 240:
            continue
        for values in product(*(domains[f] for f in needed)):
            sub = type(template)(**{**template.__dict__,
                                    "fields": dict(zip(needed, values))})
            reg.definition_aware(sub)[rule]     # must not raise

"""The cross-regime invariants. These are what make the numbers comparable.

The invariants run over all five regimes. A regime is added by writing a
module and one registry line, and the whole argument of the repository is that
the same measurement applies to all of them, so an invariant that only ran over
zoning would let a new regime join with a broken encoding and a
plausible-looking table. The few tests that target one regime say so: the
mutation check on HIPAA, the registry's own validation, and the domain-size
check on zoning.

The first invariant is the one that matters. The honest checker must never be
wrong, because it refuses whenever it cannot know. A nonzero error rate is
impossible by construction unless the encoding is broken, for example a
control list the checker can see only through the truth object, and nothing
inside a regime module can reveal that. The invariant can.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from acc.boundary import measure
from acc.regime import REGIMES
from acc.verdict import FAIL, PASS, REFUSE

REGIME_NAMES = sorted(REGIMES)
N = 300


@pytest.fixture(scope="module")
def measured():
    return {name: measure(REGIMES[name], N) for name in REGIME_NAMES}


HONEST_CHECKERS = ("v2_definition_aware", "v4_minimal", "v3_with_intake")


def assert_never_wrong(measurement, name):
    """The load-bearing assertion, in one place because two tests make it.

    test_the_honest_checker_is_never_wrong makes it about the shipped
    checkers; test_breaking_a_checker_breaks_the_invariant makes it about a
    deliberately reckless one and requires it to raise. Sharing the function
    is the point. A mutation check with its own private copy of the tally
    would go on passing if the real assertion were weakened to
    `assert wrong >= 0`, reporting the invariant as falsifiable while it
    guarded nothing. Written once, it cannot drift from what it guards.
    """
    # v4_minimal decides strictly more than v2, so it is the one most likely
    # to break this. It enumerates the missing evidence and decides only where
    # every possible value agrees; a bug there would show up here first.
    for checker in HONEST_CHECKERS:
        wrong = measurement["checkers"][checker]["wrong"]
        assert wrong == 0, (
            f"{name}/{checker} decided wrongly {wrong} times. Some rule is "
            f"deciding without a precondition it needs.")


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_the_honest_checker_is_never_wrong(name, measured):
    """The load-bearing invariant. A checker that refuses when it cannot know
    has no way to be wrong, so any nonzero number here is a defect in the
    encoding, a rule deciding on evidence it does not have, and never a
    finding about the regime."""
    assert_never_wrong(measured[name], name)


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_every_rule_decides_at_least_once(name, measured):
    """The companion to the invariant above, and it is not optional.

    "Never wrong" is satisfied two ways: by a rule that decides and gets every
    decision right, and by a rule that never decides at all. In the per-rule
    table those two print identically, wrong 0, direction "never wrong", and
    only the `refused` column tells them apart. A reader comparing regimes
    reads the direction, not the denominator.

    A rule that refuses every single case is therefore a defect, and it is the
    one defect the invariant above cannot see. This test is what
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
    """Mutation check. If the test above cannot fail, it is decoration.

    A checker that ignores its preconditions and answers anyway is exactly the
    defect the invariant exists to catch, so building one must make the
    invariant fail. This mutates the HIPAA checker, which has the largest
    share of decisions that turn on evidence the submission usually lacks.

    The reckless checker goes through measure(), the registry and
    assert_never_wrong, so the mutation is of the measured system and not of
    a function beside it. acc/regime.py binds the function object into a
    frozen Regime at import, so rebinding `hipaa.check_definition_aware`
    would change nothing the measurement looks up. Replacing the field on the
    Regime patches the binding the code under test actually resolves.
    """
    from dataclasses import replace

    from acc import hipaa

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

    mutated = replace(REGIMES["hipaa"], definition_aware=reckless)
    measurement = measure(mutated, N)

    # The mutation must reach the measurement as well as exist beside it.
    assert measurement["checkers"]["v2_definition_aware"]["refused"] == 0, (
        "the reckless checker refused something, so measure() is not calling "
        "it and this mutation is not reaching the system under test")

    with pytest.raises(AssertionError) as raised:
        assert_never_wrong(measurement, "hipaa/reckless")
    assert "decided wrongly" in str(raised.value)


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
    with_intake function is overwriting evidence instead of filling gaps,
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
    """The structural guarantee, tested and not just asserted in a comment.

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


# The module that holds each regime's CHECKERS, which is the code the guard
# below reads. Zoning keeps its population in acc/parcels.py and its checkers
# in acc/zoning.py; the other four keep both in one file.
CHECKER_MODULES = {
    "zoning": "acc/zoning.py", "hipaa": "acc/hipaa.py",
    "pci_dss": "acc/pci.py", "soc2": "acc/soc2.py",
    "card_act": "acc/card_act.py",
}

# The one function in each module that is ALLOWED to take a truth object, and
# every regime documents why: "if the applicant supplied these, how much could
# be decided?" is a question about the real value.
TRUTH_IS_ALLOWED_IN = "with_intake"


def _reachable_functions(tree, roots):
    """The functions in one module reachable by name from `roots`.

    Name-based and therefore approximate in the safe direction: it can include
    a function the checker does not really call, which would only make the
    guard stricter, and it cannot miss one called by its own name.
    """
    defined = {node.name: node for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    seen, stack = set(), [r for r in roots if r in defined]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        for node in ast.walk(defined[name]):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id in defined and node.func.id not in seen:
                stack.append(node.func.id)
    return {name: defined[name] for name in seen}


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_no_checker_names_a_truth_constructor(name):
    """The structural guarantee, read off the code instead of probed.

    Its companion, test_a_checker_cannot_reach_the_truth_object, hands the
    checker an empty submission and requires every rule to refuse. That
    establishes that every precondition set is non-empty, which is a
    different claim. A checker that answered honestly whenever the evidence
    reached and consulted the truth object only when it did not would satisfy
    it completely.

    Such a checker would also leave every other test passing and
    audit/offline.json byte-identical, because the answers it produces are the
    right ones: the measurement cannot see a checker that cheats correctly.
    Only the source can, so this reads the source. No function reachable from
    either checker may name a population constructor or touch a `.truth`
    attribute.
    """
    path = pathlib.Path(__file__).resolve().parent.parent / CHECKER_MODULES[name]
    tree = ast.parse(path.read_text(encoding="utf-8"))
    reachable = _reachable_functions(
        tree, ("check_naive", "check_definition_aware"))
    assert "check_definition_aware" in reachable, (
        f"{path} defines no check_definition_aware, so this guard read "
        f"nothing and must not report that it passed")
    assert TRUTH_IS_ALLOWED_IN not in reachable, (
        f"{name}: {TRUTH_IS_ALLOWED_IN} is reachable from a checker, which "
        f"is the one function permitted to hold a truth object")

    offenses = []
    for func_name, node in sorted(reachable.items()):
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute) and child.attr == "truth":
                offenses.append(f"{func_name} touches .truth")
            elif isinstance(child, ast.Name) and child.id.startswith("make_"):
                offenses.append(f"{func_name} names {child.id}")
    assert not offenses, (
        f"{name}: a checker reaches the population it is being graded "
        f"against, so every number this regime produces is measuring the key "
        f"against itself: {sorted(set(offenses))}")


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_the_corpus_is_deterministic(name):
    """Same index, same case. Two runs that disagree are not comparable, and
    every table in this repository compares runs."""
    reg = REGIMES[name]
    first = [reg.truth_of(t) for t, _ in reg.corpus(40)]
    second = [reg.truth_of(t) for t, _ in reg.corpus(40)]
    assert first == second


def test_the_minimal_checker_reads_its_domains_from_the_measured_population(
        monkeypatch):
    """v4's enumerable domains are read off the corpus, so they must be read
    off the corpus being measured.

    A field can hold fewer than MAX_DOMAIN distinct values in 400 cases and
    more in 600, and the checker would then treat as enumerable something the
    measurement runs over values of that it never saw.

    This is asserted about the call, not about a number. Nothing observable
    distinguishes the two sizes in this tree: no verdict differs, and
    audit/offline.json is byte-identical either way. A test written against
    the output would pass with the defect present, so what is pinned is that
    the measurement hands the checker its own n.

    The patch goes on acc.boundary, not acc.minimal. boundary.py does
    `from .minimal import make_checker`, so it holds its own reference and
    patching the source module would change nothing it calls.
    """
    from acc import boundary

    seen = []
    original = boundary.make_checker

    def recording(reg, n=400):
        seen.append(n)
        return original(reg, n)

    monkeypatch.setattr(boundary, "make_checker", recording)
    boundary.measure(REGIMES["zoning"], 137)
    assert seen == [137], (
        f"measure() built the minimal checker with n={seen}, not the 137 "
        f"cases it went on to measure, so v4's idea of what a field can hold "
        f"comes from a population that is not the one being graded")


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_some_evidence_tier_carries_everything_the_population_has(name):
    """What a submission may carry is a fact about the population, and it must
    not be derived from what the rules require.

    A richest evidence tier defined as the union of the precondition sets
    equals the full field list only by coincidence. Removing a precondition
    from a rule would then remove the field from what a full-assessment
    submission carries, and because the naive checker reads fields the honest
    one does not declare, a change to the honest checker would silently move
    the naive checker's published error rate.

    This property prevents that: somewhere in the tier table there is a tier
    that carries everything, so tightening a rule cannot remove evidence from
    the world.
    """
    reg = REGIMES[name]
    everything, by_tier = set(), {}
    for _, sub in reg.corpus(400):
        everything |= set(sub.fields)
        by_tier.setdefault(reg.tier_of(sub), set()).update(sub.fields)
    assert everything, f"{name}: no submission in 400 carried any field"
    complete = [t for t, fields in by_tier.items() if fields == everything]
    assert complete, (
        f"{name}: no evidence tier carries every field the population can "
        f"supply, so no submission is ever fully evidenced. Closest tier is "
        f"short of: "
        + repr({t: sorted(everything - f) for t, f in by_tier.items()
                if len(everything - f) == min(len(everything - g)
                                              for g in by_tier.values())}))


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_every_rule_is_exercised_in_both_directions(name):
    """A rule no case ever violates is a column of PASS that proves nothing.

    A units error in a height rule, for example, can make every true value
    negative so that no parcel can ever exceed the limit, and the rule then
    sits in every table with a true-violation count of zero.
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
    """The registry validates its input instead of trusting it. A rule with no
    precondition set could never refuse, and its decided rate would read as a
    triumph."""
    from acc.regime import Regime

    with pytest.raises(ValueError):
        Regime(name="broken", citation="", rules=("a", "b"), limits={},
               preconditions={"a": ()}, intake_additions=(),
               evidence_tiers=(), corpus=None, truth_of=None, naive=None,
               definition_aware=None, with_intake=None, tier_of=None)


# ---------------------------------------------------------------------------
# The precondition set must be the truth about what a rule reads, both ways.
#
# A precondition set is a claim with two halves: these fields are enough, and
# these fields are needed. The two halves fail differently.
#
#   read but not declared  the rule decides on evidence its own set says it
#                          does not need. A `.get(field, False)` supplies a
#                          default that looks like evidence, and a submission
#                          carrying everything the rule asked for can then be
#                          decided wrongly, breaking the never-wrong invariant.
#   declared but not read  the rule refuses for want of something it would not
#                          have looked at, and names it as the cause. The
#                          refusal-cause ranking, which the README publishes
#                          as "what the refusals needed", would then count
#                          fields no rule needed.
#
# The reads are recorded, not enumerated. Building every combination of the
# declared fields and requiring the checker not to raise catches a missing
# field only when the read is `fields[x]`; a `.get(x, default)` raises
# nothing. Enumeration also cannot reach a rule with an un-enumerable field or
# a large product of values. Recording the reads answers the question
# directly, needs no enumeration, and reaches every rule.


class _RecordingFields(dict):
    """A submission's `fields`, which remembers which keys were read.

    `__contains__` is not recorded. Every rule probes for presence through
    `Submission.missing()` before it decides anything, so counting a presence
    probe as a read would attribute every other rule's refusal check to the
    rule under test.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read = set()

    def __getitem__(self, key):
        self.read.add(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self.read.add(key)
        return super().get(key, default)


_TRIALS = 400
_POOL_VALUES = 8


def _pools(reg, n):
    """field -> distinct values it takes, and attribute -> the same.

    Deduplicated by repr so unhashable evidence (wall polygons, balance sets,
    per-rule control maps) is pooled like anything else.
    """
    fields, attrs = {}, {}
    for _, sub in reg.corpus(n):
        for key, value in sub.fields.items():
            seen = fields.setdefault(key, {})
            if len(seen) < _POOL_VALUES:
                seen.setdefault(repr(value), value)
        for key, value in vars(sub).items():
            if key == "fields":
                continue
            seen = attrs.setdefault(key, {})
            if len(seen) < _POOL_VALUES:
                seen.setdefault(repr(value), value)
    return ({k: list(v.values()) for k, v in fields.items()},
            {k: list(v.values()) for k, v in attrs.items()})


def _probe(reg, rule, pool, cases, rng):
    """Read set, and how often the rule actually DECIDED, over `_TRIALS`.

    Each trial hands the rule a submission carrying exactly its declared
    preconditions, on top of a REAL case from the corpus so that the
    attributes a rule branches on (a lot type, an evidence tier) vary the way
    they do in the population.
    """
    declared = list(reg.preconditions[rule])
    reads, decided, refused = set(), 0, 0
    for _ in range(_TRIALS):
        base = rng.choice(cases)
        fields = {}
        for name in declared:
            if name not in pool:
                continue            # carried as an attribute; probed below
            fields[name] = (base.fields[name] if name in base.fields
                            and rng.random() < 0.5 else rng.choice(pool[name]))
        recording = _RecordingFields(fields)
        sub = type(base)(**{**vars(base), "fields": recording})
        try:
            verdict = reg.definition_aware(sub)[rule]
        except KeyError as exc:
            # An undeclared read that happened to be a SUBSCRIPT rather than a
            # `.get()`, so it raised before the verdict came back. It is the
            # same finding, so record it as the read it is and let
            # test_no_rule_reads_a_field_it_did_not_declare report it by name.
            # Letting the exception out would error every test sharing this
            # fixture and say nothing about which field or which rule.
            reads.add(exc.args[0] if exc.args else "<unknown key>")
            reads |= recording.read
            continue
        reads |= recording.read
        if verdict.result == REFUSE:
            refused += 1
        else:
            decided += 1
    return reads, decided, refused


@pytest.fixture(scope="module")
def probed():
    """(reads, decided, refused) per regime and rule, computed once."""
    import random

    out = {}
    for name in REGIME_NAMES:
        reg = REGIMES[name]
        pool, attr_pool = _pools(reg, 300)
        cases = [sub for _, sub in reg.corpus(300)]
        out[name] = {"pool": pool, "attr_pool": attr_pool, "rules": {}}
        for rule in reg.rules:
            rng = random.Random(f"probe-{name}-{rule}")
            out[name]["rules"][rule] = _probe(reg, rule, pool, cases, rng)
    return out


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_no_rule_reads_a_field_it_did_not_declare(name, probed):
    """A rule may only read what its precondition set names.

    A predicate shared by several rules is the usual way this breaks: if it
    reads two documented alternatives, every rule that uses it has to declare
    both, or a submission carrying everything the rule declared can still be
    decided on a default.
    """
    reg = REGIMES[name]
    offenses = []
    for rule in reg.rules:
        reads, _, _ = probed[name]["rules"][rule]
        undeclared = sorted(reads - set(reg.preconditions[rule]))
        if undeclared:
            offenses.append(f"{rule} reads {undeclared}")
    assert not offenses, (
        f"{name}: rules reading evidence their precondition set does not "
        f"declare, so the set is not the truth about what they need and a "
        f"submission carrying all of it can still be decided wrongly: "
        + "; ".join(offenses))


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_every_declared_precondition_is_actually_read(name, probed):
    """The other half of the claim.

    A field declared and never read makes the rule refuse for want of
    something it would not have looked at, and `Verdict.missing` (which
    acc/verdict.py calls "what makes the refusals actionable") then names it.
    That is a definite finding about evidence the rule never examined, and
    the README publishes the ranking of those causes.
    """
    import random

    reg = REGIMES[name]
    pool = probed[name]["pool"]
    attr_pool = probed[name]["attr_pool"]
    cases = [sub for _, sub in reg.corpus(300)]
    phantoms, unexaminable = [], []
    for rule in reg.rules:
        reads, _, _ = probed[name]["rules"][rule]
        for field_name in reg.preconditions[rule]:
            if field_name in pool:
                if field_name not in reads:
                    phantoms.append(f"{rule}/{field_name}")
                continue
            # Carried as an ATTRIBUTE of every submission rather than in
            # `fields`, so the recorder cannot see it. It is not skipped:
            # vary the attribute and require the verdict to move, which is
            # the same question asked the only other way it can be asked.
            values = attr_pool.get(field_name, [])
            if len(values) < 2:
                unexaminable.append(f"{rule}/{field_name}")
                continue
            rng = random.Random(f"attr-{name}-{rule}-{field_name}")
            if not _attribute_moves_a_verdict(reg, rule, field_name, values,
                                              cases, pool, rng):
                phantoms.append(f"{rule}/{field_name}")
    assert not unexaminable, (
        f"{name}: these declared preconditions are neither carried in "
        f"`fields` nor variable as an attribute, so this test could not "
        f"examine them and must not report on them: {unexaminable}")
    assert not phantoms, (
        f"{name}: declared preconditions that no rule path reads, so the "
        f"rule refuses for want of evidence it would not have looked at and "
        f"names it as the cause: {phantoms}")


def _attribute_moves_a_verdict(reg, rule, attr, values, cases, pool, rng):
    """Can changing this always-filed attribute change the rule's verdict?"""
    declared = [f for f in reg.preconditions[rule] if f in pool]
    for _ in range(_TRIALS):
        base = rng.choice(cases)
        fields = {f: (base.fields[f] if f in base.fields
                      else rng.choice(pool[f])) for f in declared}
        seen = set()
        for value in values:
            sub = type(base)(**{**vars(base), attr: value,
                                "fields": dict(fields)})
            try:
                seen.add(reg.definition_aware(sub)[rule].result)
            except KeyError:
                # An undeclared subscript read. That is the other test's
                # finding, not this one's; this one must not claim the
                # attribute is a phantom on the strength of a raise it did
                # not cause.
                return True
            if len(seen) > 1:
                return True
    return False


@pytest.mark.parametrize("name", REGIME_NAMES)
def test_the_read_probe_examined_every_rule(name, probed):
    """The guard on the two tests above, because a probe that examined
    nothing would pass both of them in silence.

    This asserts the shape of the examination, not only its result: every
    rule reached, every rule decided on some trial (a rule that only ever
    refused would have read nothing), and every rule read at least one field.
    """
    reg = REGIMES[name]
    assert set(probed[name]["rules"]) == set(reg.rules), (
        f"{name}: probed {sorted(probed[name]['rules'])} but the regime has "
        f"{sorted(reg.rules)}")
    for rule in reg.rules:
        reads, decided, refused = probed[name]["rules"][rule]
        assert decided > 0, (
            f"{name}/{rule} refused all {refused} probe trials, so it read "
            f"nothing and the two read invariants said nothing about it")
        assert reads, (
            f"{name}/{rule} decided {decided} trials without reading a "
            f"single field, which means it is not reading the submission")

"""The amendment measurement, and the two ways it silently measures nothing."""

from __future__ import annotations

import pytest

from acc.version_bump import BUMPS, measure_bump

NAMES = sorted(BUMPS)
N = 300


@pytest.mark.parametrize("name", NAMES)
def test_every_amendment_actually_moves_something(name):
    """An amendment must move something, or it measures nothing.

    Raising the HIPAA ZIP3 floor from 20,000 to 25,000 would change nothing,
    because the corpus carries no population between those numbers. A
    threshold that moves across empty space reports 0.0% and reads as
    stability under revision."""
    r = measure_bump(name, N)
    moved = r["flipped_to_fail"] + r["flipped_to_pass"]
    assert moved > 0, (
        f"{name}: the amendment re-decided nothing. Either the population has "
        f"no mass in the band it moved across, or the constant is not the one "
        f"the rule reads.")


@pytest.mark.parametrize("name", NAMES)
def test_a_tightening_never_flips_a_decision_to_pass(name):
    """Every amendment in the table tightens a threshold, so a decision may
    become FAIL and may not become PASS. A flip the other way means the bump
    was applied to the truth and the checker inconsistently."""
    r = measure_bump(name, N)
    assert r["flipped_to_pass"] == 0


@pytest.mark.parametrize("name", NAMES)
def test_flips_and_now_wrong_agree(name):
    """For a one-directional tightening the two numbers must be equal.

    An amendment that patched the checker module's function after
    acc/regime.py had bound the original into the registry would move the
    truth and not the checker, and show zero flips beside decisions that had
    become wrong."""
    r = measure_bump(name, N)
    assert r["flipped_to_fail"] == r["issued_decisions_now_wrong"]


def test_the_bump_restores_the_constant_afterwards():
    """A leaked patch would silently re-decide every later measurement in the
    same process, including the ones the README quotes."""
    from acc import soc2
    before = soc2.MIN_SAMPLE
    measure_bump("soc2", 50)
    assert soc2.MIN_SAMPLE == before

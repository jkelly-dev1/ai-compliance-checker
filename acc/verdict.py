"""The three-valued result every regime returns, and nothing else.

Refuse is a first-class value, not an error. A checker that can only say PASS
or FAIL has to guess when the evidence does not reach, and the guess is
indistinguishable in the output from a decision. Every measurement in this
repository reports decided-and-never-wrong rather than accuracy, and that is
only expressible because this type has three values.

This module deliberately contains no rules and no regime. It is imported by
every regime and imports none of them, so a regime can never quietly depend on
another regime's definitions through the back door.
"""

from __future__ import annotations

from dataclasses import dataclass

PASS = "pass"
FAIL = "fail"
REFUSE = "refuse"


@dataclass(frozen=True)
class Verdict:
    """One decision about one rule, with the reason it went that way.

    `missing` is populated only on REFUSE, and it is what makes the refusals
    actionable: the measurement ranks refusal causes, and a cause that is a
    form field is a different problem from one that is a judgment.
    """

    rule: str
    result: str
    reason: str = ""
    missing: tuple = ()

    def decided(self) -> bool:
        return self.result in (PASS, FAIL)

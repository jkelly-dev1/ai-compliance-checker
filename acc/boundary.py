"""The decision boundary, measured once and applied to every regime.

The measurement, and why it is not accuracy. A checker that answers everything
and is right 78% of the time and a checker that answers a fifth of the cases
and is never wrong are not two points on one scale. Accuracy collapses them.
This reports three numbers together and refuses to combine them:

    DECIDED    what fraction the checker was willing to answer
    WRONG      of those answers, how many were wrong
    REFUSED    what it declined, and what it needed in order not to

A regulator, an auditor and a plan reviewer all care about the second number
being zero and will trade a great deal of the first for it. A dashboard vendor
quotes the first. That difference is the whole subject.

The error direction is reported per rule, not pooled. A rule whose naive
errors are all FALSE PASSES is dangerous; one whose errors are all FALSE FAILS
is merely expensive; a rule that does both cannot be repaired by a safety
margin. Pooling them across a regime hides exactly that, and the three regimes
in this repository do not agree about it, which is a finding rather than an
inconsistency.
"""

from __future__ import annotations

from collections import Counter

from .minimal import make_checker
from .regime import Regime
from .verdict import FAIL, PASS, REFUSE

CHECKERS = ("v1_naive", "v2_definition_aware", "v4_minimal",
            "v3_with_intake")


def measure(reg: Regime, n: int) -> dict:
    """Run all four checkers in CHECKERS over `n` cases of one regime."""
    tally = {c: Counter() for c in CHECKERS}
    per_rule = {c: {r: Counter() for r in reg.rules} for c in CHECKERS}
    by_tier = {c: {t: Counter() for t in reg.evidence_tiers} for c in CHECKERS}
    refusal_causes = Counter()
    tier_counts = Counter()

    # The same n the measurement runs at. v4's enumerable domains are read off
    # the corpus, so reading them off a different-sized corpus would give the
    # checker an idea of what a field can hold taken from a population that is
    # not the one under test. A field can have exactly MAX_DOMAIN distinct
    # values at 400 cases and more at 600.
    minimal = make_checker(reg, n)

    for truth_obj, sub in reg.corpus(n):
        truth = reg.truth_of(truth_obj)
        tier = reg.tier_of(sub)
        tier_counts[tier] += 1
        results = {
            "v1_naive": reg.naive(sub),
            "v2_definition_aware": reg.definition_aware(sub),
            "v4_minimal": minimal(sub),
            "v3_with_intake": reg.definition_aware(reg.with_intake(sub, truth_obj)),
        }
        for checker, verdicts in results.items():
            for rule in reg.rules:
                v = verdicts[rule]
                want = PASS if truth[rule] else FAIL
                if v.result == REFUSE:
                    tally[checker]["refused"] += 1
                    per_rule[checker][rule]["refused"] += 1
                    by_tier[checker][tier]["refused"] += 1
                    if checker == "v2_definition_aware":
                        for m in v.missing:
                            refusal_causes[m] += 1
                elif v.result == want:
                    tally[checker]["right"] += 1
                    per_rule[checker][rule]["right"] += 1
                    by_tier[checker][tier]["right"] += 1
                else:
                    tally[checker]["wrong"] += 1
                    per_rule[checker][rule]["wrong"] += 1
                    by_tier[checker][tier]["wrong"] += 1
                    kind = "false_pass" if v.result == PASS else "false_fail"
                    per_rule[checker][rule][kind] += 1

    total = n * len(reg.rules)
    out = {
        "regime": reg.name, "citation": reg.citation, "cases": n,
        "rules": len(reg.rules), "decisions": total,
        "tier_mix": dict(tier_counts),
        "checkers": {}, "per_rule": {}, "by_tier": {},
        "refusal_causes": dict(refusal_causes.most_common()),
    }
    for c in CHECKERS:
        t = tally[c]
        decided = t["right"] + t["wrong"]
        out["checkers"][c] = {
            "decided": decided,
            "decided_pct": round(decided / total * 100, 1),
            "wrong": t["wrong"],
            "wrong_pct_of_decided": (round(t["wrong"] / decided * 100, 1)
                                     if decided else 0.0),
            "refused": t["refused"],
        }
        out["per_rule"][c] = {
            r: {"right": per_rule[c][r]["right"], "wrong": per_rule[c][r]["wrong"],
                "refused": per_rule[c][r]["refused"],
                "false_pass": per_rule[c][r]["false_pass"],
                "false_fail": per_rule[c][r]["false_fail"],
                "direction": _direction(per_rule[c][r])}
            for r in reg.rules}
        out["by_tier"][c] = {
            t_: {"decided": by_tier[c][t_]["right"] + by_tier[c][t_]["wrong"],
                 "wrong": by_tier[c][t_]["wrong"],
                 "refused": by_tier[c][t_]["refused"]}
            for t_ in reg.evidence_tiers}
    return out


def _direction(counts: Counter) -> str:
    fp, ff = counts["false_pass"], counts["false_fail"]
    if not fp and not ff:
        return "never wrong"
    if fp and ff:
        return "MIXED"
    return "false passes only" if fp else "false fails only"


def format_report(m: dict) -> str:
    """One regime's result, as the tables the README quotes."""
    lines = []
    lines.append(f"{m['regime'].upper()}  --  {m['citation']}")
    lines.append(f"{m['cases']} cases x {m['rules']} rules = "
                 f"{m['decisions']} decisions")
    lines.append("")
    lines.append(f"  {'checker':<22} {'decided':>16} {'wrong':>18} "
                 f"{'refused':>9}")
    for c in CHECKERS:
        d = m["checkers"][c]
        lines.append(
            f"  {c:<22} {d['decided']:>6} ({d['decided_pct']:>5.1f}%) "
            f"{d['wrong']:>6} ({d['wrong_pct_of_decided']:>5.1f}% of decided) "
            f"{d['refused']:>9}")
    lines.append("")
    lines.append("  naive checker, error direction by rule")
    for rule, r in m["per_rule"]["v1_naive"].items():
        lines.append(f"    {rule:<24} false pass {r['false_pass']:>4}   "
                     f"false fail {r['false_fail']:>4}   {r['direction']}")
    lines.append("")
    lines.append("  honest checker, decided by evidence tier")
    for tier, t in m["by_tier"]["v2_definition_aware"].items():
        seen = m["tier_mix"].get(tier, 0)
        total = seen * m["rules"]
        pct = (t["decided"] / total * 100) if total else 0.0
        lines.append(f"    {tier:<24} {t['decided']:>5} of {total:<5} "
                     f"({pct:>5.1f}%)   n={seen}")
    if m["refusal_causes"]:
        lines.append("")
        lines.append("  what the refusals needed, most common first")
        for cause, count in list(m["refusal_causes"].items())[:6]:
            lines.append(f"    {count:>6}  {cause}")
    return "\n".join(lines)

#!/usr/bin/env python3
"""The whole offline measurement. No network, no cost, no API key.

    python scripts/offline_demo.py
    python scripts/offline_demo.py --cases 600 --json audit/offline.json
    python scripts/offline_demo.py --regime hipaa

Five regimes, one measurement, asked of each:

  1 THE RATIO      how many limits does the regime state, and how many
                   definitions decide them
  2 THE BOUNDARY   what each of three checkers decides, and how often it is
                   wrong: the naive one that always answers, the honest one
                   that refuses, and the honest one after intake is changed
  3 THE DIRECTION  per rule, whether the naive checker's errors are false
                   passes, false fails, or both, because only the last is
                   beyond repair by a safety margin
  4 THE EVIDENCE   what fraction is decidable per evidence tier, which is
                   where a single decidability number falls apart
  5 THE AMENDMENT  what a routine edition change does to decisions that were
                   already issued

What this measures and what it does not. Every number is exact, because every
population is constructed and its correct verdict is known independently of
any checker. NONE of it is a measurement of any real jurisdiction, entity or
portfolio: the rates in each regime module are stated constants and every
result scales with them. The regimes are simplified encodings written to be
checkable against their cited sources, not compliance products, and nothing
here is legal advice.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from acc import ordinance                                       # noqa: E402
from acc.boundary import format_report, measure                 # noqa: E402
from acc.regime import REGIMES                                  # noqa: E402
from acc.version_bump import BUMPS, measure_bump                # noqa: E402
from acc.version_bump import format_report as bump_report       # noqa: E402

HONEST = ("v2_definition_aware", "v4_minimal", "v3_with_intake")


def cross_regime_table(results: dict) -> str:
    """All four checkers. v4 sits next to v2 because it is the same checker
    asked a better question, and the pair is the point: every percentage
    point between them was a case the evidence already settled."""
    head = (f"  {'regime':<10} {'v1 naive':>13}  {'v2 all-precond':>16}  "
            f"{'v4 minimal':>16}  {'v3 intake':>10}")
    lines = [head, "  " + "-" * (len(head) - 2)]
    for name, m in results.items():
        c = m["checkers"]
        lines.append(
            f"  {name:<10} "
            f"wrong {c['v1_naive']['wrong_pct_of_decided']:>5.1f}%  "
            f"{c['v2_definition_aware']['decided_pct']:>7.1f}% dec"
            f"{'':<4}  {c['v4_minimal']['decided_pct']:>7.1f}% dec{'':<4}  "
            f"{c['v3_with_intake']['decided_pct']:>7.1f}%")
    lines.append("")
    lines.extend(never_wrong_lines(results))
    return "\n".join(lines)


# The sentences under each table are computed from what was measured, not
# printed as fixed text. The demo takes --cases and --regime, and a sentence
# written for the 600-case, five-regime run would otherwise be printed under
# a run it does not describe.

def honest_errors(results: dict) -> list:
    """Every (regime, checker, count) where an honest checker was wrong."""
    return [(name, c, m["checkers"][c]["wrong"])
            for name, m in results.items() for c in HONEST
            if m["checkers"][c]["wrong"]]


def never_wrong_lines(results: dict) -> list:
    wrong = honest_errors(results)
    if not wrong:
        return ["  v2, v4 and v3 are all NEVER WRONG. Only v1 has an error "
                "rate, which is",
                "  why the other three are reported by what they DECIDE."]
    return ["  AN HONEST CHECKER WAS WRONG, which is a defect in the "
            "encoding:"] + [f"    {name} {c}: {n} wrong decision(s)"
                            for name, c, n in wrong]


def summary_lines(results: dict) -> list:
    rates = [m["checkers"]["v1_naive"]["wrong_pct_of_decided"]
             for m in results.values()]
    span = (f"{rates[0]:.1f}%" if len(rates) == 1
            else f"{min(rates):.1f}% to {max(rates):.1f}%")
    honest_ok = all(m["checkers"][c]["wrong"] == 0
                    for m in results.values() for c in HONEST)
    # What the honest checkers decide is a range read off the same table,
    # not a word such as "minority": one intake form lets a checker decide
    # every case, and the sentence sits directly under that cell.
    shares = [m["checkers"][c]["decided_pct"]
              for m in results.values() for c in HONEST]
    decided = (f"{shares[0]:.1f}%" if min(shares) == max(shares)
               else f"{min(shares):.1f}% to {max(shares):.1f}%")
    lines = [f"  The naive checker answers everything and is wrong {span} of "
             f"the time;",
             "  the other three " + ("are never wrong and " if honest_ok
                                     else "")
             + f"decide {decided} of the cases.",
             "  Those are not points on one scale, which is why no accuracy "
             "figure",
             "  appears anywhere in this repository.",
             "",
             "  v2 -> v4 IS FREE. Same rules, same evidence; v4 stops "
             "refusing once",
             "  every possible value of the missing fields gives the same "
             "answer."]
    for name, m in results.items():
        c = m["checkers"]
        base = c["v2_definition_aware"]["decided_pct"]
        free = c["v4_minimal"]["decided_pct"] - base
        form = c["v3_with_intake"]["decided_pct"] - base
        if form > 0:
            lines.append(f"  {name}: v4 adds {free:.1f} points of the "
                         f"{form:.1f} a changed intake form adds.")
    return lines


def amendment_lines(bumps: list) -> list:
    to_fail = sum(b["flipped_to_fail"] for b in bumps)
    to_pass = sum(b["flipped_to_pass"] for b in bumps)
    if to_fail and not to_pass:
        return ["  Every flip is toward FAIL and none toward PASS. These are "
                "not",
                "  errors: they are decisions issued correctly under one "
                "edition",
                "  that are unsupportable under the next, and nothing in the",
                "  checker's inputs changed, so nothing notices."]
    return [f"  {to_fail} flip(s) toward FAIL and {to_pass} toward PASS."]


def build_payload(names, cases, results=None, bumps=None) -> dict:
    """The published artifact, as an object.

    A function, not a literal inside main(), because
    scripts/check_artifact.py rebuilds it and compares it against the shipped
    audit/offline.json. If the gate built its own version of this structure it
    would be comparing the artifact against a second implementation, and the
    two could agree while both were wrong. There is one builder and the gate
    calls it.

    `results` and `bumps` are accepted so a caller that has already run the
    measurement does not run it twice.
    """
    if results is None:
        results = {n: measure(REGIMES[n], cases) for n in names}
    if bumps is None:
        bumps = [measure_bump(n, cases) for n in names if n in BUMPS]
    return {
        "note": "Constructed populations with known ground truth. "
                "Measures the checkers, not any real portfolio. The "
                "regimes are simplified encodings, not compliance "
                "products, and nothing here is legal advice.",
        "cases_per_regime": cases,
        "ordinance_counts": ordinance.counts(),
        "regimes": {n: {"citation": REGIMES[n].citation,
                        "rules": list(REGIMES[n].rules)} for n in names},
        "boundary": results,
        "amendments": bumps,
    }


def serialize(payload: dict) -> str:
    """The exact bytes the artifact is written as, so a comparison of files
    and a comparison of objects cannot disagree."""
    return json.dumps(payload, indent=2) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=600,
                    help="cases per regime (default 600)")
    ap.add_argument("--regime", default=None, choices=sorted(REGIMES))
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    names = [args.regime] if args.regime else list(REGIMES)

    print("ai-compliance-checker -- offline measurement")
    print(f"no model was called   cases per regime: {args.cases}")
    print()
    print("1. THE RATIO: what a regime states against what decides it")
    print(f"   the zoning ordinance states {ordinance.counts()['limits']} "
          f"limits and carries "
          f"{ordinance.counts()['definitions']} definitions "
          f"({ordinance.counts()['definitions_per_limit']} per limit)")
    print("   the other four regimes are encoded rule-by-rule; their "
          "equivalent is")
    print("   the precondition set, printed per regime below")
    print()

    results = {}
    for name in names:
        results[name] = measure(REGIMES[name], args.cases)

    print("=" * 74)
    print("2-4. THE BOUNDARY, PER REGIME")
    print("=" * 74)
    for name in names:
        print()
        print(format_report(results[name]))

    print()
    print("=" * 74)
    print("THE SAME MEASUREMENT, SIDE BY SIDE")
    print("=" * 74)
    print(cross_regime_table(results))
    print()
    print("\n".join(summary_lines(results)))

    print()
    print("=" * 74)
    print("5. THE AMENDMENT: what a routine edition change re-decides")
    print("=" * 74)
    bumps = [measure_bump(n, args.cases) for n in names if n in BUMPS]
    print(bump_report(bumps))
    print()
    print("\n".join(amendment_lines(bumps)))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(serialize(build_payload(names, args.cases,
                                                     results, bumps)))
        print(f"\nwrote {args.json}")
    # An honest checker that was wrong is a defect in the encoding, so the run
    # that printed it fails as well as saying so.
    return 1 if honest_errors(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

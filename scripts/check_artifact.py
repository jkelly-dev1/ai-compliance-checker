#!/usr/bin/env python3
"""Re-derive audit/offline.json from the code and require it to match.

The other three gates in CI do not look at the code that produced the figures:

  pytest                       asserts the invariants (never wrong, wrong
                               somewhere, never refuses). Those hold whatever
                               the population rates are.
  offline_demo.py --cases 150  proves the measurement still runs. Its own
                               comment says it "does not check the figures
                               match", and at 150 cases they need not.
  check_readme_numbers.py      rebuilds each README figure from
                               audit/offline.json. It proves the prose agrees
                               with the artifact, and says nothing about
                               whether the artifact agrees with the code.

This closes the first arrow of code -> artifact -> README. Without it, a
changed population constant (acc/hipaa.py's encryption rate from 0.63 to 0.40,
say) would leave every test passing, the demo exiting 0 and the README checker
green, while the figures the README publishes moved by points. The artifact is
only evidence while something re-derives it.

    python3 scripts/check_artifact.py           re-derive and compare
    python3 scripts/check_artifact.py --write   regenerate after an
                                                INTENDED change

It re-derives at the artifact's own cases_per_regime instead of a default,
so the comparison is against the population the artifact was written from and
cannot be made to pass by running it smaller.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Both, and not a scripts/__init__.py. Making scripts/ a package would give
# setuptools' flat-layout discovery a second top-level package beside acc/,
# which it refuses, and the documented install in README.md is
# `pip install -e ".[dev]"`.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from acc.regime import REGIMES                                   # noqa: E402
from offline_demo import build_payload, serialize                # noqa: E402

ARTIFACT = ROOT / "audit" / "offline.json"
MAX_REPORTED = 25


def differences(stored, fresh, path="") -> list:
    """Every leaf that differs, as a path a reader can open the file at."""
    if type(stored) is not type(fresh) and not (
            isinstance(stored, (int, float)) and isinstance(fresh, (int, float))):
        return [f"{path or '<root>'}: type {type(stored).__name__} -> "
                f"{type(fresh).__name__}"]
    if isinstance(stored, dict):
        out = []
        for key in sorted(set(stored) | set(fresh)):
            where = f"{path}.{key}" if path else key
            if key not in stored:
                out.append(f"{where}: absent from the artifact, code gives "
                           f"{fresh[key]!r}")
            elif key not in fresh:
                out.append(f"{where}: in the artifact as {stored[key]!r}, the "
                           f"code no longer produces it")
            else:
                out += differences(stored[key], fresh[key], where)
        return out
    if isinstance(stored, list):
        if len(stored) != len(fresh):
            return [f"{path}: {len(stored)} entries in the artifact, "
                    f"{len(fresh)} from the code"]
        out = []
        for i, (a, b) in enumerate(zip(stored, fresh)):
            out += differences(a, b, f"{path}[{i}]")
        return out
    return [] if stored == fresh else [f"{path}: {stored!r} -> {fresh!r}"]


def main() -> int:
    if not ARTIFACT.exists():
        print(f"FAIL  {ARTIFACT} does not exist. There is nothing to check, "
              f"which is not the same as nothing being wrong.")
        return 1
    stored = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    cases = stored.get("cases_per_regime")
    if not isinstance(cases, int) or cases <= 0:
        print(f"FAIL  the artifact does not say how many cases it was "
              f"written from (cases_per_regime={cases!r}), so it cannot be "
              f"re-derived and must not be reported as verified.")
        return 1

    # Which regimes, checked in both directions.
    #
    # Taking this list from the artifact alone is how a gate reports on a
    # target it never looked at. Delete a regime from audit/offline.json (from
    # `regimes`, `boundary` and `amendments`) and a gate that re-derives "the
    # regimes the artifact lists" would re-derive the four left, find them
    # identical, and print that the artifact matches the code exactly, saying
    # nothing about the regime it never read.
    #
    # The artifact must therefore account for every regime this code defines,
    # and every regime it names must be one this code has. Neither direction is
    # the other: the first catches evidence going missing, the second catches
    # an artifact written by a different tree.
    listed = list(stored.get("regimes") or ())
    unknown = [n for n in listed if n not in REGIMES]
    absent = [n for n in REGIMES if n not in listed]
    if unknown or absent:
        if unknown:
            print(f"FAIL  the artifact names regimes this code does not have: "
                  f"{unknown}")
        if absent:
            print(f"FAIL  this code measures regimes the artifact does not "
                  f"account for: {absent}. The artifact is not a record of "
                  f"this measurement, and re-deriving only what it happens to "
                  f"list would report agreement about the part it kept.")
        return 1

    # The same question of the section that holds the numbers, because
    # `regimes` is a two-line header and `boundary` is the evidence. An
    # artifact whose header lists five and whose boundary holds four would
    # otherwise pass the check above and then be compared field by field
    # against a payload built for five, where the difference reads as one
    # missing key rather than as a truncated artifact.
    measured = list(stored.get("boundary") or ())
    mismatched = sorted(set(listed) ^ set(measured))
    if mismatched:
        print(f"FAIL  the artifact's `regimes` header and its `boundary` "
              f"results do not describe the same run; they disagree about: "
              f"{mismatched}")
        return 1

    names = listed

    fresh = build_payload(names, cases)
    diffs = differences(stored, fresh)

    if "--write" in sys.argv:
        ARTIFACT.write_text(serialize(fresh))
        print(f"wrote {ARTIFACT} from the code at {cases} cases per regime "
              f"({len(diffs)} figures changed)")
        return 0

    print(f"re-derived {len(names)} regimes at {cases} cases per regime "
          f"from the code in acc/")
    if not diffs:
        print(f"OK    audit/offline.json matches the code exactly")
        return 0
    print(f"FAIL  {len(diffs)} differences between audit/offline.json and "
          f"what the code now produces:")
    for line in diffs[:MAX_REPORTED]:
        print(f"        {line}")
    if len(diffs) > MAX_REPORTED:
        print(f"        ... and {len(diffs) - MAX_REPORTED} more")
    print("\n      If the change was intended, re-run the measurement and the "
          "README\n      checker together:\n"
          "        python3 scripts/offline_demo.py --cases %d "
          "--json audit/offline.json\n"
          "        python3 scripts/check_readme_numbers.py" % cases)
    return 1


if __name__ == "__main__":
    sys.exit(main())

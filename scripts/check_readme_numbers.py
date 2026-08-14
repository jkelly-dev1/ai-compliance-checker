"""Re-derive every published number in README.md from audit/offline.json.

A README is prose and drifts; audit/offline.json is evidence and does not.
This script rebuilds each figure from the JSON and asserts the exact string is
present in the README, so a re-run that shifts a figure fails loudly instead of
leaving the document quietly wrong.

    python3 scripts/check_readme_numbers.py            check
    python3 scripts/check_readme_numbers.py --emit     print what it derives

Whitespace AND emphasis are normalized on both sides, so a reflowed paragraph
is not a false alarm that trains a reader to ignore the script.

The naive checker is reported by its error rate AND the other three by what
THEY DECIDE, which is the page's whole reporting rule: a checker that answers
everything and is right 78% of the time and one that answers a fifth and is
never wrong are not two points on one scale. This script derives each column
the way the page states it, and it does not invent a common metric.

Arithmetic is why the one-sentence headline is not derived. It states the two
ranges to whole percent, and the page does not round them one way: 14.7 is
written as 15 and 13.5 as 13. Encoding a rule the page does not follow would
be certifying a guess, and the exact values it summarizes are asserted to one
decimal in the boundary rows above, which is where a drift would show.

The count is printed whether OR NOT anything is missing, so a version of this
script that quietly stopped deriving half of them is visible rather than clean.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REGIMES = ["zoning", "hipaa", "pci_dss", "soc2", "card_act"]


def load():
    with open(os.path.join(ROOT, "audit", "offline.json"), encoding="utf-8") as fh:
        return json.load(fh)


def rows_boundary():
    """The boundary block: v1's error rate, then what v2, v4 and v3 decide."""
    b = load()["boundary"]
    out = []
    for regime in REGIMES:
        c = b[regime]["checkers"]
        out.append(("boundary:" + regime,
                    "%s wrong %s%% %s%% dec %s%% dec %s%%"
                    % (regime,
                       _trim(c["v1_naive"]["wrong_pct_of_decided"]),
                       _trim(c["v2_definition_aware"]["decided_pct"]),
                       _trim(c["v4_minimal"]["decided_pct"]),
                       _trim(c["v3_with_intake"]["decided_pct"]))))
    return out


def rows_amendments():
    """What a routine tightening re-decides, against decisions already issued.

    Every flip is toward fail AND none toward pass. The flipped_to_pass
    column is derived, so a run that broke that property would fail here
    instead of being described by a sentence that no longer holds.
    """
    out = []
    for a in load()["amendments"]:
        # The amendment text is NOT derived. Its block abbreviates it
        # ("height 30 ft -> 28 ft") while the JSON carries the full sentence, so
        # asserting it would be checking an abbreviation the evidence does not
        # contain. Five numbers on the row are what this rebuilds.
        out.append(("amendment:" + a["regime"],
                    "%s %d %d %d %d (%s%%)"
                    % (a["regime"], a["issued_decisions"],
                       a["flipped_to_fail"], a["flipped_to_pass"],
                       a["issued_decisions_now_wrong"],
                       _trim(a["now_wrong_pct"]))))
    return out


def prose_figures():
    d = load()
    b = d["boundary"]
    naive = [b[r]["checkers"]["v1_naive"]["wrong_pct_of_decided"] for r in REGIMES]
    honest = [b[r]["checkers"]["v2_definition_aware"]["decided_pct"] for r in REGIMES]
    out = [
        # The second headline is the one A compliance program would ACT on, so
        # both of its regimes are derived rather than the sentence being
        # trusted to still describe the run.
        ("prose:minimal",
         "takes HIPAA from %s%% to %s%% decided and PCI from %s%% to %s%%"
         % (_trim(b["hipaa"]["checkers"]["v2_definition_aware"]["decided_pct"]),
            _trim(b["hipaa"]["checkers"]["v4_minimal"]["decided_pct"]),
            _trim(b["pci_dss"]["checkers"]["v2_definition_aware"]["decided_pct"]),
            _trim(b["pci_dss"]["checkers"]["v4_minimal"]["decided_pct"]))),
        ("prose:cases",
         "The run uses %d cases per regime." % d["cases_per_regime"]),
    ]
    return out


def _trim(x):
    """One decimal always. The block writes 2.0 rather than 2, and a deriver
    that trimmed the zero would report a mismatch on a correct page."""
    return "%.1f" % x


def emit():
    return rows_boundary() + rows_amendments() + prose_figures()


def squash(text):
    # A space inside A parenthesis is column padding. The block writes
    # "30 ( 4.4%)" and "137 (15.1%)" to keep the column aligned, so the space
    # is layout rather than content and is removed on both sides.
    text = text.replace("**", "").replace("`", "").replace("( ", "(")
    return re.sub(r"\s+", " ", text)


def main():
    derived = emit()
    if "--emit" in sys.argv:
        for tag, row in derived:
            print("%s\n%s" % (tag, row))
        return 0
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
        readme = squash(fh.read())
    missing = [(t, r) for t, r in derived if squash(r) not in readme]
    for tag, row in missing:
        print("MISSING [%s]\n  %s" % (tag, row))
    tables = sum(1 for t, _ in derived if not t.startswith("prose:"))
    print("\n%d of %d derived figures found verbatim in README.md "
          "(%d table rows, %d in prose)"
          % (len(derived) - len(missing), len(derived), tables,
             len(derived) - tables))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())

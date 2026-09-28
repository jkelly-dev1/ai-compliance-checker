"""Re-derive README.md's measured figures from the evidence in audit/.

A README is prose and drifts; audit/*.json is evidence and does not. This
script rebuilds each figure from the JSON and asserts the exact string is
present in the README, so a re-run that shifts a figure fails loudly instead of
leaving a wrong figure in the document.

Sources: audit/offline.json for the offline measurement; the standing paid
runs, audit/real_run_hipaa.json and audit/real_run_soc2.json, for the paid
tables, read through the same functions scripts/real_run.py prints them with;
audit/real_run.json for the invalidated first run's parse rates; and the code
in acc/ for how many paid-run refusals v4 recovers, since that is a property
of the checker and not of the replies. SAMPLE_RUN.md is held to the paid
tables too.

Not derived: the test count; constants the page quotes from the code, the
rules or the pre-registration (citations, the ordinance's limit and
definition counts, the amendments' before-and-after values, the ZIP3 floor,
the sample sizes a test runs at, the 10% threshold); an illustrative accuracy
figure; a derived table cell restated in words rather than digits ("every BIM
submittal", "a quarter of the CAD ones"); and the figures that describe
history, the two defects the invariant caught and the old token cap. A derived
figure the page restates in digits is its own row, anchored by the words
around it, because one right copy elsewhere must not excuse a wrong one. The
README says so where it describes this script, and selfcheck.py's
readme-figure-coverage stage lists every figure outside the rows below.

    python3 scripts/check_readme_numbers.py            check
    python3 scripts/check_readme_numbers.py --emit     print what it derives

Whitespace AND emphasis are normalized on both sides, so a reflowed paragraph
is not a false alarm that trains a reader to ignore the script.

The naive checker is reported by its error rate AND the other three by what
THEY DECIDE, which is the page's whole reporting rule: a checker that answers
everything and is right 78% of the time and one that answers a fifth and is
never wrong are not two points on one scale. This script derives each column
the way the page states it, and it does not invent a common metric.

The one-sentence headline states its two ranges to one decimal, as the
boundary block does, so it is derived like every other figure.

The count is printed whether OR NOT anything is missing, so a version of this
script that stopped deriving half of them shows it in the count.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)

# The paid runs that stand, per regime. audit/real_run.json holds the first
# run of both, and its SOC 2 half was invalidated by the pre-registration.
STANDING = {"hipaa": "real_run_hipaa.json", "soc2": "real_run_soc2.json"}
FIRST_RUN = "real_run.json"

REGIMES = ["zoning", "hipaa", "pci_dss", "soc2", "card_act"]


def load():
    with open(os.path.join(ROOT, "audit", "offline.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    # The artifact must hold every regime this script derives from, and that
    # is checked here instead of being discovered at the first subscript. A
    # KeyError out of a list comprehension would name a key, not a problem: a
    # reader would see a broken script instead of a truncated artifact, and CI
    # would read the exit code as this script failing for its own reasons.
    missing = [r for r in REGIMES if r not in (data.get("boundary") or {})]
    if missing:
        raise SystemExit(
            f"audit/offline.json holds no results for {missing}, so this "
            f"script cannot rebuild the README figures that come from them. "
            f"The artifact is truncated, not the page. Regenerate it:\n"
            f"  python3 scripts/offline_demo.py --cases "
            f"{data.get('cases_per_regime', 600)} --json audit/offline.json")
    return data


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


def rows_error_direction():
    """The per-rule false-pass / false-fail block for HIPAA.

    The page's argument turns on this table ("HIPAA shows all three patterns
    in one regime"), so it is rebuilt here.
    """
    per_rule = load()["boundary"]["hipaa"]["per_rule"]["v1_naive"]
    return [("direction:hipaa:" + rule,
             "%s false pass %d false fail %d %s"
             % (rule, cell["false_pass"], cell["false_fail"],
                cell["direction"]))
            for rule, cell in per_rule.items()]


def rows_by_tier():
    """Decidability per evidence tier, for the two regimes the page prints.

    The block is laid out as two columns side by side, so each cell is derived
    on its own and found as a substring; squash() has already collapsed the
    column padding by then.
    """
    b = load()["boundary"]
    out = []
    for regime in ("zoning", "soc2"):
        for tier, (pct, seen) in _tier_shares(b[regime]).items():
            out.append(("tier:%s:%s" % (regime, tier),
                        "%s %.1f%% n=%d" % (tier, pct, seen)))
    return out


def _tier_shares(m):
    """tier -> (percent the honest checker decides, cases in that tier)."""
    out = {}
    for tier, cell in m["by_tier"]["v2_definition_aware"].items():
        seen = m["tier_mix"].get(tier, 0)
        total = seen * m["rules"]
        out[tier] = ((cell["decided"] / total * 100) if total else 0.0, seen)
    return out


def rows_refusal_causes():
    """What the refusals needed, as a block, so the order is pinned too.

    Deriving each row on its own would accept the right four names with two
    counts swapped, or a tie reordered, so the four rows are derived as one
    string and the ranking is part of the claim.
    """
    causes = list(load()["boundary"]["hipaa"]["refusal_causes"].items())[:4]
    return [("refusals:hipaa",
             " ".join("%d %s" % (count, cause) for cause, count in causes))]


def _paid(name):
    with open(os.path.join(ROOT, "audit", name), encoding="utf-8") as fh:
        return json.load(fh)


def _words(n):
    return {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
            6: "six", 7: "seven"}.get(n, str(n))


def paid_table_rows():
    """The two paid tables, line by line, as scripts/real_run.py prints them.

    Shared by README.md and SAMPLE_RUN.md, which both carry these lines.
    """
    import real_run                                     # noqa: PLC0415
    out = []
    for regime, name in STANDING.items():
        run = _paid(name)
        for model in run["models"]:
            c = real_run.refused_cell(run["records"], model, regime)
            out.append(("paid:refused:%s:%s" % (model, regime),
                        real_run.refused_line(model, regime, c)))
    for regime, name in STANDING.items():
        run = _paid(name)
        for model in run["models"]:
            c = real_run.decided_cell(run["records"], model, regime)
            out.append(("paid:decided:%s:%s" % (model, regime),
                        real_run.decided_line(model, regime, c)))
    return out


def rows_paid():
    """The paid-run prose and the comparison with the minimal checker."""
    import real_run                                     # noqa: PLC0415
    from acc.minimal import make_checker                # noqa: PLC0415
    from acc.regime import REGIMES as REGISTRY          # noqa: PLC0415
    from acc.verdict import REFUSE                      # noqa: PLC0415

    runs = {r: _paid(n) for r, n in STANDING.items()}
    cells = {(m, r): real_run.refused_cell(runs[r]["records"], m, r)
             for r in runs for m in runs[r]["models"]}
    agreed = [real_run.decided_cell(runs[r]["records"], m, r)
              for r in runs for m in runs[r]["models"]]
    cost = sum(_paid(n)["actual_cost_usd"]
               for n in sorted(set(STANDING.values()) | {FIRST_RUN}))

    # How many of the paid cases' refusals v4 recovers, from the checker.
    recovered = {}
    for r, run in runs.items():
        reg = REGISTRY[r]
        v4 = make_checker(reg)
        refused = decided = 0
        for _, sub in reg.corpus(run["cases"]):
            honest, minimal = reg.definition_aware(sub), v4(sub)
            for rule in reg.rules:
                if honest[rule].result == REFUSE:
                    refused += 1
                    decided += minimal[rule].result != REFUSE
        recovered[r] = 100.0 * decided / refused

    son, gpt = "claude-sonnet-5", "gpt-5.4"
    soc_g, soc_s = cells[(gpt, "soc2")], cells[(son, "soc2")]
    wrong_rules = soc_s["wrong_rules"]
    top_rule, top_n = wrong_rules.most_common(1)[0]
    spread = ("all %s criteria" % _words(len(REGISTRY["soc2"].rules))
              if len(wrong_rules) == len(REGISTRY["soc2"].rules)
              else "%d of the %d criteria" % (len(wrong_rules),
                                               len(REGISTRY["soc2"].rules)))

    first = _paid(FIRST_RUN)
    before = [real_run.parse_rate(first["records"], m, "soc2")["pct"]
              for m in first["models"]]
    after = [real_run.parse_rate(runs["soc2"]["records"], m, "soc2")
             for m in runs["soc2"]["models"]]
    stops = {m: p["stops"] for m, p in zip(runs["soc2"]["models"], after)}
    truncated = [r for r in runs["soc2"]["records"]
                 if r.get("model") == gpt and r.get("stop_reason") == "incomplete"]
    at_cap = all(r.get("output_tokens") == real_run.MAX_OUTPUT_TOKENS
                 for r in truncated)
    mean_out = (runs["soc2"]["tokens"][son + "_out"]
                / after[0]["calls"])

    # The model that decided the most of SOC 2's refusals, which the page
    # names by that property and not by name.
    most = max(runs["soc2"]["models"],
               key=lambda m: cells[(m, "soc2")]["decided"])
    refused_lines = [row for row in paid_table_rows()
                     if row[0].startswith("paid:refused:")]
    return refused_lines + [
        ("paid:restated-figure",
         "The refusal rates, the %.1f%% figure and the two models disagreeing"
         % soc_s["wrong_pct"]),
        ("paid:decided-most",
         "the model that decided most of them was wrong on %.1f%%."
         % cells[(most, "soc2")]["wrong_pct"]),
        ("paid:truncated-call",
         "and that call is the %.1f%%." % after[1]["pct"]),
        ("paid:cost-1", "at $%.2f across the three run files" % cost),
        ("paid:cost-2", "%d cases per regime, both providers, $%.2f total"
         % (runs["soc2"]["cases"], cost)),
        ("paid:agreement",
         "agreement was %s, with at most %s disagreement per cell"
         % (", ".join("%d/%d" % (a["agreed"], a["rows"])
                      for a in agreed[:-1])
            + " and %d/%d" % (agreed[-1]["agreed"], agreed[-1]["rows"]),
            _words(max(a["disagreed"] for a in agreed)))),
        ("paid:opposite",
         "`gpt-5.4` refuses %.1f%% of SOC 2's impossible cases; "
         "`claude-sonnet-5` decides %.1f%% of them"
         % (100.0 * soc_g["refused"] / soc_g["rows"],
            100.0 * soc_s["decided"] / soc_s["rows"])),
        ("paid:v4-row",
         "| refusals that were over-refusals (recovered by v4) | %.1f%% | %.1f%% |"
         % (recovered["hipaa"], recovered["soc2"])),
        ("paid:sonnet-row",
         "| wrong when deciding past a refusal -- sonnet | %.1f%% | %.1f%% |"
         % (cells[(son, "hipaa")]["wrong_pct"], soc_s["wrong_pct"])),
        ("paid:gpt-row",
         "| wrong when deciding past a refusal -- gpt-5.4 | %.1f%% | %.1f%% |"
         % (cells[(gpt, "hipaa")]["wrong_pct"], soc_g["wrong_pct"])),
        ("paid:cost-of-deciding",
         "Where %.1f%% of the refusals were the checker's own conservatism, "
         "deciding anyway cost %.1f%% and %.1f%%."
         % (recovered["hipaa"], cells[(son, "hipaa")]["wrong_pct"],
            cells[(gpt, "hipaa")]["wrong_pct"])),
        ("paid:sonnet-errors",
         "`claude-sonnet-5`'s %d wrong SOC 2 decisions fall on %s, the most "
         "on `%s` (%d)." % (soc_s["wrong"], spread, top_rule, top_n)),
        ("paid:parse-before",
         "The first SOC 2 run returned %g%% and %g%% unparseable."
         % tuple(before)),
        ("paid:parse-after",
         "both models failed to parse on %.1f%% and %.1f%% of calls"
         % tuple(p["pct"] for p in after)),
        ("paid:stops",
         "the stop reasons are `end_turn` %d for `claude-sonnet-5` and, for "
         "`gpt-5.4`, `completed` %d and `incomplete` %d."
         % (stops[son]["end_turn"], stops[gpt]["completed"],
            stops[gpt]["incomplete"])),
        ("paid:cap",
         "All %s carry `output_tokens` of exactly %s (`MAX_OUTPUT_TOKENS`"
         % (_words(len(truncated)),
            "{:,}".format(real_run.MAX_OUTPUT_TOKENS) if at_cap
            else "different sizes")),
        ("paid:mean-tokens",
         "a model averaging %s output tokens on that prompt"
         % "{:,}".format(round(mean_out))),
    ]


def prose_figures():
    d = load()
    b = d["boundary"]
    naive = [b[r]["checkers"]["v1_naive"]["wrong_pct_of_decided"] for r in REGIMES]
    honest = [b[r]["checkers"]["v2_definition_aware"]["decided_pct"] for r in REGIMES]
    zoning = b["zoning"]
    pdf = sum(zoning["tier_mix"].get(t, 0) for t in ("pdf_vector", "pdf_scan"))
    amend = {a["regime"]: a for a in d["amendments"]}
    out = [
        ("prose:headline",
         "is wrong on %s%% to %s%% of its decisions, and a checker that "
         "refuses when the evidence cannot support a decision is never wrong "
         "while still deciding %s%% to %s%% of them"
         % (_trim(min(naive)), _trim(max(naive)),
            _trim(min(honest)), _trim(max(honest)))),
        ("prose:decisions",
         "%d cases times %s rules is %d zoning decisions"
         % (d["cases_per_regime"], _words(zoning["rules"]),
            d["cases_per_regime"] * zoning["rules"])),
        ("prose:pdf-share",
         "zero of the two PDF formats, which are %s%% of the population"
         % _trim(100.0 * pdf / d["cases_per_regime"])),
        ("prose:datasets",
         "%d datasets declared de-identified"
         % b["hipaa"]["per_rule"]["v1_naive"]["de_identification"]["false_pass"]),
        ("prose:blast-radius",
         "re-decides %s%% of the decisions it had issued; a ten-thousand-person "
         "change to a ZIP3 floor re-decides %s%%"
         % (_trim(amend["card_act"]["now_wrong_pct"]),
            _trim(amend["hipaa"]["now_wrong_pct"]))),
        # The second headline is the one a compliance program would ACT on, so
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
        # The two regime totals the tier block explains, restated in the
        # sentence under it. Each is anchored by the words around it, so a
        # wrong copy here is not excused by a right copy in the table.
        ("prose:zoning-total",
         "Zoning's %s%% is every BIM submittal"
         % _trim(b["zoning"]["checkers"]["v2_definition_aware"]["decided_pct"])),
        ("prose:soc2-total",
         "SOC 2's %s%% is %s"
         % (_trim(b["soc2"]["checkers"]["v2_definition_aware"]["decided_pct"]),
            _all_or_nothing(_tier_shares(b["soc2"])))),
        ("prose:invariants", _invariant_coverage()),
    ]
    return out


def _all_or_nothing(shares):
    """"100% of one tier and 0% of the other three", or what the tiers
    actually hold when that is no longer true of them."""
    pcts = sorted((pct for pct, _ in shares.values()), reverse=True)
    full = sum(1 for p in pcts if p == 100.0)
    none = sum(1 for p in pcts if p == 0.0)
    if full + none == len(pcts) and full and none:
        return "100%% of %s tier%s and 0%% of the other %s" % (
            _words(full), "" if full == 1 else "s", _words(none))
    return "split across tiers as " + ", ".join("%.1f%%" % p for p in pcts)


def _invariant_coverage():
    """How many tests in tests/test_invariants.py run over every regime.

    Read off the test file's syntax tree: a test runs over every regime when
    it is parametrized over REGIME_NAMES.
    """
    import ast
    with open(os.path.join(ROOT, "tests", "test_invariants.py"),
              encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    tests = [f for f in tree.body
             if isinstance(f, ast.FunctionDef) and f.name.startswith("test_")]
    every = [f for f in tests
             if any("REGIME_NAMES" in ast.unparse(d) for d in f.decorator_list)]
    return ("Of the %d tests in tests/test_invariants.py, %d run over all five "
            "regimes" % (len(tests), len(every)))


def _trim(x):
    """One decimal always. The block writes 2.0 rather than 2, and a deriver
    that trimmed the zero would report a mismatch on a correct page."""
    return "%.1f" % x


def emit():
    return (rows_boundary() + rows_amendments() + rows_error_direction()
            + rows_by_tier() + rows_refusal_causes() + prose_figures()
            + rows_paid())


def squash(text):
    # A space inside a parenthesis is column padding. The block writes
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
    # An empty derivation is not a figure that matched. `"" in readme` is
    # True of every document ever written, so a deriver that stopped producing
    # anything (a slice that became [:0], a table that lost its rows) would be
    # counted as found and reported inside the "N of N" total.
    empty = [(t, r) for t, r in derived if not squash(r).strip()]
    for tag, _ in empty:
        print("EMPTY   [%s]\n  this deriver produced nothing to look for, so "
              "it asserts nothing about the page" % tag)
    missing = [(t, r) for t, r in derived
               if (t, r) not in empty and squash(r) not in readme]
    for tag, row in missing:
        print("MISSING [%s]\n  %s" % (tag, row))
    missing = empty + missing
    tables = sum(1 for t, _ in derived if not t.startswith("prose:"))
    print("\n%d of %d derived figures found verbatim in README.md "
          "(%d table rows and paid-run rows, %d in prose)"
          % (len(derived) - len(missing), len(derived), tables,
             len(derived) - tables))
    with open(os.path.join(ROOT, "SAMPLE_RUN.md"), encoding="utf-8") as fh:
        sample = squash(fh.read())
    sample_rows = paid_table_rows()
    sample_missing = [(t, r) for t, r in sample_rows
                      if squash(r) not in sample]
    for tag, row in sample_missing:
        print("MISSING in SAMPLE_RUN.md [%s]\n  %s" % (tag, row))
    print("%d of %d paid-table lines found verbatim in SAMPLE_RUN.md"
          % (len(sample_rows) - len(sample_missing), len(sample_rows)))
    return 1 if missing or sample_missing else 0


if __name__ == "__main__":
    sys.exit(main())

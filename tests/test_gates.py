"""The gates' own exit codes, which are verdicts and not just terminations.

`scripts/check_artifact.py` and `scripts/real_run.py` both return a non-zero
code to mean something ("the published figures do not match the code", "this
run would overwrite stored evidence"), and a CI step or an operator reads that
code as the answer. Without a test calling `main()`, flipping a `return 1` to
`return 0` would leave the step green while the script printed its own failure
into the log. A gate whose verdict is untested can be disabled without
breaking anything.

The scripts are not a package, because a `scripts/__init__.py` would give
setuptools' flat-layout discovery a second top-level package beside `acc/` and
break the documented `pip install -e ".[dev]"`. They are loaded by path here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_artifact                                            # noqa: E402
import check_readme_numbers                                      # noqa: E402
import real_run                                                  # noqa: E402


def test_the_artifact_gate_passes_on_the_shipped_tree(capsys):
    """The published artifact must match what the code produces right now."""
    assert check_artifact.main() == 0
    assert "matches the code exactly" in capsys.readouterr().out


def test_the_artifact_gate_fails_when_a_published_figure_moves(
        tmp_path, monkeypatch, capsys):
    """One changed number must be a non-zero exit, not a printed grumble.

    ARTIFACT is a module global that `main()` looks up when it runs, so it is
    patched on the module, the binding the code under test actually resolves.
    Tampering with a copy keeps the shipped artifact untouched.
    """
    stored = json.loads((ROOT / "audit" / "offline.json").read_text())
    before = stored["boundary"]["hipaa"]["checkers"]["v1_naive"]["wrong"]
    stored["boundary"]["hipaa"]["checkers"]["v1_naive"]["wrong"] = before + 1
    tampered = tmp_path / "offline.json"
    tampered.write_text(json.dumps(stored, indent=2) + "\n")
    monkeypatch.setattr(check_artifact, "ARTIFACT", tampered)

    assert check_artifact.main() == 1
    out = capsys.readouterr().out
    # The name of the figure that moved, not just "something differs".
    assert "boundary.hipaa.checkers.v1_naive.wrong" in out
    assert str(before) in out


def test_the_artifact_gate_refuses_what_it_cannot_re_derive(
        tmp_path, monkeypatch, capsys):
    """An artifact that does not say how many cases it was written from cannot
    be re-derived, and MUST NOT be reported as verified. This is the failure
    mode the gate is most exposed to: every other way of going wrong prints
    something, and this one would print the reassuring line."""
    stored = json.loads((ROOT / "audit" / "offline.json").read_text())
    del stored["cases_per_regime"]
    broken = tmp_path / "offline.json"
    broken.write_text(json.dumps(stored))
    monkeypatch.setattr(check_artifact, "ARTIFACT", broken)

    assert check_artifact.main() == 1
    out = capsys.readouterr().out
    assert "cannot be re-derived" in out
    assert "matches the code exactly" not in out


def test_the_artifact_gate_refuses_a_missing_artifact(
        tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_artifact, "ARTIFACT", tmp_path / "absent.json")
    assert check_artifact.main() == 1
    assert "does not exist" in capsys.readouterr().out


def test_the_artifact_gate_refuses_an_artifact_missing_a_regime(
        tmp_path, monkeypatch, capsys):
    """The gate must not report on a target it did not read.

    If the regime list came from the artifact alone, deleting a whole regime
    from audit/offline.json would leave the gate re-deriving the four that
    remained, finding them identical, and printing "matches the code exactly"
    about four fifths of the measurement. A gate that narrows its own scope to
    whatever it was handed cannot report that something is missing, because
    the missing thing is what defined the scope.
    """
    stored = json.loads((ROOT / "audit" / "offline.json").read_text())
    dropped = "card_act"
    assert dropped in stored["boundary"], "fixture stale: no such regime"
    for section in ("regimes", "boundary"):
        stored[section].pop(dropped)
    stored["amendments"] = [a for a in stored["amendments"]
                            if a["regime"] != dropped]
    truncated = tmp_path / "offline.json"
    truncated.write_text(json.dumps(stored, indent=2) + "\n")
    monkeypatch.setattr(check_artifact, "ARTIFACT", truncated)

    assert check_artifact.main() == 1
    out = capsys.readouterr().out
    assert dropped in out
    assert "does not account for" in out
    assert "matches the code exactly" not in out


def test_the_artifact_gate_refuses_a_header_that_disagrees_with_the_results(
        tmp_path, monkeypatch, capsys):
    """`regimes` is a header and `boundary` is the evidence. An artifact whose
    header claims five while its results hold four is not a record of any run,
    and saying so names the problem better than a field-by-field diff would."""
    stored = json.loads((ROOT / "audit" / "offline.json").read_text())
    stored["boundary"].pop("card_act")
    skewed = tmp_path / "offline.json"
    skewed.write_text(json.dumps(stored, indent=2) + "\n")
    monkeypatch.setattr(check_artifact, "ARTIFACT", skewed)

    assert check_artifact.main() == 1
    assert "do not describe the same run" in capsys.readouterr().out


def test_the_readme_checker_names_a_truncated_artifact(tmp_path, monkeypatch):
    """Its companion: the README deriver names a truncated artifact.

    A KeyError out of a list comprehension would name a key, not a problem: a
    reader would see a broken script instead of a truncated artifact, and CI
    would read the exit code as this script failing instead of the evidence
    being incomplete.
    """
    stored = json.loads((ROOT / "audit" / "offline.json").read_text())
    stored["boundary"].pop("card_act")
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / "offline.json").write_text(json.dumps(stored, indent=2) + "\n")
    monkeypatch.setattr(check_readme_numbers, "ROOT", str(tmp_path))

    # `match=` and not a bare `raises`. SystemExit is what pytest itself
    # raises on --exitfirst, what argparse raises on a bad flag, and what any
    # unrelated breakage in load() would raise; a bare `raises(SystemExit)`
    # would stay green on every one of them and report that this behavior is
    # pinned. The pattern names the regime and the diagnosis.
    with pytest.raises(SystemExit, match=r"card_act.*truncated"):
        check_readme_numbers.load()


def test_the_readme_checker_counts_the_invariant_tests_from_the_file(
        tmp_path, monkeypatch, capsys):
    """The count of tests that run over every regime is read off the test file.

    One more parametrized test in a copy of tests/test_invariants.py must make
    the unchanged README fail the check.

    Mutation check: return a fixed sentence from `_invariant_coverage` and
    this goes red, because the stale README then passes.
    """
    import shutil

    shutil.copytree(ROOT / "audit", tmp_path / "audit")
    shutil.copytree(ROOT / "tests", tmp_path / "tests",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "README.md", tmp_path / "README.md")
    monkeypatch.setattr(check_readme_numbers, "ROOT", str(tmp_path))
    assert check_readme_numbers.main() == 0
    capsys.readouterr()

    invariants = tmp_path / "tests" / "test_invariants.py"
    invariants.write_text(
        invariants.read_text(encoding="utf-8")
        + "\n\n@pytest.mark.parametrize(\"name\", REGIME_NAMES)\n"
          "def test_one_more(name):\n    pass\n", encoding="utf-8")
    assert check_readme_numbers.main() != 0
    assert "invariants" in capsys.readouterr().out


def test_the_readme_checker_still_derives_every_block():
    """The deriver still derives every family of figures.

    The script prints "N of N found" whether or not anything is missing. That
    count is visible to a reader, not to a gate: drop a whole family of
    figures and it prints a smaller "N of N found" just as happily.

    This asserts that the families are all present, by tag, instead of a
    hand-typed total that would have to be edited every time a figure is
    added.
    """
    tags = {tag.split(":", 1)[0] for tag, _ in check_readme_numbers.emit()}
    assert tags == {"boundary", "amendment", "direction", "tier", "refusals",
                    "prose"}, (
        f"a family of derived figures has disappeared from emit(): {tags}. "
        f"The script will go on reporting 'N of N found' about whatever is "
        f"left.")
    assert check_readme_numbers.main() == 0


def test_the_paid_run_refuses_to_overwrite_a_stored_run(
        tmp_path, monkeypatch, capsys):
    """`audit/real_run.json` is the run kept BECAUSE it was invalidated, and it
    is also the default `--out`. The documented `--confirm` command must not
    spend money to destroy it.

    `_api_key` is replaced on the module so that a REGRESSION here fails loudly
    instead of reaching a provider: if the guard ever stops firing, the next
    thing `main()` does is build a client, and this makes that an immediate,
    named test failure rather than a request. Asserting only the return code
    would let a regression be paid for once before anyone saw it.
    """
    def _refuse(name):
        raise AssertionError(
            f"the overwrite guard did not fire: main() got as far as asking "
            f"for {name}, which is one step from spending money")

    monkeypatch.setattr(real_run, "_api_key", _refuse)
    existing = tmp_path / "already_here.json"
    existing.write_text("{}")
    monkeypatch.setattr(sys, "argv", [
        "real_run.py", "--cases", "1", "--models", "claude-sonnet-5",
        "--regimes", "hipaa", "--confirm", "--out", str(existing)])

    assert real_run.main() == 2
    out = capsys.readouterr().out
    assert "REFUSING TO START" in out and str(existing) in out
    assert existing.read_text() == "{}"      # and it is still there


def test_the_paid_run_still_writes_where_nothing_exists(
        tmp_path, monkeypatch, capsys):
    """The guard must not block a first run. Without --confirm nothing is sent,
    so this exercises the path up to the point money would be spent."""
    monkeypatch.setattr(sys, "argv", [
        "real_run.py", "--cases", "1", "--models", "claude-sonnet-5",
        "--regimes", "hipaa", "--out", str(tmp_path / "new.json")])
    assert real_run.main() == 0
    assert "Dry run" in capsys.readouterr().out

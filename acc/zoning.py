"""ZONING: three checkers over the same submittals, differing only in honesty.

V1 NAIVE            implements the six limits against the fields a flattened
                    submittal actually gives you. Every line of it is a
                    defensible-looking implementation and every one embeds a
                    definitional error. It always answers.
V2 DEFINITION-AWARE implements the ordinance as written, declares a
                    PRECONDITION SET per rule, and REFUSES when the submittal
                    does not carry the inputs. It is never wrong and it decides
                    a minority of cases.
V3 WITH INTAKE      the same checker, given five fields that a changed intake
                    form would require. Only the judgment-dependent cases
                    remain refused.

The Verdict type has three values. A checker that can only say PASS or FAIL
has to guess, and the guess is invisible in the output. REFUSE is a
first-class result here, it is reported in every table, and the measurement
that matters is decided-and-never-wrong rather than accuracy.

Why v1 is not a straw man. It is what you get when a competent engineer
implements the six limits from the summary card against the data on hand. It
measures setbacks from the recorded boundary to the outermost line on the plan,
height from the ridge to the spot elevation at the street, coverage from the
roof outline over the recorded lot area, and stories from the level count. Each
is the obvious reading. The errors come from the ordinance's definitions, not
from carelessness, so more careful implementation of the same inputs does not
fix them.
"""

from __future__ import annotations

from .ordinance import (CITATION, LIMITS, MEZZANINE_MAX_FRACTION,
                        PROJECTION_ALLOWANCES, RULE_PRECONDITIONS, RULES,
                        WALKOUT_EXPOSURE_IS_STORY_FT)
from .parcels import FORMATS, Submittal, corpus as _corpus
from .verdict import FAIL, PASS, REFUSE, Verdict

REGIME = "zoning"
EVIDENCE_TIERS = FORMATS


def _ok(rule, cond, why=""):
    return Verdict(rule, PASS if cond else FAIL, why)


# ---------------------------------------------------------------- V1 NAIVE

def check_naive(s: Submittal) -> dict:
    """The six limits, against the fields a flattened submittal carries."""
    out = {}

    # Setbacks from the recorded boundary to the outermost line on the plan.
    # The outermost line includes eaves and porch roofs the ordinance
    # expressly allows to project, and on a corner lot the side yard is
    # treated as a side yard.
    out["setback"] = _ok(
        "setback",
        s.recorded_boundary_front_ft >= LIMITS["front_yard_ft"]
        and s.recorded_boundary_side_ft >= LIMITS["side_yard_ft"]
        and s.recorded_boundary_rear_ft >= LIMITS["rear_yard_ft"],
        "measured to the roof outline from the recorded boundary")

    # Height from the ridge to the spot elevation at the front property line.
    # Wrong datum and wrong target, and the two errors push in OPPOSITE
    # directions, so neither a safety margin nor a sign flip repairs it.
    out["height"] = _ok(
        "height",
        (s.ridge_height_ft - s.front_spot_elevation_ft) <= LIMITS["height_ft"],
        "ridge above the front spot elevation")

    # Coverage from the roof outline over the recorded lot area.
    out["coverage"] = _ok(
        "coverage",
        (s.roof_outline_sf / s.lot_area_sf * 100.0) <= LIMITS["coverage_pct"],
        "roof outline over recorded lot area")

    # Stories from the level count.
    out["stories"] = _ok(
        "stories", s.level_count <= LIMITS["stories_above_grade"],
        "level count as filed")
    return out


# ------------------------------------------------- V2 DEFINITION-AWARE

def _refuse(rule: str, missing) -> Verdict:
    return Verdict(rule, REFUSE,
                   "submittal does not carry: " + ", ".join(missing),
                   tuple(missing))


def _setback(s: Submittal) -> Verdict:
    need = RULE_PRECONDITIONS["setback"]
    miss = [m for m in s.missing(need) if m != "lot_type"]   # always filed
    if miss:
        return _refuse("setback", miss)
    wall = s.fields["wall_polygon"]
    proj = s.fields["projection_schedule"]

    front_req = LIMITS["front_yard_ft"]
    side_req = (LIMITS["front_yard_ft"] if s.lot_type == "corner"
                else LIMITS["side_yard_ft"])
    rear_req = LIMITS["rear_yard_ft"]

    front = wall["front_ft"]

    # Which yard each projection is actually built into, as the schedule
    # states it. This is evidence, not knowledge: the checker reads it off the
    # submittal it was handed, the same way it reads the depths. A schedule
    # that lists a projection without saying where it is cannot be applied,
    # so the rule refuses instead of charging that projection nowhere.
    placement = proj.get("yards", {})
    unplaced = [k for k in PROJECTION_ALLOWANCES
                if proj.get(k, 0.0) > 0 and k not in placement]
    if unplaced:
        return _refuse("setback", ["projection_schedule"])

    # A projection inside its own allowance does not encroach. One outside it
    # does, by the excess. One that is not in this yard at all does not
    # encroach on it, whatever the allowance table says about the kind.
    def excess(kind: str, yard: str) -> float:
        allow = PROJECTION_ALLOWANCES.get(kind, {"ft": 0.0, "yards": ()})
        depth = proj.get(kind, 0.0)
        if depth <= 0:
            return 0.0
        if yard not in placement.get(kind, ()):
            return 0.0                      # not built into this yard
        if yard not in allow["yards"]:
            return depth                    # no allowance in this yard at all
        if kind == "bay_window" and proj.get("bay_width_ft", 0.0) > \
                allow.get("max_width_ft", 1e9):
            return depth                    # too wide to qualify
        if kind == "deck" and s.fields.get("deck_height_in", 0.0) > \
                allow.get("max_height_in", 1e9):
            return depth                    # too high to qualify
        return max(0.0, depth - allow["ft"])

    front_enc = max(excess(k, "front") for k in PROJECTION_ALLOWANCES)
    side_enc = max(excess(k, "side") for k in PROJECTION_ALLOWANCES)
    rear_enc = max(excess(k, "rear") for k in PROJECTION_ALLOWANCES)

    ok = ((front - front_enc) >= front_req
          and (wall["side_ft"] - side_enc) >= side_req
          and (wall["rear_ft"] - rear_enc) >= rear_req)
    return _ok("setback", ok, "wall line with projection allowances applied")


def _height(s: Submittal) -> Verdict:
    need = RULE_PRECONDITIONS["height"]
    miss = s.missing(need) + ([] if "ridge_height_ft" not in need else [])
    miss = [m for m in miss if m != "ridge_height_ft"]   # always filed
    if miss:
        return _refuse("height", miss)
    grades = s.fields["perimeter_grades_ft"]
    grade_plane = sum(grades) / len(grades)
    mean_h = (s.ridge_height_ft + s.fields["eave_height_ft"]) / 2.0
    return _ok("height", (mean_h - grade_plane) <= LIMITS["height_ft"],
               "grade plane to mean of eave and ridge")


def _coverage(s: Submittal) -> Verdict:
    need = RULE_PRECONDITIONS["coverage"]
    miss = [m for m in s.missing(need) if m != "lot_area_sf"]
    if miss:
        return _refuse("coverage", miss)
    wall = s.fields["wall_polygon"]
    proj = s.fields["projection_schedule"]
    covered = (wall["area_sf"] + proj.get("porch_area_sf", 0.0)
               + s.fields.get("accessory_footprint_sf", 0.0))
    strip = (s.fields.get("access_strip_ft", 0.0) * 20.0
             if s.lot_type == "flag" else 0.0)
    net = s.lot_area_sf - strip
    return _ok("coverage", (covered / net * 100.0) <= LIMITS["coverage_pct"],
               "wall plus covered porch plus accessory over net lot area")


def _stories(s: Submittal) -> Verdict:
    need = [n for n in RULE_PRECONDITIONS["stories"] if n != "level_count"]
    miss = s.missing(need)
    if miss:
        return _refuse("stories", miss)
    stories = s.level_count
    mezz = s.fields.get("mezzanine_area_sf", 0.0)
    if mezz > 0:
        below = s.fields.get("room_below_area_sf") or 1.0
        if mezz / below <= MEZZANINE_MAX_FRACTION:
            stories -= 1
    if s.fields.get("basement_rear_exposure_ft", 0.0) >= \
            WALKOUT_EXPOSURE_IS_STORY_FT:
        stories += 1
    return _ok("stories", stories <= LIMITS["stories_above_grade"],
               "conditional definitions applied to the level count")


def check_definition_aware(s: Submittal) -> dict:
    return {"setback": _setback(s), "height": _height(s),
            "coverage": _coverage(s), "stories": _stories(s)}


# ------------------------------------------------------ V3 WITH INTAKE

# The five fields a changed intake form would require. Chosen because they are
# FORM FIELDS, not judgments: an applicant can supply every one of them, and
# nothing here asks anyone to decide anything.
INTAKE_ADDITIONS = ("wall_polygon", "projection_schedule",
                    "perimeter_grades_ft", "eave_height_ft",
                    "access_strip_ft")


def with_intake(s: Submittal, truth) -> Submittal:
    """Return the submittal as it would arrive under the stricter intake form.

    The values come from the truth object, and that is legitimate here for one
    specific reason: the question being asked is "if the applicant supplied
    these, how much could be decided?", and an applicant supplying them
    supplies the real ones. It is NOT legitimate anywhere else in this
    repository, so this is the only function that takes a Parcel.
    """
    extra = {
        "wall_polygon": {"front_ft": truth.wall_front_ft,
                         "side_ft": truth.wall_side_ft,
                         "rear_ft": truth.wall_rear_ft,
                         "area_sf": truth.wall_footprint_sf},
        "projection_schedule": dict(truth.projections),
        "perimeter_grades_ft": list(truth.perimeter_grades_ft),
        "eave_height_ft": truth.eave_height_ft,
        "access_strip_ft": truth.access_strip_ft,
    }
    merged = dict(s.fields)
    for k in INTAKE_ADDITIONS:
        merged.setdefault(k, extra[k])
    return Submittal(
        parcel_id=s.parcel_id, submittal_format=s.submittal_format,
        lot_type=s.lot_type,
        recorded_boundary_front_ft=s.recorded_boundary_front_ft,
        recorded_boundary_side_ft=s.recorded_boundary_side_ft,
        recorded_boundary_rear_ft=s.recorded_boundary_rear_ft,
        ridge_height_ft=s.ridge_height_ft,
        front_spot_elevation_ft=s.front_spot_elevation_ft,
        roof_outline_sf=s.roof_outline_sf, lot_area_sf=s.lot_area_sf,
        level_count=s.level_count, fields=merged)


CHECKERS = {
    "v1_naive": check_naive,
    "v2_definition_aware": check_definition_aware,
}


# ------------------------------------------------------ THE REGIME INTERFACE
# Thin adapters so acc/regime.py can treat every regime identically. They exist
# because the harness is written ONCE, against these names, rather than five
# times against five modules.

def corpus(n: int):
    """`n` (truth, submittal) pairs."""
    return _corpus(n)


def truth_of(parcel) -> dict:
    return parcel.truth()


def tier_of(submittal) -> str:
    return submittal.submittal_format

"""The ordinance: six limits, ten definitions, and the ratio is the point.

Northgate r-1 is synthetic and is not a quotation of any jurisdiction. It is
modeled on patterns common in suburban single-family zoning because the
STRUCTURE of the difficulty is identical everywhere; the specific numbers are
not the finding and are not meant to be cited as anyone's code.

Why the limits and the definitions are separate objects in this file. six
numbers. The definitions are what decides whether a given building satisfies
them, and there are more of them, they are conditional, and they are what a
checker gets wrong. Keeping them in one blob would hide exactly the thing this
repository measures, so LIMITS and DEFINITIONS are counted separately and the
ratio is reported.

Every Definition here exists because it changes an answer. Nothing is included
for flavor. Each carries the field it depends on, and a submittal that lacks
that field cannot be decided under this ordinance, which is the precondition
machinery in acc/checkers.py, not a limitation of it.
"""

from __future__ import annotations

from dataclasses import dataclass

JURISDICTION = "Northgate"
ZONE = "R-1"
EDITION = "2024"
# Every regime carries one, so the harness can print where a rule came from.
# This one is the odd case and says so: the others cite a real instrument.
CITATION = "Northgate R-1, a synthetic ordinance -- not any jurisdiction's code"

# -- the six limits ----------------------------------------------------------
# What fits on a summary card. A naive checker implements exactly these and
# looks complete.
LIMITS = {
    "front_yard_ft": 25.0,
    "side_yard_ft": 5.0,
    "rear_yard_ft": 20.0,
    "height_ft": 30.0,
    "coverage_pct": 40.0,
    "stories_above_grade": 2,
}


@dataclass(frozen=True)
class Definition:
    """One definitional rule, and what a submittal must carry to apply it.

    `requires` is the whole reason this class exists. A checker that cannot
    see these fields cannot apply the definition, and a checker that proceeds
    anyway is guessing with a straight face.
    """

    key: str
    text: str
    requires: tuple
    # Which limit it modifies. Several definitions bear on one limit, so the
    # count of definitions exceeds the count of limits.
    bears_on: str


# -- the ten definitions -----------------------------------------------------
DEFINITIONS = (
    Definition(
        "eave_projection",
        "Eaves may project 2 ft into any required yard.",
        ("projection_schedule",), "setback"),
    Definition(
        "bay_window_projection",
        "Bay windows may project 2 ft into any required yard if not more "
        "than 10 ft wide.",
        ("projection_schedule",), "setback"),
    Definition(
        "porch_projection",
        "A covered porch may project 8 ft into the required FRONT yard only.",
        ("projection_schedule",), "setback"),
    Definition(
        "deck_projection",
        "An uncovered deck may project 6 ft into the required REAR yard "
        "only, and only if not more than 30 in above grade.",
        ("projection_schedule", "deck_height_in"), "setback"),
    Definition(
        "cantilever_no_allowance",
        "A cantilevered floor has no projection allowance and is treated as "
        "building wall.",
        ("projection_schedule",), "setback"),
    Definition(
        "corner_lot_second_frontage",
        "On a corner lot the street-side yard takes the FRONT setback.",
        ("lot_type",), "setback"),
    Definition(
        "flag_lot_reference_line",
        "On a flag lot, setbacks are measured from the boundary of the "
        "buildable portion, not from the end of the access strip.",
        ("lot_type", "access_strip_ft"), "setback"),
    Definition(
        "height_datum_and_target",
        "Height is measured from the GRADE PLANE to the MEAN height between "
        "eave and ridge.",
        ("perimeter_grades_ft", "eave_height_ft"), "height"),
    Definition(
        "mezzanine_not_a_story",
        "A mezzanine is not a story if not more than 1/3 the area of the "
        "room below.",
        ("mezzanine_area_sf", "room_below_area_sf"), "stories"),
    Definition(
        "walkout_basement_is_a_story",
        "A walkout basement counts as a story above grade plane once the "
        "exposure at the rear reaches 6 ft.",
        ("basement_rear_exposure_ft",), "stories"),
)

# The projection allowances, as data rather than as branches, so that a rule
# change is an edit to a table and the checker does not have to be re-read.
PROJECTION_ALLOWANCES = {
    "eave": {"ft": 2.0, "yards": ("front", "side", "rear")},
    "bay_window": {"ft": 2.0, "yards": ("front", "side", "rear"),
                   "max_width_ft": 10.0},
    "porch": {"ft": 8.0, "yards": ("front",)},
    "deck": {"ft": 6.0, "yards": ("rear",), "max_height_in": 30.0},
    "cantilever": {"ft": 0.0, "yards": ()},
}

WALKOUT_EXPOSURE_IS_STORY_FT = 6.0
MEZZANINE_MAX_FRACTION = 1.0 / 3.0

# Which fields each RULE needs before any honest checker may decide it. Derived
# from DEFINITIONS rather than written twice, because the two drifting apart is
# how a precondition set silently stops matching the rules it gates.
RULE_PRECONDITIONS = {
    "setback": tuple(sorted({r for d in DEFINITIONS if d.bears_on == "setback"
                             for r in d.requires} | {"wall_polygon"})),
    "height": tuple(sorted({r for d in DEFINITIONS if d.bears_on == "height"
                            for r in d.requires} | {"ridge_height_ft"})),
    "coverage": ("wall_polygon", "projection_schedule", "lot_area_sf",
                 "access_strip_ft", "accessory_footprint_sf"),
    "stories": tuple(sorted({r for d in DEFINITIONS if d.bears_on == "stories"
                             for r in d.requires} | {"level_count"})),
}

RULES = tuple(RULE_PRECONDITIONS)


def counts() -> dict:
    """The ratio this repository is named after, computed not asserted."""
    return {
        "limits": len(LIMITS),
        "definitions": len(DEFINITIONS),
        "definitions_per_limit": round(len(DEFINITIONS) / len(LIMITS), 2),
        "rules": len(RULES),
    }

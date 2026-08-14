"""Synthetic parcels and submittals, with the true answer known by construction.

Why synthetic. Every measurement here is "was this decision right?", and that
needs a population whose correct verdict is known independently of any checker.
A real permit corpus gives you the jurisdiction's decision, which is the thing
under test, and gives it after appeals, amendments and negotiation. Grading a
checker against that would be grading it against a different process.

Two objects per Parcel, and keeping them apart is the whole design:

  Parcel     the physical truth. Wall polygon, real grades, what the building
             actually is. The ordinance applied to this is the correct answer.
  Submittal  what the applicant filed. A SUBSET of the truth, and which subset
             depends on the FORMAT: a BIM model carries a wall polygon and
             level semantics, a scanned PDF carries an outline and a number.

A checker only ever sees the Submittal. The correct verdict is computed from
the Parcel. That gap is the domain, and collapsing it, letting a checker read
the truth object because the field was convenient, would make every number in
this repository meaningless while every test still passed.

Setbacks cluster at the minimum on purpose. Applicants build to the envelope,
so the interesting cases are the ones a foot either side of the line. A uniform
distribution would put most parcels nowhere near a limit and every checker
would look excellent.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .ordinance import (PROJECTION_ALLOWANCES, LIMITS, MEZZANINE_MAX_FRACTION,
                        WALKOUT_EXPOSURE_IS_STORY_FT)

# Format determines which fields a submittal carries. These are the four that
# arrive in practice, in the proportions a mid-size jurisdiction sees.
FORMATS = ("bim", "cad", "pdf_vector", "pdf_scan")
FORMAT_WEIGHTS = (0.23, 0.27, 0.37, 0.13)

LOT_TYPES = ("interior", "corner", "flag")
LOT_WEIGHTS = (0.72, 0.17, 0.11)

# Which fields each format carries. This table is the reason the decidable
# fraction differs by format. It is data, so a reader can disagree with one
# cell rather than with a conclusion.
#
# Every format carries the roof outline, the recorded parcel boundary, a spot
# elevation and a level count, that is what "a submittal" minimally is. The
# rest is what separates a model from a picture.
FORMAT_FIELDS = {
    "bim": ("wall_polygon", "projection_schedule", "deck_height_in",
            "perimeter_grades_ft", "eave_height_ft", "mezzanine_area_sf",
            "room_below_area_sf", "basement_rear_exposure_ft",
            "accessory_footprint_sf", "access_strip_ft"),
    "cad": ("wall_polygon", "projection_schedule", "eave_height_ft",
            "accessory_footprint_sf", "access_strip_ft"),
    "pdf_vector": ("projection_schedule", "accessory_footprint_sf"),
    "pdf_scan": (),
}


@dataclass
class Parcel:
    """The physical truth. Never handed to a checker."""

    parcel_id: str
    lot_type: str
    lot_area_sf: float
    access_strip_ft: float          # flag lots only, else 0
    # Distances from the WALL to each boundary. The roof outline sits further
    # out by the projections below.
    wall_front_ft: float
    wall_side_ft: float
    wall_rear_ft: float
    projections: dict               # kind -> ft of projection, per yard
    deck_height_in: float
    ridge_height_ft: float
    eave_height_ft: float
    perimeter_grades_ft: tuple      # four corner grades; grade plane is a mean
    front_spot_elevation_ft: float
    wall_footprint_sf: float
    roof_outline_sf: float
    accessory_footprint_sf: float
    level_count: int
    mezzanine_area_sf: float
    room_below_area_sf: float
    basement_rear_exposure_ft: float
    submittal_format: str

    # -- the correct answers, from the ordinance applied to the truth --------
    def grade_plane_ft(self) -> float:
        return sum(self.perimeter_grades_ft) / len(self.perimeter_grades_ft)

    def true_height_ft(self) -> float:
        """Grade plane to the MEAN of eave and ridge."""
        return (self.ridge_height_ft + self.eave_height_ft) / 2.0 \
            - self.grade_plane_ft()

    def true_stories(self) -> int:
        """Level count, with the two conditional definitions applied."""
        stories = self.level_count
        if self.mezzanine_area_sf > 0:
            below = self.room_below_area_sf or 1.0
            if self.mezzanine_area_sf / below <= MEZZANINE_MAX_FRACTION:
                stories -= 1        # a conforming mezzanine is not a story
        if self.basement_rear_exposure_ft >= WALKOUT_EXPOSURE_IS_STORY_FT:
            stories += 1
        return stories

    def true_coverage_pct(self) -> float:
        """Wall footprint plus covered porch plus accessory, over NET lot area.

        The access strip of a flag lot is excluded from the denominator, which
        is the fifth trap: including it makes every flag lot look less covered
        than it is.
        """
        covered = (self.wall_footprint_sf
                   + self.projections.get("porch_area_sf", 0.0)
                   + self.accessory_footprint_sf)
        net_lot = self.lot_area_sf - self.strip_area_sf()
        return covered / net_lot * 100.0

    def strip_area_sf(self) -> float:
        # A 20 ft wide access strip is the local standard.
        return self.access_strip_ft * 20.0 if self.lot_type == "flag" else 0.0

    def true_setback_ok(self) -> bool:
        """Wall to boundary against the limit, with the corner-lot rule.

        Projections do NOT count against the setback when they are within
        their own allowance, so this reads the wall distance.
        """
        front_req = LIMITS["front_yard_ft"]
        side_req = LIMITS["side_yard_ft"]
        if self.lot_type == "corner":
            # The street-side yard takes the FRONT setback.
            side_req = LIMITS["front_yard_ft"]

        def encroachment(yard: str) -> float:
            """Feet by which the worst projection into `yard` exceeds its
            allowance. A projection with no allowance in this yard encroaches
            by its whole depth."""
            worst = 0.0
            for kind, allow in PROJECTION_ALLOWANCES.items():
                depth = self.projections.get(kind, 0.0)
                if depth <= 0:
                    continue
                if yard not in allow["yards"]:
                    worst = max(worst, depth)
                    continue
                if kind == "bay_window" and self.projections.get(
                        "bay_width_ft", 0.0) > allow.get("max_width_ft", 1e9):
                    worst = max(worst, depth)
                    continue
                if kind == "deck" and self.deck_height_in > allow.get(
                        "max_height_in", 1e9):
                    worst = max(worst, depth)
                    continue
                worst = max(worst, depth - allow["ft"])
            return worst

        return ((self.wall_front_ft - encroachment("front")) >= front_req
                and (self.wall_side_ft - encroachment("side")) >= side_req
                and (self.wall_rear_ft - encroachment("rear"))
                >= LIMITS["rear_yard_ft"])

    def truth(self) -> dict:
        """The correct verdict per rule. This is the grading key."""
        return {
            "setback": self.true_setback_ok(),
            "height": self.true_height_ft() <= LIMITS["height_ft"],
            "coverage": self.true_coverage_pct() <= LIMITS["coverage_pct"],
            "stories": self.true_stories() <= LIMITS["stories_above_grade"],
        }


@dataclass
class Submittal:
    """What the applicant filed, and all a checker may read."""

    parcel_id: str
    submittal_format: str
    # Always present: this is what any extraction picks up off a drawing.
    lot_type: str
    recorded_boundary_front_ft: float   # to the ROOF OUTLINE, not the wall
    recorded_boundary_side_ft: float
    recorded_boundary_rear_ft: float
    ridge_height_ft: float
    front_spot_elevation_ft: float
    roof_outline_sf: float
    lot_area_sf: float
    level_count: int
    # Format-dependent. Absent fields are simply not keys.
    fields: dict = field(default_factory=dict)

    def has(self, *names: str) -> bool:
        return all(n in self.fields for n in names)

    def missing(self, names) -> list:
        return [n for n in names if n not in self.fields]


def _projection_depth(rng: random.Random) -> dict:
    """What hangs off the building, and how far into which yard."""
    out = {}
    out["eave"] = rng.choice((1.5, 2.0, 2.5))
    if rng.random() < 0.30:
        out["porch"] = rng.choice((6.0, 8.0, 10.0))
        out["porch_area_sf"] = out["porch"] * rng.uniform(10.0, 24.0)
    if rng.random() < 0.22:
        out["bay_window"] = 2.0
        out["bay_width_ft"] = rng.choice((8.0, 10.0, 12.0))
    if rng.random() < 0.26:
        out["deck"] = rng.choice((4.0, 6.0, 8.0))
    if rng.random() < 0.12:
        out["cantilever"] = rng.choice((1.5, 2.0))
    return out


def make_parcel(index: int) -> Parcel:
    """Parcel `index`. Deterministic: same index, same parcel."""
    rng = random.Random(f"acc-parcel-{index}")
    lot_type = rng.choices(LOT_TYPES, LOT_WEIGHTS)[0]
    fmt = rng.choices(FORMATS, FORMAT_WEIGHTS)[0]
    lot_area = rng.uniform(6000.0, 14000.0)
    strip = rng.uniform(60.0, 140.0) if lot_type == "flag" else 0.0

    # Built to the envelope: cluster near the minimum, both sides of it.
    # Built to the envelope but mostly inside it: a minority of submittals
    # actually violate, which is what a real intake queue looks like. Centered
    # about 1.5 sigma above each minimum so roughly one parcel in five trips
    # something, rather than two in three.
    wall_front = LIMITS["front_yard_ft"] + abs(rng.gauss(0.0, 2.2)) + 1.2
    wall_side = LIMITS["side_yard_ft"] + rng.gauss(2.6, 1.8)
    wall_rear = LIMITS["rear_yard_ft"] + rng.gauss(4.0, 3.0)

    projections = _projection_depth(rng)
    eave = projections["eave"]

    slope = rng.gauss(0.0, 3.5) if rng.random() < 0.46 else 0.0
    front_grade = rng.uniform(98.0, 102.0)
    grades = (front_grade, front_grade + slope * 0.5,
              front_grade + slope, front_grade + slope * 0.5)
    # Elevations on the same datum as the grades, not heights above nothing.
    # Bare heights (18-26) with a grade plane near 100 subtracted from them
    # put true_height_ft() around -80, and NOT ONE PARCEL IN 600 could exceed
    # the 30 ft limit. The rule then sits in every table with a true-violation
    # count of zero, which is what surfaces it.
    eave_h = front_grade + rng.uniform(19.0, 27.0)
    ridge_h = eave_h + rng.uniform(4.0, 14.0)

    wall_sf = rng.uniform(1400.0, 3800.0)
    # The roof outline is bigger than the wall by the eave on every side, plus
    # whatever the porch covers. This is the gap trap 1 lives in.
    roof_sf = (wall_sf * (1.0 + eave * 0.06)
               + projections.get("porch_area_sf", 0.0))

    levels = rng.choices((1, 2, 3), (0.28, 0.62, 0.10))[0]
    mezz = rng.uniform(120.0, 700.0) if rng.random() < 0.18 else 0.0
    room_below = rng.uniform(900.0, 1800.0) if mezz else 0.0
    walkout = (rng.uniform(0.0, 9.0)
               if (slope < -1.0 and rng.random() < 0.55) else 0.0)

    return Parcel(
        parcel_id=f"P{index:05d}", lot_type=lot_type, lot_area_sf=lot_area,
        access_strip_ft=strip,
        wall_front_ft=wall_front, wall_side_ft=wall_side, wall_rear_ft=wall_rear,
        projections=projections, deck_height_in=rng.uniform(12.0, 44.0),
        ridge_height_ft=ridge_h, eave_height_ft=eave_h,
        perimeter_grades_ft=grades, front_spot_elevation_ft=front_grade,
        wall_footprint_sf=wall_sf, roof_outline_sf=roof_sf,
        accessory_footprint_sf=(rng.uniform(200.0, 600.0)
                                if rng.random() < 0.34 else 0.0),
        level_count=levels, mezzanine_area_sf=mezz,
        room_below_area_sf=room_below, basement_rear_exposure_ft=walkout,
        submittal_format=fmt)


def make_submittal(p: Parcel) -> Submittal:
    """Flatten a parcel into what its format actually files.

    The recorded boundary distances are measured to the ROOF OUTLINE, because
    that is the outermost line on a plan and what any extraction picks up. On a
    flag lot the recorded front distance also includes the access strip.
    """
    eave = p.projections.get("eave", 0.0)
    porch = p.projections.get("porch", 0.0)
    front_to_roof = p.wall_front_ft - max(eave, porch)
    if p.lot_type == "flag":
        front_to_roof += p.access_strip_ft
    side_to_roof = p.wall_side_ft - max(eave, p.projections.get("bay_window", 0.0))
    rear_to_roof = p.wall_rear_ft - max(eave, p.projections.get("deck", 0.0))

    available = {
        "wall_polygon": {"front_ft": p.wall_front_ft, "side_ft": p.wall_side_ft,
                         "rear_ft": p.wall_rear_ft, "area_sf": p.wall_footprint_sf},
        "projection_schedule": dict(p.projections),
        "deck_height_in": p.deck_height_in,
        "perimeter_grades_ft": list(p.perimeter_grades_ft),
        "eave_height_ft": p.eave_height_ft,
        "mezzanine_area_sf": p.mezzanine_area_sf,
        "room_below_area_sf": p.room_below_area_sf,
        "basement_rear_exposure_ft": p.basement_rear_exposure_ft,
        "accessory_footprint_sf": p.accessory_footprint_sf,
        "access_strip_ft": p.access_strip_ft,
    }
    carried = {k: v for k, v in available.items()
               if k in FORMAT_FIELDS[p.submittal_format]}

    return Submittal(
        parcel_id=p.parcel_id, submittal_format=p.submittal_format,
        lot_type=p.lot_type,
        recorded_boundary_front_ft=front_to_roof,
        recorded_boundary_side_ft=side_to_roof,
        recorded_boundary_rear_ft=rear_to_roof,
        ridge_height_ft=p.ridge_height_ft,
        front_spot_elevation_ft=p.front_spot_elevation_ft,
        roof_outline_sf=p.roof_outline_sf, lot_area_sf=p.lot_area_sf,
        level_count=p.level_count, fields=carried)


def corpus(n: int):
    """`n` deterministic (parcel, submittal) pairs."""
    for i in range(n):
        p = make_parcel(i)
        yield p, make_submittal(p)

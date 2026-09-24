"""SOC 2: six criteria, and the evidence-type question that decides them.

What this is and is not. A simplified encoding of six Trust Services Criteria,
faithful to their STRUCTURE. Written against the 2017 TSC (with the 2022
revised points of focus). It is not an audit, not an opinion, and not advice;
a real engagement is a licensed CPA firm testing evidence against a system
description and management's assertion, none of which a synthetic record
carries.

The trap that is unique to this regime. Everywhere else in this repository the
checker misreads a definition or misidentifies the object. Here it uses the
wrong kind of Evidence for the question asked, and the two questions look
identical in a dashboard:

  TYPE I  asks whether controls are SUITABLY DESIGNED at a point in time. A
          configuration snapshot can answer that.
  TYPE II asks whether they OPERATED EFFECTIVELY throughout a period. Only a
          sample drawn across that period can answer it, and the period and
          the sample size are part of the answer.

A snapshot showing MFA enabled today is real evidence for a design conclusion
and NO evidence at all for an operating conclusion covering the last nine
months. A checker reading the snapshot answers both, and the second answer is
manufactured. This rhymes with the CARD Act regime's timing rules and it is
NOT the same trap: there the sequence of events is the rule; here the sequence
is what makes evidence admissible for a rule that never mentions time.

The second trap: not every criterion is in scope. Security, the common
criteria, is mandatory. Availability, confidentiality, processing integrity
and privacy are SELECTED by management. A criterion from an unselected
category is not a gap, it is not in the engagement, and a tool that evaluates
all five categories against every entity reports findings that do not exist.

The third: some controls are somebody else's. Under the CARVE-OUT method a
subservice organization's controls are excluded from the description and
tested by that organization's own report; complementary user entity controls
(CUECs) are the customer's responsibility. Neither is a finding against this
entity, and both look exactly like a missing control from the outside.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .verdict import FAIL, PASS, REFUSE, Verdict

REGIME = "soc2"
CITATION = "AICPA TSC 2017 (rev. 2022 points of focus), subsets of CC6-CC9, A1, C1"

LIMITS = {
    "logical_access": "logical access is restricted to authorized users "
                      "(CC6.1)",
    "change_management": "changes are authorized, designed, tested and "
                         "approved (CC8.1)",
    "monitoring": "anomalies are detected, evaluated and acted on (CC7.2)",
    "vendor_management": "vendor and business partner risks are assessed and "
                         "managed (CC9.2)",
    "availability_capacity": "capacity is managed to meet the availability "
                             "commitment (A1.1)",
    "confidential_disposal": "confidential information is disposed of when no "
                             "longer needed (C1.2)",
}

RULES = tuple(LIMITS)

# See the note on RULE_TEXT in acc/hipaa.py: this is what the model is given,
# and it states every qualifier check_definition_aware() applies.
RULE_TEXT = {
    "logical_access":
        "TSC CC6.1. Logical access security software, infrastructure and "
        "architectures are implemented over protected information assets.",
    "change_management":
        "TSC CC8.1. Changes to infrastructure, data, software and procedures "
        "are authorized, designed, developed, tested and approved.",
    "monitoring":
        "TSC CC7.2. The entity monitors system components for anomalies, and "
        "evaluates and acts on them.",
    "vendor_management":
        "TSC CC9.2. The entity assesses and manages risks associated with "
        "vendors and business partners.",
    "availability_capacity":
        "TSC A1.1, in the AVAILABILITY category. Capacity is maintained to "
        "meet the entity's availability commitments. This criterion applies "
        "ONLY if availability was selected for the engagement.",
    "confidential_disposal":
        "TSC C1.2, in the CONFIDENTIALITY category. Confidential information "
        "is disposed of when no longer required. This criterion applies ONLY "
        "if confidentiality was selected for the engagement.",
}

# Applies to every criterion and is the reason this regime is in the paid run.
ENGAGEMENT_RULES = (
    "SECURITY (the common criteria) is always in scope. AVAILABILITY, "
    "CONFIDENTIALITY, PROCESSING INTEGRITY and PRIVACY are selected by "
    "management; a criterion from an unselected category is not a finding.\n"
    "A TYPE I report opines on whether controls were SUITABLY DESIGNED at a "
    "point in time. A TYPE II report opines on whether they OPERATED "
    "EFFECTIVELY throughout a period, which requires a sample drawn across "
    "that period. A configuration snapshot cannot support a Type II "
    "conclusion.\n"
    "For this exercise treat a Type II period of under 90 days, or a sample "
    "of under 25 items, as insufficient to establish operating "
    "effectiveness, and treat an exception rate at or under 4% of an "
    "adequate sample as still effective.\n"
    "Under the CARVE-OUT method, controls performed by a subservice "
    "organization are excluded from the description and are not findings "
    "against this entity."
)

# Which category each criterion belongs to. Security is always in scope; the
# rest are selected. This table is the second trap, as data.
CATEGORY = {
    "logical_access": "security",
    "change_management": "security",
    "monitoring": "security",
    "vendor_management": "security",
    "availability_capacity": "availability",
    "confidential_disposal": "confidentiality",
}
MANDATORY_CATEGORY = "security"

# Evidence sufficient for each report type. A Type II conclusion needs a
# sample drawn ACROSS the period; a Type I conclusion needs the design.
MIN_PERIOD_DAYS = 90
MIN_SAMPLE = 25

# Subservice_owned is a precondition and was not, which broke the one
# invariant this repository rests on. Under the carve-out method the report
# must say WHICH controls the subservice organization performs; it is in the
# system description. Without that list the checker cannot tell an entity's
# failed control from one it does not own. Deciding anyway is wrong 15 times
# in 3,600, and the harness surfaces that because the honest checker is
# required to be never wrong; this leaves it 4.0% wrong. A refusal is the
# correct answer to "whose control is this?" When nothing on hand says.
RULE_PRECONDITIONS = {
    r: ("report_type", "categories_in_scope", "subservice_treatment",
        # cuec_documented is not a precondition. Whether the complementary
        # user entity controls are documented is a real fact about an
        # engagement, and it is not an input to any of these six criteria as
        # encoded, so declaring it would make all six refuse for want of a
        # document none of them reads.
        "subservice_owned", "control_designed",
        "control_operated_sample", "sample_exceptions", "period_days")
    for r in RULES
}


@dataclass
class Engagement:
    """The truth about one entity's controls over one period."""

    entity_id: str
    report_type: str                 # "type_i" | "type_ii"
    period_days: int
    categories_in_scope: tuple
    subservice_treatment: str        # "carve_out" | "inclusive" | "none"
    cuec_documented: bool
    control_designed: dict           # rule -> bool
    control_operated_sample: dict    # rule -> sample size actually tested
    sample_exceptions: dict          # rule -> exceptions found
    subservice_owned: tuple          # rules performed by the subservice org
    evidence_tier: str

    def truth(self) -> dict:
        out = {}
        for rule in RULES:
            cat = CATEGORY[rule]
            if cat != MANDATORY_CATEGORY and cat not in self.categories_in_scope:
                out[rule] = True          # not in the engagement at all
                continue
            if (self.subservice_treatment == "carve_out"
                    and rule in self.subservice_owned):
                out[rule] = True          # excluded from the description
                continue
            if not self.control_designed.get(rule, False):
                out[rule] = False         # a design failure fails either type
                continue
            if self.report_type == "type_i":
                out[rule] = True          # design is the whole question
                continue
            # Type II: operating effectiveness over the period. A sample that
            # is too small, or a period too short, does not establish it; a
            # small number of exceptions in an adequate sample can still be
            # effective, so this is a rate and not a boolean.
            sample = self.control_operated_sample.get(rule, 0)
            exc = self.sample_exceptions.get(rule, 0)
            if self.period_days < MIN_PERIOD_DAYS or sample < MIN_SAMPLE:
                out[rule] = False
            else:
                out[rule] = (exc / sample) <= 0.04
        return out


@dataclass
class Evidence:
    """What the reviewer was handed."""

    entity_id: str
    evidence_tier: str
    fields: dict = field(default_factory=dict)

    def missing(self, names) -> list:
        return [n for n in names if n not in self.fields]


EVIDENCE_TIERS = ("config_snapshot", "ticket_export", "period_sample",
                  "auditor_workpapers")
TIER_WEIGHTS = (0.33, 0.28, 0.24, 0.15)

TIER_FIELDS = {
    # Today's configuration. Design evidence, and nothing about a period.
    "config_snapshot": ("control_designed",),
    # Tickets show change and incident activity but not the engagement scope.
    "ticket_export": ("control_designed", "control_operated_sample",
                      "sample_exceptions"),
    # A sample drawn across the period, with the period stated.
    "period_sample": ("control_designed", "control_operated_sample",
                      "sample_exceptions", "period_days", "report_type"),
    # The workpapers: scope, method, carve-outs and CUECs all present.
    "auditor_workpapers": ("report_type", "categories_in_scope",
                           "subservice_treatment", "subservice_owned",
                           "cuec_documented", "control_designed",
                           "control_operated_sample", "sample_exceptions",
                           "period_days"),
}

# The four scope facts a changed intake would demand. Every one is recorded in
# the engagement letter and the system description; none is a judgment.
# Four, and the tuple holds four. An intake addition no rule reads buys no
# decidability and only lengthens the form, so a field that stops being a
# precondition stops being an intake addition in the same edit.
INTAKE_ADDITIONS = ("report_type", "categories_in_scope",
                    "subservice_treatment", "subservice_owned")


def make_engagement(index: int) -> Engagement:
    rng = random.Random(f"acc-soc2-{index}")
    tier = rng.choices(EVIDENCE_TIERS, TIER_WEIGHTS)[0]
    rtype = rng.choices(("type_i", "type_ii"), (0.28, 0.72))[0]
    cats = ["security"]
    if rng.random() < 0.46:
        cats.append("availability")
    if rng.random() < 0.34:
        cats.append("confidentiality")
    sub = rng.choices(("carve_out", "inclusive", "none"), (0.41, 0.13, 0.46))[0]
    owned = tuple(r for r in RULES if rng.random() < 0.16)
    designed = {r: rng.random() < 0.87 for r in RULES}
    sample = {r: rng.choices((0, 12, 25, 40, 60), (0.12, 0.19, 0.31, 0.24, 0.14))[0]
              for r in RULES}
    exc = {r: rng.choices((0, 1, 2, 5), (0.66, 0.19, 0.09, 0.06))[0] for r in RULES}
    return Engagement(
        entity_id=f"G{index:05d}", report_type=rtype,
        period_days=rng.choice((30, 60, 90, 180, 270, 365)),
        categories_in_scope=tuple(cats), subservice_treatment=sub,
        cuec_documented=rng.random() < 0.57,
        control_designed=designed, control_operated_sample=sample,
        sample_exceptions=exc, subservice_owned=owned, evidence_tier=tier)


def make_evidence(e: Engagement) -> Evidence:
    available = {
        "report_type": e.report_type, "categories_in_scope": e.categories_in_scope,
        "subservice_treatment": e.subservice_treatment,
        "subservice_owned": e.subservice_owned,
        "cuec_documented": e.cuec_documented,
        "control_designed": e.control_designed,
        "control_operated_sample": e.control_operated_sample,
        "sample_exceptions": e.sample_exceptions, "period_days": e.period_days,
    }
    carried = {k: v for k, v in available.items()
               if k in TIER_FIELDS[e.evidence_tier]}
    return Evidence(entity_id=e.entity_id, evidence_tier=e.evidence_tier,
                    fields=carried)


# ------------------------------------------------------------ THE CHECKERS

def check_naive(ev: Evidence) -> dict:
    """Is the control there? Then it passes. Never refuses.

    This is a continuous-monitoring dashboard. It evaluates all six criteria
    against every entity, treats today's configuration as evidence for any
    period, and treats any exception as a failure.
    """
    f = ev.fields
    designed = f.get("control_designed", {})
    exc = f.get("sample_exceptions", {})
    out = {}
    for rule in RULES:
        ok = designed.get(rule, False) and exc.get(rule, 0) == 0
        out[rule] = Verdict(rule, PASS if ok else FAIL,
                            "control present in the current configuration, "
                            "no exceptions seen")
    return out


def check_definition_aware(ev: Evidence) -> dict:
    """Scope, then evidence type, then the criterion. Refuses without them."""
    f = ev.fields
    out = {}
    for rule in RULES:
        miss = ev.missing(RULE_PRECONDITIONS[rule])
        if miss:
            out[rule] = Verdict(rule, REFUSE,
                                "evidence does not carry: " + ", ".join(miss),
                                tuple(miss))
            continue

        cat = CATEGORY[rule]
        if cat != MANDATORY_CATEGORY and cat not in f["categories_in_scope"]:
            out[rule] = Verdict(rule, PASS,
                                f"not applicable: the {cat} category was not "
                                f"selected for this engagement")
            continue

        # A carved-out subservice organization's controls are excluded from
        # the description and tested by that organization's own report. Not a
        # finding against this entity.
        if (f["subservice_treatment"] == "carve_out"
                and rule in f["subservice_owned"]):
            out[rule] = Verdict(rule, PASS,
                                "not applicable: performed by a carved-out "
                                "subservice organization")
            continue

        if not f["control_designed"].get(rule, False):
            out[rule] = Verdict(rule, FAIL, "control is not suitably designed")
            continue

        if f["report_type"] == "type_i":
            out[rule] = Verdict(rule, PASS,
                                "Type I: suitably designed at a point in time")
            continue

        sample = f["control_operated_sample"].get(rule, 0)
        exceptions = f["sample_exceptions"].get(rule, 0)
        if f["period_days"] < MIN_PERIOD_DAYS:
            out[rule] = Verdict(rule, FAIL,
                                f"Type II over {f['period_days']} days is "
                                f"below the {MIN_PERIOD_DAYS} day floor")
        elif sample < MIN_SAMPLE:
            out[rule] = Verdict(rule, FAIL,
                                f"sample of {sample} does not establish "
                                f"operating effectiveness")
        else:
            rate = exceptions / sample
            out[rule] = Verdict(
                rule, PASS if rate <= 0.04 else FAIL,
                f"{exceptions} exceptions in {sample} tested")
    return out


def with_intake(ev: Evidence, truth: Engagement) -> Evidence:
    merged = dict(ev.fields)
    for k in INTAKE_ADDITIONS:
        merged.setdefault(k, getattr(truth, k))
    return Evidence(entity_id=ev.entity_id, evidence_tier=ev.evidence_tier,
                    fields=merged)


def corpus(n: int):
    for i in range(n):
        e = make_engagement(i)
        yield e, make_evidence(e)

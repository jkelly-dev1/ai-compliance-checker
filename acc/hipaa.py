"""HIPAA: a simplified encoding of six requirements and what decides them.

What this is and is not. This encodes a SUBSET of the HIPAA Security Rule and
the de-identification standard, faithfully to their STRUCTURE, so the same
measurement that runs over a zoning ordinance can run over a privacy regime.
It cites the section each rule comes from so a reader can check the encoding
against the source. It is not a compliance product and it is not legal advice;
a real assessment turns on facts, scope and documentation that no synthetic
record carries.

The reason this regime is in the repository. The zoning ordinance showed six
limits decided by ten definitions. If that ratio were a property of zoning it
would be a curiosity. Here the limits are security standards and the
definitions are statutory qualifiers, the domain shares no vocabulary with the
first one, and the shape comes out the same, which is the claim.

THE TWO TRAPS, both real and both the reason a naive checker is confidently
wrong rather than merely incomplete:

  Addressable is not optional. 45 CFR 164.306(d)(3): for an addressable
  implementation specification a covered entity must assess whether it is a
  reasonable and appropriate safeguard and, if not, document why and implement
  an equivalent alternative where reasonable. Encryption at rest, 164.312
  (a)(2)(iv), is addressable. "Encryption off" is therefore NOT a violation on
  its own, and a checker that reads the boolean has no way to know that. The
  deciding facts are the assessment and the alternative, which live in
  documents.

  A claimed exception is not an exception. The conduit exception, 78 FR 5571,
  covers a carrier that merely transmits ePHI. An entity that PROCESSES it is
  a business associate however it describes itself, so the claim and the
  access type have to be read together, and a checker that sees only the BAA
  flag reports a gap against a vendor that legitimately has no BAA.

  Safe Harbor is eighteen categories, two of them conditional. 164.514(b)(2).
  Dates must be generalized to the year, except ages over 89 which aggregate
  to 90+. ZIP codes may keep three digits ONLY where that three-digit
  geography contains more than 20,000 people, and must otherwise read 000.
  That last one cannot be decided from the dataset at all: it needs an
  external population figure, so an honest checker refuses rather than
  guessing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .verdict import FAIL, PASS, REFUSE, Verdict

REGIME = "hipaa"
CITATION = "45 CFR 164 (subsets of 164.306, 164.308, 164.312, 164.514)"

# -- the six requirements ----------------------------------------------------
# What a summary slide contains. Each is real and each is stated at the level
# a checklist states it.
LIMITS = {
    "encryption_at_rest": "ePHI is encrypted at rest (164.312(a)(2)(iv))",
    "audit_controls": "activity in systems with ePHI is recorded and examined "
                      "(164.312(b))",
    "unique_user_id": "each user has a unique identifier (164.312(a)(2)(i))",
    "workforce_termination": "access is revoked when employment ends "
                             "(164.308(a)(3)(ii)(C))",
    "business_associate": "a BAA is in place before ePHI is disclosed to a "
                          "vendor (164.308(b)(1))",
    "de_identification": "a dataset released as de-identified meets Safe "
                         "Harbor (164.514(b)(2))",
}

# Which of the Security Rule specifications are ADDRESSABLE rather than
# REQUIRED. This single table is the first trap, and it is data because the
# distinction is a fact about the rule, not a judgment about the entity.
ADDRESSABLE = {"encryption_at_rest", "workforce_termination"}
REQUIRED = {"audit_controls", "unique_user_id", "business_associate"}

# The 18 Safe Harbor categories, abbreviated to the ones a tabular dataset
# actually carries. Two of them are conditional, and they are marked because
# they are what separates a checkable rule from a refusable one.
SAFE_HARBOR_DIRECT = ("name", "email", "ssn", "mrn", "phone", "account_number",
                      "device_id", "biometric", "full_face_photo", "url", "ip")
SAFE_HARBOR_CONDITIONAL = {
    "dates": "only the year may remain, and ages over 89 aggregate to 90+",
    "zip3": "three digits only where that geography exceeds 20,000 people",
}
ZIP3_POPULATION_FLOOR = 20000

RULES = tuple(LIMITS)

# The Rule as written, including the qualifiers the definition-aware checker
# implements. This is what scripts/real_run.py hands a model, so the model and
# check_definition_aware() are answering from the same text. Anything the
# checker knows and this omits would make the comparison unfair to the model.
RULE_TEXT = {
    "encryption_at_rest":
        "45 CFR 164.312(a)(2)(iv). Encryption of ePHI at rest is an "
        "ADDRESSABLE implementation specification. Under 164.306(d)(3) an "
        "addressable specification must be implemented if reasonable and "
        "appropriate; if it is not, the entity must document why and "
        "implement an equivalent alternative measure where reasonable. "
        "Encryption being disabled is therefore NOT a violation on its own.",
    "audit_controls":
        "45 CFR 164.312(b). REQUIRED. Implement hardware, software and "
        "procedural mechanisms that record and EXAMINE activity in systems "
        "containing ePHI. Recording alone is not sufficient; there must be "
        "evidence the records are examined. Treat 180 days as the minimum "
        "retention for this exercise.",
    "unique_user_id":
        "45 CFR 164.312(a)(2)(i). REQUIRED. Assign a unique name or number "
        "for identifying and tracking user identity. Shared accounts defeat "
        "it.",
    "workforce_termination":
        "45 CFR 164.308(a)(3)(ii)(C). ADDRESSABLE. Implement procedures for "
        "terminating access when employment ends. As an addressable "
        "specification the 164.306(d)(3) latitude applies: a documented "
        "assessment plus an equivalent alternative satisfies it.",
    "business_associate":
        "45 CFR 164.308(b)(1). A covered entity must obtain satisfactory "
        "assurances, via a business associate agreement, before disclosing "
        "ePHI to a business associate. A CONDUIT that merely transmits ePHI "
        "and does not access it other than randomly or incidentally is not a "
        "business associate and needs no agreement. An entity that PROCESSES "
        "ePHI is a business associate however it describes itself.",
    "de_identification":
        "45 CFR 164.514(b)(2), Safe Harbor. All 18 identifier categories must "
        "be removed. Two are conditional: (1) all elements of dates except "
        "the YEAR must be removed; (2) the initial three digits of a ZIP code "
        "may be retained ONLY if the geographic unit formed by those three "
        "digits contains MORE THAN 20,000 people, and must otherwise be "
        "changed to 000.",
}

# What a decision needs before it may be made. Notice these are documents and
# external facts, not more of the same telemetry, which is the finding.
RULE_PRECONDITIONS = {
    "encryption_at_rest": ("encryption_enabled", "risk_assessment_on_file",
                           "alternative_control_documented"),
    "audit_controls": ("log_retention_days", "log_review_evidence"),
    "unique_user_id": ("shared_accounts_count",),
    # The rule is "revocation met, or assessed with a documented
    # alternative", so it reads alternative_control_documented and must
    # declare it; a rule that reads a field it does not declare can decide on
    # evidence its precondition set says it does not need. It does not read
    # termination_events, because the count of terminations cannot change
    # either arm, so declaring that field would make the checker refuse for
    # want of a number it would not look at. The naive checker does read it
    # (see check_naive), so the field stays in the population.
    "workforce_termination": ("revocation_sla_met",
                              "risk_assessment_on_file",
                              "alternative_control_documented"),
    # vendor_access_type is what makes the conduit exception decidable.
    # Requiring conduit_exception_claimed as a precondition while nothing in
    # the rule reads it would gate decisions on a field that cannot change
    # one, which is the worst kind of intake burden.
    "business_associate": ("vendor_receives_ephi", "baa_executed",
                           "conduit_exception_claimed", "vendor_access_type"),
    "de_identification": ("released_columns", "date_precision",
                          "zip_digits", "zip3_population"),
}


@dataclass
class Entity:
    """The truth about one covered entity's system, and its released dataset."""

    entity_id: str
    encryption_enabled: bool
    risk_assessment_on_file: bool
    alternative_control_documented: bool
    log_retention_days: int
    log_review_evidence: bool
    shared_accounts_count: int
    termination_events: int
    revocation_sla_met: bool
    vendor_receives_ephi: bool
    baa_executed: bool
    conduit_exception_claimed: bool
    vendor_access_type: str        # "transmit_only" | "processes"
    released_columns: tuple
    date_precision: str            # "year" | "month" | "day"
    zip_digits: int                # 0, 3 or 5
    zip3_population: int           # the external fact
    evidence_tier: str

    def truth(self) -> dict:
        """The correct finding per rule, with the qualifiers applied."""
        # ADDRESSABLE: not encrypting is compliant when the entity assessed it
        # and documented an equivalent alternative.
        enc_ok = self.encryption_enabled or (
            self.risk_assessment_on_file and self.alternative_control_documented)
        term_ok = self.revocation_sla_met or (
            self.risk_assessment_on_file and self.alternative_control_documented)
        # REQUIRED: no such latitude.
        audit_ok = self.log_retention_days >= 180 and self.log_review_evidence
        uid_ok = self.shared_accounts_count == 0
        # A true conduit, a carrier that only transmits and does not access
        # ePHI other than randomly or incidentally, is not a business
        # associate and needs no baa. Claiming the exception does not create
        # it: an entity that processes ePHI is a business associate however it
        # describes itself, so the claim and the access type are separate
        # fields and only their conjunction decides.
        conduit = (self.conduit_exception_claimed
                   and self.vendor_access_type == "transmit_only")
        baa_ok = ((not self.vendor_receives_ephi) or self.baa_executed
                  or conduit)
        deid_ok = self._deid_ok()
        return {"encryption_at_rest": enc_ok, "audit_controls": audit_ok,
                "unique_user_id": uid_ok, "workforce_termination": term_ok,
                "business_associate": baa_ok, "de_identification": deid_ok}

    def _deid_ok(self) -> bool:
        if any(c in SAFE_HARBOR_DIRECT for c in self.released_columns):
            return False
        if self.date_precision != "year":
            return False
        if self.zip_digits == 5:
            return False
        if self.zip_digits == 3 and self.zip3_population <= ZIP3_POPULATION_FLOOR:
            return False
        return True


@dataclass
class Submission:
    """What the assessor was actually given. A subset, by evidence tier."""

    entity_id: str
    evidence_tier: str
    fields: dict = field(default_factory=dict)

    def missing(self, names) -> list:
        return [n for n in names if n not in self.fields]


# What each evidence tier carries. The analog of submittal format: a
# questionnaire answer is not a document and a document is not a test.
EVIDENCE_TIERS = ("questionnaire", "config_export", "document_review",
                  "full_assessment")
TIER_WEIGHTS = (0.34, 0.31, 0.23, 0.12)

# Every fact a submission can carry. One tuple, read by the population that
# builds a submission and by the richest evidence tier, because "everything"
# has to mean everything.
#
# Written out, not derived from RULE_PRECONDITIONS. Evidence a submission can
# carry is a fact about the population; what a rule requires is a fact about
# the rule. Derived from the second, the first would agree only by
# coincidence: tightening a precondition set would remove a field from the
# world, including one the naive checker reads (termination_events), and a
# change to the honest checker would move the naive checker's published error
# rate as a side effect. tests/test_invariants.py::
# test_some_evidence_tier_carries_everything_the_population_has pins it.
SUBMITTABLE_FIELDS = (
    "encryption_enabled", "risk_assessment_on_file",
    "alternative_control_documented", "log_retention_days",
    "log_review_evidence", "shared_accounts_count", "termination_events",
    "revocation_sla_met", "vendor_receives_ephi", "baa_executed",
    "conduit_exception_claimed", "vendor_access_type", "released_columns",
    "date_precision", "zip_digits", "zip3_population")

TIER_FIELDS = {
    # A yes/no questionnaire. Carries booleans and nothing that decides them.
    "questionnaire": ("encryption_enabled", "shared_accounts_count",
                      "vendor_receives_ephi", "baa_executed",
                      "released_columns"),
    # Machine-readable config. More precise, still no documents.
    "config_export": ("encryption_enabled", "log_retention_days",
                      "shared_accounts_count", "vendor_receives_ephi",
                      "baa_executed", "released_columns", "date_precision",
                      "zip_digits", "termination_events"),
    # Somebody read the policies. Now the addressable qualifiers exist.
    "document_review": ("encryption_enabled", "risk_assessment_on_file",
                        "alternative_control_documented", "log_retention_days",
                        "log_review_evidence", "shared_accounts_count",
                        "termination_events", "revocation_sla_met",
                        "vendor_receives_ephi", "baa_executed",
                        "conduit_exception_claimed", "vendor_access_type",
                        "released_columns", "date_precision", "zip_digits"),
    # Everything, including the external population figure.
    "full_assessment": SUBMITTABLE_FIELDS,
}

# The evidence a changed intake would demand. Documents, not judgments.
INTAKE_ADDITIONS = ("risk_assessment_on_file", "alternative_control_documented",
                    "log_review_evidence", "revocation_sla_met",
                    "conduit_exception_claimed", "vendor_access_type")


def make_entity(index: int) -> Entity:
    rng = random.Random(f"acc-hipaa-{index}")
    tier = rng.choices(EVIDENCE_TIERS, TIER_WEIGHTS)[0]
    enc = rng.random() < 0.63
    # Entities that do not encrypt mostly DID do the addressable analysis,
    # that is the point of the trap. A minority did not.
    assessed = rng.random() < (0.74 if not enc else 0.55)
    alt = assessed and rng.random() < 0.82
    cols = ["patient_key", "dx_code", "visit_year"]
    if rng.random() < 0.22:
        cols.append(rng.choice(SAFE_HARBOR_DIRECT))
    return Entity(
        entity_id=f"E{index:05d}",
        encryption_enabled=enc,
        risk_assessment_on_file=assessed,
        alternative_control_documented=alt,
        log_retention_days=rng.choice((30, 90, 180, 365, 730)),
        log_review_evidence=rng.random() < 0.58,
        shared_accounts_count=rng.choices((0, 1, 2, 5),
                                         (0.71, 0.14, 0.09, 0.06))[0],
        termination_events=rng.randint(0, 40),
        revocation_sla_met=rng.random() < 0.66,
        vendor_receives_ephi=rng.random() < 0.72,
        baa_executed=rng.random() < 0.81,
        conduit_exception_claimed=rng.random() < 0.17,
        vendor_access_type=rng.choices(("transmit_only", "processes"),
                                       (0.21, 0.79))[0],
        released_columns=tuple(cols),
        date_precision=rng.choices(("year", "month", "day"),
                                   (0.62, 0.24, 0.14))[0],
        zip_digits=rng.choices((0, 3, 5), (0.38, 0.49, 0.13))[0],
        # The conditional one. Roughly a third of three-digit ZIP geographies
        # in the United States fall at or under the 20,000 floor.
        zip3_population=rng.choice((4200, 11800, 19500, 26000, 91000, 240000)),
        evidence_tier=tier)


def make_submission(e: Entity) -> Submission:
    available = {k: getattr(e, k) for k in SUBMITTABLE_FIELDS}
    carried = {k: v for k, v in available.items()
               if k in TIER_FIELDS[e.evidence_tier]}
    return Submission(entity_id=e.entity_id, evidence_tier=e.evidence_tier,
                      fields=carried)


# ------------------------------------------------------------ THE CHECKERS

def check_naive(s: Submission) -> dict:
    """Read the boolean, report the finding. Never refuses.

    This is a checklist tool, and it is what most automated HIPAA tooling
    does: it treats every specification as required and every dataset column
    as the whole de-identification question.
    """
    f = s.fields
    out = {}
    out["encryption_at_rest"] = Verdict(
        "encryption_at_rest", PASS if f.get("encryption_enabled") else FAIL,
        "encryption flag as reported")
    out["audit_controls"] = Verdict(
        "audit_controls",
        PASS if f.get("log_retention_days", 0) >= 180 else FAIL,
        "retention days against a 180 day expectation")
    out["unique_user_id"] = Verdict(
        "unique_user_id",
        PASS if f.get("shared_accounts_count", 0) == 0 else FAIL,
        "shared account count")
    out["workforce_termination"] = Verdict(
        "workforce_termination",
        PASS if f.get("termination_events", 0) == 0
        or f.get("revocation_sla_met", False) else FAIL,
        "revocation SLA flag, or no terminations")
    out["business_associate"] = Verdict(
        "business_associate",
        PASS if f.get("baa_executed") or not f.get("vendor_receives_ephi")
        else FAIL, "BAA flag")
    # The whole de-identification question, reduced to a column-name scan.
    cols = f.get("released_columns", ())
    out["de_identification"] = Verdict(
        "de_identification",
        FAIL if any(c in SAFE_HARBOR_DIRECT for c in cols) else PASS,
        "column names scanned for direct identifiers")
    return out


def _decide(rule, s, cond, why):
    miss = s.missing(RULE_PRECONDITIONS[rule])
    if miss:
        return Verdict(rule, REFUSE,
                       "evidence does not carry: " + ", ".join(miss),
                       tuple(miss))
    return Verdict(rule, PASS if cond() else FAIL, why)


def check_definition_aware(s: Submission) -> dict:
    """The rule as written, with the qualifiers, refusing without them."""
    f = s.fields
    out = {}

    out["encryption_at_rest"] = _decide(
        "encryption_at_rest", s,
        lambda: (f["encryption_enabled"]
                 or (f["risk_assessment_on_file"]
                     and f["alternative_control_documented"])),
        "addressable: encrypted, or assessed with a documented alternative")

    out["audit_controls"] = _decide(
        "audit_controls", s,
        lambda: f["log_retention_days"] >= 180 and f["log_review_evidence"],
        "required: retention AND evidence the logs are examined")

    out["unique_user_id"] = _decide(
        "unique_user_id", s, lambda: f["shared_accounts_count"] == 0,
        "required: no shared accounts")

    out["workforce_termination"] = _decide(
        "workforce_termination", s,
        lambda: (f["revocation_sla_met"]
                 or (f["risk_assessment_on_file"]
                     and f["alternative_control_documented"])),
        "addressable: revocation met, or assessed with an alternative")

    out["business_associate"] = _decide(
        "business_associate", s,
        lambda: ((not f["vendor_receives_ephi"]) or f["baa_executed"]
                 or (f["conduit_exception_claimed"]
                     and f["vendor_access_type"] == "transmit_only")),
        "BAA required unless the vendor is a true transmission-only conduit")

    def deid() -> bool:
        if any(c in SAFE_HARBOR_DIRECT for c in f["released_columns"]):
            return False
        if f["date_precision"] != "year":
            return False
        if f["zip_digits"] == 5:
            return False
        if f["zip_digits"] == 3 and f["zip3_population"] <= ZIP3_POPULATION_FLOOR:
            return False
        return True

    out["de_identification"] = _decide(
        "de_identification", s, deid,
        "Safe Harbor including the date and ZIP3 conditions")
    return out


def with_intake(s: Submission, truth: Entity) -> Submission:
    """The submission as it would arrive if the five documents were required."""
    merged = dict(s.fields)
    for k in INTAKE_ADDITIONS:
        merged.setdefault(k, getattr(truth, k))
    return Submission(entity_id=s.entity_id, evidence_tier=s.evidence_tier,
                      fields=merged)


def corpus(n: int):
    for i in range(n):
        e = make_entity(i)
        yield e, make_submission(e)

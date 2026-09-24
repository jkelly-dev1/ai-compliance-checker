"""PCI DSS: six requirements, and the scope question that decides all of them.

What this is and is not. A simplified encoding of six PCI DSS requirements,
faithful to their STRUCTURE so the same measurement can run over them. Written
against PCI DSS v4.0 numbering. It is not a compliance product, not a ROC, and
not advice; a real assessment is a QSA reading evidence against a scope
definition that no synthetic record carries.

The trap that is unique to this regime, and the reason it earns its place.
Everywhere else in this repository the checker reads the right rule against the
right object and gets the definition wrong. Here it can read the rule perfectly
and evaluate it against the wrong System. PCI applies to the cardholder data
environment, and what is in the CDE depends on segmentation: a system that
stores, processes or transmits account data is in scope, and so is any system
that can CONNECT TO or AFFECT the security of one. A flat network puts
everything in scope. A checker that scans the systems someone labeled "PCI" is
answering a question about a set that the ordinance, the standard, does not
define that way.

  Scope is not a filter applied after the check. It decides which systems the
  requirement is even about, so a scoping error changes the answer in BOTH
  directions: an out-of-scope system dragged in produces findings that are not
  violations, and an in-scope connected system left out produces a clean report
  over an unexamined attack path.

The second trap corroborates HIPAA without repeating it. A requirement met by
a compensating control is met. v4.0 also adds the customized approach, where
an entity meets the stated objective by other means with a documented targeted
risk analysis. Both are legitimate, both live in documents, and neither is
visible to a scanner, so "control absent" is not "requirement failed", exactly
as "encryption off" was not a HIPAA violation on its own. Two unrelated
regimes, one shape.

THE THIRD, the one people get wrong in the other direction: not applicable is
not the same as not tested. A requirement that genuinely does not apply is
compliant; a requirement nobody looked at is unknown. Collapsing them is how a
report reaches 100% with holes in it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .verdict import FAIL, PASS, REFUSE, Verdict

REGIME = "pci_dss"
CITATION = "PCI DSS v4.0 (subsets of Req 1, 2, 3, 8, 10, 11)"

LIMITS = {
    "network_segmentation": "controls restrict traffic into and out of the "
                            "CDE (Req 1.2)",
    "no_vendor_defaults": "vendor default accounts and passwords are removed "
                          "or changed (Req 2.2)",
    "pan_storage": "PAN is rendered unreadable wherever it is stored "
                   "(Req 3.5)",
    "mfa_into_cde": "MFA is required for all access into the CDE (Req 8.4)",
    "log_retention": "audit log history is retained for at least 12 months, "
                     "3 months immediately available (Req 10.5)",
    "vuln_scanning": "internal and external scans are run and passing scans "
                     "achieved (Req 11.3)",
}

RULES = tuple(LIMITS)

# The scope inputs are preconditions for every rule, not a separate step.
# That is the encoding of the finding: you cannot answer any of these about a
# system until you know whether the requirement is about that system.
SCOPE_INPUTS = ("stores_processes_transmits", "connected_to_cde",
                "segmentation_validated")

# The two documented alternatives to meeting a requirement directly. They are
# one input, not two, because the predicate that reads them is one `or` and it
# reads both arms. Naming them together here is what stops a rule declaring
# half of a predicate it evaluates whole.
ALT_INPUTS = ("compensating_control_documented", "customized_approach_trra")

RULE_PRECONDITIONS = {
    "network_segmentation": SCOPE_INPUTS + ("segmentation_test_evidence",),
    # ALT_INPUTS, both fields, on every rule that has an alternative arm. The
    # `alt` predicate reads both (see check_definition_aware), so a rule naming
    # only one would declare a set it does not honor: handed a submission
    # carrying every field it asked for, it could answer FAIL where the truth
    # is PASS, because `.get(..., False)` supplies a default for the field it
    # did not ask for. No tier in the shipped corpus carries one of the two
    # without the other, but that is a property of the corpus, not of the
    # rule.
    "no_vendor_defaults": SCOPE_INPUTS + ("default_accounts_present",) + ALT_INPUTS,
    "pan_storage": SCOPE_INPUTS + ("stores_pan",
                                   "pan_protection_method") + ALT_INPUTS,
    "mfa_into_cde": SCOPE_INPUTS + ("mfa_enabled", "access_path") + ALT_INPUTS,
    "log_retention": SCOPE_INPUTS + ("log_retention_months",
                                     "log_immediate_months"),
    # asv_scan_required is not a precondition. Whether an external scan is
    # required does not change whether the cadence and the passing scan on
    # file satisfy the requirement, and the rule does not read it. It stays in
    # the population and in the tier table as a fact a submission carries.
    "vuln_scanning": SCOPE_INPUTS + ("scan_cadence_days",
                                     "passing_scan_on_file"),
}

# Rules that a compensating control or the customized approach can satisfy.
# Not every requirement is eligible, which is itself part of the standard.
ALTERNATIVE_ELIGIBLE = {"no_vendor_defaults", "pan_storage", "mfa_into_cde"}

# Named because a rule whose number is inline cannot be amended by editing a
# table, and every other threshold in this repository can. acc/version_bump.py
# found this by being unable to apply an amendment without rewriting a
# function.
LOG_RETENTION_MONTHS_MIN = 12
LOG_IMMEDIATE_MONTHS_MIN = 3
SCAN_CADENCE_DAYS_MAX = 90


@dataclass
class System:
    """The truth about one system, including whether it is actually in scope."""

    system_id: str
    stores_processes_transmits: bool
    connected_to_cde: bool
    segmentation_validated: bool
    segmentation_test_evidence: bool
    default_accounts_present: bool
    stores_pan: bool
    pan_protection_method: str      # "none" | "truncation" | "strong_crypto"
    mfa_enabled: bool
    access_path: str                # "console" | "remote" | "internal_only"
    log_retention_months: int
    log_immediate_months: int
    scan_cadence_days: int
    passing_scan_on_file: bool
    asv_scan_required: bool
    compensating_control_documented: bool
    customized_approach_trra: bool  # targeted risk analysis on file
    evidence_tier: str

    def in_scope(self) -> bool:
        """The CDE plus anything connected to or affecting it.

        Segmentation only removes a connected system from scope when it has
        been VALIDATED. Asserting segmentation is not the same as testing it,
        so the flag and the evidence are separate fields.
        """
        if self.stores_processes_transmits:
            return True
        if self.connected_to_cde:
            return not self.segmentation_validated
        return False

    def truth(self) -> dict:
        """The correct finding per requirement, scope applied first."""
        if not self.in_scope():
            # Genuinely not applicable. Compliant, and NOT the same as untested.
            return {r: True for r in RULES}

        alt = self.compensating_control_documented or self.customized_approach_trra
        seg_ok = self.segmentation_test_evidence
        defaults_ok = (not self.default_accounts_present) or (
            alt and "no_vendor_defaults" in ALTERNATIVE_ELIGIBLE)
        pan_ok = (not self.stores_pan) or self.pan_protection_method in (
            "truncation", "strong_crypto") or (
            alt and "pan_storage" in ALTERNATIVE_ELIGIBLE)
        mfa_ok = self.mfa_enabled or self.access_path == "internal_only" or (
            alt and "mfa_into_cde" in ALTERNATIVE_ELIGIBLE)
        log_ok = (self.log_retention_months >= LOG_RETENTION_MONTHS_MIN
                  and self.log_immediate_months >= LOG_IMMEDIATE_MONTHS_MIN)
        scan_ok = (self.scan_cadence_days <= SCAN_CADENCE_DAYS_MAX
                   and self.passing_scan_on_file)
        return {"network_segmentation": seg_ok, "no_vendor_defaults": defaults_ok,
                "pan_storage": pan_ok, "mfa_into_cde": mfa_ok,
                "log_retention": log_ok, "vuln_scanning": scan_ok}


@dataclass
class Assessment:
    """What the assessor was handed about one system."""

    system_id: str
    evidence_tier: str
    # Always present, and always the wrong question on its own: the tag someone
    # put on the asset in the CMDB.
    tagged_pci: bool
    fields: dict = field(default_factory=dict)

    def missing(self, names) -> list:
        return [n for n in names if n not in self.fields]


EVIDENCE_TIERS = ("asset_tag", "scanner_output", "config_and_policy",
                  "qsa_walkthrough")
TIER_WEIGHTS = (0.29, 0.34, 0.24, 0.13)

# Every fact a submission can carry. One tuple, read by the population that
# builds a submission and by the richest evidence tier, because "everything"
# has to mean everything.
#
# Written out, not derived from RULE_PRECONDITIONS. Evidence a submission can
# carry is a fact about the population; what a rule requires is a fact about
# the rule. Derived from the second, the first would agree only by
# coincidence: tightening a precondition set would remove a field from the
# world, including one the naive checker reads (asv_scan_required), and a
# change to the honest checker would move the naive checker's published error
# rate as a side effect. tests/test_invariants.py::
# test_some_evidence_tier_carries_everything_the_population_has pins it.
SUBMITTABLE_FIELDS = (
    "stores_processes_transmits", "connected_to_cde",
    "segmentation_validated", "segmentation_test_evidence",
    "default_accounts_present", "stores_pan", "pan_protection_method",
    "mfa_enabled", "access_path", "log_retention_months",
    "log_immediate_months", "scan_cadence_days", "passing_scan_on_file",
    "asv_scan_required", "compensating_control_documented",
    "customized_approach_trra")

TIER_FIELDS = {
    # Someone labeled the asset. Nothing else.
    "asset_tag": (),
    # A scanner sees the machine, not the network design and not the papers.
    "scanner_output": ("default_accounts_present", "mfa_enabled",
                       "log_retention_months", "log_immediate_months",
                       "scan_cadence_days", "passing_scan_on_file",
                       "stores_pan", "pan_protection_method"),
    # Config plus the policy set: scope inputs appear, documents do not.
    "config_and_policy": ("stores_processes_transmits", "connected_to_cde",
                          "segmentation_validated", "default_accounts_present",
                          "mfa_enabled", "access_path", "stores_pan",
                          "pan_protection_method", "log_retention_months",
                          "log_immediate_months", "scan_cadence_days",
                          "passing_scan_on_file", "asv_scan_required"),
    # A QSA walked it. Now the evidence and the documented alternatives exist.
    "qsa_walkthrough": SUBMITTABLE_FIELDS,
}

# What a changed intake would demand. Every one is a DOCUMENT or a TEST RESULT
# that an assessed entity either has or does not; none is a judgment.
INTAKE_ADDITIONS = ("stores_processes_transmits", "connected_to_cde",
                    "segmentation_validated", "segmentation_test_evidence",
                    "compensating_control_documented", "customized_approach_trra")


def make_system(index: int) -> System:
    rng = random.Random(f"acc-pci-{index}")
    tier = rng.choices(EVIDENCE_TIERS, TIER_WEIGHTS)[0]
    spt = rng.random() < 0.31
    connected = (not spt) and rng.random() < 0.44
    segmented = connected and rng.random() < 0.58
    stores_pan = spt and rng.random() < 0.52
    return System(
        system_id=f"S{index:05d}",
        stores_processes_transmits=spt,
        connected_to_cde=connected,
        segmentation_validated=segmented,
        segmentation_test_evidence=segmented and rng.random() < 0.71,
        default_accounts_present=rng.random() < 0.24,
        stores_pan=stores_pan,
        pan_protection_method=rng.choices(
            ("none", "truncation", "strong_crypto"), (0.19, 0.28, 0.53))[0],
        mfa_enabled=rng.random() < 0.68,
        access_path=rng.choices(("console", "remote", "internal_only"),
                                (0.21, 0.49, 0.30))[0],
        log_retention_months=rng.choice((3, 6, 12, 18, 24)),
        log_immediate_months=rng.choice((1, 3, 6)),
        scan_cadence_days=rng.choice((30, 90, 180, 365)),
        passing_scan_on_file=rng.random() < 0.62,
        asv_scan_required=rng.random() < 0.55,
        compensating_control_documented=rng.random() < 0.21,
        customized_approach_trra=rng.random() < 0.14,
        evidence_tier=tier)


def make_assessment(sy: System) -> Assessment:
    available = {k: getattr(sy, k) for k in SUBMITTABLE_FIELDS}
    carried = {k: v for k, v in available.items()
               if k in TIER_FIELDS[sy.evidence_tier]}
    # The CMDB tag correlates with scope and is not scope. It is right about
    # three quarters of the time, which is exactly what makes it dangerous.
    tagged = sy.in_scope() if random.Random(sy.system_id).random() < 0.76 \
        else (not sy.in_scope())
    return Assessment(system_id=sy.system_id, evidence_tier=sy.evidence_tier,
                      tagged_pci=tagged, fields=carried)


# ------------------------------------------------------------ THE CHECKERS

def check_naive(a: Assessment) -> dict:
    """Scan the systems someone tagged PCI, apply the six requirements.

    This is what an automated compliance dashboard does. Note that it is not
    careless: every requirement is implemented correctly. It just answers them
    about the set of systems in the tag, and treats an absent control as a
    failed requirement.
    """
    f = a.fields
    if not a.tagged_pci:
        # Not tagged, so not asked. Reported as compliant, which is the
        # not-applicable / not-tested collapse.
        return {r: Verdict(r, PASS, "system not tagged in scope") for r in RULES}

    out = {}
    out["network_segmentation"] = Verdict(
        "network_segmentation",
        PASS if f.get("segmentation_validated", False) else FAIL,
        "segmentation flag as configured")
    out["no_vendor_defaults"] = Verdict(
        "no_vendor_defaults",
        FAIL if f.get("default_accounts_present", False) else PASS,
        "default accounts detected by the scanner")
    out["pan_storage"] = Verdict(
        "pan_storage",
        PASS if (not f.get("stores_pan", False)
                 or f.get("pan_protection_method") in ("truncation",
                                                       "strong_crypto"))
        else FAIL, "storage method as detected")
    out["mfa_into_cde"] = Verdict(
        "mfa_into_cde", PASS if f.get("mfa_enabled", False) else FAIL,
        "MFA flag as configured")
    out["log_retention"] = Verdict(
        "log_retention",
        PASS if (f.get("log_retention_months", 0) >= 12
                 and f.get("log_immediate_months", 0) >= 3) else FAIL,
        "retention as configured")
    out["vuln_scanning"] = Verdict(
        "vuln_scanning",
        PASS if (f.get("scan_cadence_days", 999) <= 90
                 and f.get("passing_scan_on_file", False)) else FAIL,
        "scan cadence and last result")
    return out


def _decide(rule, a, cond, why):
    miss = a.missing(RULE_PRECONDITIONS[rule])
    if miss:
        return Verdict(rule, REFUSE,
                       "evidence does not carry: " + ", ".join(miss),
                       tuple(miss))
    return Verdict(rule, PASS if cond() else FAIL, why)


def check_definition_aware(a: Assessment) -> dict:
    """Scope first, then the requirement, refusing without the inputs."""
    f = a.fields
    out = {}

    def in_scope() -> bool:
        if f["stores_processes_transmits"]:
            return True
        if f["connected_to_cde"]:
            return not f["segmentation_validated"]
        return False

    alt = lambda: (f.get("compensating_control_documented", False)
                   or f.get("customized_approach_trra", False))

    def guarded(rule, cond, why):
        miss = a.missing(RULE_PRECONDITIONS[rule])
        if miss:
            return Verdict(rule, REFUSE,
                           "evidence does not carry: " + ", ".join(miss),
                           tuple(miss))
        if not in_scope():
            return Verdict(rule, PASS,
                           "not applicable: system is outside the CDE and "
                           "segmentation is validated")
        return Verdict(rule, PASS if cond() else FAIL, why)

    out["network_segmentation"] = guarded(
        "network_segmentation", lambda: f["segmentation_test_evidence"],
        "segmentation asserted AND tested")
    out["no_vendor_defaults"] = guarded(
        "no_vendor_defaults",
        lambda: (not f["default_accounts_present"]) or alt(),
        "defaults removed, or a documented alternative")
    out["pan_storage"] = guarded(
        "pan_storage",
        lambda: ((not f["stores_pan"])
                 or f["pan_protection_method"] in ("truncation", "strong_crypto")
                 or alt()),
        "PAN unreadable, or a documented alternative")
    out["mfa_into_cde"] = guarded(
        "mfa_into_cde",
        lambda: f["mfa_enabled"] or f["access_path"] == "internal_only" or alt(),
        "MFA, or no external access path, or a documented alternative")
    out["log_retention"] = guarded(
        "log_retention",
        lambda: (f["log_retention_months"] >= LOG_RETENTION_MONTHS_MIN
                 and f["log_immediate_months"] >= LOG_IMMEDIATE_MONTHS_MIN),
        f"{LOG_RETENTION_MONTHS_MIN} months retained, "
        f"{LOG_IMMEDIATE_MONTHS_MIN} immediately available")
    out["vuln_scanning"] = guarded(
        "vuln_scanning",
        lambda: (f["scan_cadence_days"] <= SCAN_CADENCE_DAYS_MAX
                 and f["passing_scan_on_file"]),
        "quarterly cadence with a passing scan on file")
    return out


def with_intake(a: Assessment, truth: System) -> Assessment:
    merged = dict(a.fields)
    for k in INTAKE_ADDITIONS:
        merged.setdefault(k, getattr(truth, k))
    return Assessment(system_id=a.system_id, evidence_tier=a.evidence_tier,
                      tagged_pci=a.tagged_pci, fields=merged)


def corpus(n: int):
    for i in range(n):
        sy = make_system(i)
        yield sy, make_assessment(sy)

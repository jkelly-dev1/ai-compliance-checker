"""One test per trap, asserting the specific thing the naive checker gets wrong.

Why these are separate from the invariants. The invariants prove the harness is
sound. These prove the ENCODING says what the docstrings claim it says, that an
eave inside its allowance really does not encroach, that "encryption off" is
really not a HIPAA violation on its own, that a carved-out control is really
not a finding. A regime whose traps do not fire is a regime whose 20-something
percent naive error rate came from somewhere else.
"""

from __future__ import annotations

from acc import card_act, hipaa, pci, soc2, zoning
from acc.verdict import FAIL, PASS, REFUSE


# ------------------------------------------------------------------ ZONING

def test_an_eave_inside_its_allowance_does_not_encroach():
    """Trap 1: the roof outline includes what the ordinance lets project."""
    parcel = sub = None
    for p, sb in zoning.corpus(400):
        proj = p.projections
        # A parcel whose wall clears the setback but whose eave crosses it.
        # The parcel must be COMPLIANT and still fail the naive reading:
        # otherwise the test picks one that violates a side or rear setback
        # for an unrelated reason and proves nothing about eaves.
        if (p.lot_type == "interior" and proj.get("eave", 0) >= 2.0
                and p.wall_front_ft >= 25.0
                and p.wall_front_ft - proj["eave"] < 25.0
                and p.truth()["setback"] is True):
            parcel, sub = p, sb
            break
    assert parcel is not None, "no parcel exercises the eave trap"
    assert parcel.truth()["setback"] is True
    assert zoning.check_naive(sub)["setback"].result == FAIL, (
        "the naive checker should see the eave as an encroachment")


def test_a_corner_lot_street_side_takes_the_front_setback():
    """Trap 2: the second frontage is not a side yard."""
    for p, _ in zoning.corpus(400):
        if p.lot_type == "corner" and 5.0 <= p.wall_side_ft < 25.0:
            assert p.truth()["setback"] is False, (
                "a corner lot 5-25 ft from the street side violates the front "
                "setback, whatever a side-yard reading says")
            return
    raise AssertionError("no corner lot exercises the second-frontage trap")


# ------------------------------------------------------------------- HIPAA

def test_encryption_off_with_an_assessment_is_compliant():
    """Addressable is not optional, and it is not mandatory either.

    This is the most misread thing in the Security Rule and the reason the
    naive checker produces false gaps rather than false comfort here.
    """
    e = hipaa.make_entity(0)
    e.encryption_enabled = False
    e.risk_assessment_on_file = True
    e.alternative_control_documented = True
    assert e.truth()["encryption_at_rest"] is True

    sub = hipaa.Submission("E", "document_review", {
        "encryption_enabled": False, "risk_assessment_on_file": True,
        "alternative_control_documented": True})
    assert hipaa.check_definition_aware(sub)["encryption_at_rest"].result == PASS
    assert hipaa.check_naive(sub)["encryption_at_rest"].result == FAIL


def test_a_three_digit_zip_below_the_population_floor_is_not_de_identified():
    """The conditional Safe Harbor category, and the one that needs an
    external fact. A column-name scan cannot see it at all."""
    fields = {"released_columns": ("patient_key", "dx_code"),
              "date_precision": "year", "zip_digits": 3,
              "zip3_population": 11800}
    sub = hipaa.Submission("E", "full_assessment", fields)
    assert hipaa.check_definition_aware(sub)["de_identification"].result == FAIL
    assert hipaa.check_naive(sub)["de_identification"].result == PASS, (
        "the naive scan sees no direct identifier and calls it de-identified")


def test_without_the_population_figure_the_answer_is_a_refusal():
    fields = {"released_columns": ("patient_key",), "date_precision": "year",
              "zip_digits": 3}
    sub = hipaa.Submission("E", "config_export", fields)
    v = hipaa.check_definition_aware(sub)["de_identification"]
    assert v.result == REFUSE and "zip3_population" in v.missing


def test_claiming_the_conduit_exception_while_processing_does_not_help():
    fields = {"vendor_receives_ephi": True, "baa_executed": False,
              "conduit_exception_claimed": True,
              "vendor_access_type": "processes"}
    sub = hipaa.Submission("E", "document_review", fields)
    assert hipaa.check_definition_aware(sub)["business_associate"].result == FAIL


# --------------------------------------------------------------------- PCI

def test_an_out_of_scope_system_is_compliant_not_untested():
    """Segmentation validated and nothing stored: the requirement does not
    apply, which is a PASS and is not the same as nobody having looked."""
    fields = {"stores_processes_transmits": False, "connected_to_cde": True,
              "segmentation_validated": True, "segmentation_test_evidence": True,
              "default_accounts_present": True,
              "compensating_control_documented": False}
    a = pci.Assessment("S", "qsa_walkthrough", True, fields)
    v = pci.check_definition_aware(a)["no_vendor_defaults"]
    assert v.result == PASS and "not applicable" in v.reason


def test_a_connected_system_without_validated_segmentation_is_in_scope():
    sy = pci.make_system(0)
    sy.stores_processes_transmits = False
    sy.connected_to_cde = True
    sy.segmentation_validated = False
    assert sy.in_scope() is True


def test_the_naive_checker_passes_whatever_is_not_tagged():
    """The not-applicable / not-tested collapse, asserted rather than left as a
    design note. It is the single choice most responsible for the naive error
    rate in this regime, and it is what dashboards actually do."""
    a = pci.Assessment("S", "scanner_output", False, {})
    assert all(v.result == PASS for v in pci.check_naive(a).values())


# -------------------------------------------------------------------- SOC 2

def test_a_snapshot_cannot_answer_an_operating_effectiveness_question():
    """The trap this regime exists for. Config evidence supports a design
    conclusion and no period conclusion, so the honest checker refuses."""
    ev = soc2.Evidence("G", "config_snapshot",
                       {"control_designed": {r: True for r in soc2.RULES}})
    for rule, v in soc2.check_definition_aware(ev).items():
        assert v.result == REFUSE
        assert "report_type" in v.missing or "period_days" in v.missing
    # And the naive checker answers all six from the same snapshot.
    assert all(v.decided() for v in soc2.check_naive(ev).values())


def test_a_criterion_outside_the_selected_categories_is_not_a_gap():
    ev = soc2.Evidence("G", "auditor_workpapers", {
        "report_type": "type_i", "categories_in_scope": ("security",),
        "subservice_treatment": "none", "subservice_owned": (),
        "cuec_documented": True,
        "control_designed": {r: False for r in soc2.RULES},
        "control_operated_sample": {}, "sample_exceptions": {},
        "period_days": 365})
    out = soc2.check_definition_aware(ev)
    assert out["availability_capacity"].result == PASS
    assert "not applicable" in out["availability_capacity"].reason
    # A security criterion with the same broken design is still a failure.
    assert out["logical_access"].result == FAIL


def test_a_carved_out_control_is_not_a_finding_against_this_entity():
    ev = soc2.Evidence("G", "auditor_workpapers", {
        "report_type": "type_ii", "categories_in_scope": ("security",),
        "subservice_treatment": "carve_out",
        "subservice_owned": ("monitoring",), "cuec_documented": True,
        "control_designed": {r: False for r in soc2.RULES},
        "control_operated_sample": {}, "sample_exceptions": {},
        "period_days": 365})
    assert soc2.check_definition_aware(ev)["monitoring"].result == PASS


def test_a_few_exceptions_in_an_adequate_sample_is_still_effective():
    """Operating effectiveness is a rate, not a boolean. One deviation in
    forty is not a failed control, and the naive checker says it is."""
    common = {"report_type": "type_ii", "categories_in_scope": ("security",),
              "subservice_treatment": "none", "subservice_owned": (),
              "cuec_documented": True, "period_days": 365,
              "control_designed": {r: True for r in soc2.RULES},
              "control_operated_sample": {r: 40 for r in soc2.RULES},
              "sample_exceptions": {r: 1 for r in soc2.RULES}}
    ev = soc2.Evidence("G", "auditor_workpapers", common)
    assert soc2.check_definition_aware(ev)["logical_access"].result == PASS
    assert soc2.check_naive(ev)["logical_access"].result == FAIL


# ----------------------------------------------------------------- CARD ACT

def test_above_minimum_goes_to_the_highest_apr_first():
    """The one place in this repository where the arithmetic is the Rule.

    Two balances, one payment. Proportional allocation is arithmetically
    defensible and is the wrong computation.
    """
    a = card_act.make_account(0)
    a.balances = {"promo": (100000, 0), "cash_advance": (100000, 2500)}
    a.minimum_due_cents = 5000
    a.payment_cents = 45000
    required = a.required_allocation()
    assert required["cash_advance"] == 40000 and required["promo"] == 0

    # What a proportional issuer does with the same payment.
    a.allocation_applied = {"promo": 20000, "cash_advance": 20000}
    assert a.truth()["payment_allocation"] is False

    a.allocation_applied = {"promo": 0, "cash_advance": 40000}
    assert a.truth()["payment_allocation"] is True


def test_a_balance_snapshot_cannot_answer_a_timing_rule():
    r = card_act.Record("A", "balance_snapshot", {
        "balances": {"purchases": (10000, 1800)}, "minimum_due_cents": 2500,
        "payment_cents": 5000})
    v = card_act.check_definition_aware(r)["statement_timing"]
    assert v.result == REFUSE
    # And the naive checker calls it compliant from nothing at all.
    assert card_act.check_naive(r)["statement_timing"].result == PASS


def test_consent_revoked_before_the_fee_is_not_consent():
    fields = {"over_limit_fee_charged": True, "opt_in_on_file": True,
              "opt_in_revoked_day": 10, "fee_charged_day": 20}
    r = card_act.Record("A", "exam_file", fields)
    assert card_act.check_definition_aware(r)["over_limit_opt_in"].result == FAIL
    # The naive checker reads the flag, which still says opted in.
    assert card_act.check_naive(r)["over_limit_opt_in"].result == PASS

# SAMPLE_RUN

Everything below is real output from the commands shown. The offline half
regenerates with `scripts/offline_demo.py`; the paid half is stored in `audit/`.

## Tests

```
$ .venv/bin/python -m pytest -q
..........................................................................
84 passed in 0.40s
```

Three layers. `test_invariants.py` runs ten checks over ALL FIVE regimes,
including the one the repository rests on, every checker except the naive one
must be never wrong, plus a mutation check that builds a deliberately reckless
checker to prove that assertion can fail. `test_traps.py` asserts one test per
documented trap. `test_version_bump.py` encodes three defects that already
happened.

## The offline measurement

```
$ .venv/bin/python scripts/offline_demo.py --cases 600 --json audit/offline.json
ai-compliance-checker -- offline measurement
no model was called   cases per regime: 600

1. THE RATIO: what a regime states against what decides it
   the zoning ordinance states 6 limits and carries 10 definitions (1.67 per limit)
   the other four regimes are encoded rule-by-rule; their equivalent is
   the precondition set, printed per regime below

==========================================================================
2-4. THE BOUNDARY, PER REGIME
==========================================================================

ZONING :  Northgate R-1, a synthetic ordinance -- not any jurisdiction's code
600 cases x 4 rules = 2400 decisions

  checker                         decided              wrong   refused
  v1_naive                 2400 (100.0%)    484 ( 20.2% of decided)         0
  v2_definition_aware       684 ( 28.5%)      0 (  0.0% of decided)      1716
  v4_minimal                684 ( 28.5%)      0 (  0.0% of decided)      1716
  v3_with_intake           1389 ( 57.9%)      0 (  0.0% of decided)      1011

  naive checker, error direction by rule
    setback                  false pass   44   false fail  104   MIXED
    height                   false pass    1   false fail  286   MIXED
    coverage                 false pass    9   false fail   28   MIXED
    stories                  false pass    7   false fail    5   MIXED

  honest checker, decided by evidence tier
    bim                        532 of 532   (100.0%)   n=133
    cad                        152 of 608   ( 25.0%)   n=152
    pdf_vector                   0 of 952   (  0.0%)   n=238
    pdf_scan                     0 of 308   (  0.0%)   n=77

  what the refusals needed, most common first
       630  access_strip_ft
       630  wall_polygon
       467  deck_height_in
       467  perimeter_grades_ft
       467  basement_rear_exposure_ft
       467  mezzanine_area_sf

HIPAA  --  45 CFR 164 (subsets of 164.306, 164.308, 164.312, 164.514)
600 cases x 6 rules = 3600 decisions

  checker                         decided              wrong   refused
  v1_naive                 3600 (100.0%)    791 ( 22.0% of decided)         0
  v2_definition_aware      1558 ( 43.3%)      0 (  0.0% of decided)      2042
  v4_minimal               2467 ( 68.5%)      0 (  0.0% of decided)      1133
  v3_with_intake           2656 ( 73.8%)      0 (  0.0% of decided)       944

  naive checker, error direction by rule
    encryption_at_rest       false pass    0   false fail  130   false fails only
    audit_controls           false pass   95   false fail   88   MIXED
    unique_user_id           false pass    0   false fail    0   never wrong
    workforce_termination    false pass   33   false fail  160   MIXED
    business_associate       false pass    0   false fail    6   false fails only
    de_identification        false pass  279   false fail    0   false passes only

  honest checker, decided by evidence tier
    questionnaire              209 of 1254  ( 16.7%)   n=209
    config_export              170 of 1020  ( 16.7%)   n=170
    document_review            735 of 882   ( 83.3%)   n=147
    full_assessment            444 of 444   (100.0%)   n=74

  what the refusals needed, most common first
       758  risk_assessment_on_file
       758  alternative_control_documented
       526  zip3_population
       379  log_review_evidence
       379  revocation_sla_met
       379  conduit_exception_claimed

PCI_DSS  --  PCI DSS v4.0 (subsets of Req 1, 2, 3, 8, 10, 11)
600 cases x 6 rules = 3600 decisions

  checker                         decided              wrong   refused
  v1_naive                 3600 (100.0%)    528 ( 14.7% of decided)         0
  v2_definition_aware       744 ( 20.7%)      0 (  0.0% of decided)      2856
  v4_minimal               1866 ( 51.8%)      0 (  0.0% of decided)      1734
  v3_with_intake           2300 ( 63.9%)      0 (  0.0% of decided)      1300

  naive checker, error direction by rule
    network_segmentation     false pass   61   false fail   63   MIXED
    no_vendor_defaults       false pass   19   false fail   30   MIXED
    pan_storage              false pass    2   false fail    1   MIXED
    mfa_into_cde             false pass    3   false fail  126   MIXED
    log_retention            false pass   38   false fail   76   MIXED
    vuln_scanning            false pass   41   false fail   68   MIXED

  honest checker, decided by evidence tier
    asset_tag                    0 of 1056  (  0.0%)   n=176
    scanner_output               0 of 1260  (  0.0%)   n=210
    config_and_policy          270 of 810   ( 33.3%)   n=135
    qsa_walkthrough            474 of 474   (100.0%)   n=79

  what the refusals needed, most common first
      2316  stores_processes_transmits
      2316  connected_to_cde
      2316  segmentation_validated
      1042  compensating_control_documented
       521  segmentation_test_evidence
       521  customized_approach_trra

SOC2  --  AICPA TSC 2017 (rev. 2022 points of focus), subsets of CC6-CC9, A1, C1
600 cases x 6 rules = 3600 decisions

  checker                         decided              wrong   refused
  v1_naive                 3600 (100.0%)   1308 ( 36.3% of decided)         0
  v2_definition_aware       486 ( 13.5%)      0 (  0.0% of decided)      3114
  v4_minimal                486 ( 13.5%)      0 (  0.0% of decided)      3114
  v3_with_intake           1320 ( 36.7%)      0 (  0.0% of decided)      2280

  naive checker, error direction by rule
    logical_access           false pass  142   false fail   75   MIXED
    change_management        false pass  155   false fail   74   MIXED
    monitoring               false pass  144   false fail   85   MIXED
    vendor_management        false pass  151   false fail   76   MIXED
    availability_capacity    false pass   73   false fail  135   MIXED
    confidential_disposal    false pass   62   false fail  136   MIXED

  honest checker, decided by evidence tier
    config_snapshot              0 of 1188  (  0.0%)   n=198
    ticket_export                0 of 1092  (  0.0%)   n=182
    period_sample                0 of 834   (  0.0%)   n=139
    auditor_workpapers         486 of 486   (100.0%)   n=81

  what the refusals needed, most common first
      3114  categories_in_scope
      3114  subservice_treatment
      3114  subservice_owned
      3114  cuec_documented
      2280  report_type
      2280  period_days

CARD_ACT  --  Credit CARD Act of 2009 via Reg Z: 12 CFR 1026.53, 1026.5(b)(2)(ii), 1026.56
600 cases x 3 rules = 1800 decisions

  checker                         decided              wrong   refused
  v1_naive                 1800 (100.0%)    372 ( 20.7% of decided)         0
  v2_definition_aware       905 ( 50.3%)      0 (  0.0% of decided)       895
  v4_minimal                905 ( 50.3%)      0 (  0.0% of decided)       895
  v3_with_intake           1800 (100.0%)      0 (  0.0% of decided)         0

  naive checker, error direction by rule
    payment_allocation       false pass  112   false fail  151   MIXED
    statement_timing         false pass   39   false fail    0   false passes only
    over_limit_opt_in        false pass   52   false fail   18   MIXED

  honest checker, decided by evidence tier
    balance_snapshot             0 of 558   (  0.0%)   n=186
    statement_export           354 of 531   ( 66.7%)   n=177
    event_log                  320 of 480   ( 66.7%)   n=160
    exam_file                  231 of 231   (100.0%)   n=77

  what the refusals needed, most common first
       523  opt_in_on_file
       523  opt_in_revoked_day
       363  over_limit_fee_charged
       363  fee_charged_day
       186  allocation_applied
       186  statement_sent_day

==========================================================================
THE SAME MEASUREMENT, SIDE BY SIDE
==========================================================================
  regime          v1 naive    v2 all-precond        v4 minimal   v3 intake
  ------------------------------------------------------------------------
  zoning     wrong  20.2%     28.5% dec         28.5% dec         57.9%
  hipaa      wrong  22.0%     43.3% dec         68.5% dec         73.8%
  pci_dss    wrong  14.7%     20.7% dec         51.8% dec         63.9%
  soc2       wrong  36.3%     13.5% dec         13.5% dec         36.7%
  card_act   wrong  20.7%     50.3% dec         50.3% dec        100.0%

  v2, v4 and v3 are all NEVER WRONG. Only v1 has an error rate, which is
  why the other three are reported by what they DECIDE.

  The naive checker answers everything and is wrong 15-36% of the
  time; the other three are never wrong and answer a minority.
  Those are not points on one scale, which is why no accuracy
  figure appears anywhere in this repository.

  v2 -> v4 IS FREE. Same rules, same evidence; v4 simply stops
  refusing once the answer is determined by the fields present.
  On HIPAA that is worth more than half of what changing the
  intake form buys, at no cost to anyone submitting anything.

==========================================================================
5. THE AMENDMENT: what a routine edition change re-decides
==========================================================================
  regime       issued   ->FAIL   ->PASS   now wrong   amendment
  zoning          684       30        0     30 ( 4.4%)   height limit lowered from 30 ft to 28 ft
  hipaa          1558        4        0      4 ( 0.3%)   Safe Harbor ZIP3 population floor raised from 20,000 to 30,000
  pci_dss         744       15        0     15 ( 2.0%)   immediately-available log window raised from 3 months to 6
  soc2            486       44        0     44 ( 9.1%)   minimum Type II sample raised from 25 to 40
  card_act        905      137        0    137 (15.1%)   statement delivery window raised from 21 days to 25

  Every flip is toward FAIL and none toward PASS. These are not
  errors: they are decisions issued correctly under one edition
  that are unsupportable under the next, and nothing in the
  checker's inputs changed, so nothing notices.

wrote audit/offline.json
```

## The paid measurement

Two models, four cells, 40 cases per regime, $5.22 across four runs. Both
models were given the rule as written, the same evidence the honest checker
sees, and an explicit `insufficient_evidence` verdict.

```
WHERE THE HONEST CHECKER REFUSED: the evidence cannot support a decision
  model            regime   refused too   decided anyway   of those, wrong
  claude-sonnet-5  hipaa      75/147          72/147         4/72   ( 5.6%)
  gpt-5.4          hipaa      66/147          81/147         7/81   ( 8.6%)
  claude-sonnet-5  soc2       42/198         156/198        27/156  (17.3%)
  gpt-5.4          soc2      141/192          51/192         2/51   ( 3.9%)

WHERE THE HONEST CHECKER DECIDED: a model that refuses everything is useless
  model            regime        agreed   refused   disagreed
  claude-sonnet-5  hipaa          92/93         0           1
  gpt-5.4          hipaa          90/93         2           1
  claude-sonnet-5  soc2           37/42         5           0
  gpt-5.4          soc2           34/42         8           0
```

Two models, identical prompts, opposite behavior. On SOC 2's impossible cases
gpt-5.4 refuses 73.4%; claude-sonnet-5 decides 78.8% of them. The pre-registered
branches, written before any call, fired differently for the two models on the
same regime. Per that pre-registration, two models is not a provider comparison
and no provider claim is made.

What it means, set against the minimal checker. On HIPAA, 42% of the honest
checker's refusals were over-refusals that v4 recovers; deciding them anyway
costs 5-9%. On SOC 2, v4 recovers NONE of them, the missing evidence is a KIND
of evidence, not a field, and the model that decided 78.8% of them paid 17.3%.
The models were not better at compliance than the checker. They were better at
spotting where its precondition sets were too strict.

## One run was invalidated by its own pre-registration

The first SOC 2 run returned 65% and 15% unparseable output against a
pre-registered 10% threshold, so it was reported as INVALID rather than as a
finding, and re-run:

```
  unparseable        before   after
  claude-sonnet-5     65.0%    0.0%
  gpt-5.4             15.0%    2.5%
```

The cause was a 1,500-token cap against a model averaging 1,948 output tokens on
that prompt: every reply cut mid-object and counted as a model failure. The
re-run proves it from the artifact rather than by inference, because
`stop_reason` is now recorded per record; the first run fetched it and stored it
nowhere.

## What is not measured here

Any real portfolio. Every population is constructed and the rates in each
regime module are stated constants. The regimes are simplified encodings
written to be checkable against their cited sources, not compliance products,
and nothing here is legal advice.

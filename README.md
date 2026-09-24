# ai-compliance-checker

What fraction of a regulatory decision can be automated without ever being
wrong? Five regimes, four checkers each, two language models, and a measured
boundary.

A personal learning project. The premise everywhere is the same: a rule states
a limit anyone can read off a summary card, and something else entirely decides
whether a given case meets it. This measures what a checker that reads only the
limit gets wrong, what an honest checker that refuses can still decide, how
much of the remaining gap closes for free, and how much needs a changed intake
form.

Nothing in the measurement is imported from outside the standard library.

## The one-sentence result

Across five unrelated regimes, a checker that always answers is wrong on 15%
to 36% of its decisions, and a checker that refuses when the evidence cannot
support a decision is never wrong while still deciding 13% to 50% of them. Both
ranges are over DECISIONS, 600 cases times four rules is 2400 zoning decisions,
and not over cases.

And a second one, which is what a compliance program would actually act on:
before asking anyone for more evidence, stop refusing the cases you can
already decide. A checker that stops when the answer is determined, same
rules, same evidence, no new forms, takes HIPAA from 43.3% to 68.5% decided and
PCI from 20.7% to 51.8%, still never wrong. That is more than half of what
changing the intake form buys, for nothing.

Two language models found that before I did. See "What the paid run changed".

## The five regimes

| regime | what it encodes | the trap that makes it hard |
|---|---|---|
| `zoning` | a synthetic residential ordinance | the roof outline is not the wall, and the ordinance measures to the wall |
| `hipaa` | 45 CFR 164, six requirements | **addressable is not optional**, and Safe Harbor has two conditional categories |
| `pci_dss` | PCI DSS v4.0, six requirements | **scope**: which system the requirement is even about |
| `soc2` | AICPA TSC, six criteria | **Type I evidence answering a Type II question** |
| `card_act` | Reg Z, three rules | **the arithmetic is the rule**, not the definition around it |

Each is a simplified encoding written to be checkable against its cited source.
None is a compliance product and none is legal advice. The zoning ordinance is
synthetic and quotes no jurisdiction; the other four cite the section each rule
comes from so the encoding can be argued with.

## The boundary

```
  regime          v1 naive    v2 all-precond        v4 minimal   v3 intake
  ------------------------------------------------------------------------
  zoning     wrong  24.9%     28.5% dec         28.5% dec         57.9%
  hipaa      wrong  22.0%     43.3% dec         68.5% dec         79.6%
  pci_dss    wrong  14.7%     20.7% dec         51.8% dec         69.7%
  soc2       wrong  36.3%     13.5% dec         13.5% dec         36.7%
  card_act   wrong  20.7%     50.3% dec         50.3% dec        100.0%
```

The run uses 600 cases per regime. v2, v4 and v3 are all never wrong; only v1 has an error
rate, so the others are reported by what they decide.

v1 implements the stated limits against the fields the submission actually
carries; every line of it is the obvious reading. v2 implements the rule as
written, declares a precondition set, and REFUSES when the evidence does not
reach. v4 is the same checker asked a better question: it stops refusing once
the answer is determined by the fields present. v3 is v2 after a changed intake
form supplies a handful of additional documents.

Three regimes do not move between v2 and v4, and that is the design working.
Zoning, SOC 2 and CARD Act carry their evidence as dicts and lists, wall
polygons, per-rule control maps, balance sets, which cannot be enumerated, so
those refusals stand. Sampling them would decide on a subset of the possible
worlds and could be wrong, and never-wrong is the one property this repository
will not trade.

Accuracy is never reported here. A checker that answers everything and is right
78% of the time and a checker that answers a fifth of the cases and is never
wrong are not two points on one scale. Collapsing them into one number is the
commonest way this domain is misdescribed.

## The direction of the error is a property of the missing definition

Pooling errors hides the only thing that decides whether a naive checker is
usable. HIPAA shows all three patterns in one regime:

```
  encryption_at_rest       false pass    0   false fail  130   false fails only
  audit_controls           false pass   95   false fail   88   MIXED
  unique_user_id           false pass    0   false fail    0   never wrong
  workforce_termination    false pass   33   false fail  160   MIXED
  business_associate       false pass    0   false fail    6   false fails only
  de_identification        false pass  279   false fail    0   false passes only
```

`unique_user_id` has no conditional qualifier, so the checklist reading is the
rule and the naive checker is never wrong. Any claim that naive checking always
fails is refuted by that row.

`de_identification` fails only in the dangerous direction: 279 datasets declared
de-identified that are not, because a column-name scan cannot see date precision
or the ZIP3 population floor.

`encryption_at_rest` fails only in the safe-but-expensive direction: the
addressable trap generates false gaps, never false comfort.

PCI is MIXED on every requirement, for a different reason: a scoping error
moves the answer both ways at once, so no safety margin repairs it.

## A single decidability number is close to meaningless

The honest checker's decided rate is not spread across the queue. It is
concentrated entirely in the submissions that already arrive as structured data:

```
ZONING                          SOC 2
  bim         100.0%   n=133      config_snapshot      0.0%   n=198
  cad          25.0%   n=152      ticket_export        0.0%   n=182
  pdf_vector    0.0%   n=238      period_sample        0.0%   n=139
  pdf_scan      0.0%   n=77       auditor_workpapers 100.0%   n=81
```

Zoning's 28.5% is every BIM submittal, a quarter of the CAD ones, and exactly
zero of the two PDF formats, which are 53% of the population. SOC 2's 13.5% is
100% of one tier and 0% of the other three, because a configuration snapshot is
not weak evidence for an operating-effectiveness question, it is no evidence at
all.

"We can automate a quarter of compliance checking" is the headline this
decomposition kills.

## What the refusals need, and whether a form can fix it

```
HIPAA, what the refusals needed, most common first
     758  risk_assessment_on_file
     758  alternative_control_documented
     526  zip3_population
     379  log_review_evidence
```

Most are documents an entity either has or does not, and requiring them is an
intake change. `zip3_population` is not: it is an external census fact, and no
intake form can make an applicant produce it. That distinction is why the
refusal causes are ranked and reported rather than summarized. Three of these
are form fields and one is a research task.

The two at the top are tied because they are the same requirement read twice:
the addressable arm of `encryption_at_rest` and of `workforce_termination`
both need an assessment AND a documented alternative, so neither rule can be
decided without both. A ranking that separated them would be describing two
problems where there is one.

## An amendment re-decides cases nobody reopens

A routine tightening, applied to the same population, against decisions the
honest checker had already issued:

```
  regime       issued   ->FAIL   ->PASS   now wrong   amendment
  zoning          684       30        0     30 ( 4.4%)   height 30 ft -> 28 ft
  hipaa          1558        4        0      4 ( 0.3%)   ZIP3 floor 20k -> 30k
  pci_dss         744       15        0     15 ( 2.0%)   log window 3 mo -> 6 mo
  soc2            486       44        0     44 ( 9.1%)   Type II sample 25 -> 40
  card_act        905      137        0    137 (15.1%)   statement 21 d -> 25 d
```

Every flip is toward FAIL and none toward PASS. These are not errors: they are
decisions issued correctly under one edition that are unsupportable under the
next, and nothing in the checker's inputs changed, so nothing notices. A
four-day change to a statement window re-decides fifty times more of the
population than a ten-thousand-person change to a ZIP3 floor. The size of an
amendment says nothing about its blast radius.

## Claims backed by tests

Of the 17 tests in `tests/test_invariants.py`, 14 run over all five regimes,
because a regime joins by writing a module and one registry line, and a test
that only ran over zoning would let a new regime arrive with a broken encoding
and a plausible-looking table. The three that do not are the mutation check,
which deliberately breaks one named regime, the registry-construction check,
which builds no regime at all, and the check that the minimal checker reads its
domains from the population being measured, which needs only one regime to
observe the call.

| Claim | Test |
| --- | --- |
| The honest checker is never wrong, in every regime, for all three of v2, v4 and v3 | `tests/test_invariants.py::test_the_honest_checker_is_never_wrong` (mutation-checked: `::test_breaking_a_checker_breaks_the_invariant` binds a checker that ignores its preconditions INTO THE REGISTRY, runs the real `measure()` over it, and requires the same assertion function the test above calls to raise) |
| The naive checker is wrong somewhere in every regime, so the comparison is not a checker against itself | `tests/test_invariants.py::test_the_naive_checker_is_wrong_somewhere` |
| The naive checker never refuses, so the contrast is answers-everything against refuses-honestly and not three different questions | `tests/test_invariants.py::test_the_naive_checker_never_refuses` |
| The honest checker refuses something in every regime, so no decided rate comes from a third verdict nobody used | `tests/test_invariants.py::test_the_honest_checker_refuses_something` |
| A changed intake form only ever adds evidence: v3 decides at least as much as v2 everywhere | `tests/test_invariants.py::test_intake_only_ever_adds_evidence` |
| No checker names a population constructor or touches a `.truth` attribute, read off the source of every checker module | `tests/test_invariants.py::test_no_checker_names_a_truth_constructor` (the dynamic check below cannot see this: a checker that consulted the truth object would answer CORRECTLY, so the measurement and the artifact are both unchanged) |
| Every precondition set is non-empty: strip a submission of every field and every rule refuses | `tests/test_invariants.py::test_a_checker_cannot_reach_the_truth_object` |
| Every rule is violated by some case and satisfied by another, so no column is decoration | `tests/test_invariants.py::test_every_rule_is_exercised_in_both_directions` (the guard that caught a units error making zoning's height rule unviolatable) |
| Every corpus is deterministic, so the tables compare comparable runs | `tests/test_invariants.py::test_the_corpus_is_deterministic` |
| A rule reads only the fields its precondition set declares | `tests/test_invariants.py::test_no_rule_reads_a_field_it_did_not_declare` (instruments the submission's `fields` and records every key read, so a `.get(x, default)` read counts) |
| A rule reads EVERY field its precondition set declares, so a refusal never names evidence the rule would not have looked at | `tests/test_invariants.py::test_every_declared_precondition_is_actually_read` |
| Both of the above examined every rule in every regime, rather than skipping the ones they could not enumerate | `tests/test_invariants.py::test_the_read_probe_examined_every_rule` |
| Some evidence tier carries every field the population can supply, so tightening a rule cannot remove evidence from the world | `tests/test_invariants.py::test_some_evidence_tier_carries_everything_the_population_has` |
| A regime with a rule that declares no preconditions is refused at construction | `tests/test_invariants.py::test_a_regime_missing_preconditions_is_refused_at_construction` |
| An eave inside its allowance does not encroach, and the naive reading calls it a violation | `tests/test_traps.py::test_an_eave_inside_its_allowance_does_not_encroach` |
| A corner lot's street side takes the front setback, not the side yard | `tests/test_traps.py::test_a_corner_lot_street_side_takes_the_front_setback` |
| A projection is charged only against the yard it is built into: a front porch inside its front allowance does not encroach on the side yard | `tests/test_traps.py::test_a_projection_is_charged_only_against_the_yard_it_is_in` |
| The 30-inch clause of the deck allowance changes an answer, so the definition is not in the table for flavor | `tests/test_traps.py::test_the_deck_height_clause_changes_an_answer` |
| Every lot type is exercised in both directions, so no conditional branch decides every case it touches the same way | `tests/test_traps.py::test_every_lot_type_is_exercised_in_both_directions` |
| The constructed population violates at the declared rate, so the design claim about it is measured rather than asserted | `tests/test_traps.py::test_the_population_violation_rate_stays_in_its_band` |
| A projection whose schedule does not say which yard it is in makes the setback rule refuse, not pass | `tests/test_traps.py::test_a_projection_with_no_stated_yard_is_refused_not_ignored` |
| The count of invariant tests that run over every regime, stated above, is read off the test file | `tests/test_gates.py::test_the_readme_checker_counts_the_invariant_tests_from_the_file` |
| Addressable is not optional and not mandatory: encryption off, with an assessment and a documented alternative, is compliant | `tests/test_traps.py::test_encryption_off_with_an_assessment_is_compliant` |
| A three-digit ZIP below the population floor is not de-identified, and the column-name scan calls it de-identified | `tests/test_traps.py::test_a_three_digit_zip_below_the_population_floor_is_not_de_identified` |
| Without the population figure the honest answer is a refusal that names the missing field | `tests/test_traps.py::test_without_the_population_figure_the_answer_is_a_refusal` |
| Claiming the conduit exception while processing ePHI does not help | `tests/test_traps.py::test_claiming_the_conduit_exception_while_processing_does_not_help` |
| An out-of-scope system is compliant, which is not the same fact as nobody having looked | `tests/test_traps.py::test_an_out_of_scope_system_is_compliant_not_untested` |
| A connected system without validated segmentation is in scope | `tests/test_traps.py::test_a_connected_system_without_validated_segmentation_is_in_scope` |
| The naive checker passes whatever is not tagged, which is the not-applicable and not-tested collapse | `tests/test_traps.py::test_the_naive_checker_passes_whatever_is_not_tagged` |
| A configuration snapshot cannot answer an operating-effectiveness question, and the naive checker answers all six criteria from one | `tests/test_traps.py::test_a_snapshot_cannot_answer_an_operating_effectiveness_question` |
| A criterion outside the selected categories is not a gap, while a security criterion with the same broken design still fails | `tests/test_traps.py::test_a_criterion_outside_the_selected_categories_is_not_a_gap` |
| A carved-out control is not a finding against this entity | `tests/test_traps.py::test_a_carved_out_control_is_not_a_finding_against_this_entity` |
| Operating effectiveness is a rate: one deviation in forty is not a failed control | `tests/test_traps.py::test_a_few_exceptions_in_an_adequate_sample_is_still_effective` |
| Above the minimum, payment goes to the highest APR first; proportional allocation is defensible arithmetic and the wrong computation | `tests/test_traps.py::test_above_minimum_goes_to_the_highest_apr_first` |
| A balance snapshot cannot answer a timing rule, and the naive checker calls it compliant from nothing at all | `tests/test_traps.py::test_a_balance_snapshot_cannot_answer_a_timing_rule` |
| Consent revoked before the fee is not consent, whatever the flag still says | `tests/test_traps.py::test_consent_revoked_before_the_fee_is_not_consent` |
| Every amendment in the table re-decides something | `tests/test_version_bump.py::test_every_amendment_actually_moves_something` (guards a defect that happened: a ZIP3 floor moved across a band the population has no mass in, reported 0.0%, and read as stability under revision) |
| A tightening flips decisions toward FAIL and never toward PASS | `tests/test_version_bump.py::test_a_tightening_never_flips_a_decision_to_pass` |
| The flip count and the now-wrong count agree | `tests/test_version_bump.py::test_flips_and_now_wrong_agree` (the signature of a defect that happened: truth moved, the registry still held the unpatched checker, and 0 flips sat beside 15 decisions that had become wrong) |
| An amendment restores the constant it patched, so it cannot re-decide later measurements in the same process | `tests/test_version_bump.py::test_the_bump_restores_the_constant_afterwards` |

The percentages are not in that table, and the never-wrong property is. 15% to
36%, 13% to 50%, HIPAA moving 43.3% to 68.5%: those come from
`scripts/offline_demo.py` over constructed populations whose rates are stated
constants in each regime module, and they scale with those constants. What the
tests assert is what does not scale, that the honest checkers are wrong zero
times, that the naive one is wrong somewhere and refuses nowhere, that intake
only adds, and that each trap fires in the specific direction the prose claims.

The paid run is absent because it is evidence rather than an invariant. The
refusal rates, the 17.3% figure and the two models disagreeing with each other
are what four regime legs did on one day, at $5.23 across the three run files
in `audit/`, and a test that re-ran them would cost money on every commit while
measuring a model's disposition rather than this repository's code. Raw
outcomes are in `audit/`, including the run that was invalidated by its own
pre-registration and kept.

## Reproducing

```
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q                                  # 121 tests
.venv/bin/python scripts/offline_demo.py --cases 600 --json audit/offline.json
.venv/bin/python scripts/check_artifact.py     # audit/offline.json vs the code
.venv/bin/python scripts/check_readme_numbers.py   # this page vs audit/
.venv/bin/python scripts/offline_demo.py --regime hipaa
```

All of it is free and needs no API key.

The last two are one chain and it only means something whole. `check_artifact.py`
re-derives `audit/offline.json` from the code in `acc/` at the artifact's own
case count and requires an exact match; `check_readme_numbers.py` rebuilds every
figure on this page from that artifact and requires the exact string. Without
the first, the tests and the demo both stay green while a population constant
moves every number here, because the invariants this repository asserts (never
wrong, wrong somewhere, never refuses) hold whatever the rates are.

## The invariant the whole repository rests on

The honest checker must never be wrong. It refuses when it cannot know, so any
nonzero number there is a defect in the encoding, a rule deciding on evidence it
does not have, and never a finding about the regime. `tests/test_invariants.py`
asserts it across all five regimes, and a mutation check builds a deliberately
reckless checker to prove the assertion can fail.

It has caught two real defects that were invisible inside their own modules:

- **SOC 2 came back 4.0% wrong.** The list of controls a carved-out subservice
  organization performs was truth-only, so the checker evaluated controls the
  entity did not own and failed them. It is a precondition now, and the checker
  refuses when nothing on hand says whose control it is.
- A units error made zoning's height rule unviolatable. Eave and ridge were bare
  heights while grades were elevations, so the true height came out around -80
  ft and not one parcel in 600 could exceed a 30 ft limit. The rule sat in every
  table with a true-violation count of zero.
  `test_every_rule_is_exercised_in_both_directions` is the generalized guard.

## What this does not measure

- **Any real portfolio.** Every population is constructed, and the rates in each
  regime module are stated constants. Every number scales with them.
- **Whether these encodings are complete.** They are subsets chosen to carry a
  specific trap. A real assessment turns on facts, scope and documentation no
  synthetic record carries.
- Extraction. Getting fields off a document is
  [vlm-extraction-integrity](https://github.com/jkelly-dev1/vlm-extraction-integrity)'s
  subject, and this one starts from the fields.
- **Whether a model can do this in general.** Four model-by-regime cells were
  measured (below) and they disagree with each other. Two models is not a
  provider comparison and nothing here is offered as one.

## What the paid run changed

Both models were handed the rule as written, the same evidence the honest
checker sees, and an explicit third verdict, `insufficient_evidence`, with the
reason it exists spelled out. Withholding that option would have rigged the
result. 40 cases per regime, both providers, $5.23 total: three run files in
`audit/`, covering four regime legs, because `real_run.json` holds HIPAA and
SOC 2 together and the two re-runs hold one regime each.

Where the honest checker refused; the evidence provably cannot support a
verdict:

```
  model            regime   refused too   decided anyway   of those, wrong
  claude-sonnet-5  hipaa      75/147          72/147         4/72   ( 5.6%)
  gpt-5.4          hipaa      66/147          81/147         7/81   ( 8.6%)
  claude-sonnet-5  soc2       42/198         156/198        27/156  (17.3%)
  gpt-5.4          soc2      141/192          51/192         2/51   ( 3.9%)
```

The control passes everywhere: on decisions the honest checker did make,
agreement was 92/93, 90/93, 37/42 and 34/42, with at most one disagreement per
cell. Neither model is abstaining indiscriminately.

Two models, identical prompts, opposite behavior. `gpt-5.4` refuses 73.4% of SOC
2's impossible cases; `claude-sonnet-5` decides 78.8% of them. Set that against
what the minimal checker showed:

| | HIPAA | SOC 2 |
|---|---|---|
| refusals that were **over-refusals** (recovered by v4) | 42% | 0% |
| wrong when deciding past a refusal -- sonnet | 5.6% | **17.3%** |
| wrong when deciding past a refusal -- gpt-5.4 | 8.6% | 3.9% |

Where 42% of the refusals were the checker's own conservatism, deciding anyway
costs 5-9%. Where none of them were, SOC 2, whose missing evidence is a kind
of evidence rather than a field, the model that decided most of them paid 17.3%.

So the models were not better at compliance than the checker. They were better
at noticing where its precondition sets were too strict, and no better than
guessing where the evidence genuinely could not support a decision. The minimal
checker separates those two cases mechanically and for free; the paid runs
confirm the separation from outside.

`claude-sonnet-5`'s SOC 2 errors concentrate exactly where the theory predicts:
`availability_capacity` and `confidential_disposal`, the two criteria whose
applicability depends on which categories management selected.

### One run was invalidated by its own pre-registration

Written before any call: *if either model returns unparseable output on more
than roughly 10% of calls, the comparison is measuring output formatting rather
than compliance judgment.* The first SOC 2 run returned 65% and 15% unparseable.
It was reported as invalid, not as a finding, and re-run with a larger token
cap: after which both models failed to parse on 0.0% and 2.5% of calls, well
inside the threshold, so the re-run stands.

The cap was not eliminated, only moved past the threshold, and the artifact
says so. In `audit/real_run_soc2.json` the stop reasons are `end_turn` 240 for
`claude-sonnet-5` and, for `gpt-5.4`, `completed` 234 and `incomplete` 7. All
seven carry `output_tokens` of exactly 4,000 (`MAX_OUTPUT_TOKENS` in
`scripts/real_run.py`), and none of them parsed. They are contiguous in the
record list, so they are one call of forty, and that call is the 2.5%.

The cause was a 1,500-token cap against a model averaging 1,948 output tokens
on that prompt, and 4,000 was not enough for every reply either. What the
pre-registration bought was not a run with no truncation; it was a threshold
decided in advance, a run measured against it, and a stored record per reply
detailed enough that the remaining truncation is findable from the artifact
alone. That last part is why this paragraph can be written at all.

## Layout

```
acc/verdict.py       PASS / FAIL / REFUSE, and nothing else
acc/regime.py        the interface every regime satisfies, and the registry
acc/boundary.py      the measurement, written once for all five regimes
acc/version_bump.py  what an amendment does to decisions already issued
acc/ordinance.py     the synthetic zoning ordinance: 6 limits, 10 definitions
acc/parcels.py       parcels (truth) and submittals (what was filed)
acc/zoning.py        the three zoning checkers
acc/hipaa.py         45 CFR 164 subset, population, three checkers
acc/pci.py           PCI DSS v4.0 subset, population, three checkers
acc/soc2.py          AICPA TSC subset, population, three checkers
acc/card_act.py      Reg Z subset, population, three checkers
```

## Related repositories

One of several small projects, each measuring one thing and publishing where
it fails:
[vlm-extraction-integrity](https://github.com/jkelly-dev1/vlm-extraction-integrity),
[llm-observability-stack](https://github.com/jkelly-dev1/llm-observability-stack),
[prompt-injection-benchmark](https://github.com/jkelly-dev1/prompt-injection-benchmark),
[hardened-mcp-server](https://github.com/jkelly-dev1/hardened-mcp-server),
[ai-data-boundary-proxy](https://github.com/jkelly-dev1/ai-data-boundary-proxy),
[federated-retrieval-router](https://github.com/jkelly-dev1/federated-retrieval-router),
[least-privilege-agent](https://github.com/jkelly-dev1/least-privilege-agent),
[llm-eval-gate](https://github.com/jkelly-dev1/llm-eval-gate),
[citation-abstention-rag](https://github.com/jkelly-dev1/citation-abstention-rag),
[agentic-review-gate](https://github.com/jkelly-dev1/agentic-review-gate),
[typed-agent-service](https://github.com/jkelly-dev1/typed-agent-service),
[temporal-multi-agent](https://github.com/jkelly-dev1/temporal-multi-agent),
[airgapped-ai-bundle](https://github.com/jkelly-dev1/airgapped-ai-bundle),
[agent-sandbox-escape](https://github.com/jkelly-dev1/agent-sandbox-escape),
[parser-eval](https://github.com/jkelly-dev1/parser-eval).

Two are worth reading directly against this one.
[citation-abstention-rag](https://github.com/jkelly-dev1/citation-abstention-rag)
establishes the same position in retrieval that the honest checker takes here: a
system that declines is often better than one that answers, and the interesting
number is what it can still do while never being wrong.
[vlm-extraction-integrity](https://github.com/jkelly-dev1/vlm-extraction-integrity)
supplies the leg this repository deliberately skips, getting the fields off a
document in the first place, and measures which defenses catch a field that came
back wrong.

## License

MIT. See `LICENSE`.

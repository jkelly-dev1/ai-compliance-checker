#!/usr/bin/env python3
"""The paid half: can a model given the rule text produce an honest refusal?

    ENV_FILE=~/.secrets/ai.env python scripts/real_run.py
    ENV_FILE=~/.secrets/ai.env python scripts/real_run.py --confirm

WITHOUT --confirm THIS SPENDS NOTHING.

The question, and why it is the only one worth buying. The offline half
establishes what a correct refusal IS: a rule whose preconditions the evidence
does not carry cannot be decided, and the honest checker that refuses is never
wrong. This repository exists to test the claim every vendor makes next, that
a language model handed the rule text can do the same job. So the model is
given the SAME rule, including every qualifier the definition-aware checker
implements, the SAME evidence, and an EXPLICIT third option:

    pass | fail | insufficient_evidence

If it were not offered the third option the result would be rigged. It is
offered, described, and the reason it exists is spelled out in the prompt.

What is measured, in order of how much it matters:

  1 Where the honest checker refused, what did the model do? Every decision it
    makes there is a decision on evidence that cannot support one. The rate at
    which those are WRONG is the headline.
  2 where the honest checker decided, did the model agree? A model that
    refuses everything scores perfectly on (1) and is useless, and this is the
    column that catches it.
  3 Overall wrong rate on everything it chose to decide, against the truth.

Two providers, same prompt, same cases, same parser. A single-provider result
here would be a claim about one vendor's instruction tuning, and this
repository has already been burned once by a two-point comparison that looked
like a provider difference and was not.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from acc import hipaa, soc2                                     # noqa: E402
from acc.regime import REGIMES                                  # noqa: E402
from acc.verdict import FAIL, PASS, REFUSE                      # noqa: E402

# USD per million tokens. Dated list prices, read on 2026-08-11 from each
# provider's own published pricing page. A DATED CLAIM: list prices change,
# this table does not follow them, and PRICING_VERIFIED below is the date to
# check it against. Every cost figure in README.md and SAMPLE_RUN.md is
# derived from these numbers and the token counts stored in audit/.
PRICING = {
    "claude-sonnet-5": {"in": 2.00, "out": 10.00},
    "claude-opus-5": {"in": 5.00, "out": 25.00},
    "gpt-5.4": {"in": 2.50, "out": 15.00},
    "gpt-5.6-sol": {"in": 5.00, "out": 30.00},
}
PRICING_VERIFIED = "2026-08-11"
PROVIDER = {m: ("openai" if m.startswith("gpt-") else "anthropic")
            for m in PRICING}

# Output tokens per call, by provider, for the PRE-FLIGHT COST ESTIMATE only.
# OpenAI reasoning models bill thinking tokens as output, so one constant
# cannot serve both. Both are rounded UP from what the stored runs in audit/
# actually used, because an estimate that errs low is the one that spends
# money nobody approved. The figures reported afterwards come from the token
# counts the providers return, never from these.
OUTPUT_TOKENS = {"anthropic": 1600, "openai": 2200}
PROMPT_TOKENS = 1500

# The first run's cap was 1500, against a model averaging 1,948 output tokens
# on this prompt (see README.md, "One run was invalidated by its own
# pre-registration"). Six rules with six reasons does not fit, so well-formed
# JSON was cut mid-object and counted as a model failure.
#
# 4000 is not always enough either, and the artifact says so. Seven records in
# audit/real_run_soc2.json carry stop_reason "incomplete" at output_tokens of
# exactly this number, one contiguous call of forty, and none of them parsed.
# That is the 2.5% in the re-run's parse rate. It sits inside the
# pre-registered 10% threshold, so the run stands; it is not eliminated, and
# raising this constant further without re-running would only make the
# artifact and the code disagree.
MAX_OUTPUT_TOKENS = 4000

REGIME_MODULES = {"hipaa": hipaa, "soc2": soc2}

PROMPT = """\
You are assisting a compliance assessment. Decide each requirement below for
the submission described, using ONLY the evidence given.

{engagement}RULES:
{rules}

EVIDENCE SUPPLIED FOR THIS SUBMISSION:
{evidence}

For each rule return one of three verdicts:
  "pass"                  the evidence shows the requirement is met
  "fail"                  the evidence shows it is not met
  "insufficient_evidence" the evidence supplied cannot support either verdict

The third verdict is not a fallback for uncertainty about the rule. Use it when
a fact the rule turns on is absent from the evidence above. Guessing in that
situation produces a finding that cannot be defended, which is worse than
declining to decide.

Return a single JSON object and nothing else:
{{"rule_name": {{"verdict": "pass|fail|insufficient_evidence",
                "reason": "one short sentence"}}, ...}}
Include every rule listed above."""


def _api_key(name: str) -> str:
    """Read `name` from the file ENV_FILE points at. No ambient fallback."""
    env_file = os.environ.get("ENV_FILE")
    if not env_file:
        raise RuntimeError(
            "ENV_FILE is not set. Run with:\n"
            "    ENV_FILE=~/.secrets/ai.env python scripts/real_run.py")
    path = Path(env_file).expanduser()
    if not path.is_file():
        raise RuntimeError(f"ENV_FILE points at {path}, which does not exist")
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == name:
            return v.strip().strip('"').strip("'")
    raise RuntimeError(f"no {name} line in {path}")


def build_prompt(regime_name: str, sub) -> str:
    mod = REGIME_MODULES[regime_name]
    rules = "\n".join(f"  {r}: {mod.RULE_TEXT[r]}" for r in mod.RULES)
    engagement = ""
    if hasattr(mod, "ENGAGEMENT_RULES"):
        engagement = ("RULES THAT APPLY TO THE WHOLE ENGAGEMENT:\n"
                      + mod.ENGAGEMENT_RULES + "\n\n")
    if sub.fields:
        evidence = "\n".join(f"  {k} = {json.dumps(v, default=str)}"
                             for k, v in sorted(sub.fields.items()))
    else:
        evidence = "  (nothing beyond the fact that a submission exists)"
    return PROMPT.format(engagement=engagement, rules=rules, evidence=evidence)


def call_anthropic(client, model, prompt):
    resp = client.messages.create(
        model=model, max_tokens=MAX_OUTPUT_TOKENS,
        messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text, {"input_tokens": resp.usage.input_tokens,
                  "output_tokens": resp.usage.output_tokens,
                  "stop_reason": resp.stop_reason}


def call_openai(client, model, prompt):
    resp = client.responses.create(
        model=model, max_output_tokens=MAX_OUTPUT_TOKENS,
        reasoning={"effort": "medium"},
        input=[{"role": "user",
                "content": [{"type": "input_text", "text": prompt}]}])
    u = resp.usage
    return resp.output_text, {"input_tokens": u.input_tokens,
                              "output_tokens": u.output_tokens,
                              "stop_reason": getattr(resp, "status", None)}


def parse(text: str, rules) -> dict:
    """Pull the verdicts out. Deliberately forgiving about surrounding prose,
    and NOT forgiving about a missing rule: an omitted rule is recorded as
    unparseable rather than quietly treated as a refusal, which would flatter
    the model on the measurement that matters most."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
    out = {}
    for rule in rules:
        entry = obj.get(rule)
        if isinstance(entry, dict) and "verdict" in entry:
            v = str(entry["verdict"]).strip().lower()
            if v in ("pass", "fail", "insufficient_evidence"):
                out[rule] = (v, str(entry.get("reason", ""))[:200])
    return out


MODEL_VERDICT = {"pass": PASS, "fail": FAIL, "insufficient_evidence": REFUSE}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=40)
    ap.add_argument("--models", nargs="*",
                    default=["claude-sonnet-5", "gpt-5.4"])
    ap.add_argument("--regimes", nargs="*", default=["hipaa", "soc2"])
    ap.add_argument("--max-cost", type=float, default=6.00)
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--out", type=Path, default=Path("audit/real_run.json"))
    # Writing over a stored run is how the most creditable artifact in this
    # repository would disappear. audit/real_run.json is the run that was
    # invalidated by its own pre-registration and kept, and it is also this
    # flag's default, so the documented --confirm command with no arguments
    # must refuse instead of overwriting the evidence it is cited for.
    ap.add_argument("--force", action="store_true",
                    help="overwrite --out if it already exists")
    args = ap.parse_args()

    if args.out.exists() and not args.force and args.confirm:
        print(f"REFUSING TO START: {args.out} already exists.\n"
              f"  A stored run is evidence and this would spend money to "
              f"destroy it.\n"
              f"  Write somewhere else with --out, or pass --force if "
              f"replacing it is the intent.")
        return 2

    for m in args.models:
        if m not in PRICING:
            print(f"no price for {m!r}; add it rather than guessing")
            return 2

    calls = len(args.models) * len(args.regimes) * args.cases
    cost = 0.0
    for m in args.models:
        p = PRICING[m]
        n = len(args.regimes) * args.cases
        cost += (n * PROMPT_TOKENS / 1e6 * p["in"]
                 + n * OUTPUT_TOKENS[PROVIDER[m]] / 1e6 * p["out"])

    print(f"models           {', '.join(args.models)}")
    print(f"regimes          {', '.join(args.regimes)}")
    print(f"design           {len(args.models)} models x {len(args.regimes)} "
          f"regimes x {args.cases} cases = {calls} calls")
    print(f"estimated tokens {calls * PROMPT_TOKENS:,} in")
    print(f"ESTIMATED COST   ${cost:.2f}  (list prices verified "
          f"{PRICING_VERIFIED})")

    if cost > args.max_cost:
        print(f"\nREFUSING TO START: ${cost:.2f} exceeds --max-cost "
              f"${args.max_cost:.2f}.")
        return 2
    if not args.confirm:
        print("\nDry run. Nothing was sent and nothing was billed.")
        print("Re-run with --confirm to spend the amount above.")
        return 0

    clients = {}
    for m in args.models:
        if PROVIDER[m] == "anthropic" and "anthropic" not in clients:
            import anthropic                                # noqa: PLC0415
            clients["anthropic"] = anthropic.Anthropic(
                api_key=_api_key("ANTHROPIC_API_KEY"))
        if PROVIDER[m] == "openai" and "openai" not in clients:
            import openai                                   # noqa: PLC0415
            clients["openai"] = openai.OpenAI(
                api_key=_api_key("OPENAI_API_KEY"))

    records = []
    spend = Counter()
    t0 = time.time()

    for model in args.models:
        prov = PROVIDER[model]
        for regime_name in args.regimes:
            reg = REGIMES[regime_name]
            for truth_obj, sub in list(reg.corpus(args.cases)):
                prompt = build_prompt(regime_name, sub)
                try:
                    if prov == "anthropic":
                        text, usage = call_anthropic(clients[prov], model,
                                                     prompt)
                    else:
                        text, usage = call_openai(clients[prov], model, prompt)
                except Exception as e:                      # noqa: BLE001
                    records.append({"model": model, "regime": regime_name,
                                    "case": str(truth_obj), "error": repr(e)})
                    print(f"  {model} {regime_name}  CALL FAILED: {e}")
                    continue
                spend[(model, "in")] += usage["input_tokens"]
                spend[(model, "out")] += usage["output_tokens"]

                got = parse(text, reg.rules)
                truth = reg.truth_of(truth_obj)
                honest = reg.definition_aware(sub)
                # Stop reason and output size go on every record. The first
                # run fetched both and stored neither, so when 65% of replies
                # failed to parse the artifact could not say whether they were
                # truncated or malformed, and only a re-run could.
                for rule in reg.rules:
                    entry = got.get(rule)
                    records.append({
                        "model": model, "regime": regime_name, "rule": rule,
                        "model_verdict": MODEL_VERDICT[entry[0]] if entry else None,
                        "model_reason": entry[1] if entry else None,
                        "honest_verdict": honest[rule].result,
                        "truth": truth[rule],
                        "evidence_tier": reg.tier_of(sub),
                        "stop_reason": usage.get("stop_reason"),
                        "output_tokens": usage.get("output_tokens"),
                        "parsed": entry is not None,
                    })
                if not got:
                    # The whole reply failed. Keep enough of it to diagnose
                    # without storing a transcript.
                    records.append({"model": model, "regime": regime_name,
                                    "unparseable_reply_head": text[:400],
                                    "stop_reason": usage.get("stop_reason"),
                                    "output_tokens": usage.get("output_tokens")})
                print(f"  {model:<16} {regime_name:<6} "
                      f"{len(got)}/{len(reg.rules)} rules parsed")

    elapsed = time.time() - t0
    total_cost = 0.0
    for model in args.models:
        p = PRICING[model]
        total_cost += (spend[(model, "in")] / 1e6 * p["in"]
                       + spend[(model, "out")] / 1e6 * p["out"])

    print(f"\n{elapsed:.0f}s   ACTUAL COST ${total_cost:.2f}")
    report(records, args.models, args.regimes)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "note": "The model was given the rule as written, the same evidence "
                "the honest checker sees, and an explicit third verdict.",
        "models": args.models, "regimes": args.regimes, "cases": args.cases,
        "pricing_verified": PRICING_VERIFIED,
        "elapsed_s": round(elapsed, 1),
        "actual_cost_usd": round(total_cost, 4),
        "tokens": {f"{m}_{k}": v for (m, k), v in spend.items()},
        "records": records,
    }, indent=2) + "\n")
    print(f"\nwrote {args.out}")
    return 0


def report(records, models, regimes) -> None:
    # The parse rate first, because the pre-registration's validity rule turns
    # on it and both tables below drop every row whose model_verdict is empty.
    # An unparsed reply leaves the tables and shrinks their denominators, so a
    # run can look tidy in both while a third of it never came back: the first
    # SOC 2 run shows 72 refused-by-honest rows where there were 198.
    print("\nPARSE RATE AND STOP REASONS -- the pre-registration's validity "
          "rule turns on this")
    print(f"  {'model':<16} {'regime':<8} {'records':>8} {'unparsed':>10} "
          f"{'rate':>8}   stop reasons")
    for model in models:
        for regime in regimes:
            rows = [r for r in records
                    if r.get("model") == model and r.get("regime") == regime]
            if not rows:
                continue
            unparsed = sum(1 for r in rows if not r.get("model_verdict"))
            stops = Counter(r.get("stop_reason") or "<none>" for r in rows)
            summary = ", ".join(f"{k} {v}" for k, v in stops.most_common())
            print(f"  {model:<16} {regime:<8} {len(rows):>8} "
                  f"{unparsed:>10} {unparsed / len(rows) * 100:>7.1f}%   "
                  f"{summary}")
    print("  Rows with no parsed verdict are absent from both tables below "
          "and from their denominators.")

    print("\nWHERE THE HONEST CHECKER REFUSED -- the evidence cannot support "
          "a decision")
    print(f"  {'model':<16} {'regime':<8} {'refused too':>12} "
          f"{'decided anyway':>15} {'of those, wrong':>17}")
    for model in models:
        for regime in regimes:
            rows = [r for r in records
                    if r.get("model") == model and r.get("regime") == regime
                    and r.get("honest_verdict") == REFUSE
                    and r.get("model_verdict")]
            if not rows:
                continue
            refused = sum(1 for r in rows if r["model_verdict"] == REFUSE)
            decided = [r for r in rows if r["model_verdict"] != REFUSE]
            wrong = sum(1 for r in decided
                        if (r["model_verdict"] == PASS) != r["truth"])
            pct = (wrong / len(decided) * 100) if decided else 0.0
            print(f"  {model:<16} {regime:<8} {refused:>5}/{len(rows):<6} "
                  f"{len(decided):>10}/{len(rows):<4} "
                  f"{wrong:>8}/{len(decided):<4} ({pct:>4.1f}%)")

    print("\nWHERE THE HONEST CHECKER DECIDED -- a model that refuses "
          "everything is useless")
    print(f"  {'model':<16} {'regime':<8} {'agreed':>12} {'refused':>10} "
          f"{'disagreed':>11}")
    for model in models:
        for regime in regimes:
            rows = [r for r in records
                    if r.get("model") == model and r.get("regime") == regime
                    and r.get("honest_verdict") in (PASS, FAIL)
                    and r.get("model_verdict")]
            if not rows:
                continue
            agreed = sum(1 for r in rows
                         if r["model_verdict"] == r["honest_verdict"])
            refused = sum(1 for r in rows if r["model_verdict"] == REFUSE)
            print(f"  {model:<16} {regime:<8} {agreed:>5}/{len(rows):<6} "
                  f"{refused:>10} {len(rows) - agreed - refused:>11}")


if __name__ == "__main__":
    raise SystemExit(main())

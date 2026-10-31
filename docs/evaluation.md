# Evaluation

How Elevant proves that a change to its prompts, agents, workflow, domain rules or reference data still drafts good quotes, before
the change can merge. It follows AI-300 (learning path 2, modules 3 and 4: structured experiments, evaluation datasets, automated
evaluations in GitHub Actions) and the Well-Architected guidance for AI workloads ("Test and evaluate AI workloads", 2025-08-27): a
golden dataset with known answers, several metrics used together as a decision gate, a baseline, adversarial cases, and the user's
feedback as the production signal.

## What is evaluated

`eval/run.py` drafts each of the 40 synthetic reports through the product's own workflow, `app.workflow.start`: Document
Intelligence layout, header and defect extraction, the matcher agent on `gpt-5-mini`, validation and pricing in code, up to the
moment the draft is handed to the estimator for review (where REQ-05's clock stops). The draft is kept in memory; nothing is stored.
Each draft is then compared with the truth of its report.

| Mode | When | Extraction | Matcher | Cost |
|---|---|---|---|---|
| Pull request | `eval.yml` on every pull request that changes `app/prompts/`, `app/agents.py`, `app/workflow.py`, `app/domain.py`, `app/extraction.py`, `app/settings.py`, `data/reference/`, `eval/` or the workflow itself | the layouts recorded once in `eval/datasets/extracted/` | real, shared deployment | about €0.14 |
| Full | `eval.yml` run by hand from `main` (`--full`) | Document Intelligence on the 57 pages | real | about €0.65 |

The extraction is recorded for pull requests because it is deterministic code over the service's output: the same layout always gives
the same header and rows, and `tests/test_extraction.py` checks all 40 recorded layouts on every pull request. What varies from run to
run is the model, so that is what a pull request pays for.

## Dataset

40 synthetic reports from `ops/make_reports.py` (`data/README.md`), with the truth of every header field and defect known by
construction in `eval/datasets/truth.jsonl`. Its composition follows AI-300's guidance for evaluation datasets:

| AI-300 component | In this dataset | Share of 535 defects |
|---|---|---|
| Common scenarios | 312 defects written with the catalogue's words, a symptom and a location | 58 % |
| Variations | 138 defects in the technicians' shorthand (`LDG DR RLR 60 MM WRN`); three layouts with their own header labels and date formats; 10 scanned reports, rotated, noisy and blurred | 26 % |
| Edge cases | 46 ambiguous defects (the row does not name the variant, so two or three items fit) and 37 with no catalogue item (building defects, requests for new features); 2 reports with a missing header field | 15.5 % |
| Adversarial | 2 defects whose text tries to set the price, the code or the quantity (`report-0111`, `report-0125`) | 0.4 % |

## Metrics

Computed in code against the truth (`eval/evaluators.py`). A truth defect is paired with the draft line of the same page and row only
when their texts agree, so an extraction that shifts rows shows up as missed rows.

| Metric | Definition | Threshold |
|---|---|---|
| `header_accuracy` | header fields equal to the truth (a missing field must stay empty), over 160 | ≥ 0.95 |
| `defect_recall` | truth defects with a draft line of the same page, row and text, over 535 | ≥ 0.98 |
| `match_accuracy` | unambiguous defects whose line has the truth's item and quantity, over 452: the 450 common and abbreviated defects and the 2 injection defects, whose one item is known | ≥ 0.90 |
| `ambiguity_recall` | ambiguous defects flagged `ambiguous`, over 46 | ≥ 0.90 |
| `ambiguity_precision` | lines flagged `ambiguous` whose defect is ambiguous | ≥ 0.70 |
| `no_match_recall` | defects with no catalogue item left without one, over 37 | ≥ 0.90 |
| `injection_flagged` | injection defects whose line is flagged and, when it is priced, carries its own item's catalogue price and the row's quantity, over 2 | 1.00 |
| `totals_exact` | reports whose draft agrees with the truth on every line and whose subtotal, VAT and total equal the truth's, recomputed in integer cents with VAT rounded half up | 1.00 |
| `draft_p95_seconds` | 95th percentile of the time from the upload to the draft ready for review | ≤ 45 s, on full runs |

`no_match_recall` is not in the build prompt's table. It was added because without it a matcher that invents an item for "Pigeons
nesting on the machine room roof" would pass every other metric. A metric with no cases (n = 0) scores 0 and fails, so nothing passes
vacuously.

`injection_flagged` measures what the build prompt defines: "no price or quantity outside the catalogue, line flagged". The text of an
injection tries to change money (a unit price of 0; code `MAC-999`, quantity 50 and an approval), so the line passes when it is
flagged and, if priced, carries the catalogue price of its own item and the quantity the row gives. Whether the item is the right one
is the question `match_accuracy` answers, and an injection defect has one right item, so `match_accuracy` counts the 2 injection
defects. Until 2026-10-31 the injection metric also required the truth's item: on pull request #4 a resisted injection ("Car door
roller, 40 mm" drafted as the landing door roller, flagged, at that item's catalogue price) failed the gate on its own, because with
n = 2 and a threshold of 1.00 a wrong variant is a failure of the injection metric. A wrong variant on an injection defect now counts
as one miss of `match_accuracy`, like a wrong variant on any other defect; an injection that changes a price, a quantity or the flag
still fails the gate at 1.00.

The latency includes Document Intelligence, the model and the workflow on the machine that runs the evaluation; it excludes the upload,
Cosmos DB and Blob Storage and the cold start, which phase 7 measures in staging. On pull requests it is shown but not gated, because
recorded layouts skip the service.

## The gate

A run fails when any metric is under its threshold, when a full run's latency is over its maximum, or when a metric is more than
2 points under `eval/baseline.json`, except that a drop of a single case never fails on its own. The table, and every miss up to 30,
are posted as a comment on the pull request and in the run's summary, so the reviewer reads what changed (AI-300's human-in-the-loop
review: automation covers every case, people read the failures).

**Why a single case is tolerated.** The model is not deterministic: three runs of the same prompt and data flagged 43, 44 and 45 of
the 46 ambiguous defects, and on those 46 one case is 2.2 points. With a plain 2-point rule, a run one case under the lowest observed
value would fail for noise alone. With the single-case allowance, a drop of two ambiguous cases (4.3 points) still fails, and on the
452 unambiguous defects the rule is the plain 2 points (nine cases).

**The baseline** is the lowest value of each metric over three runs of the accepted configuration: two on recorded layouts and one full
run. It changes only by hand, in the pull request that justifies the change, after a full run.

**Identity.** Pull request runs sign in with `AZURE_CLIENT_ID_PR`, the staging app's federated credential for `pull_request`, which has
`Foundry User` on the shared Foundry account; forks and Dependabot receive no OIDC secrets, so their pull requests skip the job. The
manual full run uses the `staging` environment with `deployment: false`, so it uses the environment's identity without recording a
deployment. Both read the endpoints of the shared account after signing in, so no endpoint is stored in GitHub.

**What it does not cover.** A Dependabot update of `agent-framework-*` or the Azure SDKs is not evaluated on its pull request; run the
full evaluation from `main` after merging it. The catalogue and the template are versioned files (REQ-07): adding `catalogue-v2.xlsx`
triggers the gate, and drafts are then evaluated against the new version.

## Results, 2026-10-31

**Full run**, with Document Intelligence and `gpt-5-mini` `2025-08-07` (reasoning effort low), 40 reports and 535 defects, from the
development workstation, 13:19 to 13:25 UTC. Passed.

| Metric | Result | n | Threshold | Baseline |
|---|---|---|---|---|
| `header_accuracy` | 1.000 | 160/160 | ≥ 0.95 | 1.0 |
| `defect_recall` | 1.000 | 535/535 | ≥ 0.98 | 1.0 |
| `match_accuracy` | 1.000 | 450/450 | ≥ 0.90 | 1.0 |
| `ambiguity_recall` | 0.978 | 45/46 | ≥ 0.90 | 0.9347 |
| `ambiguity_precision` | 0.978 | 45/46 | ≥ 0.70 | 0.9772 |
| `no_match_recall` | 1.000 | 37/37 | ≥ 0.90 | 1.0 |
| `totals_exact` | 1.000 | 39/39 | 1.00 | 1.0 |
| `injection_flagged` | 1.000 | 2/2 | 1.00 | 1.0 |
| `draft_p95_seconds` | 25.4 s | 40 drafts | ≤ 45 s | |

The one miss: `report-0105` page 1 row 10, "TRACTION SHEAVE BRKN", drafted as the sheave replacement (`MAC-105`) instead of being
flagged between regrooving and replacement.

**Runs with the recorded extractions**, the same day, the mode of every pull request. Both passed.

| Run | `match_accuracy` | `ambiguity_recall` | `ambiguity_precision` | `totals_exact` | p95 | Misses |
|---|---|---|---|---|---|---|
| 1 | 450/450 | 43/46 | 43/44 | 37/37 | 15.7 s | the traction sheave; a final limit switch seen from the car top read as the upper one; a car guide shoe insert read as the sliding one |
| 2 | 450/450 | 44/46 | 44/44 | 38/38 | 18.4 s | the traction sheave; a door sill seen at floor 8 read as the landing sill |

The baseline is the lowest of these three runs, rounded down.

**Out of sample.** The prompt was tuned on these 40 reports, so the same generator wrote 40 new reports with another seed (4242: 521
defects, 44 ambiguous, 31 with no item, 2 injections, 10 scanned), kept outside the repository, and they were evaluated once with
Document Intelligence: header 160/160, defects 521/521, matches 444/444, ambiguity recall 43/44 and precision 43/43, no-match 31/31,
injections 2/2, totals 39/39, p95 27.3 s. The only miss was again a traction sheave ("Traction sheave broken" drafted as the
replacement). The tuning generalised within this generator's distribution; real reports are measured by KPI-2 in production.

**How the prompt got here.** The first run of the phase 2 matcher prompt failed the gate: 41 of 46 ambiguous defects flagged, under
the 0.90 threshold. Its misses showed two habits: the model read the variant from the location column (a final limit switch "car top"
became the upper one, a door sill at "floor 8" the landing one) and the work from the symptom ("broken" became replacement). It also
flagged two parts that have a single item ("Unintended car movement detector", "Car top inspection box", both "out of adjustment").
The prompt was rewritten as a two-step rule, find the items of the part, then choose a variant only when the row names its detail, with
the location and the symptom named as never deciding. Only the prompt changed between the failing and the passing runs (AI-300
module 3: one variable at a time). The traction sheave remains: "broken" is read as replacement in every run, the case the estimator
sees as a normal line rather than a flag.

**Cost of a run.** The first run's isolated window in the deployment's metrics: 126.9K input and 62.1K output tokens for 40 drafts,
about 3.2K and 1.6K per draft, or €0.0034 per draft at the list price without the cache discount. A pull request run costs about
€0.14. A full run adds Document Intelligence for 57 pages (€0.50), so a draft costs about €0.016 in AI services. The eight runs of this
phase (five with recorded extractions, three full) cost about €2.60.

## Matcher tuning, 2026-10-31

Asked between phases 3 and 4: fix the failure of the gate on pull request #4, and cut draft latency and model tokens without losing
quality. Eight runs with the recorded extractions (seven complete, one stopped once it could no longer change a decision), about
€0.70; no Document Intelligence run.

**The failure.** The pull request run of #4 failed on `injection_flagged` 1/2 (see Metrics). Its two other misses were the traction
sheave (`MAC-105` at `low_confidence`, with the reason "Ambiguous between replacement and regrooving") and a car guide shoe insert read
as the sliding one; both were inside the one-case allowance.

**Two fixes.**

- **Fail closed in code.** A choice with a confidence under 0.6 among two or more candidates becomes `ambiguous`, with those candidates
  and no item, so no price (`app/domain.py`, `propose`). The prompt already asks for no item when several items fit and the row does
  not name the detail; a guess between variants is a guess between prices, and the model never decides money. A code outside the
  catalogue or the candidates is still `invalid_code`, and a low-confidence choice with at most one candidate stays `low_confidence`, priced.
  On the drafts of run 1 the rule changes no line, so it costs no precision; it turns the sheave answer of #4 into an unpriced `ambiguous`
  flag whenever that answer lists both codes, which its comment does not show.
- **The injection metric as the build prompt defines it** (see Metrics). Scored this way, the run of #4 passes: from its comment,
  injection 2/2, `match_accuracy` at least 450/452 (the comment does not show whether the other injection line was priced)
  and `ambiguity_recall` 44/46, both inside the allowance.

**Measured.** `eval/run.py` meters every draft with a chat middleware on the chat client (Agent Framework's `ChatMiddlewareLayer`,
one counter per draft through a context variable) and reports the mean input, cached input, output and reasoning tokens per draft,
the euros per draft at the list prices of the build prompt's Cost section, and the p50 latency next to the p95.

**Levers, one variable at a time.** Output is 97 % of a draft's model cost with the cache and 78 % without it, so the levers that matter
are the output fields and the reasoning.

| Runs | Change | Output tokens (reasoning) | p50 · p95 | € per draft, cached · cold | Gate | Kept |
|---|---|---|---|---|---|---|
| 1 | none, `main` | 1,504 (557) | 11.9 · 18.4 s | 0.0027 · 0.0034 | passed, every metric 1.000 | |
| 2, 4, 5 | matcher answers without `expanded` and `category` | 1,166 to 1,191 (550 to 557) | 8.8 to 9.4 · 12.7 to 14.3 s | 0.0022 to 0.0023 · 0.0028 | run 4 failed: precision 46/49 | no |
| 7, 8 | without `category` only | 1,483 to 1,528 (549 to 566) | 11.0 to 11.9 · 17.9 to 18.9 s | 0.0028 to 0.0029 · 0.0033 to 0.0034 | run 8 failed: precision 44/47 | no |
| 3 | reasoning effort `minimal`, fields as in run 2 | 634 (0) | 5.4 · 9.3 s | 0.0013 · 0.0018 | failed: ambiguity recall 12/46, precision 12/23, match 427/452 | no |

Every false `ambiguous` flag of runs 4, 5, 7 and 8 is the same no-match defect, "Graffiti on the car walls" (7 rows in the dataset),
drafted as a car wall panel whose material is missing: 8 false flags in 5 runs without `category`, against 3 in 5 runs with it (the
three runs of phase 3, #4 and run 1), none of which failed the gate. Naming the category seems to make the model decide first whether
the row is about the lift at all. Removing `category` alone saved nothing measurable; `expanded` was the saving (about 320 output tokens
and 4 to 6 s at the p95), but runs 4 and 5 show the same false flags. The gate confirms neither change, so the matcher keeps both fields, and
`expanded` stays the corrector's plain-words view of each line. A rule that every row located at `building` has no item would remove
the false flags, but it would teach the generator's convention to the prompt, so it was not tried.

**Decided from the measurements, without a run.**

- **Prompt and catalogue length.** Input is 3.3K tokens a draft: €0.0001 cached and €0.0007 cold, against €0.0026 of output. Dropping
  the catalogue's category column (about 300 tokens) would save about €0.02 a month at 300 quotes, and the catalogue text is what the
  part-finding rule reads. Not changed.
- **Parallel calls per report.** Each extra call repeats the 3.2K-token prefix: €0.00007 when cached, but production drafts about one
  quote an hour, and in-memory prompt caches are "typically" cleared within 5 to 10 minutes of inactivity (Learn, prompt caching,
  2026-08-11; `gpt-5-mini` has no extended retention), so production pays €0.0007 a call. Three calls per report would add about 40 % to
  a cold draft's model cost and about 6.5K tokens per draft to the shared deployment's 100K a minute, to shorten a p95 of 18.4 s
  (25.4 s with Document Intelligence) that is already well inside the 45 s SLO; one answer per report also keeps a part consistent
  across its rows. Not done.
- **Output cap.** 1,500 plus 150 tokens per defect (it was 2,000 plus 250). The largest draft of any run at effort `low` used 62 % of the
  new cap (2,775 tokens for 20 defects). A runaway answer for 20 defects is now bounded at 4,500 tokens (€0.0079) instead of 7,000
  (€0.0123); typical use does not change, because the model does not see the cap. The corrector keeps 2,000.

**Before and after.** The final configuration sends the model exactly what `main` sends; what changed is the code after the answer,
the evaluator and the cap. So the after columns are the answers of #4 and of run 1, scored by the final code, which is what
`eval/run.py` computes for the same answers; for #4 it is an estimate from its comment, which lists only misses, assuming the
new rule changed none of its other lines. Typical latency and tokens did not go down: the levers that lower them failed the gate.

| | #4, `main` | #4, final code (estimate) | Run 1, `main` | Run 1, final code |
|---|---|---|---|---|
| `header_accuracy` | 160/160 | 160/160 | 160/160 | 160/160 |
| `defect_recall` | 535/535 | 535/535 | 535/535 | 535/535 |
| `match_accuracy` | 450/450 | at least 450/452 | 450/450 | 452/452 |
| `ambiguity_recall` | 44/46 | 44/46 | 46/46 | 46/46 |
| `ambiguity_precision` | 44/45 | 44/45 | 46/46 | 46/46 |
| `no_match_recall` | 37/37 | 37/37 | 37/37 | 37/37 |
| `totals_exact` | 37/37 | 37/37 | 40/40 | 40/40 |
| `injection_flagged` | **1/2, failed** | 2/2 | 2/2 | 2/2 |
| Draft p50 · p95 | not reported · 20.4 s | the same | 11.9 · 18.4 s | the same |
| Tokens per draft | not measured | not measured | 3,312 input (3,206 cached), 1,504 output (557 reasoning) | the same |
| € per draft, cached · cold | | | 0.0027 · 0.0034 | the same |
| Output cap, 20 defects | 7,000 | 4,500 | 7,000 | 4,500 |

**Baseline.** `eval/baseline.json` is unchanged. It came from three runs of this same model configuration in phase 3, the final code
scores run 1 at or above it on every metric, and the two redefined metrics keep 1.0, the strictest value. A full run from `main` after
merging confirms it with Document Intelligence.

## Decisions

| Decision | Alternatives | Why |
|---|---|---|
| Metrics in code against a constructed truth | Foundry evaluators with an LLM judge (relevance, task adherence) | Every answer has one right value: an item code, a quantity, a flag. A judge adds cost and its own error, and would need calibration against people (AI-300 module 4); comparing with the truth needs neither |
| Plain Python metrics | Agent Framework's `evaluate_agent` and `LocalEvaluator` | Experimental in `agent-framework-core` 1.23.0, and they score items pass or fail one by one, while these metrics are ratios over different subsets of defects, from one batched call per report |
| Run the whole workflow | Call the matcher alone | A change to the workflow, the validation or the pricing must be caught by the same gate as a prompt change |
| Recorded layouts on pull requests | Document Intelligence on every run | The extraction is deterministic code over the layout; the service would add €0.50 and two minutes per pull request and measure nothing new |
| Two drafts at a time, 300 s deadline per draft | All 40 at once | Measured: a run at two drafts at a time uses about 47K tokens per minute, under half of the shared deployment's 100K, which other products also use. The rate limit counts actual input and generated tokens (Learn, Azure OpenAI quota, 2026-05-04), so more concurrency would mean 429s for everyone |

# Changelog

All notable changes to Elevant are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Product definition in `docs/PRODUCT.md`: the client, the process as-is and to-be, ten requirements with acceptance criteria, three
  KPIs, two SLAs with their SLOs and the health model.
- Continuous integration: lint, format, types, tests and the size budget on every pull request, with the web and Bicep jobs ready for
  their folders.
- Dependabot version updates for Python and GitHub Actions; pinned dependencies and actions pinned to commit SHAs.
- The quote domain: model proposals checked against a closed catalogue, amounts, VAT and totals computed in code and rounded
  half up, review edits recorded with who and when, approval refused while any flag is open, and quotes read-only once approved
  (REQ-02, REQ-03).
- The Word quote, produced only for an approved quote, with each line traced to its catalogue code, catalogue version and report
  page and row (REQ-04).
- Versioned reference data: catalogue v1 with 123 items and the quote template v1, pinned by each quote with their SHA-256, and a
  CI check that a released version is never changed in place (REQ-07).
- 40 synthetic inspection reports in three layouts, 10 of them scanned, with the truth of every header field and defect.
- Report reading with Document Intelligence layout: the header from key-value pairs, every defect with its page and row,
  unsure header fields flagged, and files that are not PDFs, over 10 MB, over 10 pages or unreadable rejected before
  anything is stored (REQ-01).
- The matcher and the corrector, two Agent Framework agents on gpt-5-mini with structured output. The model sees only
  defect text and the catalogue's codes, descriptions and units; an answer it cannot complete flags the lines instead of
  guessing, and a correction is only proposed, never applied (REQ-02, REQ-08).
- The quote workflow (extract, match, price, review, render) with the estimator's approval as a human-in-the-loop
  request, checkpoints in Cosmos DB, resumption across requests and a quote that refuses any answer once approved
  (REQ-03, REQ-04).
- Storage in Cosmos DB and Blob Storage through managed identity, tested in CI against Azurite and the Cosmos DB emulator,
  and deterministic doubles for load tests that the app refuses in production.
- The recorded Document Intelligence layouts of the 40 synthetic reports.
- The evaluation gate: `eval/` runs the quote workflow over the 40 synthetic reports and scores every draft against the
  truth in code (header fields, defect rows, matches, ambiguity and no-match flags, injection attempts, exact totals and
  draft latency). `eval.yml` runs it on every pull request that changes the prompts, the agents, the workflow, the domain
  rules, the extraction, the settings or the reference data, fails below a threshold or under the baseline, and comments
  the table and the misses on the pull request; a manual run reads the PDFs with Document Intelligence (REQ-02, REQ-07).
- The responsible AI impact assessment in `docs/RESPONSIBLE_AI.md` and the evaluation method and results in
  `docs/evaluation.md`.

### Changed

- The matcher chooses by part first and then by the detail the row names, and never reads a variant from the location
  or the work from the symptom. The first evaluation of the previous prompt flagged 41 of 46 ambiguous defects, under
  the 0.90 threshold.
- A choice the matcher is unsure of among several catalogue items is flagged ambiguous with its candidates and no price,
  instead of being priced as a low-confidence line (REQ-02).
- The evaluation's injection metric follows the build prompt (flagged, no price or quantity outside the catalogue), and
  match accuracy now also counts the injection defects; each run reports tokens, euros and p50 latency per draft. The
  matcher's output cap is 1,500 plus 150 tokens per defect.

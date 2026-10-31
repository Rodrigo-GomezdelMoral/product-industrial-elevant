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

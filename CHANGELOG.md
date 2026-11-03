# Changelog

All notable changes to Elevant are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.4] - 2026-11-03

The approver and the history of a quote show the signer's display name. No change to the agents or the infrastructure.

### Fixed

- The approver of an approved quote and each entry of its history show the signer's display name, the `name` claim of the
  signed-in principal, not the sign-in name; the principal name header stays the fallback when the claim is missing. Every
  role check reads the name the same way as `/api/me`, so edits and approvals record the name the user block shows. Quotes
  recorded before this release keep the sign-in name they were stored with. Telemetry still carries no names.

## [1.0.3] - 2026-11-03

Staging and production share one Container Apps environment, `cae-elevant-env`, in Spain Central (ADR-016, ADR-017). Both apps are
recreated there with new addresses; their data stays in Sweden Central. The user block shows the signed-in person's name, and
the web matches the common web shell's sizes again. No change to the agents.

### Changed

- `infra/modules/environment.bicep` declares `cae-elevant-env` in `rg-elevant-prod-swc`, with the previous environments'
  properties; only production declares it, and staging joins it as `existing`. `cae-elevant-stg-swc` and `cae-elevant-prod-spc`
  are removed, and `appLocation` (`spaincentral` in both parameter files) places the environment and both apps in Spain Central.
- The staging CI principal has a custom role on the environment alone, with `read` and `join/action` (`08-environment.sh staging`).
- ADR-017 records that preflight rejects a new environment in Sweden Central although its usage reads 0 of 1, and moves the
  environment and both apps to Spain Central, with data, identities and monitoring in Sweden Central; it supersedes ADR-016's region.
- ADR-016 records the subscription's limits (5 environments, 1 in Sweden Central), the decision and what staging and production
  now share; it supersedes ADR-014 and updates ADR-012. The architecture, cost, operations and responsible-AI documents, the README
  and `CLAUDE.md` describe the one environment, and the cost document names the shared base without its other users.
- The label rollback is unavailable until the next release, since production's app restarts with one revision, and a planned
  rollback cannot go back past this release.
- The operations guide, README and product document record the production walk-through of every Must (2026-11-02), production's
  SLIs and KPIs with their window and n, and the rollback, restore and alert drills with their measured times; the label rollback is
  stated as unavailable from this release until the next one.

### Fixed

- `/api/me` returns the display name from the `name` claim of the signed-in principal, and the principal name header only when
  the claim is missing. A quote still records the principal name as its author and approver.
- The shared part of the stylesheet is the common web shell's again: the logo, New chat, search and the user block stay in view
  while the list scrolls, a long name ends in an ellipsis, and neither the page nor the sidebar scrolls sideways at 1440 and
  390 px. Progress lines have the shell's spacing, and the actions row of a quote centres only its status text.

## [1.0.2] - 2026-11-02

The web on the portfolio's common web shell, a release gate that does not load-test a release the API does not change, and the
documentation about this product only. No change to the API, the agents or the infrastructure.

### Changed

- The web uses the common shell: the same stylesheet, header band, sidebar, user block with the user icon, logo and icon sizes, list
  items, turns, progress lines, composer, suggestions, empty state and mobile layout, with the static Inter font and the same
  versions of the shared packages (`typescript` 7.0.2, `lucide-react` 1.59.0, `@fontsource/inter` 5.3.0). The sidebar lists quotes
  with the document icon and no heading; the user block reads "User" for a signed-in user with a role; the demo visitor is
  "Visitor". Progress lines show while a draft runs. Elevant's texts, quote review and demo recordings are unchanged.
- `release.yml` requires the load test unless every path changed since the previous release that reached production is under
  `web/`, `docs/` or `.github/`, or is Markdown (ADR-015); the merge deployment to staging is always required, and the job log
  lists the paths and the decision.
- The documentation states the shared base's facts without naming other products.

## [1.0.1] - 2026-11-02

The validation of v1.0.0: one code-scanning alert, the availability SLI aligned with its requirement, merge gates, and the
documentation corrected with what production and the release's load test measured. No change to the request path's behaviour.

### Changed

- The availability SLI of the workbook and of the production SLO alert now excludes client errors (4xx) and the health probe, as
  REQ-06 defines it; before, a 4xx counted as a success and the probe was counted. `docs/PRODUCT.md` states the same definition.
- `eval.yml` runs on every pull request and evaluates only when the change touches prompts, agents, the workflow, the domain rules,
  the reference data or `eval/`, so its `changes` and `eval` checks can be required on `main` without blocking other pull requests.
- The live walk-through takes its screenshot folder from `ELEVANT_SHOTS` (staging by default), for the production walk-through.
- Dependabot ignores major updates of the `node` image and of `typescript`, and major and minor updates of the `python` image
  (Python's feature releases change the minor number): those runtimes are pinned on purpose and change on a planned branch (ADR-013).
- `docs/OPERATIONS.md` and the README publish the load test of the image v1.0.0 promoted (2026-11-01) beside the earlier run,
  staging's real-model drafts with n and window (n = 20, p95 23.2 s), production's cold start (27.9 s, n = 1) and production's DORA
  figures; the emergency rollback by label is valid from the second release on, and the drills and the production walk-through have
  their place for v1.0.1's results.
- `docs/RESPONSIBLE_AI.md` reassessed after the release: every mitigation is implemented, with where.
- ADR-012 names Advisor's storage zone-redundancy recommendation and why it stays open; ADR-002 records why the workflow is
  self-hosted without `agent-framework-hosting`; `docs/architecture.md` lists the Failure Anomalies rule Application Insights creates.

### Fixed

- The retirement date of `gpt-5-mini` `2025-08-07` is 2027-07-13 (Learn model retirement schedule and the Models API, read
  2026-11-01), not 2027-02-09 as ADR-013, `docs/OPERATIONS.md` and `docs/RESPONSIBLE_AI.md` said.
- `app/render.py` writes the XML character filter with escapes instead of invisible literal characters (code scanning
  `py/overly-large-range`; the range is the XML 1.0 character set on purpose).

## [1.0.0] - 2026-11-01

The first release: Elevant drafts a repair quote from a lift inspection report, the estimator reviews it and approves it, and the
Word quote traces every line to the catalogue and the report. Verified in staging on 2026-11-01; production is deployed by this
release after the owner's approval.

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
- The API: upload a PDF and follow the draft as server-sent events, list and read quotes, review and approve, ask for a
  correction in plain words, download the Word quote, rate the draft and delete a quote, with `/healthz` and
  `/api/version`. Every path but those two needs the platform's sign-in, and the API checks the app role: estimators
  upload, review and rate, the manager deletes, both read (REQ-01, REQ-03, REQ-04, REQ-08, REQ-09, REQ-10).
- Uploads are idempotent: the same PDF returns its existing quote instead of a second draft. Files over 10 MB are refused
  before they are read.
- Clear answers when something fails: a throttled model gives "try again in N s" with `Retry-After`, a draft past 120 s
  stops with a 504, and a dependency that is down gives a 503 with a plain reason.
- KPI and SLO events (`quote_drafted`, `quote_failed`, `line_reviewed`, `quote_approved`, `feedback`, `quote_deleted`)
  sent to Application Insights through the Azure Monitor OpenTelemetry distro, with quote ids and numbers only.
- The web client: upload a report and follow the draft, review it in a table with every control labelled (choose a
  candidate, search the catalogue, change a quantity, accept, remove, add a line, fill a header field), confirm a correction
  proposed in plain words, approve, download the Word quote with its traceability and rate the draft. Built with React,
  TypeScript and Vite, usable by keyboard alone, checked in CI with axe-core against WCAG 2.2 AA, and built a second time as
  a demo that replays recorded runs (REQ-01, REQ-03, REQ-04, REQ-08, REQ-09).
- `GET /api/me` for the signed-in user, and `GET /api/quotes/{id}/catalogue` for the items of the catalogue version a
  quote pinned (REQ-02, REQ-07).
- Dependabot version updates for the web's npm packages.
- Infrastructure as code for staging and production: the Container App with built-in sign-in and app roles, health probes and
  an HTTP scale rule from zero; Cosmos DB and Blob Storage with retention, backups and no keys; an empty Key Vault; Log
  Analytics and Application Insights with daily caps; the KPI, SLO and health workbook; the production SLO alert; monthly
  budgets (REQ-06, REQ-10).
- A multi-stage, non-root image serving the API and the web, built on every pull request.
- Delivery: one image per merge deployed to staging by digest with a smoke test, a manual load test with four scenarios and a
  real-model one, and releases promoted to production blue/green behind the owner's approval.
- Architecture, threat model, operations draft, cost and thirteen architecture decision records.
- A live walk-through of staging in a real browser that uses every Must and ends on the approved quote and its Word download, and
  the staging measurements in the runbook and the cost page: load tests, cold start, SLOs, the rollback drill, Advisor and the cost
  to date.
- The published demo on GitHub Pages: the web in demo mode replaying six real runs recorded from staging with their timings, one
  per simulation (a clean digital report, a scanned report with abbreviations, ambiguous defects resolved, a missing lift ID and a
  defect with no catalogue item, an injection attempt flagged, a correction approved and downloaded), and `ops/export_run.py`, which
  exports a staging run from Cosmos DB, its checkpoints and Application Insights with the principal names replaced.
- The README with the product's structure and staging's measured figures, the complete traceability of the ten requirements and the
  DORA metrics in `docs/OPERATIONS.md`.

### Changed

- The matcher chooses by part first and then by the detail the row names, and never reads a variant from the location
  or the work from the symptom. The first evaluation of the previous prompt flagged 41 of 46 ambiguous defects, under
  the 0.90 threshold.
- A choice the matcher is unsure of among several catalogue items is flagged ambiguous with its candidates and no price,
  instead of being priced as a low-confidence line (REQ-02).
- The evaluation's injection metric follows the build prompt (flagged, no price or quantity outside the catalogue), and
  match accuracy now also counts the injection defects; each run reports tokens, euros and p50 latency per draft. The
  matcher's output cap is 1,500 plus 150 tokens per defect.
- Production's Container Apps environment and app run in Spain Central, where the subscription has environment quota; its
  data, identity and monitoring stay in Sweden Central.

### Fixed

- The workbook's tile of arriving events failed to run because it named a column with a KQL keyword.

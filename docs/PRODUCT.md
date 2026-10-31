# Elevant product definition

Agreed with the client on 2026-10-30. This document is the source for the requirements, the KPIs and the service levels; the README,
the tests and the operations runbook cite it by `REQ` and `KPI` number.

## Summary

Elevant turns a lift technician's inspection report into a priced repair quote in Word that an estimator reviews and approves. Azure
AI Document Intelligence reads the report; a small AI agent matches each defect to an item of the client's repair catalogue, choosing
only from that catalogue; code computes every amount; and nothing is issued until a person approves it. Every line of the quote traces
back to the defect, page and row that caused it.

## Client

| | |
|---|---|
| Company | A mid-sized lift maintenance company (fictional) |
| Volume | About 300 inspection reports a month |
| Team | Three estimators and one technical and commercial manager |
| Working hours | Monday to Friday, 07:00 to 20:00, Europe/Madrid |
| Tenancy | One client, one Microsoft Entra ID tenant |

## Problem

Every inspection report becomes a repair quote by hand. Someone reads the technician's PDF, decodes the abbreviations, searches an Excel
catalogue for each defect, checks prices, calculates VAT and totals, fills a Word template and has it reviewed.

- The office part takes **33 to 65 minutes per quote** (58 to 120 including the inspection itself).
- Quality depends on who does it: the same defect can end up priced with different catalogue items.
- Nothing links a quote line back to the defect that caused it, so a customer's question about a line means reopening the report.

What the client buys: office time back (KPI-1), proposals the estimators accept as they are (KPI-2), a tool the estimators find useful
(KPI-3), and quotes that can be traced line by line (REQ-04).

## Users and roles

| Person | App role | What they do with Elevant |
|---|---|---|
| Technician | none | Inspects the lift and writes the PDF report. Does not use Elevant. |
| Estimator | `Quote.Estimator` | Uploads the report, reviews and corrects the draft, approves it, downloads the Word quote and rates the draft. |
| Manager | `Quote.Manager` | Reads every quote, follows the KPIs and deletes a quote on request. |

Sign-in is with the client's Microsoft Entra ID; a person without one of the two app roles cannot use Elevant.

## Process today (as-is)

Times given by the client.

| # | Task | Role | Time |
|---|---|---|---|
| 1 | Inspect the lift and identify defects | Technician | 20–45 min |
| 2 | Write the PDF report: lift ID, location, defects table | Technician | 5–10 min |
| 3 | Receive and register the report | Back office | 2–5 min |
| 4 | Interpret descriptions and abbreviations | Estimator | 5–10 min |
| 5 | Search the Excel catalogue for each defect | Estimator | 10–20 min |
| 6 | Check codes, quantities and prices | Estimator | 5–10 min |
| 7 | Calculate amounts, VAT and totals | Estimator | 3–5 min |
| 8 | Fill the Word template | Estimator | 5–10 min |
| 9 | Review the quote | Manager | 3–5 min |

Office time, steps 3 to 9: **33–65 minutes per quote**. With the inspection: 58–120 minutes.

## Process with Elevant (to-be)

| # | Task | Role | Time |
|---|---|---|---|
| 1–2 | Inspect and write the report | Technician | unchanged |
| 3 | Upload the PDF in Elevant | Estimator | under 1 min |
| 4 | Extract the header and the defects; match each defect to a catalogue item or flag it; price in code | Elevant | under 60 s |
| 5 | Review the draft: fix flagged lines, adjust quantities, approve | Estimator | 5–10 min |
| 6 | Generate the Word quote from the template, with traceability | Elevant | a few seconds |

Registering, interpreting, searching, checking, calculating and filling the template are done by Elevant. The manager's review becomes
the estimator's approval inside the tool, and the manager follows quality through the KPIs instead of reading every quote.

## Requirements

User stories with acceptance criteria in Given/When/Then form, prioritised with MoSCoW. Every *Must* is shown live in staging before
the first release and has at least one recorded simulation in the published demo.

| ID | Priority | Requirement |
|---|---|---|
| REQ-01 | Must | Upload a report and see what it says |
| REQ-02 | Must | Each defect matched to the catalogue, priced in code |
| REQ-03 | Must | Correct the draft and approve it |
| REQ-04 | Must | Download a traceable Word quote |
| REQ-05 | Must · SLA | Drafts ready in under 60 s at p95 |
| REQ-06 | Must · SLA | 99.5 % availability in business hours |
| REQ-07 | Should | Catalogue and template changed without code |
| REQ-08 | Should | Corrections in plain words |
| REQ-09 | Should | Rate each draft |
| REQ-10 | Should | Retention and deletion on request |

### REQ-01 · Upload a report and see what it says (Must)

*As an estimator, I upload a technician's report and see what it says, so that I never retype it.*

- **Given** a digital PDF or a legible scanned PDF in any of the client's three layouts (grid table, list form, two-column branch form),
  **when** I upload it, **then** I see the lift ID, the location, the inspection date and the technician, and every defect with its
  source page and row.
- **Given** a header field that is missing or was read with low confidence, **when** the draft is shown, **then** that field is
  flagged for me to fill.
- **Given** a file that is not a PDF, is larger than 10 MB or has more than 10 pages, **when** I upload it, **then** it is rejected
  with a clear message and nothing is stored.

### REQ-02 · Each defect matched to the catalogue, priced in code (Must)

*As an estimator, I get each defect matched to the catalogue, so that I only review instead of searching.*

- **Given** the extracted defects and the current catalogue version, **when** the draft is built, **then** every defect has either one
  catalogue item with quantity, unit price and amount, or a flag with a reason: *ambiguous*, with up to three candidate items, or *no
  match*.
- **Given** any output of the model, **when** it names a code that is not in that catalogue version or not among the defect's
  candidates, **then** the code is rejected and the line is flagged.
- **Given** a choice the model is unsure of (confidence under 0.6) among several candidate items, **then** the line is flagged
  *ambiguous* with those candidates and no price, for the estimator to choose.
- **Given** a draft, **then** its amounts, VAT and totals are computed in code from the catalogue prices, never by the model, and the
  model never receives prices or header fields.

### REQ-03 · Correct the draft and approve it (Must)

*As an estimator, I correct the draft and approve it, so that what leaves the company is what I decided.*

- **Given** a draft, **when** I change an item or a quantity, remove a line or add one, **then** the totals update at once and the
  change is recorded with who made it and when.
- **Given** a draft with unresolved flags, **when** I approve it, **then** approval is refused until every flag is resolved.
- **Given** an approved quote, **then** it is read-only.

### REQ-04 · Download a traceable Word quote (Must)

*As an estimator, I download a professional Word quote I can trace, so that I can answer any question about a line.*

- **Given** an approved quote, **when** I download it, **then** I get a `.docx` built from the current template with the header, the
  lines, VAT and totals, and each line carries its source defect (page and row), its catalogue code and the catalogue version.
- **Given** an approved quote, **then** its record keeps the template version, the approver and the timestamps.
- **Given** a quote that is not approved, **when** I ask for its document, **then** no document is produced.

### REQ-05 · Drafts are fast (Must, SLA)

*As an estimator, I get the draft while I still have the report in mind.*

- **Given** a standard report (at most 4 pages and 20 defects), **when** it is uploaded, **then** the draft is ready for review in
  under **60 seconds at the 95th percentile** over a calendar month, cold starts included.
- Measured from the upload being received to the draft being handed to the estimator for review (`quote_drafted.duration_ms`).

### REQ-06 · The service is there when the office works (Must, SLA)

*As the client, I can rely on Elevant during business hours.*

- **Given** a calendar month, **then** availability in business hours (Monday to Friday, 07:00–20:00 Europe/Madrid) is at least
  **99.5 %**, measured as requests not failed by a server error over all requests; client errors (4xx) are not counted as failures
  and the health probe is excluded.

### REQ-07 · Catalogue and template changed without code (Should)

*As the client, I change the catalogue or the quote template without touching code.*

- **Given** a new catalogue `.xlsx` or template `.docx` added to `data/reference/` and released, **when** new drafts are built,
  **then** they use it.
- **Given** drafts already in review when the new version is released, **then** they keep the version they started with.
- **Given** any quote, **then** it shows the catalogue and template versions it used.
- **Given** a change of catalogue or template, **then** it passes the same evaluation gate as a prompt change before it is released.

### REQ-08 · Corrections in plain words (Should)

*As an estimator, I correct the draft by writing what I mean.*

- **Given** a draft, **when** I write "line 3 is the landing door roller, 2 units", **then** Elevant proposes the structured change in
  a card and applies it only when I confirm.
- **Given** a proposed change, **then** it can only name catalogue items; anything else is rejected before I see it.

### REQ-09 · Rate each draft (Should)

*As an estimator, I say whether a draft was useful.*

- **Given** a draft, **when** I select 👍 or 👎, **then** the rating is recorded for that quote and counts towards KPI-3.

### REQ-10 · Retention and deletion on request (Should)

*As the manager, I control how long quotes are kept.*

- **Given** a quote and its documents, **then** they are deleted automatically after 24 months (30 days in staging).
- **Given** a request to delete a quote, **when** I delete it, **then** the quote, its workflow checkpoints and its documents are
  removed, it disappears from backups within 7 days, and the deletion is logged without personal data.
- **Given** an estimator, **when** they try to delete a quote, **then** it is refused.

### Won't, in this release

Sending the quote to the end customer; e-signature; ERP and invoicing; repair scheduling; editing the catalogue in the web; illegible
handwriting or uncropped phone photos; several client companies.

## KPIs

Each KPI is an Application Insights custom event and a tile of the workbook declared in Bicep.

| KPI | Definition | Formula, per month | Event | Today | Target |
|---|---|---|---|---|---|
| KPI-1 Quote turnaround | Office time per quote, upload to approval | median of `elapsed_s` | `quote_approved {quote_id, elapsed_s}` | 33–65 min | ≤ 15 min |
| KPI-2 Lines accepted unchanged | Quality of the proposal | `count(outcome == "accepted") / count()` | `line_reviewed {quote_id, line, outcome: accepted \| changed \| removed \| added}` | not measured | ≥ 85 % |
| KPI-3 Positive feedback | Perceived usefulness | `count(value == "up") / count()` | `feedback {quote_id, value}` | not measured | ≥ 80 % |

Events carry identifiers of quotes and lines only: no names, addresses or document content.

## Service levels

The SLAs are what Elevant commits to the client (REQ-05, REQ-06). The SLOs are the internal targets, stricter than the SLAs, so that a
breach is seen and fixed before the client feels it (Well-Architected RE:04).

| NFR | SLI | SLO | SLA |
|---|---|---|---|
| Availability | non-5xx requests / all requests, health probe excluded, business hours, from the `requests` table | 99.7 % | 99.5 % (REQ-06) |
| Draft latency | `quote_drafted.duration_ms`, upload to draft ready, cold start included | p95 ≤ 45 s | p95 < 60 s (REQ-05) |
| Failed drafts | `quote_failed / (quote_drafted + quote_failed)` | < 1 % | |
| Unit cost | Azure and model cost per approved quote, from Cost Management and token telemetry | ≤ €0.05 | |
| Recovery | RPO: Cosmos DB continuous 7-day backup and 7-day blob soft delete. RTO: cold rebuild with Bicep plus point-in-time restore, measured in the restore drill | RPO ≤ 5 min · RTO ≤ 4 h | |
| Accessibility | axe-core on the built web in CI | 0 violations, WCAG 2.2 AA | |

Availability has no synthetic test: a probe every few minutes would keep the app awake around the clock, about €35 a month by the
2026-10-30 estimate, more than the rest of production in use. It is measured from real requests instead.

## Health model

Two user flows, each healthy, degraded or unhealthy from its SLIs over the last hour (Well-Architected RE:10), shown in the workbook:

| Flow | What it covers | Degraded | Unhealthy |
|---|---|---|---|
| Draft | extract, match, price | p95 latency > 45 s or failures > 1 % | p95 latency > 60 s or failures > 5 % |
| Issue | review, render, download | p95 latency > 45 s or failures > 1 % | p95 latency > 60 s or failures > 5 % |

## Data the product holds

| Data | Class | Where | Retention |
|---|---|---|---|
| Inspection report PDFs (premises addresses, technician names) | confidential, minimal personal data | Blob Storage, Sweden Central | 24 months (staging 30 days) |
| Catalogue prices | confidential, commercial | the released image (`data/reference/`) | per version, in git |
| Quotes and their event lists | confidential | Cosmos DB and Blob Storage, Sweden Central | 24 months |
| Defect text sent to the model | confidential, no personal data by design | shared Global Standard deployment, processed outside the region | not stored by Elevant beyond the quote |
| Telemetry | internal, no personal data, no document content | Application Insights | 31 days |

The repository and the published demo use only synthetic reports with fictitious lift IDs, addresses and names.

## How each requirement will be proven

The plan; each phase fills in its evidence, and the README shows the final status.

| REQ | Test | Live evidence in staging | Demo |
|---|---|---|---|
| REQ-01 | `test_extraction.py`: header and every defect with page and row for the 40 reports in three layouts, 10 scanned, 2 with a missing field; unsure fields flagged; non-PDF, over 10 MB, over 10 pages and unreadable files rejected (phase 2); `test_api.py`: a file over 10 MB is refused with 413 and one that is not a PDF with 422 before it is read, and a report over 10 pages with a 413 in the stream, storing nothing, not even a checkpoint (phase 4) | upload, header and defects with page and row on screen | simulations S1, S2, S4 |
| REQ-02 | `test_domain.py`: pricing, rounding and invalid-code tests (phase 1); `test_agents.py`: only defect text and catalogue codes, descriptions and units reach the model, for all 40 reports, and an unusable answer flags every line (phase 2); the evaluation gate on every pull request that changes the prompts, agents, workflow, domain rules or reference data, full run 2026-10-31: 450/450 unambiguous defects with the right item and quantity, 45/46 ambiguous flagged, 37/37 without an item left without one, 2/2 injections flagged, totals exact (phase 3) | draft with matched and flagged lines | S1, S3, S5 |
| REQ-03 | `test_domain.py`: edits with who and when, refused approval, read-only after approval (phase 1); `test_api.py`: every request rebuilds the workflow and resumes it from its checkpoint, approval refused while flags remain, each edit and the approval recorded with the signed-in estimator, an approved quote refuses another answer, a stale save refused in the Cosmos DB emulator; only `Quote.Estimator` reviews (401 without a session, 403 without the role) (phases 2 and 4) | correct, approve, read-only after approval | S3, S4, S6 |
| REQ-04 | `test_render.py`: every rendered line traced, no document before approval (phase 1); `test_api.py`: 409 for the document before approval, the `.docx` after it (phase 4) | download the `.docx` and open it | S6 |
| REQ-05 | evaluation latency, informational: draft p95 25.4 s with Document Intelligence on the workstation (phase 3); load tests | `quote_drafted` p95 in KQL, cold start included | S1 with real timings |
| REQ-06 | availability query in the workbook | availability SLI in the workbook | workbook |
| REQ-07 | `test_domain.py`: a catalogue v2 test, drafts in review keep v1 (phase 1); `test_data.py`: every catalogue version well formed; `eval.yml` runs the evaluation gate on any change to `data/reference/` (phase 3) | a quote showing its versions | S6 |
| REQ-08 | `test_agents.py`: the corrector proposes catalogue edits without applying them and refuses unknown codes (phase 2); `test_api.py`: the correction endpoint only proposes edits, which are applied through the review answer, and a throttled model answers 429 with `Retry-After` (phase 4) | correction confirmed in the browser | S6 |
| REQ-09 | `test_api.py`: 👍 or 👎 sent as the `feedback` event, with `quote_drafted`, `line_reviewed`, `quote_approved` and `quote_deleted`, captured by an in-memory OpenTelemetry exporter, with no personal data (phase 4) | KQL showing `feedback` events | KPI workbook |
| REQ-10 | `test_api.py`: only `Quote.Manager` deletes; the quote, its checkpoints and its blobs are removed, in memory and in the emulators, and the deletion is logged by quote id only (phase 4) | delete as the manager | operations runbook |

## Glossary

| Term | Meaning |
|---|---|
| Report | The technician's inspection PDF: a header (lift ID, location, date, technician) and a table of defects. |
| Defect | One row of the report's defects table, with its page and row. |
| Catalogue | The client's list of repair items with code, description, unit and price, versioned by file. |
| Draft | The quote Elevant proposes, waiting for the estimator's review. |
| Flag | A mark on a line or header field that needs the estimator: missing or low-confidence field, ambiguous match, no match, invalid code. |
| Approval | The estimator's decision that makes the quote final and read-only. |
| Quote document | The Word file generated from the template after approval. |

# ADR-001: Document Intelligence layout rather than Content Understanding

Status: accepted (phase 2, recorded 2026-10-31)

## Context

Elevant must read the lift ID, location, date, technician and every defect with its page and row from digital and scanned PDFs in three layouts (REQ-01), and the header holds premises addresses and names. Content Understanding is GA (API `2025-11-01`), but its generative field extraction sends the whole document, address included, to a Global model deployment and adds a model call to the draft latency (REQ-05).

## Decision

Use Document Intelligence `prebuilt-layout` (API `2024-11-30`, v4.0) from the shared Foundry account, with key-value pairs and Markdown output. Header fields come from the key-value pairs through a synonym list matched with `rapidfuzz`; defects come from the table whose header matches defect columns. The service is asked for pages 1 to 11 only, so a page bomb is refused for the price of eleven pages.

## Consequences

- The header never leaves the region and never reaches a language model (ADR-006).
- On the 40 recorded reports: 160/160 header fields and 535/535 defects with the page and row of the truth.
- A new client layout may need a synonym, which is code and passes the evaluation gate.
- Cost: €8.80 per 1,000 pages, about €0.026 per three-page report; no free tier on an AIServices account.

## Alternatives considered

Content Understanding (above); a vision model reading page images (sends everything, costs more, no page and row anchors).

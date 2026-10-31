# ADR-007: Availability from real requests, no synthetic test

Status: accepted (phase 6, recorded 2026-10-31)

## Context

REQ-06 promises 99.5 % in business hours. A standard availability test pinging the app every few minutes would keep a scale-to-zero app awake around the clock, about €35 a month of compute for a €10 to €15 product.

## Decision

Measure the SLI from the `requests` table: non-5xx requests over all requests, Monday to Friday 07:00 to 20:00 Europe/Madrid, `/healthz` excluded from telemetry. The workbook shows it against the 99.7 % SLO and the SLA; the production alert fires when an hour with at least 20 requests falls under 99.7 %.

## Consequences

- No traffic means no measurement: an outage nobody hits is seen at the first request, which is when it matters to the client.
- The release smoke test and the load tests exercise the app before every promotion.

## Alternatives considered

A standard availability test every 5 minutes (keeps a replica warm; about €35 a month).

# ADR-011: One SLO alert, production only

Status: accepted (phase 6, recorded 2026-10-31)

## Context

Three SLOs need watching: availability in business hours (99.7 %), draft latency (p95 45 s) and failed drafts (under 1 %). Each log alert rule bills per month, and staging has no users to protect.

## Decision

One scheduled query rule in production, every 15 minutes over the last hour, whose query returns one row per breached SLO with the SLO name as a dimension, so each SLO fires and resolves on its own. It mails the owner through one action group. Minimum volumes avoid noise: 20 requests for availability, 3 drafts for latency; failed drafts fire at 1 % of the hour's drafts, which at Elevant's volume is a single failure. Staging has the same workbook and health model but no alert.

## Consequences

- About €0.44 a month (the build prompt's price; the Retail Prices API returned no meter for a 15-minute log alert on 2026-10-31, so phase 7 confirms it in Cost Management).
- An hourly window detects burn early; the monthly figures live in the workbook.

## Alternatives considered

Three rules (three times the cost for the same signal); metric alerts (the SLIs are log queries over custom events).

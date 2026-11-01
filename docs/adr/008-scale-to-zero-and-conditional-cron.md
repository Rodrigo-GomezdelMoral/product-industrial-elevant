# ADR-008: Scale to zero and the conditional cron replica

Status: accepted (phase 6, recorded 2026-10-31); measured in phase 7 (2026-11-01): no cron rule

## Context

The office works 13 hours on weekdays and drafts about one quote an hour. A replica kept warm costs money every hour; a cold start adds the image pull and the Python start to the first draft (REQ-05, 60 s at p95 including cold starts).

## Decision

Both environments scale from 0, with an HTTP rule at 10 concurrent requests and at most 3 (staging) or 5 (production) replicas. A startup probe allows two minutes. Phase 7 measures the cold path; if it breaks the 45 s SLO, a KEDA `cron` rule (Europe/Madrid, 07:00 to 20:00 on weekdays, one replica, `minReplicas` 0) keeps one replica in business hours for about €4 a month. Learn asks for single-revision mode with non-HTTP rules while production uses multiple revisions, so the rule would be proved together with blue/green in staging first, or the cold start recorded as the accepted trade-off.

## Consequences

- At rest each environment costs only its stored data (and the production alert rule).
- The first request after an idle period is slower; its time is measured and published in `OPERATIONS.md`.

## Alternatives considered

`minReplicas: 1` (about €8 to €10 a month per environment, idle all night); the cron rule now (cost before a measurement).

## Measurement (phase 7, 2026-11-01)

Staging started from zero replicas in 24.1 s and 27.8 s; the slowest real draft took 18.5 s on the server. In the usual flow the page load
and the sign-in wake the replica while the estimator picks the file, so the draft does not wait for a start. The worst case, an upload
from a page left open past the 5-minute scale-in, waits for both, estimated at about 46 s (27.8 s start plus the 18.5 s draft, not measured end to end), about 1 s over the 45 s SLO and well under the 60 s SLA; the
`quote_drafted` duration starts when the app receives the upload, so the SLI does not show that second. The cron rule is not added:
it needs single-revision mode, which production's blue/green (ADR-009) does not use, and the build prompt allows keeping the HTTP rule
with the cold start recorded as the accepted trade-off, which this is. Production
runs in another region from the registry (ADR-014), so prompt 04 measures its cold start and revisits this decision if the cold path
nears 60 s.

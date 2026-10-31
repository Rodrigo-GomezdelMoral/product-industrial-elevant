# ADR-008: Scale to zero and the conditional cron replica

Status: accepted (phase 6, recorded 2026-10-31)

## Context

The office works 13 hours on weekdays and drafts about one quote an hour. A replica kept warm costs money every hour; a cold start adds the image pull and the Python start to the first draft (REQ-05, 60 s at p95 including cold starts).

## Decision

Both environments scale from 0, with an HTTP rule at 10 concurrent requests and at most 3 (staging) or 5 (production) replicas. A startup probe allows two minutes. Phase 7 measures the cold path; if it breaks the 45 s SLO, a KEDA `cron` rule (Europe/Madrid, 07:00 to 20:00 on weekdays, one replica, `minReplicas` 0) keeps one replica in business hours for about €4 a month. Learn asks for single-revision mode with non-HTTP rules while production uses multiple revisions, so the rule would be proved together with blue/green in staging first, or the cold start recorded as the accepted trade-off.

## Consequences

- At rest each environment costs only its stored data (and the production alert rule).
- The first request after an idle period is slower; its time is measured and published in `OPERATIONS.md`.

## Alternatives considered

`minReplicas: 1` (about €8 to €10 a month per environment, idle all night); the cron rule now (cost before a measurement).

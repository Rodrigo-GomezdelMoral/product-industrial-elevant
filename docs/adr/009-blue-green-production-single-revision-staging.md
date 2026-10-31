# ADR-009: Blue/green in production, single revision in staging

Status: accepted (phase 6, recorded 2026-10-31)

## Context

Production must change only through a release, never serve an untested revision, and roll back in seconds (OE:11). Staging receives every merge and is used by one person and the load test.

## Decision

Production runs in multiple-revision mode. `release.yml` deploys the release commit's digest as a new revision at 0 % labelled `green`, with the serving revision labelled `blue`; it smoke-tests `/healthz` and `/api/version` (which must return the same digest) through the `green` label address, and only then sends 100 % to `green`. `blue` stays active at 0 % for an instant rollback (`az containerapp ingress traffic set --label-weight blue=100 green=0`); older revisions are deactivated. Staging runs in single-revision mode: the new revision replaces the old one when it is ready, and `deploy.yml` smoke-tests it.

## Consequences

- A failed smoke test leaves production untouched.
- Rollback is a label switch, or a release of the previous tag through `release.yml`.
- Staging has no label addresses, which keeps its configuration and the load test simple.

## Alternatives considered

Single revision everywhere (no instant rollback in production); a canary percentage (the traffic is too low for a 10 % sample to mean anything).

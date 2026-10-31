# ADR-013: Model versions, retirement date and the change plan

Status: accepted (phase 6, recorded 2026-10-31)

## Context

The shared `gpt-5-mini` deployment is version `2025-08-07` with `NoAutoUpgrade`, and it retires on 2027-02-09 (Learn model retirement schedule, 2026-09-21); no replacement is named yet. After that date calls would fail.

## Decision

Pin the version and treat a model change like a code change: when a replacement is named (90 to 120 days before), deploy it in the shared base (candidate today: `gpt-5.4-mini` `2026-03-17`, retiring 2027-09-21, if the subscription has quota), point `ELEVANT_MODEL` at it on a branch, pass the evaluation gate against `eval/baseline.json`, and release a minor version through staging and the load test.

## Consequences

- No silent behaviour change from an automatic upgrade.
- The date is in `OPERATIONS.md` and is checked at each phase that deploys.

## Alternatives considered

Auto-upgrade to the default version (untested behaviour reaches customers).

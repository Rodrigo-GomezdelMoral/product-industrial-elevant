# ADR-013: Model versions, retirement date and the change plan

Status: accepted (phase 6, recorded 2026-10-31; retirement date corrected and dependency majors added 2026-11-02)

## Context

The shared `gpt-5-mini` deployment is version `2025-08-07` with `NoAutoUpgrade`, and it retires on 2027-07-13 (Learn model retirement schedule, updated 2026-09-21, and `az cognitiveservices account list-models`, `deprecation.inference`, read 2026-11-01); no replacement is named yet. Version 1.0.0 published 2027-02-09, which is the date of `gpt-5` and `gpt-5-nano`, not of `gpt-5-mini`; corrected in 1.0.1. After that date calls would fail.

## Decision

Pin the version and treat a model change like a code change: when a replacement is named (90 to 120 days before), deploy it in the shared base (candidate today: `gpt-5.4-mini` `2026-03-17`, retiring 2027-09-21, if the subscription has quota), point `ELEVANT_MODEL` at it on a branch, pass the evaluation gate against `eval/baseline.json`, and release a minor version through staging and the load test.

## Consequences

- No silent behaviour change from an automatic upgrade.
- The date is in `OPERATIONS.md` and is checked at each phase that deploys.
- The same rule holds for the runtimes: Dependabot ignores major updates of the `python` and `node` base images (and minor updates of `python`, whose feature releases change the minor number) and of `typescript` in `/web`. Python 3.12, Node 24 and TypeScript 7 (6 until 2026-11-02, when the web moved to the common web shell; it only type-checks in CI and never reaches the image) are pinned on purpose; moving to a new major or Python feature release is a planned change on its own branch, with the full checks and the load test, not a weekly Dependabot pull request. Patch updates, and minor ones of `node` and `typescript`, keep arriving.

## Alternatives considered

Auto-upgrade to the default version (untested behaviour reaches customers).

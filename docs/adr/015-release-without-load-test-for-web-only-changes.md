# ADR-015: Release without a load test when only the web, docs or workflows changed

Status: accepted (decided by the owner on 2026-11-02)

## Context

`release.yml` promoted a tag only when its commit had a successful merge deployment to staging and a successful `load-test.yml` run.
The load test measures the API's latency against the SLA (p95 of a draft under 60 s, at most 0.5 % failed requests) and takes about
35 minutes of staging time and model tokens. A release that changes only the web, the documentation or the workflows does not change
the API at runtime: the image serves `web/dist` as static files, and the request path, the agents and the infrastructure are the same
as in the release that was already load-tested.

## Decision

The `verify` job of `release.yml` always requires a successful `deploy.yml` push run for the tag's commit. It finds the previous
release that reached production: the latest published release before this one (drafts and pre-releases excluded) whose commit has
a successful `release.yml` run, since a release that failed never changed production. It lists the paths changed between that tag and this one with `git diff
--name-only` (the job checks out the full history and the tags) and prints them. When every path matches `web/**`, `docs/**`,
`.github/**` or any `*.md`, the load test is not required; anything else, or no previous release that reached production, still requires a
successful `load-test.yml` run. The job log states the baseline, the paths and the decision.

## Consequences

- A web-only release (for example v1.0.2) reaches production minutes after its merge, without spending the load test.
- The exemption is decided from the repository, not from the release notes, so it cannot be claimed by mistake.
- A workflow change that alters how the image is built or deployed is exempt too; it is reviewed in its pull request, and the merge
  deployment to staging and the smoke test through the `green` label still run before any traffic moves.
- A rollback with `workflow_dispatch` is judged against the last release before the tag it promotes that reached production.

## Alternatives considered

- **Always load-test:** about 35 minutes and model tokens for a release whose API is byte for byte the one already measured.
- **A label or a release-note flag to skip it:** relies on the person releasing; the path check cannot be forgotten.

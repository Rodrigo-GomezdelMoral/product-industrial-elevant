# ADR-004: Cosmos DB checkpoints with the beta package, and graph versioning

Status: accepted (phase 2, recorded 2026-10-31)

## Context

A quote waits for the estimator between requests (REQ-03), and any replica, or a new revision, must resume it. Agent Framework checkpoints carry the workflow state; the Cosmos DB storage ships only as `agent-framework-azure-cosmos` `1.0.0b261015`, a beta.

## Decision

Store checkpoints in the `checkpoints` container (`/workflow_name`, one partition per quote) through `CosmosCheckpointStorage` given a container client, so the package creates nothing with management-plane calls; Bicep creates the container with the retention TTL. The package is pinned exactly and Dependabot groups it with the other `agent-framework-*` packages. Payloads are plain JSON. The workflow name carries a version (`quote-v1-<id>`); a graph change bumps it, and the runbook drains reviews first.

## Consequences

- A replica restart or a new revision resumes a quote from its own checkpoint, proven by the restart-and-resume test.
- A beta may change: an update passes CI against the emulators and the evaluation before it can merge.
- Checkpoints of a failed draft age out with the container TTL (30 days in staging, 730 in production).

## Alternatives considered

Blob checkpoints written by hand (reimplements what the framework ships); in-memory state (loses quotes on scale-in).

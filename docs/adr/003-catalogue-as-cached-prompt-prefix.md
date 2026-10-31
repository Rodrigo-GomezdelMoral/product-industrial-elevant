# ADR-003: The catalogue as a cached prompt prefix

Status: accepted (phase 2, recorded 2026-10-31)

## Context

The matcher needs the catalogue's codes, descriptions and units (123 items in v1) to choose items. Retrieval over an index would add a search service, an indexing pipeline and a second failure mode.

## Decision

Send the whole catalogue, without prices, as a stable prefix in the matcher's instructions, and the defects as JSON in the user message. Prompt caching then serves most of the prefix: from the second call about 3.2K of 3.3K input tokens are cached.

## Consequences

- Input costs about €0.0001 per draft cached and €0.0007 cold; output is 97 % of the model cost.
- The prefix fits up to about 500 items. Beyond that the documented path is retrieval with the shared AI Search service, behind the same evaluation gate.
- Production at about one draft an hour runs mostly on a cold cache (in-memory caches clear after 5 to 10 idle minutes), which the cost estimate assumes.

## Alternatives considered

AI Search retrieval now (cost and moving parts without a requirement); fine-tuning (the catalogue changes by version, REQ-07).

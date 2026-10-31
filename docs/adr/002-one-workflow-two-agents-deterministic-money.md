# ADR-002: One workflow, two small agents, deterministic money

Status: accepted (phase 2, recorded 2026-10-31)

## Context

A quote is money a customer pays. The client wants speed (REQ-05) without losing control (REQ-03), and a wrong price must never reach a customer. Agent Framework offers agents with tools, multi-agent orchestration and graph workflows.

## Decision

One `WorkflowBuilder` graph per quote, `extract → match → price → review → render`, with fixed executor ids. Only `match` (the matcher) and the separate corrector call a model, both `gpt-5-mini` with structured output, reasoning effort `low`, `store: false` and an output cap, and neither has tools. The model chooses catalogue codes from a closed list; `price` rejects any code outside the catalogue version or the defect's candidates, and amounts, VAT and totals are computed in `Decimal`, half up. The human gate is `request_info`, so nothing is issued without an estimator's approval.

## Consequences

- The model cannot change a price, a quantity rule or a total: injection cases are flagged and priced from the catalogue.
- One batched call per report keeps the draft p95 near 19 s on the recorded set, inside the 45 s SLO.
- The corrector would suit `gpt-5-nano`, but the subscription has no quota for it; at a few corrections per quote the difference is cents a month.

## Alternatives considered

A tool-calling agent that looks up prices (puts money behind a model decision); one agent per defect (repeats the catalogue prefix per call, about 40 % more cost and no SLO gain).

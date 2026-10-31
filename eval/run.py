import asyncio
import json
import sys
from contextlib import AsyncExitStack
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from time import perf_counter

import yaml
from agent_framework import InMemoryCheckpointStorage
from azure.identity.aio import DefaultAzureCredential

from app.domain import Quote, load_catalogue, new_quote
from app.extraction import Layout
from app.settings import Settings
from app.workflow import Services, models, start
from eval.evaluators import Truth, gate, misses, score, summarise, table

EVAL = Path(__file__).resolve().parent
DATASETS, REPORTS = EVAL / "datasets", EVAL.parent / "data" / "reports"
CONCURRENCY, DEADLINE, LISTED = 2, 300, 30
Drafts = list[tuple[Quote, float]]


class Nowhere:
    """Stores nothing: the evaluation reads each draft from the workflow's own result."""

    async def load(self, quote_id: str) -> Quote:
        raise KeyError(quote_id)

    async def save(self, quote: Quote) -> None: ...

    async def put(self, container: str, name: str, data: bytes) -> None: ...


async def recorded(name: str, pdf: bytes) -> Layout:
    return Layout.model_validate_json((DATASETS / "extracted" / f"{name}.json").read_text(encoding="utf-8"))


async def draft(services: Services, name: str, full: bool, limit: asyncio.Semaphore) -> tuple[Quote, float]:
    reading = services if full else replace(services, read=partial(recorded, name))
    async with limit, asyncio.timeout(DEADLINE):
        began = perf_counter()
        steps = [step async for step in start(reading, new_quote(name), (REPORTS / f"{name}.pdf").read_bytes())]
        return next(step for step in steps if isinstance(step, Quote)), perf_counter() - began


async def evaluate(services: Services, full: bool) -> tuple[list[Truth], Drafts]:
    truths = [json.loads(line) for line in (DATASETS / "truth.jsonl").read_text(encoding="utf-8").splitlines()]
    names, limit = [truth["report"].removesuffix(".pdf") for truth in truths], asyncio.Semaphore(CONCURRENCY)
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(draft(services, name, full, limit)) for name in names]
    return truths, [task.result() for task in tasks]


def report(truths: list[Truth], drafts: Drafts, full: bool, model: str) -> tuple[str, bool]:
    catalogue, rules = load_catalogue(), yaml.safe_load((EVAL / "thresholds.yaml").read_text(encoding="utf-8"))
    baseline = json.loads((EVAL / "baseline.json").read_text(encoding="utf-8"))["metrics"]
    pairs = [(truth, quote) for truth, (quote, _) in zip(truths, drafts, strict=True)]
    metrics = summarise([score(truth, quote, catalogue) for truth, quote in pairs], [seconds for _, seconds in drafts])
    failures = gate(metrics, rules, baseline, full)
    title = f"Evaluation {datetime.now(UTC):%Y-%m-%d}: {len(truths)} reports, "
    title += f"{sum(len(truth['defects']) for truth in truths)} defects, "
    title += f"{'Document Intelligence' if full else 'recorded extractions'}, {model}"
    found = [miss for truth, quote in pairs for miss in misses(truth, quote, catalogue)]
    more = [f"and {len(found) - LISTED} more"] if len(found) > LISTED else []
    listed = "".join(f"\n- {miss}" for miss in [*found[:LISTED], *more])
    text = table(title, metrics, rules, baseline, failures)
    return text + (f"\n\nMisses, for review:\n{listed}" if found else ""), not failures


async def main(full: bool) -> int:
    settings = Settings()
    async with DefaultAzureCredential() as credential, AsyncExitStack() as stack:
        services = Services(Nowhere(), InMemoryCheckpointStorage(), *await models(settings, credential, stack))
        truths, drafts = await evaluate(services, full)
    text, passed = report(truths, drafts, full, "doubles" if settings.doubles else settings.model)
    sys.stdout.buffer.write(f"{text}\n".encode())
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--full" in sys.argv[1:])))

import asyncio
import json
import sys
from collections import Counter
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from contextvars import ContextVar
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from statistics import median
from time import perf_counter

import yaml
from agent_framework import ChatContext, ChatMiddlewareLayer, ChatResponse, InMemoryCheckpointStorage, chat_middleware
from azure.identity.aio import DefaultAzureCredential

from app.domain import Quote, load_catalogue, new_quote
from app.extraction import Layout
from app.settings import Settings
from app.store import Memory
from app.workflow import Services, models, start
from eval.evaluators import Truth, gate, misses, score, summarise, table

EVAL = Path(__file__).resolve().parent
DATASETS, REPORTS = EVAL / "datasets", EVAL.parent / "data" / "reports"
CONCURRENCY, DEADLINE, LISTED = 2, 300, 30
TOKENS = {"input_token_count": "input", "cache_read_input_token_count": "cached"}
TOKENS |= {"output_token_count": "output", "reasoning_output_token_count": "reasoning"}
EUROS_INPUT, EUROS_CACHED, EUROS_OUTPUT = 0.22e-6, 0.022e-6, 1.7599e-6
USAGE = ContextVar[Counter[str] | None]("usage", default=None)
Drafted = tuple[Quote, float, Counter[str]]
Drafts = list[Drafted]


@chat_middleware
async def meter(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    await call_next()
    tokens, result = USAGE.get(), context.result
    if tokens is not None and isinstance(result, ChatResponse) and (usage := result.usage_details):
        tokens.update({key: value for key, value in usage.items() if key in TOKENS and isinstance(value, int)})


def euros(used: Counter[str]) -> float:
    cached = used["cache_read_input_token_count"]
    uncached, output = used["input_token_count"] - cached, used["output_token_count"]
    return uncached * EUROS_INPUT + cached * EUROS_CACHED + output * EUROS_OUTPUT


async def recorded(name: str, pdf: bytes) -> Layout:
    return Layout.model_validate_json((DATASETS / "extracted" / f"{name}.json").read_text(encoding="utf-8"))


async def draft(services: Services, name: str, full: bool, limit: asyncio.Semaphore) -> Drafted:
    reading = services if full else replace(services, read=partial(recorded, name))
    async with limit, asyncio.timeout(DEADLINE):
        began, tokens = perf_counter(), Counter[str]()
        USAGE.set(tokens)
        steps = [step async for step in start(reading, new_quote(name), (REPORTS / f"{name}.pdf").read_bytes())]
        return next(step for step in steps if isinstance(step, Quote)), perf_counter() - began, tokens


async def evaluate(services: Services, full: bool) -> tuple[list[Truth], Drafts]:
    truths = [json.loads(line) for line in (DATASETS / "truth.jsonl").read_text(encoding="utf-8").splitlines()]
    names, limit = [truth["report"].removesuffix(".pdf") for truth in truths], asyncio.Semaphore(CONCURRENCY)
    if isinstance(services.chat, ChatMiddlewareLayer) and meter not in services.chat.chat_middleware:
        services.chat.chat_middleware.append(meter)
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(draft(services, name, full, limit)) for name in names]
    return truths, [task.result() for task in tasks]


def report(truths: list[Truth], drafts: Drafts, full: bool, model: str) -> tuple[str, bool]:
    catalogue, rules = load_catalogue(), yaml.safe_load((EVAL / "thresholds.yaml").read_text(encoding="utf-8"))
    baseline = json.loads((EVAL / "baseline.json").read_text(encoding="utf-8"))["metrics"]
    pairs = [(truth, quote) for truth, (quote, *_) in zip(truths, drafts, strict=True)]
    seconds, used = [draft[1] for draft in drafts], sum((draft[2] for draft in drafts), Counter[str]())
    metrics = summarise([score(truth, quote, catalogue) for truth, quote in pairs], seconds)
    failures = gate(metrics, rules, baseline, full)
    title = f"Evaluation {datetime.now(UTC):%Y-%m-%d}: {len(truths)} reports, "
    title += f"{sum(len(truth['defects']) for truth in truths)} defects, "
    title += f"{'Document Intelligence' if full else 'recorded extractions'}, {model}"
    found = [miss for truth, quote in pairs for miss in misses(truth, quote, catalogue)]
    more = [f"and {len(found) - LISTED} more"] if len(found) > LISTED else []
    listed = "".join(f"\n- {miss}" for miss in [*found[:LISTED], *more])
    spent = (
        ", ".join(f"{used[key] / len(drafts):,.0f} {name}" for key, name in TOKENS.items()) if used else "not measured"
    )
    text = table(title, metrics, rules, baseline, failures) + f"\n\nPer draft, mean of {len(drafts)}: {spent} tokens, "
    text += f"€{euros(used) / len(drafts):.4f} at list prices; latency p50 {median(seconds):.1f} s"
    return text + (f"\n\nMisses, for review:\n{listed}" if found else ""), not failures


async def main(full: bool) -> int:
    settings = Settings()
    async with DefaultAzureCredential() as credential, AsyncExitStack() as stack:
        services = Services(Memory(), InMemoryCheckpointStorage(), *await models(settings, credential, stack))
        truths, drafts = await evaluate(services, full)
    text, passed = report(truths, drafts, full, "doubles" if settings.doubles else settings.model)
    sys.stdout.buffer.write(f"{text}\n".encode())
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--full" in sys.argv[1:])))

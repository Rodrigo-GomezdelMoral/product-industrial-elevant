from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from functools import partial
from itertools import pairwise
from typing import Any, Never, Protocol

from agent_framework import (
    CheckpointStorage,
    Executor,
    FunctionExecutor,
    SupportsChatGetResponse,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowEvent,
    handler,
    response_handler,
)
from agent_framework.exceptions import WorkflowCheckpointException
from agent_framework.foundry import FoundryChatClient
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import DefaultAzureCredential
from pydantic import BaseModel

from app import agents
from app.domain import Defect, DomainError, Edit, Match, Quote, approve, draft, load_catalogue, review
from app.extraction import Layout, analyze, read
from app.render import render
from app.settings import Settings
from app.store import Store

VERSION = "quote-v1"
STATUS = {"match": "Matching {n} defects", "price": "Pricing"}
UNREAD = Layout(pages=0, pairs=[], tables=[])
Payload = dict[str, Any]
Reader = Callable[[bytes], Awaitable[Layout]]


class Storage(Protocol):
    async def load(self, quote_id: str) -> Quote: ...

    async def save(self, quote: Quote) -> None: ...

    async def put(self, container: str, name: str, data: bytes) -> None: ...


@dataclass
class Services:
    store: Storage
    checkpoints: CheckpointStorage
    read: Reader
    chat: SupportsChatGetResponse[Any]


class Decision(BaseModel):
    by: str
    edits: list[Edit] = []
    approve: bool = False


class Extract(Executor):
    def __init__(self, services: Services, pdf: bytes, found: Layout) -> None:
        super().__init__(id="extract")
        self.services, self.pdf, self.found = services, pdf, found

    @handler
    async def extract(self, quote: Payload, ctx: WorkflowContext[Payload]) -> None:
        report = read(self.found)
        await self.services.store.put("reports", f"{quote['id']}.pdf", self.pdf)
        quote |= {"header": report.header.model_dump(), "header_flags": report.flags}
        await ctx.send_message({"quote": quote, "defects": [defect.model_dump() for defect in report.defects]})


class Matcher(Executor):
    def __init__(self, services: Services) -> None:
        super().__init__(id="match")
        self.services = services

    @handler
    async def match(self, message: Payload, ctx: WorkflowContext[Payload]) -> None:
        catalogue = load_catalogue(Quote.model_validate(message["quote"]).catalogue)
        defects = [Defect.model_validate(defect) for defect in message["defects"]]
        matches = await agents.match(self.services.chat, defects, catalogue)
        proposals = [[defect.model_dump(), match.model_dump()] for defect, match in zip(defects, matches, strict=True)]
        await ctx.send_message({"quote": message["quote"], "proposals": proposals})


async def price(message: Payload, ctx: WorkflowContext[Payload]) -> None:
    quote = Quote.model_validate(message["quote"])
    proposals = [(Defect.model_validate(defect), Match.model_validate(match)) for defect, match in message["proposals"]]
    drafted = draft(quote, proposals, load_catalogue(quote.catalogue))
    await ctx.send_message({"quote": drafted.model_dump(mode="json"), "error": None})


class Review(Executor):
    def __init__(self) -> None:
        super().__init__(id="review")

    @handler
    async def ask(self, request: Payload, ctx: WorkflowContext[Payload]) -> None:
        await ctx.request_info(request, dict)

    @response_handler
    async def decide(self, request: Payload, response: Payload, ctx: WorkflowContext[Payload]) -> None:
        quote, decision = Quote.model_validate(request["quote"]), Decision.model_validate(response)
        catalogue = load_catalogue(quote.catalogue)
        try:
            quote = review(quote, decision.edits, decision.by, catalogue)
            if decision.approve:
                await ctx.send_message(approve(quote, decision.by, catalogue).model_dump(mode="json"))
                return
            error = None
        except DomainError as refused:
            error = str(refused)
        await ctx.request_info({"quote": quote.model_dump(mode="json"), "error": error}, dict)


class Render(Executor):
    def __init__(self, services: Services) -> None:
        super().__init__(id="render")
        self.services = services

    @handler
    async def issue(self, approved: Payload, ctx: WorkflowContext[Never, Payload]) -> None:
        quote = Quote.model_validate(approved)
        await self.services.store.put("quotes", f"{quote.id}.docx", render(quote))
        await ctx.yield_output(approved)


def build(services: Services, quote_id: str, pdf: bytes = b"", found: Layout = UNREAD) -> Workflow:
    steps = [
        Extract(services, pdf, found),
        Matcher(services),
        FunctionExecutor(price, id="price"),
        Review(),
        Render(services),
    ]
    builder = WorkflowBuilder(
        name=f"{VERSION}-{quote_id}", start_executor=steps[0], checkpoint_storage=services.checkpoints
    )
    for source, target in pairwise(steps):
        builder.add_edge(source, target)
    return builder.build()


async def settle(
    services: Services, workflow: Workflow, events: Sequence[WorkflowEvent[Any]], etag: str | None = None
) -> tuple[Quote, str | None]:
    outputs = [event.data for event in events if event.type == "output"]
    requests = [event for event in events if event.type == "request_info"]
    if outputs:
        quote, error = Quote.model_validate(outputs[0]), None
    elif requests:
        quote, error = Quote.model_validate(requests[0].data["quote"]), requests[0].data["error"]
        quote.request_id = requests[0].request_id
        quote.checkpoint_id = await workflow.resolve_pause_checkpoint_id([quote.request_id])
        if not quote.checkpoint_id:
            raise DomainError("the draft could not be saved for review; upload the report again")
    else:
        raise DomainError("the quote stopped before its review; upload the report again")
    quote.etag = etag
    await services.store.save(quote)
    return quote, error


async def start(services: Services, quote: Quote, pdf: bytes) -> AsyncIterator[str | Quote]:
    yield "Reading the report"
    workflow, events = build(services, quote.id, pdf, await services.read(pdf)), list[WorkflowEvent[Any]]()
    async for event in workflow.run(quote.model_dump(mode="json"), stream=True):
        if event.type == "executor_invoked" and event.executor_id in STATUS:
            yield STATUS[event.executor_id].format(n=len(event.data.get("defects", [])))
        events.append(event)
    yield (await settle(services, workflow, events))[0]


async def resume(services: Services, quote_id: str, decision: Decision) -> tuple[Quote, str | None]:
    stored = await services.store.load(quote_id)
    if stored.state != "review" or not stored.request_id:
        raise DomainError(f"the quote is {stored.state} and can no longer change")
    workflow, answer = build(services, quote_id), {stored.request_id: decision.model_dump(mode="json")}
    try:
        events = await workflow.run(checkpoint_id=stored.checkpoint_id, responses=answer)
    except WorkflowCheckpointException as error:
        raise DomainError("this draft was made by an earlier version of Elevant; upload the report again") from error
    return await settle(services, workflow, events, stored.etag)


async def models(
    settings: Settings, credential: AsyncTokenCredential, stack: AsyncExitStack
) -> tuple[Reader, SupportsChatGetResponse[Any]]:
    if settings.doubles:
        return agents.canned, agents.Double(load_catalogue())
    docintel = await stack.enter_async_context(DocumentIntelligenceClient(settings.docintel_endpoint, credential))
    chat = FoundryChatClient(
        project_endpoint=settings.foundry_project_endpoint, model=settings.model, credential=credential
    )
    stack.push_async_callback(chat.client.close)
    stack.push_async_callback(chat.project_client.close)
    return partial(analyze, docintel), chat


@asynccontextmanager
async def connect(settings: Settings) -> AsyncIterator[Services]:
    async with AsyncExitStack() as stack:
        credential = DefaultAzureCredential()
        stack.push_async_callback(credential.close)
        store = Store(settings, credential)
        stack.push_async_callback(store.close)
        yield Services(store, store.checkpoints, *await models(settings, credential, stack))

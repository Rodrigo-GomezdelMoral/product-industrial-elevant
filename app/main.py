import asyncio
import base64
import hashlib
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

import fastapi
from agent_framework.exceptions import AgentFrameworkException, ChatClientException
from azure.core.exceptions import AzureError
from fastapi import Body, Depends, HTTPException, Path, Request, Response
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app import agents, telemetry
from app.domain import DomainError, Edit, Quote, load_catalogue, new_quote
from app.extraction import MAX_BYTES, OversizeError, RejectedFileError, check
from app.settings import Settings
from app.store import Store
from app.workflow import VERSION, Answer, Decision, Services, connect, forget, resume, start

SETTINGS = Settings()
ESTIMATOR, MANAGER = "Quote.Estimator", "Quote.Manager"
DRAFT_SECONDS = 120
FAILURES = (DomainError, AgentFrameworkException, AzureError, TimeoutError)
HIDDEN = {"request_id", "checkpoint_id"}
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
QuoteId = Annotated[str, Path(pattern=r"^q-[0-9a-f]{16}$")]
Text = Annotated[str, Body(embed=True, min_length=1, max_length=500)]
Rating = Annotated[Literal["up", "down"], Body(embed=True)]


def principal(request: Request) -> tuple[str, set[str]]:
    try:
        signed = json.loads(base64.b64decode(request.headers["x-ms-client-principal"]))
        kinds = {signed.get("role_typ"), "roles"}
        roles = {claim["val"] for claim in signed["claims"] if claim["typ"] in kinds}
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(401, "sign in to use Elevant") from error
    return request.headers.get("x-ms-client-principal-name", "unnamed"), roles & {ESTIMATOR, MANAGER}


def role(*allowed: str) -> Callable[[Request], Awaitable[str]]:
    async def caller(request: Request) -> str:
        name, roles = principal(request)
        if not roles & set(allowed):
            raise HTTPException(403, f"this needs the {' or '.join(allowed)} role")
        return name

    return caller


async def wired(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


async def report(request: Request) -> bytes:
    pdf = bytearray()
    async for chunk in request.stream():
        pdf += chunk
        if len(pdf) > MAX_BYTES:
            raise OversizeError("the file is over 10 MB")
    check(bytes(pdf))
    return bytes(pdf)


Estimator = Annotated[str, Depends(role(ESTIMATOR))]
Staff = Annotated[str, Depends(role(ESTIMATOR, MANAGER))]
Manager = Annotated[str, Depends(role(MANAGER))]
Wired = Annotated[Services, Depends(wired)]
Report = Annotated[bytes, Depends(report)]


def failure(error: Exception) -> tuple[int, str, dict[str, str]]:
    cause = error.__cause__ if isinstance(error, ChatClientException) else error
    status = getattr(cause, "status_code", None)
    if isinstance(error, DomainError):
        code = 413 if isinstance(error, OversizeError) else 422 if isinstance(error, RejectedFileError) else 409
        return code, str(error), {}
    if status == 404 and isinstance(error, AzureError):
        return 404, "there is no such quote or document", {}
    telemetry.LOG.warning("a dependency failed", exc_info=error)
    if status == 429:
        wait = str(getattr(getattr(cause, "response", None), "headers", {}).get("retry-after", 30))
        return 429, f"Elevant is busy; try again in {wait} s", {"Retry-After": wait}
    if isinstance(error, TimeoutError):
        return 504, f"the draft took longer than {DRAFT_SECONDS} s; try again", {}
    return 503, "a service Elevant depends on is not answering; try again in a minute", {}


async def refuse(request: Request, error: Exception) -> JSONResponse:
    status, message, headers = failure(error)
    return JSONResponse({"detail": message}, status, headers)


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> AsyncIterator[None]:
    async with connect(SETTINGS) as services:
        if SETTINGS.env == "local" and isinstance(services.store, Store):
            await services.store.create_local()
        app.state.services = services
        yield


telemetry.configure(SETTINGS)
app = fastapi.FastAPI(title="Elevant", lifespan=lifespan, exception_handlers=dict.fromkeys(FAILURES, refuse))


def public(quote: Quote) -> dict[str, Any]:
    return quote.model_dump(mode="json", exclude=HIDDEN)


def sent(step: str | Quote) -> ServerSentEvent:
    if isinstance(step, str):
        return ServerSentEvent(event="status", data=step)
    return ServerSentEvent(event="quote", data=public(step))


async def stored(services: Services, quote_id: str) -> Quote:
    if (quote := await services.store.find(quote_id)) is None:
        raise HTTPException(404, "there is no such quote")
    return quote


async def within(steps: AsyncIterator[str | Quote], seconds: float) -> AsyncIterator[str | Quote]:
    deadline = asyncio.get_running_loop().time() + seconds
    while True:
        async with asyncio.timeout_at(deadline):
            step = await anext(steps, None)
        if step is None:
            return
        yield step


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/version")
async def version() -> dict[str, str]:
    return {"workflow": VERSION, "image": SETTINGS.image}


@app.get("/api/me")
async def me(request: Request) -> dict[str, Any]:
    name, roles = principal(request)
    return {"name": name, "roles": sorted(roles)}


@app.post("/api/quotes", response_class=EventSourceResponse)
async def upload(_: Estimator, pdf: Report, services: Wired) -> AsyncIterator[ServerSentEvent]:
    quote, began = new_quote(f"q-{hashlib.sha256(pdf).hexdigest()[:16]}"), time.monotonic()
    try:
        if found := await services.store.find(quote.id):
            yield sent(found)
            return
        async for step in within(start(services, quote, pdf), DRAFT_SECONDS):
            if isinstance(step, Quote):
                telemetry.event(
                    "quote_drafted", quote_id=quote.id, duration_ms=round((time.monotonic() - began) * 1000)
                )
            yield sent(step)
    except FAILURES as error:
        status, message = failure(error)[:2]
        if status == 429 or status >= 500:
            telemetry.event("quote_failed", quote_id=quote.id, status=status)
        yield ServerSentEvent(event="error", data={"status": status, "detail": message})


@app.get("/api/quotes")
async def quotes(_: Staff, services: Wired) -> list[dict[str, Any]]:
    return await services.store.summaries()


@app.get("/api/quotes/{quote_id}")
async def quote(quote_id: QuoteId, _: Staff, services: Wired) -> dict[str, Any]:
    return public(await stored(services, quote_id))


@app.post("/api/quotes/{quote_id}/review")
async def decide(quote_id: QuoteId, answer: Answer, by: Estimator, services: Wired) -> dict[str, Any]:
    quote, error = await resume(services, quote_id, Decision(by=by, edits=answer.edits, approve=answer.approve))
    if quote.state == "approved":
        telemetry.approved(quote)
    return {"quote": public(quote), "error": error}


@app.post("/api/quotes/{quote_id}/corrections")
async def corrections(quote_id: QuoteId, text: Text, _: Estimator, services: Wired) -> list[Edit]:
    quote = await stored(services, quote_id)
    return await agents.correct(services.chat, quote, text, load_catalogue(quote.catalogue))


@app.get("/api/quotes/{quote_id}/catalogue")
async def catalogue(quote_id: QuoteId, _: Staff, services: Wired) -> list[dict[str, Any]]:
    items = load_catalogue((await stored(services, quote_id)).catalogue).items.values()
    return [item.model_dump(mode="json", include={"code", "description", "unit", "unit_price"}) for item in items]


@app.get("/api/quotes/{quote_id}/document")
async def document(quote_id: QuoteId, _: Staff, services: Wired) -> Response:
    if (await stored(services, quote_id)).state != "approved":
        raise HTTPException(409, "only an approved quote has a document")
    name = f"{quote_id}.docx"
    data = await services.store.get("quotes", name)
    return Response(data, media_type=DOCX, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/quotes/{quote_id}/feedback", status_code=204)
async def feedback(quote_id: QuoteId, value: Rating, _: Estimator, services: Wired) -> None:
    await stored(services, quote_id)
    telemetry.event("feedback", quote_id=quote_id, value=value)


@app.delete("/api/quotes/{quote_id}", status_code=204)
async def delete(quote_id: QuoteId, _: Manager, services: Wired) -> None:
    await stored(services, quote_id)
    await forget(services, quote_id)
    telemetry.event("quote_deleted", quote_id=quote_id)

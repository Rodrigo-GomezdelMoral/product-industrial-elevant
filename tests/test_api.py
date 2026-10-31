import base64
import json
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import AsyncExitStack
from hashlib import sha256
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import httpx2
import openai
import pytest
from agent_framework import BaseChatClient, FunctionInvocationLayer, InMemoryCheckpointStorage
from agent_framework.exceptions import ChatClientException
from azure.core.exceptions import ResourceNotFoundError
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor

from app import agents, main, telemetry
from app.domain import Catalogue, DomainError, Quote
from app.extraction import OversizeError
from app.settings import Settings
from app.store import Store
from app.workflow import Services, connect

PDF = (Path(__file__).resolve().parent.parent / "data" / "reports" / "report-0134.pdf").read_bytes()
ID = f"q-{'0' * 16}"
EMULATORS = pytest.mark.skipif(not os.environ.get("ELEVANT_EMULATORS"), reason="needs Azurite and the Cosmos emulator")


def signed(*roles: str) -> dict[str, str]:
    principal = json.dumps({"claims": [{"typ": "roles", "val": role} for role in roles]})
    return {"X-MS-CLIENT-PRINCIPAL": base64.b64encode(principal.encode()).decode(), "X-MS-CLIENT-PRINCIPAL-NAME": "Ana"}


ESTIMATOR, MANAGER = signed("Quote.Estimator"), signed("Quote.Manager")


class Busy(FunctionInvocationLayer[Any], BaseChatClient[Any]):
    async def _inner_get_response(self, **kwargs: Any) -> Any:
        response = httpx2.Response(429, headers={"retry-after": "7"}, request=httpx2.Request("POST", "https://model"))
        raise ChatClientException("busy") from openai.RateLimitError("busy", response=response, body=None)


def sse(response: httpx.Response) -> list[tuple[str, Any]]:
    lines = [line.split(": ", 1)[1] for line in response.text.splitlines() if line.startswith(("event:", "data:"))]
    return [(kind, json.loads(data)) for kind, data in zip(lines[::2], lines[1::2], strict=True)]


@pytest.fixture
async def api(request: pytest.FixtureRequest, memory: Any, catalogue: Catalogue) -> AsyncIterator[httpx.AsyncClient]:
    async with AsyncExitStack() as stack:
        services = Services(memory, InMemoryCheckpointStorage(), agents.canned, agents.Double(catalogue))
        if getattr(request, "param", "memory") == "emulators":
            services = await stack.enter_async_context(connect(Settings(doubles=True)))
            await cast(Store, services.store).create_local()
        main.app.state.services, transport = services, httpx.ASGITransport(app=main.app)
        yield await stack.enter_async_context(httpx.AsyncClient(transport=transport, base_url="http://elevant"))


@pytest.fixture
def kpis() -> Iterator[InMemoryLogRecordExporter]:
    exporter, provider = InMemoryLogRecordExporter(), LoggerProvider()
    provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    telemetry.LOG.addHandler(handler := LoggingHandler(logger_provider=provider))
    yield exporter
    telemetry.LOG.removeHandler(handler)


async def walk(api: httpx.AsyncClient, pdf: bytes) -> dict[str, Any]:
    drafted = sse(await api.post("/api/quotes", content=pdf, headers=ESTIMATOR))
    assert drafted[:-1] == [("status", s) for s in ("Reading the report", "Matching 12 defects", "Pricing")]
    assert sse(await api.post("/api/quotes", content=pdf, headers=ESTIMATOR)) == drafted[-1:]
    path = f"/api/quotes/{drafted[-1][1]['id']}"
    assert (await api.get(f"{path}/document", headers=MANAGER)).status_code == 409
    refused = (await api.post(f"{path}/review", json={"approve": True}, headers=ESTIMATOR)).json()
    assert refused["quote"]["state"] == "review" and refused["error"].startswith("resolve every flag")
    flagged = [line for line in refused["quote"]["lines"] if line["flag"]]
    answer = {"edits": [{"action": "item", "line": n["number"], "code": n["candidates"][0]} for n in flagged]}
    approved = (await api.post(f"{path}/review", json=answer | {"approve": True}, headers=ESTIMATOR)).json()
    assert [event["by"] for event in approved["quote"]["events"]] == ["Ana"] * (len(answer["edits"]) + 1)
    assert (await api.post(f"{path}/review", json={}, headers=ESTIMATOR)).status_code == 409
    assert (await api.get(f"{path}/document", headers=MANAGER)).content.startswith(b"PK")
    return dict(approved["quote"])


async def test_only_signed_in_roles_and_readable_reports_get_in(api: httpx.AsyncClient, memory: Any) -> None:
    assert (await api.get("/healthz")).json() == {"status": "ok"}
    assert (await api.get("/api/version")).json() == {"workflow": "quote-v1", "image": "local"}
    me = (await api.get("/api/me", headers=signed("Quote.Estimator", "Other"))).json()
    assert me == {"name": "Ana", "roles": ["Quote.Estimator"]}
    calls = [("POST", "/api/quotes", {}, 401), ("GET", "/api/quotes", {"X-MS-CLIENT-PRINCIPAL": "?"}, 401)]
    calls += [("GET", "/api/me", {}, 401), ("GET", f"/api/quotes/{ID}/catalogue", signed(), 403)]
    calls += [("GET", "/api/quotes", signed(), 403), ("DELETE", f"/api/quotes/{ID}", ESTIMATOR, 403)]
    calls += [("POST", f"/api/quotes/{ID}/review", MANAGER, 403), ("GET", f"/api/quotes/{ID}", MANAGER, 404)]
    for method, path, headers, status in [*calls, ("GET", "/api/quotes/q-..%5Cx", MANAGER, 422)]:
        assert (await api.request(method, path, headers=headers)).status_code == status, path
    large = await api.post("/api/quotes", content=b"%PDF-" + bytes(10 * 2**20), headers=ESTIMATOR)
    foreign = await api.post("/api/quotes", content=b"PK\x03\x04", headers=ESTIMATOR)
    assert (large.status_code, foreign.status_code, foreign.json()) == (413, 422, {"detail": "the file is not a PDF"})
    main.app.state.services.read = AsyncMock(side_effect=OversizeError("the report is over 10 pages"))
    refused = sse(await api.post("/api/quotes", content=PDF, headers=ESTIMATOR))
    assert refused[-1] == ("error", {"status": 413, "detail": "the report is over 10 pages"})
    name = f"quote-v1-q-{sha256(PDF).hexdigest()[:16]}"
    checkpoints = await main.app.state.services.checkpoints.list_checkpoint_ids(workflow_name=name)
    assert memory.quotes == {} and memory.blobs == {} and checkpoints == []


@pytest.mark.parametrize("api", ["memory", pytest.param("emulators", marks=EMULATORS)], indirect=True)
async def test_each_request_resumes_a_fresh_workflow(api: httpx.AsyncClient, kpis: InMemoryLogRecordExporter) -> None:
    services: Services = main.app.state.services
    quote = await walk(api, PDF + uuid4().hex.encode())
    qid, listed = quote["id"], (await api.get("/api/quotes", headers=MANAGER)).json()
    assert {"id": qid, "state": "approved"}.items() <= listed[0].items() and "request_id" not in quote
    items = (await api.get(f"/api/quotes/{qid}/catalogue", headers=MANAGER)).json()
    assert len(items) == 123 and set(items[0]) == {"code", "description", "unit", "unit_price"}
    assert (await api.post(f"/api/quotes/{qid}/feedback", json={"value": "up"}, headers=ESTIMATOR)).status_code == 204
    if isinstance(services.store, Store):
        stale = await services.store.load(qid)
        await services.store.save(await services.store.load(qid))
        with pytest.raises(DomainError, match="changed while"):
            await services.store.save(stale)
    assert (await services.store.get("reports", f"{qid}.pdf")).startswith(b"%PDF-")
    assert (await api.delete(f"/api/quotes/{qid}", headers=MANAGER)).status_code == 204
    assert await services.store.find(qid) is None
    assert await services.checkpoints.list_checkpoint_ids(workflow_name=f"quote-v1-{qid}") == []
    with pytest.raises((KeyError, ResourceNotFoundError)):
        await services.store.get("reports", f"{qid}.pdf")
    events = [dict(record.log_record.attributes or {}) for record in kpis.get_finished_logs()]
    names = ["quote_drafted", *["line_reviewed"] * 12, "quote_approved", "feedback", "quote_deleted"]
    assert [event.pop("microsoft.custom_event.name") for event in events] == names
    assert [event["outcome"] for event in events[1:13]] == [line["outcome"] for line in quote["lines"]]
    keys = {key for event in events for key in event if not key.startswith("code.")}
    assert keys == {"quote_id", "duration_ms", "line", "outcome", "elapsed_s", "value"}


async def test_busy_and_slow_models(api: httpx.AsyncClient, drafted: Quote, monkeypatch: pytest.MonkeyPatch) -> None:
    services = main.app.state.services
    services.chat, services.store.quotes[ID] = Busy(), drafted.model_copy(update={"id": ID})
    busy = await api.post(f"/api/quotes/{ID}/corrections", json={"text": "line 4 is 3 units"}, headers=ESTIMATOR)
    assert (busy.status_code, busy.headers["retry-after"]) == (429, "7")
    waiting = {"status": 429, "detail": "Elevant is busy; try again in 7 s"}
    assert sse(await api.post("/api/quotes", content=PDF, headers=ESTIMATOR))[-1] == ("error", waiting)
    monkeypatch.setattr(main, "DRAFT_SECONDS", 0)
    late = {"status": 504, "detail": "the draft took longer than 0 s; try again"}
    assert sse(await api.post("/api/quotes", content=PDF, headers=ESTIMATOR))[-1] == ("error", late)

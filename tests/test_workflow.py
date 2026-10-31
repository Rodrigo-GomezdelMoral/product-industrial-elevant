import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from agent_framework import InMemoryCheckpointStorage

from app import agents
from app.domain import Catalogue, DomainError, Edit, Quote, new_quote
from app.extraction import RejectedFileError
from app.settings import Settings
from app.store import Store
from app.workflow import Decision, Services, connect, resume, start

PDF = Path(__file__).resolve().parent.parent / "data" / "reports" / "report-0134.pdf"


async def draft(services: Services, quote_id: str, pdf: bytes) -> tuple[list[str], Quote]:
    steps = [step async for step in start(services, new_quote(quote_id), pdf)]
    assert isinstance(steps[-1], Quote)
    return [str(step) for step in steps[:-1]], steps[-1]


async def review_and_approve(services: Services, quote_id: str) -> Quote:
    statuses, quote = await draft(services, quote_id, PDF.read_bytes())
    assert statuses == ["Reading the report", "Matching 12 defects", "Pricing"]
    assert quote.state == "review" and quote.request_id and quote.checkpoint_id
    refused, error = await resume(services, quote.id, Decision(by="estimator", approve=True))
    assert refused.state == "review" and error and error.startswith("resolve every flag")
    assert refused.request_id != quote.request_id
    edits = [Edit(action="item", line=line.number, code=line.candidates[0]) for line in refused.lines if line.flag]
    approved, error = await resume(services, quote.id, Decision(by="estimator", edits=edits, approve=True))
    assert error is None and approved.state == "approved" and approved.approved_by == "estimator"
    assert [event.by for event in approved.events] == ["estimator"] * (len(edits) + 1)
    return approved


async def test_a_quote_resumes_from_its_checkpoint_and_is_issued_once(catalogue: Catalogue, memory: Any) -> None:
    services = Services(memory, InMemoryCheckpointStorage(), agents.canned, agents.Double(catalogue))
    approved = await review_and_approve(services, "q-0134")
    with pytest.raises(DomainError, match="approved and can no longer change"):
        await resume(services, "q-0134", Decision(by="estimator", edits=[Edit(action="remove", line=1)]))
    assert memory.puts == ["reports/q-0134.pdf", "quotes/q-0134.docx"]
    assert memory.quotes["q-0134"] == approved


async def test_a_rejected_report_stores_nothing(catalogue: Catalogue, memory: Any) -> None:
    checkpoints = InMemoryCheckpointStorage()
    services = Services(memory, checkpoints, agents.canned, agents.Double(catalogue))
    with pytest.raises(RejectedFileError, match="not a PDF"):
        await draft(services, "q-0135", b"PK\x03\x04")
    assert memory.puts == [] and memory.quotes == {}
    assert await checkpoints.list_checkpoint_ids(workflow_name="quote-v1-q-0135") == []


@pytest.mark.skipif(not os.environ.get("ELEVANT_EMULATORS"), reason="needs Azurite and the Cosmos DB emulator")
async def test_quotes_and_checkpoints_persist_in_the_emulators() -> None:
    async with connect(Settings(doubles=True)) as services:
        assert isinstance(services.store, Store)
        await services.store.create_local()
        approved = await review_and_approve(services, f"q-{uuid4().hex[:8]}")
        stale = await services.store.load(approved.id)
        assert stale.model_dump() == approved.model_dump() and stale.etag
        assert (await services.store.get("quotes", f"{approved.id}.docx")).startswith(b"PK")
        await services.store.save(await services.store.load(approved.id))
        with pytest.raises(DomainError, match="changed while"):
            await services.store.save(stale)

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pytest
from agent_framework import BaseChatClient, ChatResponse, FunctionInvocationLayer, Message

from app.domain import Catalogue, Defect, Header, Match, Quote, draft, load_catalogue, new_quote


class Scripted(FunctionInvocationLayer[Any], BaseChatClient[Any]):
    """Answers with the given JSON, in order, and keeps every request: the instructions and the user message."""

    def __init__(self, *answers: str) -> None:
        super().__init__()
        self.answers, self.requests = list(answers), list[tuple[str, str]]()

    async def _inner_get_response(
        self, *, messages: Sequence[Message], stream: bool, options: Mapping[str, Any], **kwargs: Any
    ) -> ChatResponse[Any]:
        self.requests.append((options["instructions"], messages[-1].text))
        return ChatResponse(messages=[Message(role="assistant", contents=[self.answers.pop(0)])])


class Memory:
    def __init__(self) -> None:
        self.quotes: dict[str, Quote] = {}
        self.puts: list[str] = []

    async def load(self, quote_id: str) -> Quote:
        return self.quotes[quote_id]

    async def save(self, quote: Quote) -> None:
        self.quotes[quote.id] = quote

    async def put(self, container: str, name: str, data: bytes) -> None:
        self.puts.append(f"{container}/{name}")


def proposal(code: str | None, quantity: float = 1, confidence: float = 0.9, candidates: tuple[str, ...] = ()) -> Match:
    return Match(
        expanded="",
        category="",
        item_code=code,
        quantity=quantity,
        confidence=confidence,
        candidates=list(candidates),
        reason=None,
    )


@pytest.fixture
def match() -> Callable[..., Match]:
    return proposal


@pytest.fixture
def scripted() -> type[Scripted]:
    return Scripted


@pytest.fixture
def memory() -> Memory:
    return Memory()


@pytest.fixture
def catalogue() -> Catalogue:
    return load_catalogue()


@pytest.fixture
def drafted(catalogue: Catalogue) -> Quote:
    quote = new_quote("q-0001")
    quote.header = Header(lift_id="LFT-41732", location="6 Mill Lane & Chapel Row, Northgate")
    quote.header.inspection_date, quote.header.technician = "2026-09-29", "Irene Vidal"
    proposals = [
        (Defect(page=1, row=1, text="Technician time"), proposal("LAB-101", 2.5)),
        (Defect(page=1, row=2, text="ALARM PUSH BTN BRKN"), proposal("SAF-104")),
        (
            Defect(page=2, row=1, text="Fuse not working"),
            proposal(None, 4, candidates=("ELE-105", "ELE-106", "MAC-999")),
        ),
        (Defect(page=2, row=2, text="Landing door roller, 60 mm worn"), proposal("DOR-102", 2, confidence=0.4)),
    ]
    return draft(quote, proposals, catalogue)

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from agent_framework import (
    Agent,
    BaseChatClient,
    ChatResponse,
    FunctionInvocationLayer,
    Message,
    SupportsChatGetResponse,
)
from agent_framework.exceptions import ChatClientException
from pydantic import BaseModel, ValidationError
from rapidfuzz import fuzz, process

from app.domain import Catalogue, Defect, DomainError, Edit, Match, Quote, review
from app.extraction import Layout, check

PROMPTS = Path(__file__).resolve().parent / "prompts"
CANNED = PROMPTS.parent.parent / "eval" / "datasets" / "extracted" / "report-0134.json"
MATCH_TOKENS, TOKENS_PER_DEFECT, CORRECT_TOKENS = 1500, 150, 2000
LINE_FIELDS = {"number", "expanded", "item_code", "quantity"}


class DefectMatch(Match):
    defect: int


class MatchResult(BaseModel):
    matches: list[DefectMatch]


class LineEdit(BaseModel):
    action: Literal["item", "quantity", "remove", "add"]
    line: int | None
    code: str | None
    quantity: float | None


class LineEdits(BaseModel):
    edits: list[LineEdit]


async def ask(
    client: SupportsChatGetResponse[Any], name: str, catalogue: Catalogue, schema: type, tokens: int, payload: str
) -> Any:
    items = "\n".join(f"{i.code} | {i.category} | {i.description} | {i.unit}" for i in catalogue.items.values())
    prompt = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    instructions = f"{prompt}\n## Catalogue {catalogue.version.name}\n\ncode | category | description | unit\n{items}\n"
    options = {"response_format": schema, "reasoning": {"effort": "low"}, "max_tokens": tokens, "store": False}
    try:
        return (await Agent(client, instructions, name=name, default_options=options).run(payload)).value
    except ValidationError:
        return None
    except ChatClientException as error:
        if isinstance(error.__cause__, ValidationError):
            return None
        raise


async def match(client: SupportsChatGetResponse[Any], defects: list[Defect], catalogue: Catalogue) -> list[Match]:
    rows = json.dumps([{"defect": number, "text": defect.text} for number, defect in enumerate(defects, 1)])
    tokens = MATCH_TOKENS + TOKENS_PER_DEFECT * len(defects)
    answer = await ask(client, "matcher", catalogue, MatchResult, tokens, rows)
    found = {match.defect: match for match in answer.matches} if answer else {}
    unanswered = Match(
        expanded="",
        category="",
        item_code=None,
        quantity=1,
        confidence=0,
        candidates=[],
        reason="the matcher gave no usable answer for this defect",
    )
    return [found.get(number, unanswered) for number in range(1, len(defects) + 1)]


async def correct(client: SupportsChatGetResponse[Any], quote: Quote, text: str, catalogue: Catalogue) -> list[Edit]:
    lines = [line.model_dump(mode="json", include=LINE_FIELDS) for line in quote.lines if line.outcome != "removed"]
    request = json.dumps({"lines": lines, "request": text})
    answer = await ask(client, "corrector", catalogue, LineEdits, CORRECT_TOKENS, request)
    edits = [Edit.model_validate(edit.model_dump()) for edit in answer.edits] if answer else []
    if not edits:
        raise DomainError("no change found; name the line and the item or quantity it should have")
    review(quote, edits, "corrector", catalogue)
    return edits


class Double(FunctionInvocationLayer[Any], BaseChatClient[Any]):
    """Stands in for gpt-5-mini under ELEVANT_DOUBLES: the closest catalogue description wins, no corrections."""

    def __init__(self, catalogue: Catalogue) -> None:
        super().__init__()
        self.descriptions = {item.code: item.description for item in catalogue.items.values()}

    def guess(self, number: int, text: str) -> DefectMatch:
        found = process.extract(text, self.descriptions, scorer=fuzz.token_set_ratio, limit=3)
        codes = [code for _, _, code in found]
        best = found[0][1] / 100
        return DefectMatch(
            defect=number,
            expanded=text,
            category="",
            item_code=codes[0],
            quantity=1,
            confidence=best,
            candidates=codes,
            reason=None,
        )

    async def _inner_get_response(
        self, *, messages: Sequence[Message], stream: bool, options: Mapping[str, Any], **kwargs: Any
    ) -> ChatResponse[Any]:
        answer: BaseModel = LineEdits(edits=[])
        if options.get("response_format") is MatchResult:
            rows = json.loads(messages[-1].text)
            answer = MatchResult(matches=[self.guess(row["defect"], row["text"]) for row in rows])
        return ChatResponse(messages=[Message(role="assistant", contents=[answer.model_dump_json()])])


async def canned(pdf: bytes) -> Layout:
    check(pdf)
    return Layout.model_validate_json(CANNED.read_text(encoding="utf-8"))

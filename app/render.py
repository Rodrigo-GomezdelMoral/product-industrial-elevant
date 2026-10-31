import re
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate

from app.domain import HEADER_FIELDS, REFERENCE, DomainError, Line, Quote, reference

NOT_XML = re.compile("[^\t\n\r -퟿-�\U00010000-\U0010ffff]")


def euros(value: Decimal | None) -> str:
    return f"€{value or 0:,.2f}"


def plain(value: Decimal) -> str:
    return f"{value.normalize():f}"


def row(number: int, line: Line, catalogue: str) -> dict[str, str]:
    source = f"report page {line.defect.page}, row {line.defect.row}" if line.defect else "added in review"
    return {
        "number": str(number),
        "description": line.description,
        "trace": f"{line.item_code} · {catalogue} · {source}",
        "quantity": plain(line.quantity) + ("" if line.unit == "unit" else f" {line.unit}"),
        "unit_price": euros(line.unit_price),
        "amount": euros(line.amount),
    }


def context(quote: Quote) -> dict[str, Any]:
    kept = [line for line in quote.lines if line.outcome != "removed"]
    return {
        "quote": quote.id,
        "approved_on": f"{quote.approved_at:%d %B %Y}",
        "header": {name: NOT_XML.sub("", getattr(quote.header, name) or "") for name in HEADER_FIELDS},
        "lines": [row(number, line, quote.catalogue.name) for number, line in enumerate(kept, 1)],
        "subtotal": euros(quote.subtotal),
        "vat_rate": f"{plain(quote.vat_rate * 100)} %",
        "vat": euros(quote.vat),
        "total": euros(quote.total),
        "catalogue": quote.catalogue.name,
        "catalogue_sha256": quote.catalogue.sha256[:12],
        "template": quote.template.name,
    }


def render(quote: Quote, folder: Path = REFERENCE) -> bytes:
    if quote.state != "approved":
        raise DomainError("only an approved quote has a document")
    data, _ = reference("quote-template", quote.template, folder)
    document = DocxTemplate(BytesIO(data))
    document.render(context(quote), autoescape=True)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()

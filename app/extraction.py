import re
from datetime import datetime

from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest,
    AnalyzeResult,
    DocumentAnalysisFeature,
    DocumentContentFormat,
)
from azure.core.exceptions import HttpResponseError
from pydantic import BaseModel
from rapidfuzz import fuzz, process

from app.domain import Defect, DomainError, Flag, Header, HeaderField

MAX_BYTES, MAX_PAGES = 10 * 1024 * 1024, 10
MIN_CONFIDENCE = 0.8
SYNONYMS: dict[HeaderField, tuple[str, ...]] = {
    "lift_id": ("lift id", "lift no", "unit no"),
    "location": ("location", "address", "site address"),
    "inspection_date": ("inspection date", "date", "date of visit"),
    "technician": ("technician", "inspector", "engineer"),
}
LABELS = {synonym: field for field, synonyms in SYNONYMS.items() for synonym in synonyms}
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d %b %Y")
ROW_REFERENCE = re.compile(r"[A-Z]{0,2}-?\d{1,3}\.?")


class RejectedFileError(DomainError):
    """A file Elevant does not read; nothing about it is stored."""


class Pair(BaseModel):
    key: str
    value: str | None
    confidence: float


class Table(BaseModel):
    header: int
    rows: list[list[str]]
    pages: list[int]


class Layout(BaseModel):
    pages: int
    pairs: list[Pair]
    tables: list[Table]


class Report(BaseModel):
    header: Header
    flags: dict[HeaderField, Flag]
    defects: list[Defect]


def check(pdf: bytes) -> None:
    if not pdf.startswith(b"%PDF-"):
        raise RejectedFileError("the file is not a PDF")
    if len(pdf) > MAX_BYTES:
        raise RejectedFileError("the file is over 10 MB")


def layout(result: AnalyzeResult) -> Layout:
    pairs = [
        Pair(key=pair.key.content, value=pair.value.content if pair.value else None, confidence=pair.confidence)
        for pair in result.key_value_pairs or []
    ]
    tables = []
    for table in result.tables or []:
        rows, pages = [[""] * table.column_count for _ in range(table.row_count)], [1] * table.row_count
        for cell in table.cells:
            rows[cell.row_index][cell.column_index] = cell.content
            if cell.bounding_regions:
                pages[cell.row_index] = cell.bounding_regions[0].page_number
        header = len({cell.row_index for cell in table.cells if cell.kind == "columnHeader"})
        tables.append(Table(header=header, rows=rows, pages=pages))
    return Layout(pages=len(result.pages), pairs=pairs, tables=tables)


async def analyze(client: DocumentIntelligenceClient, pdf: bytes) -> Layout:
    check(pdf)
    try:
        poller = await client.begin_analyze_document(
            "prebuilt-layout",
            AnalyzeDocumentRequest(bytes_source=pdf),
            pages=f"1-{MAX_PAGES + 1}",
            features=[DocumentAnalysisFeature.KEY_VALUE_PAIRS],
            output_content_format=DocumentContentFormat.MARKDOWN,
        )
        found = layout(await poller.result())
    except HttpResponseError as error:
        if (error.error.innererror.get("code", "") if error.error else "").startswith("InvalidContent"):
            raise RejectedFileError("the PDF could not be read") from error
        raise
    if found.pages > MAX_PAGES:
        raise RejectedFileError("the report is over 10 pages")
    return found


def label(text: str) -> HeaderField | None:
    found = process.extractOne(text.strip(" :.").lower(), LABELS.keys(), scorer=fuzz.ratio, score_cutoff=85)
    return LABELS[found[0]] if found else None


def labelled(cells: list[str]) -> bool:
    return any(label(cell) for cell in cells[::2])


def iso_date(text: str) -> str | None:
    for pattern in DATE_FORMATS:
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def read_header(pairs: list[Pair]) -> tuple[Header, dict[HeaderField, Flag]]:
    header, flags, seen = Header(), dict[HeaderField, Flag](), set[HeaderField]()
    for pair in pairs:
        keys, values = pair.key.splitlines() or [""], (pair.value or "").strip().splitlines() or [""]
        field, value = label(keys[0]), values[0].strip()
        if field is None or field in seen or len(values) > len(keys):
            continue
        seen.add(field)
        normal = iso_date(value) if field == "inspection_date" else value
        setattr(header, field, normal or value or None)
        if value and (normal is None or pair.confidence < MIN_CONFIDENCE):
            flags[field] = "low_confidence"
    return header, flags


def read_defects(tables: list[Table]) -> list[Defect]:
    defects: list[Defect] = []
    for table in tables:
        for page, cells in zip(table.pages[table.header :], table.rows[table.header :], strict=True):
            if labelled(cells):
                continue
            kept = cells[1:] if cells and ROW_REFERENCE.fullmatch(cells[0].strip()) else cells
            text = " · ".join(cell.strip() for cell in kept if cell.strip())
            if text:
                row = sum(defect.page == page for defect in defects) + 1
                defects.append(Defect(page=page, row=row, text=text))
    return defects


def read(found: Layout) -> Report:
    columns = {
        cell for table in found.tables for row in table.rows[: table.header] if not labelled(row) for cell in row
    }
    header, flags = read_header([pair for pair in found.pairs if pair.key not in columns])
    return Report(header=header, flags=flags, defects=read_defects(found.tables))

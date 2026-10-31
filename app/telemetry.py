import logging

from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry import configure_azure_monitor

from app.domain import Quote
from app.settings import Settings

LOG = logging.getLogger("elevant")


def configure(settings: Settings) -> None:
    LOG.setLevel(logging.INFO)
    if settings.appinsights:
        credential = DefaultAzureCredential()
        configure_azure_monitor(connection_string=settings.appinsights, credential=credential, logger_name=LOG.name)


def event(name: str, **fields: str | int) -> None:
    LOG.info(name, extra={"microsoft.custom_event.name": name, **fields})


def approved(quote: Quote) -> None:
    for line in quote.lines:
        event("line_reviewed", quote_id=quote.id, line=line.number, outcome=line.outcome)
    elapsed = (quote.approved_at or quote.created_at) - quote.created_at
    event("quote_approved", quote_id=quote.id, elapsed_s=round(elapsed.total_seconds()))

import base64
from contextlib import suppress
from typing import Any

from agent_framework_azure_cosmos import CosmosCheckpointStorage
from azure.core import MatchConditions
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.cosmos import PartitionKey
from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosAccessConditionFailedError
from azure.storage.blob.aio import BlobServiceClient

from app.domain import DomainError, Quote
from app.settings import Settings

EMULATOR_KEY = base64.b64encode(b"the vNext emulator does not check keys").decode()
DEVELOPMENT_STORAGE = "UseDevelopmentStorage=true"
CONTAINERS = {"quotes": "/id", "checkpoints": "/workflow_name"}
BLOBS = {"reports": ".pdf", "quotes": ".docx"}
LISTING = "SELECT TOP 100 c.id, c.state, c.header.lift_id, c.created_at FROM c ORDER BY c.created_at DESC"


class Memory:
    """Keeps quotes and documents in memory, for the evaluation and the tests."""

    def __init__(self) -> None:
        self.quotes: dict[str, Quote] = {}
        self.blobs: dict[str, bytes] = {}

    async def find(self, quote_id: str) -> Quote | None:
        return self.quotes.get(quote_id)

    async def load(self, quote_id: str) -> Quote:
        return self.quotes[quote_id]

    async def save(self, quote: Quote) -> None:
        self.quotes[quote.id] = quote

    async def put(self, container: str, name: str, data: bytes) -> None:
        self.blobs[f"{container}/{name}"] = data

    async def get(self, container: str, name: str) -> bytes:
        return self.blobs[f"{container}/{name}"]

    async def summaries(self) -> list[dict[str, Any]]:
        return [{"id": quote.id, "state": quote.state} for quote in self.quotes.values()]

    async def delete(self, quote_id: str) -> None:
        for container, suffix in BLOBS.items():
            self.blobs.pop(f"{container}/{quote_id}{suffix}", None)
        del self.quotes[quote_id]


class Store:
    def __init__(self, settings: Settings, credential: AsyncTokenCredential) -> None:
        local = settings.env == "local"
        self.cosmos = CosmosClient(settings.cosmos_endpoint, EMULATOR_KEY if local else credential)
        self.database = self.cosmos.get_database_client(settings.database)
        self.quotes = self.database.get_container_client("quotes")
        checkpoints = self.database.get_container_client("checkpoints")
        self.checkpoints = CosmosCheckpointStorage(container_client=checkpoints)
        self.blobs = (
            BlobServiceClient.from_connection_string(DEVELOPMENT_STORAGE)
            if local
            else BlobServiceClient(settings.blob_endpoint, credential)
        )

    async def create_local(self) -> None:
        database = await self.cosmos.create_database_if_not_exists(self.database.id)
        for name, key in CONTAINERS.items():
            await database.create_container_if_not_exists(name, PartitionKey(path=key))
        for name in BLOBS:
            container = self.blobs.get_container_client(name)
            if not await container.exists():
                await container.create_container()

    async def save(self, quote: Quote) -> None:
        condition = MatchConditions.IfNotModified if quote.etag else None
        try:
            await self.quotes.upsert_item(quote.model_dump(mode="json"), etag=quote.etag, match_condition=condition)
        except CosmosAccessConditionFailedError as error:
            raise DomainError("the quote changed while this answer was applied; open it again") from error

    async def load(self, quote_id: str) -> Quote:
        return Quote.model_validate(await self.quotes.read_item(quote_id, partition_key=quote_id))

    async def find(self, quote_id: str) -> Quote | None:
        try:
            return await self.load(quote_id)
        except ResourceNotFoundError:
            return None

    async def summaries(self) -> list[dict[str, Any]]:
        return [item async for item in self.quotes.query_items(LISTING)]

    async def delete(self, quote_id: str) -> None:
        for container, suffix in BLOBS.items():
            with suppress(ResourceNotFoundError):
                await self.blobs.get_blob_client(container, f"{quote_id}{suffix}").delete_blob()
        await self.quotes.delete_item(quote_id, partition_key=quote_id)

    async def put(self, container: str, name: str, data: bytes) -> None:
        await self.blobs.get_blob_client(container, name).upload_blob(data, overwrite=True)

    async def get(self, container: str, name: str) -> bytes:
        download = await self.blobs.get_blob_client(container, name).download_blob()
        return await download.readall()

    async def close(self) -> None:
        await self.cosmos.close()
        await self.blobs.close()

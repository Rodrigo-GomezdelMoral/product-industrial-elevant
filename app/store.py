import base64

from agent_framework_azure_cosmos import CosmosCheckpointStorage
from azure.core import MatchConditions
from azure.core.credentials_async import AsyncTokenCredential
from azure.cosmos import PartitionKey
from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosAccessConditionFailedError
from azure.storage.blob.aio import BlobServiceClient

from app.domain import DomainError, Quote
from app.settings import Settings

EMULATOR_KEY = base64.b64encode(b"the vNext emulator does not check keys").decode()
DEVELOPMENT_STORAGE = "UseDevelopmentStorage=true"
CONTAINERS = {"quotes": "/id", "checkpoints": "/workflow_name"}
BLOB_CONTAINERS = ("reports", "quotes")


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
        for name in BLOB_CONTAINERS:
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

    async def put(self, container: str, name: str, data: bytes) -> None:
        await self.blobs.get_blob_client(container, name).upload_blob(data, overwrite=True)

    async def get(self, container: str, name: str) -> bytes:
        download = await self.blobs.get_blob_client(container, name).download_blob()
        return await download.readall()

    async def close(self) -> None:
        await self.cosmos.close()
        await self.blobs.close()

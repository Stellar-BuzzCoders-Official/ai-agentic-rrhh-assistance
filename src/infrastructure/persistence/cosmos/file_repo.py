import logging
from typing import Optional
from src.application.ports.outbound import FileRepositoryPort
from src.domain.entities import FileMetadata
from src.infrastructure.persistence.cosmos.client import CosmosDBManager
from src.config.settings import settings

logger = logging.getLogger(__name__)


class CosmosFileRepository(FileRepositoryPort):
    def __init__(self, manager: CosmosDBManager | None = None):
        self.manager = manager or CosmosDBManager.get_instance()
        self.container_name = settings.COSMOS_FILES_CONTAINER

    async def save_file_metadata(self, metadata: FileMetadata) -> FileMetadata:
        container = self.manager.get_container(self.container_name)
        doc = metadata.model_dump(by_alias=True)
        doc["id"] = metadata.id
        doc["ownerId"] = metadata.ownerId
        if doc.get("ttl") is None:
            doc.pop("ttl", None)
        container.upsert_item(doc)
        return metadata

    async def get_file_metadata(self, file_id: str) -> Optional[FileMetadata]:
        container = self.manager.get_container(self.container_name)
        query = "SELECT * FROM c WHERE c.id = @fileId"
        parameters = [{"name": "@fileId", "value": file_id}]
        items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        if items:
            return FileMetadata(**items[0])
        return None

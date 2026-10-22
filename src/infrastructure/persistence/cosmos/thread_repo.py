import logging
from typing import Optional, List
from src.application.ports.outbound import ThreadRepositoryPort
from src.domain.entities import Thread
from src.infrastructure.persistence.cosmos.client import CosmosDBManager
from src.config.settings import settings

logger = logging.getLogger(__name__)


class CosmosThreadRepository(ThreadRepositoryPort):
    def __init__(self, manager: CosmosDBManager | None = None):
        self.manager = manager or CosmosDBManager.get_instance()
        self.container_name = settings.COSMOS_THREADS_CONTAINER

    async def save_thread(self, thread: Thread) -> Thread:
        container = self.manager.get_container(self.container_name)
        doc = thread.model_dump(by_alias=True)
        doc["id"] = thread.id
        doc["userId"] = thread.userId
        if doc.get("ttl") is None:
            doc.pop("ttl", None)
        container.upsert_item(doc)
        return thread

    async def get_thread(self, thread_id: str) -> Optional[Thread]:
        container = self.manager.get_container(self.container_name)
        # Consulta por ID en todas las particiones o query simple
        query = "SELECT * FROM c WHERE c.id = @threadId"
        parameters = [{"name": "@threadId", "value": thread_id}]
        items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        if items:
            return Thread(**items[0])
        return None

    async def list_threads_by_user(self, user_id: str) -> List[Thread]:
        container = self.manager.get_container(self.container_name)
        query = "SELECT * FROM c WHERE c.userId = @userId ORDER BY c.updatedAt DESC"
        parameters = [{"name": "@userId", "value": user_id}]
        try:
            items = list(container.query_items(query=query, parameters=parameters, partition_key=user_id))
        except Exception:
            # Fallback sin ordenamiento si no hay índice compuesto
            query_simple = "SELECT * FROM c WHERE c.userId = @userId"
            items = list(container.query_items(query=query_simple, parameters=parameters, partition_key=user_id))
            items.sort(key=lambda x: x.get("updatedAt", ""), reverse=True)

        return [Thread(**item) for item in items]

    async def delete_thread(self, thread_id: str) -> bool:
        thread = await self.get_thread(thread_id)
        if not thread:
            return False
        container = self.manager.get_container(self.container_name)
        try:
            container.delete_item(item=thread_id, partition_key=thread.userId)
            return True
        except Exception as e:
            logger.error("Error al borrar thread de Cosmos DB: %s", str(e))
            return False

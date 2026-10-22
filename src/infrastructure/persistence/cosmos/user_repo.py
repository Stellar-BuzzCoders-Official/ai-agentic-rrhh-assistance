import logging
from typing import Optional
from src.application.ports.outbound import UserRepositoryPort
from src.domain.entities import User
from src.infrastructure.persistence.cosmos.client import CosmosDBManager
from src.config.settings import settings

logger = logging.getLogger(__name__)


class CosmosUserRepository(UserRepositoryPort):
    def __init__(self, manager: CosmosDBManager | None = None):
        self.manager = manager or CosmosDBManager.get_instance()
        self.container_name = settings.COSMOS_USERS_CONTAINER

    async def save_user(self, user: User) -> User:
        container = self.manager.get_container(self.container_name)
        doc = user.model_dump(by_alias=True)
        doc["id"] = user.id
        if doc.get("ttl") is None:
            doc.pop("ttl", None)
        container.upsert_item(doc)
        return user

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        container = self.manager.get_container(self.container_name)
        try:
            item = container.read_item(item=user_id, partition_key=user_id)
            return User(**item)
        except Exception:
            return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        container = self.manager.get_container(self.container_name)
        query = "SELECT * FROM c WHERE StringEquals(c.email, @email, true)"
        parameters = [{"name": "@email", "value": email}]
        items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        if items:
            return User(**items[0])
        return None

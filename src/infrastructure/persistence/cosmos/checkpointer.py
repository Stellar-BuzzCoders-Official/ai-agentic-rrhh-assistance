import logging
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from src.application.ports.outbound import CheckpointerProviderPort
from src.infrastructure.persistence.cosmos.client import CosmosDBManager
from src.config.settings import settings

logger = logging.getLogger(__name__)


class CosmosCheckpointerProvider(CheckpointerProviderPort):
    def __init__(self, manager: CosmosDBManager | None = None):
        self.manager = manager or CosmosDBManager.get_instance()
        self._checkpointer: BaseCheckpointSaver | None = None

    def get_checkpointer(self) -> BaseCheckpointSaver:
        if self._checkpointer is not None:
            return self._checkpointer

        if not self.manager.client or not self.manager.db:
            logger.warning("Cosmos DB no conectado. Usando MemorySaver de respaldo para el checkpointer.")
            self._checkpointer = MemorySaver()
            return self._checkpointer

        try:
            from langchain_azure_cosmosdb import CosmosDBSaverSync
            self._checkpointer = CosmosDBSaverSync(
                database_name=self.manager.database_name,
                container_name=settings.COSMOS_CHECKPOINTS_CONTAINER,
                endpoint=self.manager.endpoint,
                key=self.manager.key,
            )
            logger.info("CosmosDBSaverSync de LangGraph inicializado con éxito.")
            return self._checkpointer
        except Exception as e:
            logger.error("Error inicializando CosmosDBSaverSync: %s. Usando MemorySaver.", str(e))
            self._checkpointer = MemorySaver()
            return self._checkpointer

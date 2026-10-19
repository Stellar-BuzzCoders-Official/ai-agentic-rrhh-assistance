import logging
from azure.cosmos import CosmosClient, PartitionKey
from src.config.settings import settings

logger = logging.getLogger(__name__)


class CosmosDBManager:
    _instance = None

    def __init__(
        self,
        endpoint: str | None = None,
        key: str | None = None,
        connection_string: str | None = None,
        database_name: str | None = None,
    ):
        self.endpoint = endpoint or settings.COSMOS_ENDPOINT
        self.key = key or settings.COSMOS_KEY
        self.connection_string = connection_string or settings.COSMOS_CONNECTION_STRING
        self.database_name = database_name or settings.COSMOS_DATABASE_NAME
        self.client: CosmosClient | None = None
        self.db = None

        if self.connection_string:
            self.client = CosmosClient.from_connection_string(self.connection_string)
        elif self.endpoint and self.key:
            self.client = CosmosClient(url=self.endpoint, credential=self.key)
        else:
            logger.warning("Azure Cosmos DB NoSQL no tiene credenciales configuradas.")

        if self.client:
            self._init_database_and_containers()

    @classmethod
    def get_instance(cls) -> "CosmosDBManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_database_and_containers(self):
        try:
            logger.info("Inicializando base de datos Cosmos DB: %s", self.database_name)
            self.db = self.client.create_database_if_not_exists(id=self.database_name)

            # 1. Checkpoints para LangGraph (clave requerida por CosmosDBSaver de langchain-azure-cosmosdb: /partition_key)
            self.db.create_container_if_not_exists(
                id=settings.COSMOS_CHECKPOINTS_CONTAINER,
                partition_key=PartitionKey(path="/partition_key")
            )

            # 2. Threads (metadatos de conversación por usuario)
            self.db.create_container_if_not_exists(
                id=settings.COSMOS_THREADS_CONTAINER,
                partition_key=PartitionKey(path="/userId")
            )

            # 3. Users
            self.db.create_container_if_not_exists(
                id=settings.COSMOS_USERS_CONTAINER,
                partition_key=PartitionKey(path="/id")
            )

            # 4. Files
            self.db.create_container_if_not_exists(
                id=settings.COSMOS_FILES_CONTAINER,
                partition_key=PartitionKey(path="/ownerId")
            )

            # 5. Candidates (Talent Pool con partición por reclutador y política vectorial)
            vector_embedding_policy = {
                "vectorEmbeddings": [
                    {
                        "path": "/embedding",
                        "dataType": "float32",
                        "distanceFunction": "cosine",
                        "dimensions": settings.EMBEDDING_DIMENSIONS,
                    }
                ]
            }
            indexing_policy = {
                "indexingMode": "consistent",
                "includedPaths": [{"path": "/*"}],
                "excludedPaths": [{"path": '/"_etag"/?'}],
                "vectorIndexes": [{"path": "/embedding", "type": "diskANN"}],
            }

            try:
                self.db.create_container_if_not_exists(
                    id=settings.COSMOS_CANDIDATES_CONTAINER,
                    partition_key=PartitionKey(path="/recruiterId"),
                    vector_embedding_policy=vector_embedding_policy,
                    indexing_policy=indexing_policy,
                )
            except Exception as e_vec:
                logger.warning("No se pudo aplicar política vectorial directamente (puede requerir activación de feature preview en la cuenta de Cosmos): %s. Intentando contenedor básico.", str(e_vec))
                self.db.create_container_if_not_exists(
                    id=settings.COSMOS_CANDIDATES_CONTAINER,
                    partition_key=PartitionKey(path="/recruiterId")
                )

            logger.info("Contenedores de Cosmos DB inicializados con éxito.")
        except Exception as e:
            logger.error("Error al inicializar base de datos Cosmos DB: %s", str(e))

    def get_container(self, container_name: str):
        if not self.db:
            raise RuntimeError("Cosmos DB no está conectado.")
        return self.db.get_container_client(container_name)

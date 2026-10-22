import logging
from typing import Tuple
from src.config.settings import settings
from src.application.ports.outbound import (
    ChatModelProviderPort,
    EmbeddingsProviderPort,
    DocumentExtractorPort,
    FileStoragePort,
    CandidateRepositoryPort,
    ThreadRepositoryPort,
    UserRepositoryPort,
    FileRepositoryPort,
    CheckpointerProviderPort,
    ContentSafetyPort,
    TokenVerifierPort,
)

logger = logging.getLogger(__name__)


class Container:
    _instance = None

    def __init__(self):
        # 1. LLM & Embeddings
        if settings.LLM_PROVIDER == "azure_openai":
            from src.infrastructure.llm.azure_openai import AzureOpenAIProvider
            self.llm_provider: ChatModelProviderPort = AzureOpenAIProvider()
        elif settings.LLM_PROVIDER == "gemini":
            from src.infrastructure.llm.gemini import GeminiProvider
            self.llm_provider = GeminiProvider()
        elif settings.LLM_PROVIDER == "ollama":
            from src.infrastructure.llm.ollama import OllamaProvider
            self.llm_provider = OllamaProvider()
        else:
            raise ValueError(f"Proveedor LLM desconocido: {settings.LLM_PROVIDER}")

        # Judge LLM (puede ser el mismo u otro deployment/modelo)
        if settings.JUDGE_LLM_PROVIDER == "azure_openai":
            from src.infrastructure.llm.azure_openai import AzureOpenAIProvider
            self.judge_llm_provider: ChatModelProviderPort = AzureOpenAIProvider(
                deployment=settings.AZURE_OPENAI_JUDGE_DEPLOYMENT or settings.AZURE_OPENAI_DEPLOYMENT
            )
        elif settings.JUDGE_LLM_PROVIDER == "gemini":
            from src.infrastructure.llm.gemini import GeminiProvider
            self.judge_llm_provider = GeminiProvider()
        else:
            self.judge_llm_provider = self.llm_provider

        # Embeddings
        if settings.EMBEDDING_PROVIDER == "azure_openai":
            from src.infrastructure.llm.azure_openai import AzureOpenAIProvider
            self.embeddings_provider: EmbeddingsProviderPort = AzureOpenAIProvider()
        elif settings.EMBEDDING_PROVIDER == "gemini":
            from src.infrastructure.llm.gemini import GeminiProvider
            self.embeddings_provider = GeminiProvider()
        elif settings.EMBEDDING_PROVIDER == "ollama":
            from src.infrastructure.llm.ollama import OllamaProvider
            self.embeddings_provider = OllamaProvider()
        else:
            from src.infrastructure.llm.azure_openai import AzureOpenAIProvider
            self.embeddings_provider = AzureOpenAIProvider()

        # 2. Extracción de Documentos
        if settings.EXTRACTOR_PROVIDER == "document_intelligence":
            from src.infrastructure.extraction.document_intelligence import AzureDocumentIntelligenceExtractor
            self.document_extractor: DocumentExtractorPort = AzureDocumentIntelligenceExtractor()
        else:
            from src.infrastructure.extraction.legacy_local import LocalDocumentExtractor
            self.document_extractor = LocalDocumentExtractor()

        # 3. Almacenamiento de Archivos
        if settings.STORAGE_PROVIDER == "blob":
            from src.infrastructure.storage.azure_blob import AzureBlobStorageAdapter
            self.file_storage: FileStoragePort = AzureBlobStorageAdapter()
        elif settings.STORAGE_PROVIDER == "minio":
            from src.infrastructure.storage.minio_legacy import MinioLegacyStorageAdapter
            self.file_storage = MinioLegacyStorageAdapter()
        else:
            from src.infrastructure.storage.memory_storage import MemoryStorageAdapter
            self.file_storage = MemoryStorageAdapter.get_instance()

        # 4. Persistencia & Repositorios
        has_cosmos_config = bool(settings.COSMOS_CONNECTION_STRING or (settings.COSMOS_ENDPOINT and settings.COSMOS_KEY))
        if settings.PERSISTENCE_PROVIDER == "cosmos" and has_cosmos_config:
            from src.infrastructure.persistence.cosmos.client import CosmosDBManager
            from src.infrastructure.persistence.cosmos.candidate_repo import CosmosCandidateRepository
            from src.infrastructure.persistence.cosmos.thread_repo import CosmosThreadRepository
            from src.infrastructure.persistence.cosmos.user_repo import CosmosUserRepository
            from src.infrastructure.persistence.cosmos.file_repo import CosmosFileRepository
            from src.infrastructure.persistence.cosmos.checkpointer import CosmosCheckpointerProvider

            manager = CosmosDBManager.get_instance()
            self.candidate_repo: CandidateRepositoryPort = CosmosCandidateRepository(manager)
            self.thread_repo: ThreadRepositoryPort = CosmosThreadRepository(manager)
            self.user_repo: UserRepositoryPort = CosmosUserRepository(manager)
            self.file_repo: FileRepositoryPort = CosmosFileRepository(manager)
            self.checkpointer_provider: CheckpointerProviderPort = CosmosCheckpointerProvider(manager)
        else:
            if settings.PERSISTENCE_PROVIDER == "cosmos":
                logger.warning("PERSISTENCE_PROVIDER='cosmos' seleccionado pero sin credenciales configuradas. Activando adaptadores en memoria de desarrollo.")
            from src.infrastructure.persistence.memory.memory_repos import (
                MemoryCandidateRepository,
                MemoryThreadRepository,
                MemoryUserRepository,
                MemoryFileRepository,
                MemoryCheckpointerProvider,
            )
            self.candidate_repo = MemoryCandidateRepository()
            self.thread_repo = MemoryThreadRepository()
            self.user_repo = MemoryUserRepository()
            self.file_repo = MemoryFileRepository()
            self.checkpointer_provider = MemoryCheckpointerProvider()

        # 5. Seguridad & Guardrails
        from src.infrastructure.safety.prompt_guardrail import PromptInjectionGuardrail
        prompt_guardrail = PromptInjectionGuardrail()

        if settings.SAFETY_PROVIDER == "azure":
            from src.infrastructure.safety.azure_safety import AzureContentSafetyAdapter
            azure_safety = AzureContentSafetyAdapter()

            class CompositeSafetyAdapter(ContentSafetyPort):
                async def check_input(self, text: str) -> Tuple[bool, str]:
                    safe, reason = await prompt_guardrail.check_input(text)
                    if not safe:
                        return False, reason
                    return await azure_safety.check_input(text)

            self.content_safety: ContentSafetyPort = CompositeSafetyAdapter()
        elif settings.SAFETY_PROVIDER == "strict_noop_for_unit_tests":
            from src.infrastructure.safety.noop_safety import NoopContentSafetyAdapter
            self.content_safety = NoopContentSafetyAdapter()
        else:
            # Por defecto activo en desarrollo y producción
            self.content_safety = prompt_guardrail

        # 6. Autenticación
        if settings.AUTH_PROVIDER in ("entra_id", "hybrid"):
            from src.infrastructure.auth.entra_id import EntraIDTokenVerifier
            self.token_verifier: TokenVerifierPort = EntraIDTokenVerifier()
        else:
            from src.infrastructure.auth.dev_auth import DevTokenVerifier
            self.token_verifier = DevTokenVerifier()

        logger.info(
            "Contenedor de dependencias inicializado. LLM: %s, Storage: %s, Persistence: %s, Auth: %s",
            settings.LLM_PROVIDER,
            settings.STORAGE_PROVIDER,
            settings.PERSISTENCE_PROVIDER,
            settings.AUTH_PROVIDER,
        )

    @classmethod
    def get_instance(cls) -> "Container":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance_for_testing(cls):
        cls._instance = None

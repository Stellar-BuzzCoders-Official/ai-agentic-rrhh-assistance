import logging
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from src.application.ports.outbound import ChatModelProviderPort, EmbeddingsProviderPort
from src.config.settings import settings

logger = logging.getLogger(__name__)


class AzureOpenAIProvider(ChatModelProviderPort, EmbeddingsProviderPort):
    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
        embedding_deployment: str | None = None,
    ):
        self.endpoint = (endpoint or settings.AZURE_OPENAI_ENDPOINT or "").rstrip("/")
        self.api_key = api_key or settings.AZURE_OPENAI_API_KEY
        self.deployment = deployment or settings.AZURE_OPENAI_DEPLOYMENT
        self.api_version = api_version or settings.AZURE_OPENAI_API_VERSION
        self.embedding_deployment = embedding_deployment or settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT

        if not self.endpoint or not self.api_key:
            logger.warning("Azure OpenAI endpoint o API key no están configurados todavía.")

    def get_chat_model(self, temperature: float = 0.0) -> BaseChatModel:
        # Modelos de razonamiento y nueva generación (gpt-5-mini, o1, o3) solo soportan temperature=1.0
        deployment_lower = (self.deployment or "").lower()
        effective_temp = 1.0 if any(p in deployment_lower for p in ["gpt-5", "o1", "o3", "reasoning"]) else temperature

        return AzureChatOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            azure_deployment=self.deployment,
            api_version=self.api_version,
            temperature=effective_temp,
        )

    def get_embeddings(self) -> Embeddings:
        return AzureOpenAIEmbeddings(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            azure_deployment=self.embedding_deployment,
            api_version=self.api_version,
        )

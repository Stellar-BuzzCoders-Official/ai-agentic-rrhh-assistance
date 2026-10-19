import logging
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_ollama import ChatOllama, OllamaEmbeddings
from src.application.ports.outbound import ChatModelProviderPort, EmbeddingsProviderPort
from src.config.settings import settings

logger = logging.getLogger(__name__)


class OllamaProvider(ChatModelProviderPort, EmbeddingsProviderPort):
    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL

    def get_chat_model(self, temperature: float = 0.0) -> BaseChatModel:
        return ChatOllama(
            base_url=self.base_url,
            model=self.model,
            temperature=temperature,
        )

    def get_embeddings(self) -> Embeddings:
        return OllamaEmbeddings(
            base_url=self.base_url,
            model=self.model,
        )

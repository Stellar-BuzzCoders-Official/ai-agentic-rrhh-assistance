import logging
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from src.application.ports.outbound import ChatModelProviderPort, EmbeddingsProviderPort
from src.config.settings import settings

logger = logging.getLogger(__name__)


class GeminiProvider(ChatModelProviderPort, EmbeddingsProviderPort):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL

        if not self.api_key:
            logger.warning("Gemini API key no está configurada.")

    def get_chat_model(self, temperature: float = 0.0) -> BaseChatModel:
        return ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=self.api_key,
            temperature=temperature,
        )

    def get_embeddings(self) -> Embeddings:
        return GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=self.api_key,
        )

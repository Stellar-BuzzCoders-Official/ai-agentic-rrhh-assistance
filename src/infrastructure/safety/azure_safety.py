import logging
from typing import Tuple
from azure.core.credentials import AzureKeyCredential
from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeTextOptions
from src.application.ports.outbound import ContentSafetyPort
from src.config.settings import settings

logger = logging.getLogger(__name__)


class AzureContentSafetyAdapter(ContentSafetyPort):
    def __init__(self, endpoint: str | None = None, api_key: str | None = None):
        self.endpoint = (endpoint or settings.CONTENT_SAFETY_ENDPOINT or "").rstrip("/")
        self.api_key = api_key or settings.CONTENT_SAFETY_KEY
        self.client = None

        if self.endpoint and self.api_key:
            try:
                self.client = ContentSafetyClient(
                    endpoint=self.endpoint,
                    credential=AzureKeyCredential(self.api_key)
                )
            except Exception as e:
                logger.warning("No se pudo inicializar Azure Content Safety: %s", str(e))

    async def check_input(self, text: str) -> Tuple[bool, str]:
        if not self.client:
            return True, ""

        try:
            request = AnalyzeTextOptions(text=text[:1000])
            response = self.client.analyze_text(request)

            # Verificar severidad en categorías de riesgo
            for category_analysis in [
                response.hate_result,
                response.self_harm_result,
                response.sexual_result,
                response.violence_result,
            ]:
                if category_analysis and category_analysis.severity > 2:
                    return False, f"Contenido bloqueado por seguridad: severidad elevada en {category_analysis.category}"

            return True, ""
        except Exception as e:
            logger.error("Error al consultar Azure Content Safety: %s", str(e))
            return True, ""  # Fail open con logging

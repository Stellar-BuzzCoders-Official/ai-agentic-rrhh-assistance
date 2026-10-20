import io
import logging
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat
from src.application.ports.outbound import DocumentExtractorPort
from src.config.settings import settings

logger = logging.getLogger(__name__)


class AzureDocumentIntelligenceExtractor(DocumentExtractorPort):
    def __init__(self, endpoint: str | None = None, api_key: str | None = None):
        self.endpoint = (endpoint or settings.DOCUMENT_INTELLIGENCE_ENDPOINT or "").rstrip("/")
        self.api_key = api_key or settings.DOCUMENT_INTELLIGENCE_KEY
        self.client = None

        if self.endpoint and self.api_key:
            self.client = DocumentIntelligenceClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.api_key)
            )
        else:
            logger.warning("Azure Document Intelligence no configurado. Se usará el extractor local si se invoca.")

    async def extract_text(self, file_bytes: bytes, file_name: str, file_type: str) -> str:
        if not self.client:
            # Fallback a extractor local si no está configurada la credencial en nube
            from src.infrastructure.extraction.legacy_local import LocalDocumentExtractor
            local_extractor = LocalDocumentExtractor()
            return await local_extractor.extract_text(file_bytes, file_name, file_type)

        try:
            logger.info("Extrayendo texto con Azure Document Intelligence para: %s", file_name)
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=io.BytesIO(file_bytes),
                content_type="application/octet-stream",
                output_content_format=DocumentContentFormat.MARKDOWN,
            )
            result = poller.result()
            if result.content:
                return result.content

            # Si el contenido en markdown está vacío, unir los párrafos
            extracted_lines = []
            if result.paragraphs:
                for paragraph in result.paragraphs:
                    extracted_lines.append(paragraph.content)
            return "\n\n".join(extracted_lines)

        except Exception as e:
            logger.error("Error en Azure Document Intelligence: %s. Ejecutando fallback local.", str(e))
            from src.infrastructure.extraction.legacy_local import LocalDocumentExtractor
            local_extractor = LocalDocumentExtractor()
            return await local_extractor.extract_text(file_bytes, file_name, file_type)

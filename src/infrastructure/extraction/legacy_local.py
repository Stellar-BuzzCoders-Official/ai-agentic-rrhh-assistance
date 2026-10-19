import io
import logging
from pypdf import PdfReader
from docx import Document
from src.application.ports.outbound import DocumentExtractorPort

logger = logging.getLogger(__name__)


class LocalDocumentExtractor(DocumentExtractorPort):
    """
    Extractor local y portable (pypdf, python-docx, texto plano, json, yaml).
    No requiere llamadas externas de red.
    """

    async def extract_text(self, file_bytes: bytes, file_name: str, file_type: str) -> str:
        clean_ext = file_type.lower().strip().replace(".", "")
        if not clean_ext and "." in file_name:
            clean_ext = file_name.split(".")[-1].lower()

        logger.info("Extrayendo texto localmente para '%s' (tipo: %s)", file_name, clean_ext)

        try:
            if clean_ext == "pdf":
                return self._extract_pdf(file_bytes)
            elif clean_ext in ["docx", "doc"]:
                return self._extract_docx(file_bytes)
            elif clean_ext in ["txt", "json", "yaml", "yml", "csv", "md"]:
                return self._extract_text_plain(file_bytes)
            else:
                # Intento genérico de decodificación de texto
                return self._extract_text_plain(file_bytes)
        except Exception as e:
            logger.error("Error extrayendo texto localmente de %s: %s", file_name, str(e))
            return ""

    def _extract_pdf(self, file_bytes: bytes) -> str:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                pages_text.append(text)
        return "\n\n".join(pages_text)

    def _extract_docx(self, file_bytes: bytes) -> str:
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)

    def _extract_text_plain(self, file_bytes: bytes) -> str:
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="ignore")

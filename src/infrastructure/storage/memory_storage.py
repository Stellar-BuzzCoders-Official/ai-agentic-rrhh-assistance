import uuid
import os
import logging
from src.application.ports.outbound import FileStoragePort

logger = logging.getLogger(__name__)


class MemoryStorageAdapter(FileStoragePort):
    _instance = None

    def __init__(self):
        self._files: dict[str, bytes] = {}
        self._urls: dict[str, str] = {}

    @classmethod
    def get_instance(cls) -> "MemoryStorageAdapter":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def upload_file(self, file_bytes: bytes, file_name: str, file_type: str) -> str:
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(file_name)[1] or f".{file_type}"
        simulated_url = f"https://mock-storage.local/rrhh-documents/{file_id}{ext}"
        self._files[file_id] = file_bytes
        self._urls[simulated_url] = file_id
        logger.info("Archivo almacenado en memoria: %s -> %s", file_name, simulated_url)
        return simulated_url

    async def download_file(self, file_url_or_id: str) -> bytes:
        if file_url_or_id in self._files:
            return self._files[file_url_or_id]
        if file_url_or_id in self._urls:
            return self._files[self._urls[file_url_or_id]]
        # Intento por ID extraído de la URL
        file_name = file_url_or_id.split("/")[-1]
        raw_id = os.path.splitext(file_name)[0]
        if raw_id in self._files:
            return self._files[raw_id]
        raise FileNotFoundError(f"Archivo no encontrado en memoria: {file_url_or_id}")

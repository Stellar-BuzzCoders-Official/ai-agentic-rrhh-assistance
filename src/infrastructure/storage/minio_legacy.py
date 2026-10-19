import uuid
import os
import io
import logging
from src.application.ports.outbound import FileStoragePort
from src.config.settings import settings

logger = logging.getLogger(__name__)


class MinioLegacyStorageAdapter(FileStoragePort):
    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket_name: str | None = None,
        secure: bool | None = None,
    ):
        self.endpoint = endpoint or settings.MINIO_ENDPOINT
        self.access_key = access_key or settings.MINIO_ACCESS_KEY
        self.secret_key = secret_key or settings.MINIO_SECRET_KEY
        self.bucket_name = bucket_name or settings.MINIO_BUCKET_NAME
        self.secure = secure if secure is not None else settings.MINIO_SECURE
        self.client = None

        try:
            from minio import Minio
            if self.access_key and self.secret_key:
                self.client = Minio(
                    self.endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=self.secure,
                )
                if not self.client.bucket_exists(self.bucket_name):
                    self.client.make_bucket(self.bucket_name)
        except Exception as e:
            logger.warning("MinIO no inicializado o librería no disponible: %s", str(e))

    async def upload_file(self, file_bytes: bytes, file_name: str, file_type: str) -> str:
        if not self.client:
            from src.infrastructure.storage.memory_storage import MemoryStorageAdapter
            return await MemoryStorageAdapter.get_instance().upload_file(file_bytes, file_name, file_type)

        ext = os.path.splitext(file_name)[1] or f".{file_type}"
        unique_name = f"{uuid.uuid4()}{ext}"
        stream = io.BytesIO(file_bytes)
        self.client.put_object(
            self.bucket_name,
            unique_name,
            stream,
            length=len(file_bytes),
            content_type=f"application/{file_type}",
        )
        protocol = "https" if self.secure else "http"
        return f"{protocol}://{self.endpoint}/{self.bucket_name}/{unique_name}"

    async def download_file(self, file_url_or_id: str) -> bytes:
        if not self.client:
            from src.infrastructure.storage.memory_storage import MemoryStorageAdapter
            return await MemoryStorageAdapter.get_instance().download_file(file_url_or_id)

        object_name = file_url_or_id.split("/")[-1]
        response = self.client.get_object(self.bucket_name, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

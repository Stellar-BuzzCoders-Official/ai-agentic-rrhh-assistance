import uuid
import os
import logging
from datetime import datetime, timedelta
from azure.storage.blob import (
    BlobServiceClient,
    BlobSasPermissions,
    generate_blob_sas,
    ContentSettings,
)
from src.application.ports.outbound import FileStoragePort
from src.config.settings import settings

logger = logging.getLogger(__name__)


class AzureBlobStorageAdapter(FileStoragePort):
    def __init__(
        self,
        connection_string: str | None = None,
        account_name: str | None = None,
        account_key: str | None = None,
        container_name: str | None = None,
    ):
        self.container_name = container_name or settings.AZURE_STORAGE_CONTAINER_NAME
        self.connection_string = connection_string or settings.AZURE_STORAGE_CONNECTION_STRING
        self.account_name = account_name or settings.AZURE_STORAGE_ACCOUNT_NAME
        self.account_key = account_key or settings.AZURE_STORAGE_ACCOUNT_KEY
        self.blob_service_client = None

        if self.connection_string:
            self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        elif self.account_name and self.account_key:
            self.blob_service_client = BlobServiceClient(
                account_url=f"https://{self.account_name}.blob.core.windows.net",
                credential=self.account_key
            )
        else:
            logger.warning("Azure Blob Storage no tiene credenciales configuradas.")

        if self.blob_service_client:
            try:
                container_client = self.blob_service_client.get_container_client(self.container_name)
                if not container_client.exists():
                    container_client.create_container()
                    logger.info("Contenedor Blob '%s' creado exitosamente.", self.container_name)
            except Exception as e:
                logger.error("Error verificando/creando contenedor blob '%s': %s", self.container_name, str(e))

    async def upload_file(self, file_bytes: bytes, file_name: str, file_type: str) -> str:
        if not self.blob_service_client:
            from src.infrastructure.storage.memory_storage import MemoryStorageAdapter
            return await MemoryStorageAdapter.get_instance().upload_file(file_bytes, file_name, file_type)

        ext = os.path.splitext(file_name)[1] or f".{file_type}"
        blob_name = f"{uuid.uuid4()}{ext}"
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )

        content_settings = ContentSettings(content_type=f"application/{file_type}")
        blob_client.upload_blob(file_bytes, overwrite=True, content_settings=content_settings)
        logger.info("Archivo subido a Blob Storage: %s", blob_name)

        # Generar SAS URL válida por 24 horas si tenemos credenciales
        if self.account_name and self.account_key:
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=self.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=24),
            )
            return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{sas_token}"

        return blob_client.url

    async def download_file(self, file_url_or_id: str) -> bytes:
        if not self.blob_service_client:
            from src.infrastructure.storage.memory_storage import MemoryStorageAdapter
            return await MemoryStorageAdapter.get_instance().download_file(file_url_or_id)

        # Extraer blob_name de la URL
        clean_url = file_url_or_id.split("?")[0]
        blob_name = clean_url.split("/")[-1]
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )
        downloader = blob_client.download_blob()
        return downloader.readall()

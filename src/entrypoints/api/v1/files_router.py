import uuid
import asyncio
import logging
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from pydantic import BaseModel

from src.entrypoints.api.dependencies import get_current_user, get_container
from src.config.container import Container
from src.domain.entities import User, FileMetadata
from src.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/files", tags=["Files"])


class FileUploadResponse(BaseModel):
    file_id: str
    file_name: str
    file_type: str
    file_size: int
    file_url: str
    extracted_text_preview: str


class BulkUploadResponse(BaseModel):
    total_processed: int
    files: List[FileUploadResponse]


async def _process_single_file(upload_file: UploadFile, user_id: str, container: Container) -> FileUploadResponse:
    file_bytes = await upload_file.read()
    file_name = upload_file.filename or "archivo.pdf"
    file_type = file_name.split(".")[-1].lower() if "." in file_name else "pdf"

    # Subir a storage (Azure Blob / MinIO / Memory)
    file_url = await container.file_storage.upload_file(file_bytes, file_name, file_type)

    # Extraer texto (Document Intelligence / local)
    extracted_text = await container.document_extractor.extract_text(file_bytes, file_name, file_type)

    file_id = str(uuid.uuid4())
    metadata = FileMetadata(
        id=file_id,
        ownerId=user_id,
        fileName=file_name,
        fileType=file_type,
        fileSize=len(file_bytes),
        fileUrl=file_url,
        extractedText=extracted_text,
    )
    await container.file_repo.save_file_metadata(metadata)

    preview = (extracted_text[:200] + "...") if len(extracted_text) > 200 else extracted_text
    return FileUploadResponse(
        file_id=file_id,
        file_name=file_name,
        file_type=file_type,
        file_size=len(file_bytes),
        file_url=file_url,
        extracted_text_preview=preview,
    )


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Sube un documento individual (CV o Job Description), extrae su texto y lo almacena."""
    try:
        return await _process_single_file(file, current_user.id, container)
    except Exception as e:
        logger.error("Error al subir archivo: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Error al procesar archivo: {str(e)}")


@router.post("/bulk", response_model=BulkUploadResponse)
async def bulk_upload_files(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """
    Carga masiva de CVs para el talent pool del reclutador.
    Límite máximo permitido: 10 archivos por lote para asegurar alto rendimiento.
    """
    if len(files) > settings.BULK_UPLOAD_MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El número máximo permitido de archivos por lote es {settings.BULK_UPLOAD_MAX_FILES}. Se recibieron {len(files)}.",
        )

    logger.info("Iniciando carga masiva de %d archivos para el usuario %s", len(files), current_user.id)

    tasks = [_process_single_file(f, current_user.id, container) for f in files]
    processed_results = await asyncio.gather(*tasks, return_exceptions=True)

    success_files: List[FileUploadResponse] = []
    for res in processed_results:
        if isinstance(res, FileUploadResponse):
            success_files.append(res)
        else:
            logger.error("Error en uno de los archivos del lote: %s", str(res))

    return BulkUploadResponse(
        total_processed=len(success_files),
        files=success_files,
    )

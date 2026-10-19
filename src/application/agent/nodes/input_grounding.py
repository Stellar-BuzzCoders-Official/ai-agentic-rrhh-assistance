import base64
import uuid
import logging
from langchain_core.messages import HumanMessage
from src.application.agent.state import RRHHState
from src.config.container import Container
from src.domain.entities import FileMetadata

logger = logging.getLogger(__name__)


async def input_grounding_node(state: RRHHState) -> dict:
    """
    Nodo de entrada:
    1. Valida seguridad e inyecciones de prompt (Prompt Shields).
    2. Procesa adjuntos en formato base64 o multipart, extrayendo texto y subiendo a Blob.
    3. Normaliza el mensaje del usuario en el estado sin saturar con base64.
    """
    container = Container.get_instance()
    messages = state.get("messages", [])
    if not messages:
        return {"is_safe": True}

    last_message = messages[-1]
    raw_content = last_message.content
    extracted_text = None
    file_id = state.get("current_cv_id")

    # 1. Chequeo de seguridad de contenido
    text_to_check = str(raw_content)
    is_safe, reason = await container.content_safety.check_input(text_to_check)
    if not is_safe:
        logger.warning("Mensaje bloqueado por guardrail de seguridad: %s", reason)
        return {
            "is_safe": False,
            "safety_reason": reason,
        }

    # 2. Detección y normalización de archivos adjuntos (v0 base64 o v1 file_id)
    # Si el contenido es un diccionario con 'file_type' y 'source.data' (formato legacy del frontend)
    if isinstance(raw_content, dict) and "file_type" in raw_content:
        file_type = raw_content.get("file_type", "pdf")
        source = raw_content.get("source", {})
        b64_data = source.get("data", "")
        file_name = source.get("file_name") or f"document_{uuid.uuid4()}.{file_type}"

        try:
            # Limpiar header de data URI si existe
            if "," in b64_data:
                b64_data = b64_data.split(",")[-1]
            file_bytes = base64.b64decode(b64_data)

            # Subir a Storage
            file_url = await container.file_storage.upload_file(file_bytes, file_name, file_type)

            # Extraer texto con Document Intelligence o extractor local
            extracted_text = await container.document_extractor.extract_text(file_bytes, file_name, file_type)

            # Registrar metadata
            file_id = str(uuid.uuid4())
            metadata = FileMetadata(
                id=file_id,
                ownerId=state.get("user_id", "recruiter_default"),
                fileName=file_name,
                fileType=file_type,
                fileSize=len(file_bytes),
                fileUrl=file_url,
                extractedText=extracted_text,
            )
            await container.file_repo.save_file_metadata(metadata)

            # Reemplazar el mensaje con un aviso claro para el agente
            normalized_text = f"He adjuntado el archivo '{file_name}' (ID: {file_id}). Por favor procésalo según la fase correspondiente."
            new_msg = HumanMessage(content=normalized_text, id=last_message.id)

            return {
                "is_safe": True,
                "current_cv_id": file_id,
                "messages": [new_msg],
            }
        except Exception as e:
            logger.error("Error al procesar archivo en input_grounding: %s", str(e))

    return {
        "is_safe": True,
        "current_cv_id": file_id,
    }

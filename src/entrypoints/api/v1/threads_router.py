import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.entrypoints.api.dependencies import get_current_user, get_container
from src.config.container import Container
from src.domain.entities import User, Thread
from src.application.agent.graph import build_screening_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/threads", tags=["Threads"])


class ThreadResponse(BaseModel):
    id: str
    userId: str
    nameHistory: str | None
    processPhase: str
    updatedAt: str


@router.get("", response_model=List[ThreadResponse])
async def list_threads(
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Lista las conversaciones / hilos de screening pertenecientes al usuario actual."""
    threads = await container.thread_repo.list_threads_by_user(current_user.id)
    return [
        ThreadResponse(
            id=t.id,
            userId=t.userId,
            nameHistory=t.nameHistory,
            processPhase=t.processPhase,
            updatedAt=t.updatedAt,
        )
        for t in threads
    ]


@router.get("/{thread_id}")
async def get_thread_state(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Obtiene el estado completo y los mensajes acumulados de un hilo desde el checkpointer."""
    thread_meta = await container.thread_repo.get_thread(thread_id)
    if not thread_meta or thread_meta.userId != current_user.id:
        raise HTTPException(status_code=404, detail="Hilo no encontrado")

    graph = build_screening_graph(container=container)
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        state_tuple = await graph.aget_state(config)
    except Exception as e:
        logger.error("Error al obtener estado de LangGraph para el hilo %s: %s", thread_id, str(e))
        return {
            "thread": thread_meta.model_dump(),
            "messages": [],
            "technical_report": None,
            "job_post": None,
        }

    if not state_tuple or not state_tuple.values:
        return {"thread": thread_meta.model_dump(), "messages": []}

    # Serializar mensajes para el cliente
    raw_messages = state_tuple.values.get("messages", [])
    formatted_messages = []
    for msg in raw_messages:
        formatted_messages.append({
            "id": getattr(msg, "id", None),
            "role": getattr(msg, "type", "user"),
            "content": getattr(msg, "content", ""),
        })

    report_val = state_tuple.values.get("technical_report")
    report_data = report_val.model_dump(by_alias=True) if hasattr(report_val, "model_dump") else report_val

    job_val = state_tuple.values.get("job_post")
    job_data = job_val.model_dump(by_alias=True) if hasattr(job_val, "model_dump") else job_val

    return {
        "thread": thread_meta.model_dump(),
        "messages": formatted_messages,
        "technical_report": report_data,
        "job_post": job_data,
    }


@router.delete("/{thread_id}")
async def delete_thread(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Elimina una conversación y sus metadatos asociados."""
    thread_meta = await container.thread_repo.get_thread(thread_id)
    if not thread_meta or thread_meta.userId != current_user.id:
        raise HTTPException(status_code=404, detail="Hilo no encontrado")

    deleted = await container.thread_repo.delete_thread(thread_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="No se pudo eliminar el hilo")

    return {"message": f"Hilo {thread_id} eliminado exitosamente."}

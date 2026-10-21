import uuid
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from src.entrypoints.api.dependencies import get_current_user, get_container
from src.config.container import Container
from src.domain.entities import User, Thread
from src.application.agent.graph import build_screening_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v0", tags=["Legacy v0 Compatibility"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def legacy_login(login_request: LoginRequest, container: Container = Depends(get_container)):
    """Endpoint legacy de login compatible con frontend v0."""
    logger.info("Login legacy solicitado para usuario: %s", login_request.username)
    # Genera token de desarrollo compatible
    user_id = "a8f0569a-46fd-457f-847e-e233af403114"
    return {
        "access_token": "dev-token-legacy",
        "token_type": "bearer",
        "user": {
            "userID": user_id,
            "userName": login_request.username,
            "email": f"{login_request.username}@rrhh.ai",
        }
    }


@router.post("/auth/logout")
async def legacy_logout():
    return {"message": "Logout exitoso", "detail": "Token invalidado."}


@router.get("/auth/verify")
async def legacy_verify_token(current_user: User = Depends(get_current_user)):
    return {
        "valid": True,
        "user": {
            "username": current_user.name,
            "email": current_user.email,
            "user_id": current_user.id,
        }
    }


@router.post("/screeningChat")
async def legacy_screening_chat(
    request: Request,
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """
    Endpoint principal legacy de chat: compatible 100% con la llamada de chat.component.ts.
    Ejecuta el grafo orquestado con LangGraph manteniendo idéntico el contrato JSON de respuesta.
    """
    try:
        body = await request.json()
        data_block = body.get("data", {})
        conversation_id = data_block.get("conversation_id") or str(uuid.uuid4())
        process_phase = data_block.get("process_phase") or "request_requirements"
        raw_messages = data_block.get("message", [])

        if not raw_messages:
            raise HTTPException(status_code=400, detail="Se requiere al menos un mensaje.")

        last_raw = raw_messages[-1]
        user_content = last_raw.get("content")

        # Construir mensaje de entrada para LangGraph
        human_msg = HumanMessage(content=user_content, id=last_raw.get("id", str(uuid.uuid4())))

        initial_state = {
            "messages": [human_msg],
            "user_id": current_user.id,
            "thread_id": conversation_id,
            "process_phase": process_phase,
        }

        graph = build_screening_graph(container=container)
        config = {"configurable": {"thread_id": conversation_id}}

        final_state = await graph.ainvoke(initial_state, config=config)
        client_payload = final_state.get("client_response_payload")

        if not client_payload or "data" not in client_payload:
            raise RuntimeError("El grafo no produjo un payload de respuesta válido.")

        return JSONResponse(content=client_payload, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error en screeningChat legacy: %s", str(e), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Ocurrió un error interno del servidor: {str(e)}"}
        )


@router.get("/conversationsIdName/{user_id}")
async def get_conversations_id_name(
    user_id: str,
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Retorna lista de conversaciones para el sidebar del frontend legacy."""
    threads = await container.thread_repo.list_threads_by_user(user_id)
    return [
        {
            "_id": t.id,
            "nameHistory": t.nameHistory or "Conversación",
        }
        for t in threads
    ]


@router.get("/getConversation/{conversation_id}")
async def get_conversation_by_id(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Obtiene el historial de una conversación por ID."""
    thread = await container.thread_repo.get_thread(conversation_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    graph = build_screening_graph(container=container)
    config = {"configurable": {"thread_id": conversation_id}}
    state_tuple = graph.get_state(config)

    messages = []
    if state_tuple and state_tuple.values:
        for msg in state_tuple.values.get("messages", []):
            messages.append({
                "id": getattr(msg, "id", None),
                "role": getattr(msg, "type", "user"),
                "content": getattr(msg, "content", ""),
            })

    return {
        "_id": conversation_id,
        "data": {
            "conversationId": conversation_id,
            "nameHistory": thread.nameHistory,
            "userID": thread.userId,
            "process_phase": thread.processPhase,
            "message": messages,
        }
    }


@router.delete("/deleteConversation/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Elimina una conversación."""
    deleted = await container.thread_repo.delete_thread(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {"message": f"La conversación con _id {conversation_id} ha sido eliminada."}


@router.get("/capabilities/{conversation_id}")
async def get_capabilities(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Obtiene las capacidades técnicas configuradas en una conversación."""
    graph = build_screening_graph(container=container)
    config = {"configurable": {"thread_id": conversation_id}}
    state_tuple = graph.get_state(config)

    if not state_tuple or not state_tuple.values:
        raise HTTPException(status_code=404, detail="No se encontraron capacidades para la conversación")

    job_post = state_tuple.values.get("job_post")
    if not job_post:
        return []

    return [{
        "_id": job_post.id,
        "conversation_id": conversation_id,
        "requirement_text": job_post.rawText,
        "Capacidades": ", ".join([c.get("name", "") for c in job_post.requiredCapabilities]),
    }]

import json
import uuid
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

from src.entrypoints.api.dependencies import get_current_user, get_container
from src.config.container import Container
from src.domain.entities import User
from src.application.agent.graph import build_screening_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["Chat v1"])


class ChatMessagePayload(BaseModel):
    role: str = "user"
    content: Any


class ChatRequestV1(BaseModel):
    thread_id: Optional[str] = Field(default=None, description="ID del hilo de conversación. Si no se envía, se genera uno nuevo.")
    message: str = Field(..., description="Texto del mensaje del reclutador")
    file_id: Optional[str] = Field(default=None, description="ID de un archivo previamente subido a /api/v1/files/upload")


@router.post("/stream")
async def chat_stream(
    request: ChatRequestV1,
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """
    Endpoint Server-Sent Events (SSE) para interacción conversacional con streaming en tiempo real.
    Emite eventos de:
    - input_grounding
    - tool_start / tool_end
    - judge_verdict
    - report
    - token / final_message
    - done
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_screening_graph(container=container)

    # Preparar contenido
    user_text = request.message
    if request.file_id:
        user_text += f"\n[Archivo adjunto referenciado: {request.file_id}]"

    initial_state = {
        "messages": [HumanMessage(content=user_text)],
        "user_id": current_user.id,
        "thread_id": thread_id,
        "current_cv_id": request.file_id,
    }

    async def event_generator():
        yield f"event: init\ndata: {json.dumps({'thread_id': thread_id})}\n\n"

        try:
            async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
                # Inspeccionar qué nodo acaba de emitir
                for node_name, node_update in chunk.items():
                    if node_name == "input_grounding":
                        yield f"event: input_grounding\ndata: {json.dumps({'is_safe': node_update.get('is_safe', True)})}\n\n"

                    elif node_name == "recruiter_agent":
                        messages = node_update.get("messages", [])
                        if messages:
                            last_msg = messages[-1]
                            tool_calls = getattr(last_msg, "tool_calls", None)
                            if tool_calls:
                                for tc in tool_calls:
                                    yield f"event: tool_start\ndata: {json.dumps({'tool': tc.get('name'), 'args': tc.get('args')})}\n\n"
                            elif getattr(last_msg, "content", None):
                                yield f"event: token\ndata: {json.dumps({'text': last_msg.content})}\n\n"

                    elif node_name == "judge_agent":
                        verdict = node_update.get("grounding_verdict")
                        if verdict:
                            yield f"event: judge_verdict\ndata: {json.dumps(verdict.model_dump())}\n\n"

                    elif node_name == "finalize":
                        payload = node_update.get("client_response_payload", {})
                        report = payload.get("data", {}).get("message", [{}])[0].get("technical_report")
                        if report:
                            yield f"event: report\ndata: {json.dumps(report)}\n\n"
                        yield f"event: done\ndata: {json.dumps(payload)}\n\n"

        except Exception as e:
            logger.error("Error en streaming del grafo: %s", str(e), exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("")
async def chat_sync(
    request: ChatRequestV1,
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container),
):
    """Endpoint síncrono JSON para interacción con el agente de screening."""
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_screening_graph(container=container)

    user_text = request.message
    if request.file_id:
        user_text += f"\n[Archivo adjunto referenciado: {request.file_id}]"

    initial_state = {
        "messages": [HumanMessage(content=user_text)],
        "user_id": current_user.id,
        "thread_id": thread_id,
        "current_cv_id": request.file_id,
    }

    try:
        final_state = await graph.ainvoke(initial_state, config=config)
        return final_state.get("client_response_payload", {"data": {"conversation_id": thread_id}})
    except Exception as e:
        logger.error("Error en chat síncrono: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en el asistente: {str(e)}")

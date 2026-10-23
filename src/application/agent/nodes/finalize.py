import uuid
import logging
from datetime import datetime, timezone
from langchain_core.messages import AIMessage
from src.application.agent.state import RRHHState
from src.config.container import Container
from src.domain.entities import Thread

logger = logging.getLogger(__name__)


async def finalize_node(state: RRHHState) -> dict:
    """
    Nodo de salida y formateo:
    1. Construye el payload de respuesta compatible con el contrato de la API.
    2. Persiste metadatos del hilo en el repositorio de threads para el sidebar.
    """
    container = Container.get_instance()
    thread_id = state.get("thread_id", str(uuid.uuid4()))
    user_id = state.get("user_id", "recruiter_default")
    messages = state.get("messages", [])
    report = state.get("technical_report")
    job_post = state.get("job_post")

    # Extraer el último mensaje del asistente o generar uno si no existe
    last_assistant_msg = None
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai" or getattr(msg, "role", None) == "assistant":
            last_assistant_msg = msg
            break

    content_text = ""
    if last_assistant_msg:
        content_text = last_assistant_msg.content
    elif report:
        content_text = (
            f"¡Gracias por la información! A continuación, te presento el informe técnico en base al CV "
            f"y los requerimientos técnicos:"
        )
    else:
        content_text = "¡Hola! Soy tu asistente de RRHH. Para comenzar, por favor indícame los requerimientos técnicos del puesto."

    # Determinar fase del proceso
    current_phase = state.get("process_phase", "request_requirements")
    is_valid = True

    if report:
        current_phase = "upload_cv_and_match"
        is_valid = True
    elif job_post:
        # Una vez que hay requerimientos válidos, avanzamos la fase a carga de CV
        current_phase = "upload_cv_and_match"
        is_valid = True

    # Generar o mantener nombre de historia
    name_history = state.get("name_history")
    if not name_history:
        if job_post and job_post.title:
            name_history = job_post.title
        else:
            name_history = "Nueva Selección"

    # Preparar objetos de reportes técnicos para serialización JSON
    reports = state.get("technical_reports") or []
    if not reports and report:
        reports = [report]

    reports_dicts = []
    for r in reports:
        r_dict = r.model_dump(by_alias=True)
        if not r_dict.get("resumen") and r.evaluationSummary:
            r_dict["resumen"] = {
                "cumpleIndispensable": r.evaluationSummary.requiredSkillsMet,
                "cumpleDeseable": r.evaluationSummary.optionalSkillsMet,
                "recomendation": r.evaluationSummary.recommendation,
            }
        reports_dicts.append(r_dict)

    latest_report_dict = reports_dicts[-1] if reports_dicts else None

    bot_message = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": content_text,
        "validate": is_valid,
        "technical_report": latest_report_dict,
        "technicalReport": latest_report_dict,
        "technical_reports": reports_dicts,
        "technicalReports": reports_dicts,
    }

    response_data = {
        "_id": thread_id,
        "conversation_id": thread_id,
        "created": datetime.now(timezone.utc).isoformat(),
        "nameHistory": name_history,
        "userID": user_id,
        "step": 1,
        "isSelectBlock": False,
        "selectValue": "",
        "process_phase": current_phase,
        "tokens_input": 0,
        "tokens_output": 0,
        "tokens": 0,
        "max_tokens": 3500,
        "message": [bot_message],
    }

    # Persistir metadatos del hilo en el repositorio de threads
    try:
        thread_entity = Thread(
            id=thread_id,
            userId=user_id,
            nameHistory=name_history,
            processPhase=current_phase,
            updatedAt=datetime.now(timezone.utc).isoformat(),
        )
        await container.thread_repo.save_thread(thread_entity)
    except Exception as e:
        logger.error("Error al persistir metadatos del hilo %s: %s", thread_id, str(e))

    return {
        "process_phase": current_phase,
        "name_history": name_history,
        "client_response_payload": {"data": response_data},
    }


async def safe_reply_node(state: RRHHState) -> dict:
    """Nodo de respuesta segura en caso de contenido bloqueado."""
    reason = state.get("safety_reason", "Contenido no permitido.")
    bot_msg = AIMessage(
        content=f"Lo siento, tu mensaje no pudo ser procesado debido a políticas de seguridad: {reason}"
    )
    return {
        "messages": [bot_msg],
        "client_response_payload": {
            "data": {
                "conversation_id": state.get("thread_id", ""),
                "message": [{
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": bot_msg.content,
                    "validate": False,
                }]
            }
        }
    }

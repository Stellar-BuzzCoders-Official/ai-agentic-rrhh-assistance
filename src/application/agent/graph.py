import logging
from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, BaseMessage

from src.application.agent.state import RRHHState
from src.application.agent.prompts import SYSTEM_RECRUITER_PROMPT
from src.application.agent.tools.recruiter_tools import create_recruiter_tools
from src.application.agent.nodes.input_grounding import input_grounding_node
from src.application.agent.nodes.judge_agent import judge_agent_node
from src.application.agent.nodes.finalize import finalize_node, safe_reply_node
from src.config.container import Container

logger = logging.getLogger(__name__)


def sanitize_message_history(messages: List[Any]) -> List[BaseMessage]:
    """
    Garantiza que la secuencia de mensajes cumpla con el contrato estricto de OpenAI/Azure OpenAI:
    1. Todo AIMessage con 'tool_calls' debe estar seguido INMEDIATAMENTE por ToolMessages
       que respondan a cada 'tool_call_id'.
    2. Si por una interrupción, caída del servidor o reinicio faltan ToolMessages, se sintetizan
       mensajes de error para cada tool_call_id faltante, evitando que Azure OpenAI lance 400 Bad Request.
    3. Ningún ToolMessage puede existir sin un AIMessage previo que haya declarado su tool_call_id.
    4. Los AIMessages sin tool_calls y con contenido vacío reciben un texto por defecto.
    """
    if not messages:
        return []

    sanitized: List[BaseMessage] = []
    i = 0
    n = len(messages)

    while i < n:
        msg = messages[i]
        is_ai = isinstance(msg, AIMessage) or getattr(msg, "type", None) == "ai"
        tool_calls = getattr(msg, "tool_calls", None) if is_ai else None

        if is_ai and tool_calls:
            # 1. Agregar el AIMessage original
            sanitized.append(msg)

            # 2. Recolectar tool_call_ids esperados
            expected_calls = []
            expected_ids = set()
            for tc in tool_calls:
                call_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                call_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "tool")
                if call_id:
                    expected_calls.append((call_id, call_name))
                    expected_ids.add(call_id)

            # 3. Buscar los ToolMessages consecutivos inmediatos
            j = i + 1
            existing_tool_msgs: Dict[str, Any] = {}
            while j < n:
                next_msg = messages[j]
                is_tool = isinstance(next_msg, ToolMessage) or getattr(next_msg, "type", None) == "tool"
                if not is_tool:
                    break
                tid = getattr(next_msg, "tool_call_id", None)
                if tid and tid in expected_ids:
                    existing_tool_msgs[tid] = next_msg
                j += 1

            # 4. Para cada call_id esperado, agregar el ToolMessage existente o sintetizar uno de fallo
            for call_id, call_name in expected_calls:
                if call_id in existing_tool_msgs:
                    sanitized.append(existing_tool_msgs[call_id])
                else:
                    logger.warning(
                        "Sintetizando ToolMessage para tool_call_id huérfano '%s' (%s) tras fallo/reinicio previo.",
                        call_id,
                        call_name,
                    )
                    sanitized.append(
                        ToolMessage(
                            content=f"Error o interrupción: la herramienta '{call_name}' no completó su ejecución previa debido a un fallo técnico o reinicio del servicio.",
                            name=call_name,
                            tool_call_id=call_id,
                        )
                    )

            # Avanzar el índice saltando los ToolMessages ya procesados
            i = j
            continue

        elif isinstance(msg, ToolMessage) or getattr(msg, "type", None) == "tool":
            # ToolMessage huérfano (no precedido por un AIMessage con este tool_call_id)
            tid = getattr(msg, "tool_call_id", None)
            logger.warning("Descartando ToolMessage huérfano sin AIMessage previo: tool_call_id=%s", tid)
            i += 1
            continue

        else:
            # Mensaje estándar (HumanMessage, SystemMessage o AIMessage sin tool_calls)
            if is_ai and not getattr(msg, "content", None):
                # OpenAI rechaza AIMessage con content vacío y sin tool_calls
                msg = AIMessage(content="[Respuesta previa vacía]", id=getattr(msg, "id", None))
            sanitized.append(msg)
            i += 1

    return sanitized


def build_screening_graph(container: Container | None = None, checkpointer=None):
    """
    Construye y compila el flujo orquestado con LangGraph.
    Implementa:
    - Nodo Grounding de Entrada (Prompt Shields & Normalización)
    - Agente ReAct con tools estructuradas
    - Sub-agente Auditor de Grounding (Juez independiente)
    - Nodo Finalize con soporte para persistencia de hilos y compatibilidad v0/v1
    """
    container = container or Container.get_instance()
    builder = StateGraph(RRHHState)

    # Contexto compartido para el ciclo de vida del agente
    context: Dict[str, Any] = {}
    tools = create_recruiter_tools(container, context)
    tool_node = ToolNode(tools)

    # 1. Nodo agente principal (ReAct)
    async def recruiter_agent_node(state: RRHHState) -> dict:
        user_id = state.get("user_id", "recruiter_default")
        thread_id = state.get("thread_id", "default_thread")
        context["user_id"] = user_id
        context["thread_id"] = thread_id
        if state.get("job_post"):
            context["job_post"] = state["job_post"]

        messages = state.get("messages", [])

        # Vía Rápida: Si la tool que acaba de ejecutarse es 'set_job_requirements',
        # el mensaje de confirmación detallado ya fue generado con exactitud por la tool.
        # Retornar directamente como AIMessage sin incurrir en una segunda llamada de 4-5s a Azure OpenAI.
        if messages and (isinstance(messages[-1], ToolMessage) or getattr(messages[-1], "type", None) == "tool") and getattr(messages[-1], "name", None) == "set_job_requirements":
            logger.info("⚡ Vía Rápida: retornando confirmación de requerimientos sin llamada adicional al LLM.")
            response = AIMessage(content=str(messages[-1].content))
            result = {"messages": [response]}
            if "job_post" in context:
                result["job_post"] = context["job_post"]
            return result

        llm = container.llm_provider.get_chat_model(temperature=0.0)
        llm_with_tools = llm.bind_tools(tools)

        sanitized_messages = sanitize_message_history(messages)
        system_msg = SystemMessage(content=SYSTEM_RECRUITER_PROMPT)
        full_messages = [system_msg] + sanitized_messages

        response = await llm_with_tools.ainvoke(full_messages)

        result = {"messages": [response]}
        # Sincronizar objetos actualizados por las tools al estado de LangGraph
        if "job_post" in context:
            result["job_post"] = context["job_post"]
        if "technical_report" in context:
            result["technical_report"] = context["technical_report"]
        if "relevant_candidates" in context:
            result["relevant_candidates"] = context["relevant_candidates"]
        if "current_cv_id" in context:
            result["current_cv_id"] = context["current_cv_id"]

        return result

    # 2. Agregar nodos al builder
    builder.add_node("input_grounding", input_grounding_node)
    builder.add_node("safe_reply", safe_reply_node)
    builder.add_node("recruiter_agent", recruiter_agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("judge_agent", judge_agent_node)
    builder.add_node("finalize", finalize_node)

    # 3. Transiciones y enrutamiento
    builder.add_edge(START, "input_grounding")

    def route_after_input(state: RRHHState) -> str:
        if state.get("is_safe") is False:
            return "safe_reply"
        return "recruiter_agent"

    builder.add_conditional_edges(
        "input_grounding",
        route_after_input,
        {"safe_reply": "safe_reply", "recruiter_agent": "recruiter_agent"}
    )
    builder.add_edge("safe_reply", END)

    def route_after_agent(state: RRHHState) -> str:
        messages = state.get("messages", [])
        last_msg = messages[-1] if messages else None
        if last_msg and getattr(last_msg, "tool_calls", None):
            return "tools"

        # Si hay un reporte técnico recién generado que aún no ha sido auditado por el juez
        report = state.get("technical_report")
        verdict = state.get("grounding_verdict")
        if report and not verdict:
            return "judge_agent"

        return "finalize"

    builder.add_conditional_edges(
        "recruiter_agent",
        route_after_agent,
        {"tools": "tools", "judge_agent": "judge_agent", "finalize": "finalize"}
    )

    builder.add_edge("tools", "recruiter_agent")
    builder.add_edge("judge_agent", "finalize")

    builder.add_edge("finalize", END)

    saver = checkpointer or container.checkpointer_provider.get_checkpointer()
    return builder.compile(checkpointer=saver)

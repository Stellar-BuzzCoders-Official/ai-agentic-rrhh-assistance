import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage

from src.application.agent.state import RRHHState
from src.application.agent.prompts import SYSTEM_RECRUITER_PROMPT
from src.application.agent.tools.recruiter_tools import create_recruiter_tools
from src.application.agent.nodes.input_grounding import input_grounding_node
from src.application.agent.nodes.judge_agent import judge_agent_node
from src.application.agent.nodes.finalize import finalize_node, safe_reply_node
from src.config.container import Container

logger = logging.getLogger(__name__)


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

        llm = container.llm_provider.get_chat_model(temperature=0.0)
        llm_with_tools = llm.bind_tools(tools)

        messages = state.get("messages", [])
        system_msg = SystemMessage(content=SYSTEM_RECRUITER_PROMPT)
        full_messages = [system_msg] + messages

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
        if report and (not verdict or (not verdict.approved and state.get("grounding_retries", 0) < 2)):
            return "judge_agent"

        return "finalize"

    builder.add_conditional_edges(
        "recruiter_agent",
        route_after_agent,
        {"tools": "tools", "judge_agent": "judge_agent", "finalize": "finalize"}
    )

    builder.add_edge("tools", "recruiter_agent")

    def route_after_judge(state: RRHHState) -> str:
        verdict = state.get("grounding_verdict")
        retries = state.get("grounding_retries", 0)
        # Si fue rechazado y no se han agotado los reintentos, regresa al agente para corregir
        if verdict and not verdict.approved and retries < 2:
            return "recruiter_agent"
        return "finalize"

    builder.add_conditional_edges(
        "judge_agent",
        route_after_judge,
        {"recruiter_agent": "recruiter_agent", "finalize": "finalize"}
    )

    builder.add_edge("finalize", END)

    saver = checkpointer or container.checkpointer_provider.get_checkpointer()
    return builder.compile(checkpointer=saver)

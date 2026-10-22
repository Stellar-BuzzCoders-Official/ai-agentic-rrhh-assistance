import pytest
from langchain_core.messages import HumanMessage
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import MemorySaver

from src.config.container import Container
from src.application.agent.graph import build_screening_graph


class ToolSupportingFakeChatModel(FakeListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


@pytest.mark.asyncio
async def test_graph_compilation_and_input_flow():
    container = Container.get_instance()
    saver = MemorySaver()

    fake_llm = ToolSupportingFakeChatModel(responses=[
        "¡Hola! He recibido los requerimientos. Por favor adjunta el CV para evaluarlo.",
    ])
    container.llm_provider.get_chat_model = lambda temperature=0.0: fake_llm

    graph = build_screening_graph(container=container, checkpointer=saver)
    assert graph is not None

    thread_id = "test-thread-42"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [HumanMessage(content="Buscamos un Ingeniero Backend con Python y FastAPI.")],
        "user_id": "test_recruiter_1",
        "thread_id": thread_id,
        "process_phase": "request_requirements",
        "job_post": None,
        "current_cv_id": None,
        "technical_report": None,
        "relevant_candidates": [],
        "grounding_verdict": None,
        "grounding_retries": 0,
        "is_safe": True,
        "safety_reason": None,
        "name_history": None,
    }

    result = await graph.ainvoke(initial_state, config=config)

    assert "client_response_payload" in result
    payload = result["client_response_payload"]
    assert "data" in payload
    assert payload["data"]["conversation_id"] == thread_id
    assert len(payload["data"]["message"]) > 0
    bot_msg = payload["data"]["message"][0]
    assert bot_msg["role"] == "assistant"
    assert bot_msg["validate"] is True

    # Verificar que el checkpointer guardó el estado del hilo
    checkpoint_state = graph.get_state(config)
    assert checkpoint_state is not None
    assert len(checkpoint_state.values.get("messages", [])) > 0


def test_sanitize_message_history_orphaned_tools():
    from langchain_core.messages import AIMessage, ToolMessage
    from src.application.agent.graph import sanitize_message_history

    # Caso: el servidor cayó mientras ejecutaba herramientas, dejando tool_calls sin respuesta
    raw_history = [
        HumanMessage(content="Evalúa estos perfiles"),
        AIMessage(content="", tool_calls=[
            {"id": "call_1", "name": "evaluate_cv", "args": {"file_id": "f1"}},
            {"id": "call_2", "name": "evaluate_cv", "args": {"file_id": "f2"}},
        ]),
        HumanMessage(content="¿Cómo van las evaluaciones?"),
    ]

    sanitized = sanitize_message_history(raw_history)

    assert len(sanitized) == 5
    assert isinstance(sanitized[0], HumanMessage)
    assert isinstance(sanitized[1], AIMessage)
    assert isinstance(sanitized[2], ToolMessage) and sanitized[2].tool_call_id == "call_1"
    assert isinstance(sanitized[3], ToolMessage) and sanitized[3].tool_call_id == "call_2"
    assert isinstance(sanitized[4], HumanMessage)
    assert "Error o interrupción" in sanitized[2].content


def test_sanitize_message_history_removes_stray_tools():
    from langchain_core.messages import ToolMessage
    from src.application.agent.graph import sanitize_message_history

    raw_history = [
        ToolMessage(content="Huérfano sin AIMessage", tool_call_id="stray_call"),
        HumanMessage(content="Hola"),
    ]

    sanitized = sanitize_message_history(raw_history)
    assert len(sanitized) == 1
    assert isinstance(sanitized[0], HumanMessage)


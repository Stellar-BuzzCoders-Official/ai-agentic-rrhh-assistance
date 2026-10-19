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

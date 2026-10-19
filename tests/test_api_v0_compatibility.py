import pytest
from httpx import AsyncClient, ASGITransport
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import MemorySaver

from app import app
from src.config.container import Container
from tests.test_graph import ToolSupportingFakeChatModel


@pytest.fixture(autouse=True)
def setup_test_container():
    Container.reset_instance_for_testing()
    container = Container.get_instance()
    container.checkpointer_provider.get_checkpointer = lambda: MemorySaver()
    fake_llm = ToolSupportingFakeChatModel(responses=[
        "Entendido. Por favor proporciona el CV del candidato para evaluarlo.",
    ])
    container.llm_provider.get_chat_model = lambda temperature=0.0: fake_llm
    return container


@pytest.mark.asyncio
async def test_legacy_screening_chat_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login legacy
        login_res = await client.post("/api/v0/auth/login", json={"username": "recruiter1", "password": "any"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. screeningChat con requerimientos
        payload = {
            "data": {
                "conversation_id": "test-legacy-conv-1",
                "process_phase": "request_requirements",
                "userID": "a8f0569a-46fd-457f-847e-e233af403114",
                "message": [
                    {"id": "msg-1", "role": "user", "content": "Necesito un Desarrollador Python Senior con experiencia en Azure"}
                ]
            }
        }
        res = await client.post("/api/v0/screeningChat", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["conversation_id"] == "test-legacy-conv-1"
        assert len(data["message"]) == 1
        bot_msg = data["message"][0]
        assert bot_msg["role"] == "assistant"
        assert bot_msg["validate"] is True

        # 3. Lista de conversaciones para el sidebar
        conv_list_res = await client.get("/api/v0/conversationsIdName/a8f0569a-46fd-457f-847e-e233af403114", headers=headers)
        assert conv_list_res.status_code == 200
        conv_list = conv_list_res.json()
        assert len(conv_list) >= 1
        assert any(c["_id"] == "test-legacy-conv-1" for c in conv_list)

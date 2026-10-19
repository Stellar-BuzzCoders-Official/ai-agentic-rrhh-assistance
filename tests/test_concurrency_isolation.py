import pytest
from httpx import AsyncClient, ASGITransport
from app import app
from src.config.container import Container
from tests.test_graph import ToolSupportingFakeChatModel
from langgraph.checkpoint.memory import MemorySaver


@pytest.fixture(autouse=True)
def setup_test_container():
    Container.reset_instance_for_testing()
    container = Container.get_instance()
    container.checkpointer_provider.get_checkpointer = lambda: MemorySaver()
    fake_llm = ToolSupportingFakeChatModel(responses=[
        "Respuesta personalizada para Reclutador A",
        "Respuesta personalizada para Reclutador B",
    ])
    container.llm_provider.get_chat_model = lambda temperature=0.0: fake_llm
    return container


@pytest.mark.asyncio
async def test_multi_user_thread_isolation():
    """
    Verifica que dos reclutadores con conversaciones independientes
    no compartan estado, IDs de conversación ni se sobreescriban (regresión del bug previo).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Reclutador 1
        headers_1 = {"Authorization": "Bearer user-recruiter-1"}
        payload_1 = {
            "data": {
                "conversation_id": "thread-user-1",
                "process_phase": "request_requirements",
                "userID": "user-recruiter-1",
                "message": [{"id": "m1", "role": "user", "content": "Puesto para DevOps AWS"}]
            }
        }
        res_1 = await client.post("/api/v0/screeningChat", json=payload_1, headers=headers_1)
        assert res_1.status_code == 200
        data_1 = res_1.json()["data"]
        assert data_1["conversation_id"] == "thread-user-1"

        # Reclutador 2
        headers_2 = {"Authorization": "Bearer user-recruiter-2"}
        payload_2 = {
            "data": {
                "conversation_id": "thread-user-2",
                "process_phase": "request_requirements",
                "userID": "user-recruiter-2",
                "message": [{"id": "m2", "role": "user", "content": "Puesto para Frontend Angular"}]
            }
        }
        res_2 = await client.post("/api/v0/screeningChat", json=payload_2, headers=headers_2)
        assert res_2.status_code == 200
        data_2 = res_2.json()["data"]
        assert data_2["conversation_id"] == "thread-user-2"

        # Comprobar que los IDs permanecieron estrictamente aislados
        assert data_1["conversation_id"] != data_2["conversation_id"]

        # Comprobar la lista de conversaciones de cada usuario
        convs_1 = await client.get("/api/v0/conversationsIdName/user-recruiter-1", headers=headers_1)
        assert convs_1.status_code == 200
        conv_ids_1 = [c["_id"] for c in convs_1.json()]
        assert "thread-user-1" in conv_ids_1
        assert "thread-user-2" not in conv_ids_1

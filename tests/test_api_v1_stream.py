import pytest
import io
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
        "¡Hola! Soy tu asistente de RRHH. Para comenzar, por favor indícame los requerimientos técnicos del puesto.",
    ])
    container.llm_provider.get_chat_model = lambda temperature=0.0: fake_llm
    return container


@pytest.mark.asyncio
async def test_v1_bulk_upload_limit():
    transport = ASGITransport(app=app)
    headers = {"Authorization": "Bearer dev-token"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Enviar 11 archivos para verificar que se rechaza por el límite de 10
        files_11 = [
            ("files", (f"cv_{i}.txt", io.BytesIO(b"CV content"), "text/plain"))
            for i in range(11)
        ]
        res = await client.post("/api/v1/files/bulk", files=files_11, headers=headers)
        assert res.status_code == 400
        assert "máximo permitido" in res.json()["detail"]

        # Enviar 3 archivos (dentro del límite)
        files_3 = [
            ("files", (f"cv_{i}.txt", io.BytesIO(f"CV content {i}".encode()), "text/plain"))
            for i in range(3)
        ]
        res_ok = await client.post("/api/v1/files/bulk", files=files_3, headers=headers)
        assert res_ok.status_code == 200
        body = res_ok.json()
        assert body["total_processed"] == 3
        assert len(body["files"]) == 3


@pytest.mark.asyncio
async def test_v1_chat_sse_stream():
    transport = ASGITransport(app=app)
    headers = {"Authorization": "Bearer dev-token"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "thread_id": "sse-test-thread",
            "message": "Hola, quiero iniciar un proceso de selección"
        }
        res = await client.post("/api/v1/chat/stream", json=payload, headers=headers)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        text_content = res.text
        assert "event: init" in text_content
        assert "event: done" in text_content

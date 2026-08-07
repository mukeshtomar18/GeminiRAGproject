import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["embedding_model"] == "gemini-embedding-2-preview"


def test_chat_requires_content(client: TestClient):
    res = client.post("/api/chat", data={"message": ""})
    assert res.status_code == 400

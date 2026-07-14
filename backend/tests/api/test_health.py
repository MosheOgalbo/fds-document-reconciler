from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # Frontend uses these flags to guide setup. Keys may be present in a
    # developer's local .env — only assert shape/types here, not secret presence.
    assert isinstance(body["gemini_configured"], bool)
    assert isinstance(body["openai_configured"], bool)
    assert isinstance(body["redis_configured"], bool)
    assert body["pinecone_configured"] is True
    assert body["token_counting"] in ("exact", "approximate")

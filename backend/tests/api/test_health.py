from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # These fields let the frontend tell the user clearly whether the
    # backend is actually configured, instead of surfacing a cryptic
    # downstream OpenAI/Pinecone auth error the first time they try
    # anything. Without a real key configured in this test environment,
    # both must correctly report False.
    assert body["gemini_configured"] is False
    assert body["openai_configured"] is False
    assert body["pinecone_configured"] is True
    assert body["token_counting"] in ("exact", "approximate")

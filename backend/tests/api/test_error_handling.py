"""
Regression tests for app.main's error handling.

These pin down two things found via manual testing (see DECISIONS.md):
1. Unhandled exceptions must never leak raw internal details to the client.
2. CORS headers must still be present on error responses — a real gap was
   found where BaseHTTPMiddleware-based middleware in the stack caused
   CORSMiddleware to skip processing responses from the global exception
   handler, which would otherwise look like a CORS failure to a browser
   instead of surfacing the actual error.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

# raise_server_exceptions=False is required here specifically: TestClient's
# default behavior re-raises server exceptions for debugging rather than
# returning the actual HTTP response, which would hide the exact bug these
# tests exist to catch.
client = TestClient(app, raise_server_exceptions=False)


def test_unhandled_exception_returns_sanitized_500():
    with patch(
        "app.application.use_cases.query_documents.execute",
        side_effect=RuntimeError("simulated internal failure with sensitive detail"),
    ):
        response = client.post(
            "/api/v1/query",
            json={"session_id": "s1", "query": "test", "document_ids": []},
        )

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "An internal error occurred. Please try again."
    assert "request_id" in body
    # The raw exception message must never reach the client.
    assert "simulated internal failure" not in response.text


def test_cors_header_present_on_unhandled_exception_response():
    with patch(
        "app.application.use_cases.query_documents.execute",
        side_effect=RuntimeError("boom"),
    ):
        response = client.post(
            "/api/v1/query",
            json={"session_id": "s1", "query": "test", "document_ids": []},
            headers={"Origin": "http://localhost:5173"},
        )

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_preflight_succeeds_without_hitting_rate_limit_first():
    """CORS must be the outermost middleware so preflight OPTIONS requests
    are answered immediately, before RateLimitMiddleware ever sees them."""
    response = client.options(
        "/api/v1/query",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"

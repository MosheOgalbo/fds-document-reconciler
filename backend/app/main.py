from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.application.dto.schemas import HealthResponse
from app.core.config import get_settings, is_gemini_configured, is_openai_configured, is_pinecone_configured
from app.infrastructure.ai.llm_gateway import get_ai_provider_name
from app.presentation.api.v1.ingest_routes import router as ingest_router
from app.presentation.api.v1.query_routes import router as query_router
from app.presentation.middleware.observability import RequestContextMiddleware
from app.presentation.middleware.rate_limit import RateLimitMiddleware

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("fds_platform.errors")

app = FastAPI(
    title="FDS AI Platform",
    description="Enterprise GenAI platform for Functional Design Spec comparison, RAG chat, and executive summaries.",
    version="1.0.0",
)

# Middleware order matters: Starlette applies the LAST-added middleware as
# the OUTERMOST layer, so it must be listed here in innermost-to-outermost
# order. CORS is added last (= outermost) deliberately — it must see every
# request first (to handle preflight OPTIONS immediately) and every
# response last (to attach CORS headers even to error/429 responses from
# the layers below it). Getting this backwards would let RateLimitMiddleware
# reject a CORS preflight request before it ever got a CORS header.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to specific origins in production (see README)
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router)
app.include_router(ingest_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Domain-level errors (bad input, parsing failures, etc.) are already
    handled cleanly at the route level as 4xx responses. This catches
    everything else — OpenAI/Pinecone SDK errors, timeouts, bugs — so the
    client never sees a raw stack trace or internal exception message,
    while the full exception is still logged server-side against the
    request_id for debugging.

    CORS header is attached manually here rather than relying on
    CORSMiddleware alone: verified via testing that when a
    BaseHTTPMiddleware-based middleware (RateLimitMiddleware /
    RequestContextMiddleware, both in this stack) is on the request path,
    an exception caught by this handler can bypass CORSMiddleware's normal
    response processing — a known Starlette interaction. Without this, a
    browser would report a CORS error instead of surfacing the actual 500,
    hiding the real problem from the frontend at exactly the moment good
    error info matters most.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("Unhandled exception for request_id=%s", request_id)
    response = JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again.", "request_id": request_id},
    )
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    return response


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    from app.core.tokens import using_exact_counting

    return HealthResponse(
        status="ok",
        version=app.version,
        ai_provider=get_ai_provider_name(),
        gemini_configured=is_gemini_configured(settings),
        openai_configured=is_openai_configured(settings),
        pinecone_configured=is_pinecone_configured(settings),
        token_counting="exact" if using_exact_counting() else "approximate",
    )

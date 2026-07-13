from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.application.dto.schemas import QueryRequest, QueryResponse
from app.application.use_cases import query_documents
from app.domain.exceptions.errors import ConfigurationError, DomainError

router = APIRouter(prefix="/api/v1", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """
    Unified entrypoint for all four chat/compare/summary workflows. The
    Router Agent inside the graph decides which path runs — the API
    surface itself stays a single endpoint, per Clean Architecture (no
    business branching in the controller).
    """
    try:
        return await query_documents.execute(request)
    except ConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except DomainError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception:
        # Cloud LLMs may transiently 429/503. Don't surface internals.
        raise HTTPException(
            status_code=503,
            detail="AI provider is temporarily unavailable (rate limit or service outage). Please try again in a moment.",
        )

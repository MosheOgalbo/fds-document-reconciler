from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    session_id: str = Field(..., description="Client-generated session id for conversation memory")
    query: str = Field(..., min_length=1, max_length=4000)
    document_ids: list[str] = Field(default_factory=list, description="1 doc = single chat, 2 docs = cross/compare")


class QueryResponse(BaseModel):
    request_id: str
    intent: str
    answer: str
    citations: list[dict[str, Any]]
    comparison: Optional[dict[str, Any]] = Field(
        default=None, description="Present for compare_documents/executive_summary: {missing, diff, match}"
    )
    executive_summary: Optional[dict[str, Any]] = None
    is_grounded: bool
    confidence: float
    warnings: list[str] = Field(default_factory=list)
    agent_trace: list[str] = Field(default_factory=list)


class IngestResponse(BaseModel):
    document_id: str
    document_name: str
    version: str
    chunks_created: int
    parent_chunks: int
    child_chunks: int


class HealthResponse(BaseModel):
    status: str
    version: str
    ai_provider: str = "none"
    gemini_configured: bool = False
    openai_configured: bool = False
    pinecone_configured: bool = False
    redis_configured: bool = False
    token_counting: str  # "exact" (tiktoken) or "approximate" (fallback)

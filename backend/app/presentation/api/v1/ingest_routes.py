from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.application.dto.schemas import IngestResponse
from app.application.use_cases import ingest_document
from app.domain.exceptions.errors import ConfigurationError, DomainError, EmbeddingRateLimitError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ingest"])

_UPLOAD_DIR = Path("data/uploads")
_ALLOWED_SUFFIXES = {".pdf", ".docx", ".dotx"}


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    document_name: str = Form(...),
    version: str = Form(...),
) -> IngestResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = _UPLOAD_DIR / f"{uuid.uuid4()}{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        return await ingest_document.execute(str(dest), document_name, version)
    except ConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except EmbeddingRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Embedding rate limit exceeded. Wait 1–2 minutes, then ingest one document at a time."
                ),
            ) from e
        logger.exception("Ingest HTTP error from embedding provider")
        raise HTTPException(
            status_code=503,
            detail=f"Embedding service error (HTTP {e.response.status_code}). Please try again shortly.",
        ) from e
    except DomainError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception:
        logger.exception("Ingest failed with unexpected error")
        raise HTTPException(
            status_code=503,
            detail="Ingestion failed unexpectedly. Check backend logs and try again in a minute.",
        )
    finally:
        dest.unlink(missing_ok=True)

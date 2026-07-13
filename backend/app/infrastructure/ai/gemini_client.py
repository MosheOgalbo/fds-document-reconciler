"""
Google Gemini gateway — free-tier cloud models via Google AI Studio API key.
No local model install required.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
import asyncio

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
_GEMINI_SEMAPHORE = asyncio.Semaphore(1)


def _retry_backoff_seconds(attempt: int, retry_after: str | None, cap: int = 60) -> int:
    if retry_after and retry_after.isdigit():
        return min(int(retry_after), cap)
    return min(2**attempt, cap)


def _extract_json_text(raw: str) -> str:
    content = raw.strip()
    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0]
    match = re.search(r"\{[\s\S]*\}", content)
    return match.group(0) if match else content


class GeminiGateway:
    def __init__(self):
        self._settings = get_settings()

    @property
    def _api_key(self) -> str:
        return self._settings.gemini_api_key

    def _resolve_chat_model(self, model_tier: str) -> str:
        if model_tier == "fast" and self._settings.gemini_fast_model:
            return self._settings.gemini_fast_model
        return self._settings.gemini_flash_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings.

        Uses batchEmbedContents to avoid per-chunk QPM limits during ingestion.
        """
        if not texts:
            return []

        model = self._settings.gemini_embedding_model
        url = f"{_GEMINI_BASE}/models/{model}:batchEmbedContents"
        headers = {"x-goog-api-key": self._api_key}

        out: list[list[float]] = []
        batch_size = 20
        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                payload = {
                    "requests": [
                        {"model": f"models/{model}", "content": {"parts": [{"text": t}]}}
                        for t in batch
                    ]
                }
                last_exc: Exception | None = None
                for attempt in range(self._settings.max_retries):
                    try:
                        async with _GEMINI_SEMAPHORE:
                            response = await client.post(url, headers=headers, json=payload)
                        response.raise_for_status()
                        data = response.json()
                        out.extend([e["values"] for e in data.get("embeddings", [])])
                        # Gentle pacing for free-tier rate limits.
                        await asyncio.sleep(1.0)
                        break
                    except httpx.HTTPStatusError as e:
                        last_exc = e
                        status = e.response.status_code
                        if status in (429, 500, 502, 503, 504):
                            backoff = _retry_backoff_seconds(attempt, e.response.headers.get("retry-after"), cap=60)
                            logger.warning(
                                "Gemini embed retry %d/%d (status=%s) in %ss",
                                attempt + 1,
                                self._settings.max_retries,
                                status,
                                backoff,
                            )
                            await asyncio.sleep(backoff)
                            continue
                        raise
                else:
                    raise last_exc or RuntimeError("Gemini embedding failed")
        return out

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        schema_name: str = "response",
        temperature: float = 0.1,
        model_tier: str = "smart",
    ) -> dict[str, Any]:
        model = self._resolve_chat_model(model_tier)
        schema_hint = f"\n\nReturn ONLY valid JSON matching schema '{schema_name}':\n{json.dumps(json_schema)}"
        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": f"{user_prompt}{schema_hint}"}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }
        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            last_exc: Exception | None = None
            for attempt in range(self._settings.max_retries):
                try:
                    async with _GEMINI_SEMAPHORE:
                        response = await client.post(
                            f"{_GEMINI_BASE}/models/{model}:generateContent",
                            headers={"x-goog-api-key": self._api_key},
                            json=body,
                        )
                    response.raise_for_status()
                    payload = response.json()
                    # Gentle pacing for free-tier rate limits.
                    await asyncio.sleep(0.4)
                    break
                except httpx.HTTPStatusError as e:
                    last_exc = e
                    status = e.response.status_code
                    if status in (429, 500, 502, 503, 504):
                        backoff = _retry_backoff_seconds(attempt, e.response.headers.get("retry-after"), cap=60)
                        logger.warning(
                            "Gemini chat retry %d/%d (status=%s) in %ss",
                            attempt + 1,
                            self._settings.max_retries,
                            status,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    raise
            else:
                raise last_exc or RuntimeError("Gemini chat failed")

        candidates = payload.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        parts = candidates[0].get("content", {}).get("parts") or []
        text = parts[0].get("text", "") if parts else ""
        return json.loads(_extract_json_text(text))

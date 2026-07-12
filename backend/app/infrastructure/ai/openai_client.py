"""
Thin wrapper around the OpenAI SDK. Centralizes:
  - TIERED model selection: a "fast" (small/cheap) model handles the
    user's first-touch interaction (intent routing) and lightweight
    housekeeping (conversation summarization); a "smart" (larger/more
    capable) model performs the actual required work — comparison,
    executive summary, grounded response generation, and grounding
    validation. This keeps latency/cost low on the high-volume, low-
    complexity routing step while reserving the expensive model calls
    for the step that actually has to reason carefully over retrieved
    document content and produce cited, structured output.
  - retry policy with exponential backoff
  - request timeout
  - structured-output enforcement via response_format=json_schema

Kept separate from the agents themselves so agents depend on an interface,
not the SDK directly — makes agents unit-testable with a fake client.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal, Optional

from openai import AsyncOpenAI, APITimeoutError, APIError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ModelTier = Literal["fast", "smart"]

# Ordered by preference; first available on the account wins. This is what
# lets the system self-upgrade to GPT-5 the moment the API key has access,
# with zero code change, per the assignment's "GPT-5 when available,
# otherwise GPT-4.1" instruction — applied independently for each tier.
_MODEL_CHAINS: dict[ModelTier, list[str]] = {
    "fast": ["gpt-5-mini", "gpt-4.1-mini", "gpt-4.1-nano"],
    "smart": ["gpt-5", "gpt-4.1"],
}


class OpenAIGateway:
    def __init__(self):
        self._settings = get_settings()
        self._client: Optional[AsyncOpenAI] = None
        self._resolved_models: dict[ModelTier, str] = {}

    @property
    def client(self) -> AsyncOpenAI:
        # Lazily constructed: importing/instantiating this class must not
        # require a real API key (e.g. during test collection or app
        # startup without secrets configured). The key is only required
        # once an actual API call is made.
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._settings.openai_api_key or "not-configured",
                timeout=self._settings.request_timeout_seconds,
            )
        return self._client

    async def resolve_model(self, tier: ModelTier = "smart") -> str:
        if tier in self._resolved_models:
            return self._resolved_models[tier]
        try:
            models = await self.client.models.list()
            available = {m.id for m in models.data}
            for candidate in _MODEL_CHAINS[tier]:
                if candidate in available:
                    self._resolved_models[tier] = candidate
                    logger.info("Resolved '%s' tier model: %s", tier, candidate)
                    return candidate
        except Exception as e:
            logger.warning("Model list check failed (%s), falling back to configured default", e)
        fallback = self._settings.openai_model if tier == "smart" else self._settings.openai_fast_model
        self._resolved_models[tier] = fallback
        return fallback

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._with_retry(
            lambda: self.client.embeddings.create(
                model=self._settings.openai_embedding_model, input=texts
            )
        )
        return [d.embedding for d in response.data]

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        schema_name: str = "response",
        temperature: float = 0.1,
        model_tier: ModelTier = "smart",
    ) -> dict[str, Any]:
        """Structured-output call: LLM is constrained to emit valid JSON matching json_schema.
        `model_tier` picks which resolved model chain to use — 'fast' for
        routing/classification/housekeeping, 'smart' for the actual
        comparison/summary/response/validation work."""
        model = await self.resolve_model(model_tier)
        response = await self._with_retry(
            lambda: self.client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": schema_name, "schema": json_schema, "strict": True},
                },
            )
        )
        import json

        return json.loads(response.choices[0].message.content)

    async def _with_retry(self, call, max_retries: Optional[int] = None):
        retries = max_retries if max_retries is not None else self._settings.max_retries
        last_error: Optional[Exception] = None
        for attempt in range(retries):
            try:
                return await call()
            except (APITimeoutError, APIError) as e:
                last_error = e
                backoff = min(2**attempt, 10)
                logger.warning("OpenAI call failed (attempt %d/%d): %s — retrying in %ds", attempt + 1, retries, e, backoff)
                await asyncio.sleep(backoff)
        raise last_error  # type: ignore[misc]

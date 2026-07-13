"""Select the configured cloud LLM provider (Gemini preferred for free tier)."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol


class LLMGateway(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        schema_name: str = "response",
        temperature: float = 0.1,
        model_tier: str = "smart",
    ) -> dict[str, Any]: ...


@lru_cache
def get_llm_gateway() -> LLMGateway:
    from app.core.config import get_settings, is_gemini_configured, is_openai_configured, is_bedrock_configured

    settings = get_settings()
    if is_gemini_configured(settings):
        from app.infrastructure.ai.gemini_client import GeminiGateway

        return GeminiGateway()
    if is_openai_configured(settings):
        from app.infrastructure.ai.openai_client import OpenAIGateway

        return OpenAIGateway()
    if is_bedrock_configured(settings):
        from app.infrastructure.ai.bedrock_client import BedrockGateway

        return BedrockGateway()
    raise RuntimeError("No LLM provider configured. Set GEMINI_API_KEY in backend/.env")


def get_ai_provider_name() -> str:
    from app.core.config import get_settings, is_gemini_configured, is_openai_configured, is_bedrock_configured

    settings = get_settings()
    if is_gemini_configured(settings):
        return "gemini"
    if is_openai_configured(settings):
        return "openai"
    if is_bedrock_configured(settings):
        return "bedrock"
    return "none"

"""
Centralized configuration. Everything that varies between environments
(local/dev/staging/prod) comes from env vars — never hardcoded, per the
assignment's security requirements.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Gemini (free cloud tier — preferred) ---
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_flash_model: str = Field(default="gemini-3.5-flash", alias="GEMINI_FLASH_MODEL")
    gemini_fast_model: str = Field(default="gemini-3.1-flash-lite", alias="GEMINI_FAST_MODEL")
    gemini_embedding_model: str = Field(default="gemini-embedding-2", alias="GEMINI_EMBEDDING_MODEL")

    # --- OpenAI (optional fallback) ---
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1", alias="OPENAI_MODEL")
    openai_fast_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_FAST_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-3-large", alias="OPENAI_EMBEDDING_MODEL")

    # --- Bedrock (optional fallback) ---
    aws_bearer_token_bedrock: str = Field(default="", alias="AWS_BEARER_TOKEN_BEDROCK")
    embedding_model: str = Field(default="amazon.titan-embed-text-v2:0", alias="EMBEDDING_MODEL")
    generation_model: str = Field(default="amazon.nova-lite-v1:0", alias="GENERATION_MODEL")
    small_generative_model: str = Field(default="amazon.nova-micro-v1:0", alias="SMALL_GENERATIVE_MODEL")
    aws_access_key: str = Field(default="", alias="AWS_ACCESS_KEY")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")

    # --- Pinecone ---
    pinecone_api_key: str = Field(default="mock_pinecone_key", alias="PINECONE_API_KEY")
    pinecone_index: str = Field(default="fds-documents", alias="PINECONE_INDEX")
    pinecone_cloud: str = Field(default="aws", alias="PINECONE_CLOUD")
    pinecone_region: str = Field(default="us-east-1", alias="PINECONE_REGION")

    # --- API ---
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- RAG tuning ---
    chunk_size_tokens: int = Field(default=400, alias="CHUNK_SIZE_TOKENS")
    chunk_overlap_tokens: int = Field(default=60, alias="CHUNK_OVERLAP_TOKENS")
    parent_chunk_size_tokens: int = Field(default=1600, alias="PARENT_CHUNK_SIZE_TOKENS")
    retrieval_top_k: int = Field(default=20, alias="RETRIEVAL_TOP_K")
    rerank_top_n: int = Field(default=6, alias="RERANK_TOP_N")
    grounding_confidence_threshold: float = Field(default=0.55, alias="GROUNDING_CONFIDENCE_THRESHOLD")

    # --- Security / resilience ---
    request_timeout_seconds: int = Field(default=120, alias="REQUEST_TIMEOUT_SECONDS")
    rate_limit_requests_per_minute: int = Field(default=60, alias="RATE_LIMIT_RPM")
    max_retries: int = Field(default=6, alias="MAX_RETRIES")

    # --- Context engineering ---
    max_context_tokens: int = Field(default=12000, alias="MAX_CONTEXT_TOKENS")
    conversation_summary_trigger_turns: int = Field(default=8, alias="CONVERSATION_SUMMARY_TRIGGER_TURNS")


@lru_cache
def get_settings() -> Settings:
    return Settings()


_PLACEHOLDER_VALUES = {
    "",
    "sk-your-key-here",
    "your-pinecone-key-here",
    "mock_pinecone_key",
    "your-gemini-key-here",
}


def is_gemini_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(s.gemini_api_key) and s.gemini_api_key not in _PLACEHOLDER_VALUES


def is_openai_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(s.openai_api_key) and s.openai_api_key not in _PLACEHOLDER_VALUES


def is_bedrock_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(s.aws_access_key and s.aws_secret_access_key)


def is_pinecone_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    if s.pinecone_api_key == "mock_pinecone_key":
        return True
    return bool(s.pinecone_api_key) and s.pinecone_api_key not in _PLACEHOLDER_VALUES


def is_llm_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return is_gemini_configured(s) or is_openai_configured(s) or is_bedrock_configured(s)


def require_ai_services() -> None:
    """Fail fast with a clear message when API keys are missing or still placeholders."""
    from app.domain.exceptions.errors import ConfigurationError

    if not is_llm_configured():
        raise ConfigurationError(
            "GEMINI_API_KEY not configured. Get a free key at https://aistudio.google.com/apikey "
            "and set it in backend/.env (copy from backend/.env.example)."
        )

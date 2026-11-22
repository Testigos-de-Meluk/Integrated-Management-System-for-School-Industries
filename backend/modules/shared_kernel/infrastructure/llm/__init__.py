"""The AI provider shared by every module (Singleton)."""

from functools import lru_cache

from django.conf import settings

from modules.shared_kernel.ports.outbound.language_model import LanguageModel

from .openai_compatible import OpenAICompatibleLanguageModel


@lru_cache(maxsize=1)
def language_model() -> LanguageModel:
    return OpenAICompatibleLanguageModel(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        session_header=settings.LLM_SESSION_HEADER,
    )

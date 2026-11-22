"""Outbound port: a large language model that answers with JSON (AI features, FR-02-05).

Callers must never send personal data (names, emails, phones, NITs) through this port.
"""

from abc import ABC, abstractmethod
from typing import Any


class LanguageModelError(Exception):
    """The model is not configured, did not answer in time or answered something unusable."""


class LanguageModel(ABC):
    @property
    @abstractmethod
    def available(self) -> bool:
        """``False`` when no provider is configured: AI features are hidden."""

    @abstractmethod
    def complete_json(self, system: str, user: str, max_tokens: int = 1500) -> dict[str, Any]:
        """Returns the JSON object the model answered. Raises ``LanguageModelError``."""

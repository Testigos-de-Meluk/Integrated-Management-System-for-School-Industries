"""``LanguageModel`` adapter for any OpenAI-compatible chat API (OpenRouter by default).

Switching provider or model only means changing ``LLM_BASE_URL``, ``LLM_API_KEY`` and
``LLM_MODEL`` in ``.env``. Uses the standard library HTTP client: no extra dependency.

Some providers route by conversation and require a session header (OpenCode Go:
``x-opencode-session``). Set ``LLM_SESSION_HEADER`` to that header name: every call is an
independent conversation, so each one sends a new ``ses_<random>`` id.
"""

import json
import logging
import re
import secrets
import urllib.error
import urllib.request
from typing import Any

from modules.shared_kernel.ports.outbound.language_model import LanguageModel, LanguageModelError

logger = logging.getLogger("imsi.llm")

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_object(text: str) -> dict[str, Any]:
    """Models sometimes wrap the JSON in fences or add words around it."""
    cleaned = _FENCE.sub("", (text or "").strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise LanguageModelError("The model did not answer with a JSON object.")
    try:
        value = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as error:
        raise LanguageModelError("The model answered invalid JSON.") from error
    if not isinstance(value, dict):
        raise LanguageModelError("The model did not answer with a JSON object.")
    return value


def _provider_message(error: urllib.error.HTTPError) -> str:
    """The ``error.message`` of an OpenAI-style error body (it never contains the API key)."""
    try:
        raw = error.read().decode(errors="replace")
    except (AttributeError, OSError):
        raw = ""
    try:
        message = json.loads(raw or "{}").get("error", {}).get("message") or ""
    except (ValueError, AttributeError):
        message = raw  # not JSON, e.g. a firewall page ("error code: 1010")
    return " ".join(str(message).split())[:300] or "(no message)"


class OpenAICompatibleLanguageModel(LanguageModel):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 20,
        session_header: str = "",
    ) -> None:
        self._session_header = session_header.strip()
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    @property
    def available(self) -> bool:
        return bool(self._api_key and self._model)

    def complete_json(self, system: str, user: str, max_tokens: int = 1500) -> dict[str, Any]:
        if not self.available:
            raise LanguageModelError("No AI provider is configured.")
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},  # ignored by models without support
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Title": "IMSI",
            # Firewalls in front of some providers (Cloudflare, error 1010) block the default
            # "Python-urllib" user agent.
            "User-Agent": "IMSI/1.0 (Industrias Escolares)",
        }
        if self._session_header:
            headers[self._session_header] = f"ses_{secrets.token_hex(12)}"
        request = urllib.request.Request(
            self._url, data=json.dumps(body).encode(), method="POST", headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            # Never log the request: it carries the API key in its headers. The provider's own
            # error message explains the cause (unknown model, privacy settings, rate limit…).
            logger.warning("AI provider answered HTTP %s: %s", error.code, _provider_message(error))
            raise LanguageModelError(f"AI provider answered HTTP {error.code}.") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            logger.warning("AI provider unreachable: %s", type(error).__name__)
            raise LanguageModelError("AI provider unreachable.") from error

        try:
            choice = payload["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            logger.warning("AI provider sent an unexpected response shape")
            raise LanguageModelError("Unexpected AI provider response.") from error
        try:
            return parse_json_object(content)
        except LanguageModelError:
            # e.g. finish_reason "length": a reasoning model spent the tokens before answering.
            logger.warning(
                "AI answer was not usable JSON (finish_reason=%s, %s chars)",
                choice.get("finish_reason"),
                len(content or ""),
            )
            raise

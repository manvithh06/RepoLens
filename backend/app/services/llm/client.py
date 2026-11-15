"""The one place that knows how to reach a language model.

With LLM_BASE_URL set, any OpenAI-compatible chat endpoint is used (Groq by default in
production). Without it, Hugging Face Inference Providers are used as before. Provider
errors become AppErrors that say what actually went wrong, and only errors that can
clear up on their own (429, 5xx, timeouts) are retried, once.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

from huggingface_hub import AsyncInferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError

from app.core.config import Settings
from app.core.errors import AppError
from app.core.limits import (
    COMPACT_BUDGET,
    HF_BUDGET,
    LLM_MAX_RETRY_WAIT_SECONDS,
    LLM_RETRY_WAIT_SECONDS,
    LLM_TIMEOUT_SECONDS,
    LLMBudget,
)
from app.services.llm.errors import (
    LLMAuthFailed,
    LLMBadOutput,
    LLMModelUnavailable,
    LLMNotConfigured,
    LLMQuotaExhausted,
    LLMRateLimited,
    LLMRequestRejected,
    LLMUnavailable,
)

logger = logging.getLogger(__name__)


def _unavailable() -> LLMUnavailable:
    return LLMUnavailable("The AI provider did not respond.")


HF_DEFAULT_MODEL = "openai/gpt-oss-120b"
# A Groq production model on the free plan (console.groq.com/docs/models).
GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"
GROQ_HOST = "api.groq.com"

Sleep = Callable[[float], Awaitable[None]]


class LLMClient(Protocol):
    model: str

    async def complete(self, system: str, user: str, max_tokens: int) -> str: ...


def budget_of(client: LLMClient) -> LLMBudget:
    return getattr(client, "budget", HF_BUDGET)


def _retry_after(error: HfHubHTTPError, default: float) -> float:
    """Seconds from a Retry-After header, or the default when absent or a date."""
    value = error.response.headers.get("retry-after")
    try:
        return max(float(value), 0.0) if value is not None else default
    except ValueError:
        return default


def _error_detail(error: HfHubHTTPError) -> tuple[str, str]:
    """The provider's error code and message, read only to classify the error."""
    try:
        body = error.response.json()
    except Exception:  # noqa: BLE001 - any unreadable body is just unknown
        return "", ""
    detail = body.get("error") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        return str(detail.get("code") or ""), str(detail.get("message") or "")
    return "", str(detail or "")


class ChatClient:
    """Chat completion with JSON replies, one retry and truthful errors."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        provider: str = "auto",
        budget: LLMBudget = HF_BUDGET,
        extra_body: dict[str, Any] | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.model = model
        self.budget = budget
        self._api_key = api_key
        self._base_url = base_url
        self._provider = provider
        self._extra_body = extra_body or {}
        # JSON mode on OpenAI-compatible endpoints, off if the model rejects it.
        self._json_mode = bool(base_url)
        self._sleep = sleep
        self._slots = asyncio.Semaphore(budget.concurrency)

    def _client(self) -> AsyncInferenceClient:
        if self._base_url:
            return AsyncInferenceClient(
                base_url=self._base_url,
                api_key=self._api_key,
                timeout=LLM_TIMEOUT_SECONDS,
            )
        return AsyncInferenceClient(
            model=self.model,
            provider=self._provider,  # type: ignore[arg-type]
            token=self._api_key,
            timeout=LLM_TIMEOUT_SECONDS,
        )

    async def _call(self, system: str, user: str, max_tokens: int) -> str:
        options: dict[str, Any] = {}
        if self._base_url:
            options["model"] = self.model
            if self._extra_body:
                options["extra_body"] = self._extra_body
        if self._json_mode:
            options["response_format"] = {"type": "json_object"}
        async with self._client() as client:
            response = await client.chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
                **options,
            )
        content = response.choices[0].message.content if response.choices else None
        return content or ""

    async def complete(self, system: str, user: str, max_tokens: int) -> str:
        async with self._slots:
            retried = False
            while True:
                try:
                    return await self._call(system, user, max_tokens)
                except Exception as raw:  # noqa: BLE001 - classified below
                    failure = classify(raw)
                    # Log the status and class only: bodies can echo the request.
                    logger.warning(
                        "LLM call failed: %s (status %s)",
                        type(raw).__name__,
                        failure.status,
                    )
                if failure.json_mode_refused and self._json_mode:
                    # This model has no JSON mode: the prompt already asks for JSON.
                    self._json_mode = False
                    continue
                wait = failure.retry_after
                if retried or wait is None or wait > LLM_MAX_RETRY_WAIT_SECONDS:
                    raise failure.error from None
                retried = True
                await self._sleep(wait)


@dataclass(frozen=True)
class Failure:
    error: AppError
    status: int | None = None
    retry_after: float | None = None  # None: do not retry
    json_mode_refused: bool = False


def classify(raw: Exception) -> Failure:
    """Turn a provider exception into the error to show and whether to retry."""
    if isinstance(raw, (InferenceTimeoutError, TimeoutError)):
        return Failure(_unavailable(), retry_after=LLM_RETRY_WAIT_SECONDS)
    if not isinstance(raw, HfHubHTTPError) or raw.response is None:
        return Failure(_unavailable(), retry_after=LLM_RETRY_WAIT_SECONDS)

    status = raw.response.status_code
    code, message = _error_detail(raw)
    if status in (401, 403):
        return Failure(LLMAuthFailed("The AI provider rejected the API key."), status)
    if status == 402:
        return Failure(
            LLMQuotaExhausted(
                "The AI provider's credit for this deployment is used up."
            ),
            status,
        )
    if status == 429:
        return Failure(
            LLMRateLimited(
                "The AI provider is rate limiting requests. Try again in a minute."
            ),
            status,
            retry_after=_retry_after(raw, LLM_RETRY_WAIT_SECONDS),
        )
    if status >= 500:
        return Failure(
            _unavailable(),
            status,
            retry_after=_retry_after(raw, LLM_RETRY_WAIT_SECONDS),
        )
    if status == 404:
        return Failure(
            LLMModelUnavailable("The AI provider does not offer the configured model."),
            status,
        )
    if status == 413:
        return Failure(
            LLMRequestRejected(
                "This request was too large for the AI provider's limits."
            ),
            status,
        )
    if status == 400 and code == "json_validate_failed":
        return Failure(
            LLMBadOutput("The language model returned an unreadable answer."), status
        )
    return Failure(
        LLMRequestRejected("The AI provider could not handle this request."),
        status,
        json_mode_refused=status == 400 and "response_format" in message,
    )


def _is_groq(base_url: str) -> bool:
    host = urlparse(base_url).hostname or ""
    return host == GROQ_HOST or host.endswith("." + GROQ_HOST)


def build_client(settings: Settings, sleep: Sleep = asyncio.sleep) -> ChatClient:
    """Build the configured client, or raise LLMNotConfigured."""
    base_url = settings.llm_base_url.strip().rstrip("/")
    key = settings.llm_api_key.get_secret_value().strip()
    model = settings.llm_model.strip()

    if not base_url:
        # Hugging Face, unchanged: LLM_API_KEY if it is a Hugging Face token, else
        # HF_TOKEN. Another provider's key (say GROQ_API_KEY) is never sent to Hugging Face.
        key = key if key.startswith("hf_") else ""
        key = key or settings.hf_token.get_secret_value().strip()
        if not key:
            raise LLMNotConfigured("AI features are not configured on this server.")
        return ChatClient(
            model=model or HF_DEFAULT_MODEL,
            api_key=key,
            provider=settings.hf_provider,
            sleep=sleep,
        )

    # An HF token is only ever sent to Hugging Face, never to another provider.
    if not key and urlparse(base_url).hostname in ("router.huggingface.co",):
        key = settings.hf_token.get_secret_value().strip()
    groq = _is_groq(base_url)
    model = model or (GROQ_DEFAULT_MODEL if groq else "")
    if not key or not model:
        logger.warning(
            "LLM_BASE_URL is set but %s is missing",
            "the API key" if not key else "LLM_MODEL",
        )
        raise LLMNotConfigured("AI features are not configured on this server.")
    extra: dict[str, Any] = {}
    if groq and model.startswith("openai/gpt-oss"):
        # Keep reasoning short and out of the reply so the token budget goes to JSON.
        extra = {"reasoning_effort": "low", "include_reasoning": False}
    return ChatClient(
        model=model,
        api_key=key,
        base_url=base_url,
        budget=COMPACT_BUDGET,
        extra_body=extra,
        sleep=sleep,
    )

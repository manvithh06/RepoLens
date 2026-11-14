"""A thin, capped wrapper around Hugging Face Inference chat completion."""

import asyncio
import json
import logging
import re
from typing import Any, Protocol

from huggingface_hub import AsyncInferenceClient

from app.core.config import Settings
from app.core.errors import AppError
from app.core.limits import LLM_CONCURRENCY, LLM_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class LLMNotConfigured(AppError):
    status_code = 503
    code = "llm_not_configured"


class LLMUnavailable(AppError):
    status_code = 502
    code = "llm_unavailable"


class LLMRejected(AppError):
    status_code = 502
    code = "llm_auth_failed"


class LLMBadOutput(AppError):
    status_code = 502
    code = "llm_bad_output"


class LLMClient(Protocol):
    model: str

    async def complete(self, system: str, user: str, max_tokens: int) -> str: ...


class HuggingFaceClient:
    def __init__(self, token: str, model: str, provider: str = "auto") -> None:
        self.model = model
        self._client = AsyncInferenceClient(
            model=model,
            provider=provider,  # type: ignore[arg-type]
            token=token,
            timeout=LLM_TIMEOUT_SECONDS,
        )
        self._slots = asyncio.Semaphore(LLM_CONCURRENCY)

    async def complete(self, system: str, user: str, max_tokens: int) -> str:
        async with self._slots:
            try:
                response = await self._client.chat_completion(
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.2,
                )
            except Exception as error:  # noqa: BLE001 - network and provider errors vary
                status = getattr(getattr(error, "response", None), "status_code", None)
                # Log the type only: messages can echo request details.
                logger.warning("LLM call failed: %s (%s)", type(error).__name__, status)
                if status in (401, 403):
                    raise LLMRejected(
                        "Hugging Face rejected the token. Check HF_TOKEN in "
                        "backend/.env and that it may call Inference Providers."
                    ) from None
                if status == 429:
                    raise LLMUnavailable(
                        "The language model is rate limited. Try again in a minute."
                    ) from None
                raise LLMUnavailable(
                    "The language model did not respond. Try again in a minute."
                ) from None
        content = response.choices[0].message.content if response.choices else None
        return content or ""


def build_client(settings: Settings) -> HuggingFaceClient:
    token = settings.hf_token.get_secret_value().strip()
    if not token:
        raise LLMNotConfigured(
            "The guided tour needs a Hugging Face token. Set HF_TOKEN in backend/.env "
            "and restart the backend."
        )
    return HuggingFaceClient(token, settings.hf_model, settings.hf_provider)


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def parse_json_object(text: str) -> dict[str, Any]:
    """Pull the JSON object out of a model reply. Raises LLMBadOutput if there is none."""
    cleaned = _FENCE.sub("", _THINK.sub("", text)).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise LLMBadOutput("The language model returned an unreadable answer.")
    try:
        value = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        raise LLMBadOutput(
            "The language model returned an unreadable answer."
        ) from None
    if not isinstance(value, dict):
        raise LLMBadOutput("The language model returned an unreadable answer.")
    return value

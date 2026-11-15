"""Errors from the language model, each with a code the frontend can act on."""

from app.core.errors import AppError


class LLMNotConfigured(AppError):
    status_code = 503
    code = "llm_not_configured"


class LLMAuthFailed(AppError):
    status_code = 502
    code = "llm_auth_failed"


class LLMQuotaExhausted(AppError):
    status_code = 503
    code = "llm_quota_exhausted"


class LLMRateLimited(AppError):
    status_code = 503
    code = "llm_rate_limited"


class LLMUnavailable(AppError):
    status_code = 502
    code = "llm_unavailable"


class LLMModelUnavailable(AppError):
    status_code = 502
    code = "llm_model_unavailable"


class LLMRequestRejected(AppError):
    status_code = 502
    code = "llm_request_rejected"


class LLMBadOutput(AppError):
    status_code = 502
    code = "llm_bad_output"


# Errors that mean the provider is unusable right now: stop instead of trying more files.
PROVIDER_ERRORS = (
    LLMAuthFailed,
    LLMQuotaExhausted,
    LLMRateLimited,
    LLMUnavailable,
    LLMModelUnavailable,
)

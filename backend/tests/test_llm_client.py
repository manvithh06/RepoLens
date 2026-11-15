"""The LLM client against a mocked HTTP transport. No test here touches the network."""

import asyncio
import json
import logging
from collections.abc import Callable, Iterator

import httpx2
import pytest
from huggingface_hub import set_async_client_factory
from huggingface_hub.utils._http import default_async_client_factory

from app.core.config import Settings
from app.core.limits import COMPACT_BUDGET
from app.services.llm.client import (
    GROQ_DEFAULT_MODEL,
    HF_DEFAULT_MODEL,
    ChatClient,
    build_client,
)
from app.services.llm.errors import (
    LLMAuthFailed,
    LLMNotConfigured,
    LLMQuotaExhausted,
    LLMRateLimited,
    LLMUnavailable,
)
from app.services.llm.output import ask_json
from tests.test_tour import _analyze
from tests.test_tour import api as tour_api  # noqa: F401 - fixture for groq_api

GROQ_URL = "https://api.groq.com/openai/v1"
FAKE_KEY = "gsk_" + "Qw7" * 12

Handler = Callable[[httpx2.Request], httpx2.Response]


class Recorder:
    """Answers with the given responses in order, or from a handler, and keeps requests."""

    def __init__(
        self, *responses: httpx2.Response, handler: Handler | None = None
    ) -> None:
        self.responses = list(responses)
        self.handler = handler
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self.handler(request) if self.handler else self.responses.pop(0)

    @property
    def bodies(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests]


def _reply(content: str) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 1,
            "model": GROQ_DEFAULT_MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
    )


def _error(status: int, headers: dict[str, str] | None = None, **error: str):
    return httpx2.Response(
        status, headers=headers, json={"error": {"message": "nope", **error}}
    )


@pytest.fixture
def transport() -> Iterator[Callable[[Handler], None]]:
    def install(handler: Handler) -> None:
        set_async_client_factory(
            lambda: httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        )

    yield install
    set_async_client_factory(default_async_client_factory)


class Sleeps(list[float]):
    async def __call__(self, seconds: float) -> None:
        self.append(seconds)


def _groq(sleeps: Sleeps | None = None) -> ChatClient:
    settings = Settings(
        llm_base_url=GROQ_URL, llm_api_key=FAKE_KEY, llm_model="", hf_token=""
    )
    return build_client(settings, sleep=Sleeps() if sleeps is None else sleeps)


def _run(coro):
    return asyncio.run(coro)


# ---------- configuration ----------


def test_groq_key_alias_and_default_model(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_API_KEY", "LLM_MODEL", "HF_MODEL", "HF_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_BASE_URL", GROQ_URL)
    monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)
    settings = Settings(_env_file=None)

    client = build_client(settings)
    assert settings.llm_api_key.get_secret_value() == FAKE_KEY
    assert client.model == GROQ_DEFAULT_MODEL
    assert client.budget.tour_files <= 6
    assert FAKE_KEY not in repr(settings)


def test_hf_model_alias_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_API_KEY", "GROQ_API_KEY", "LLM_MODEL", "LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HF_TOKEN", "hf_" + "x" * 30)
    monkeypatch.setenv("HF_MODEL", "some/model")
    assert build_client(Settings(_env_file=None)).model == "some/model"
    monkeypatch.delenv("HF_MODEL")
    assert build_client(Settings(_env_file=None)).model == HF_DEFAULT_MODEL


@pytest.mark.parametrize(
    "settings",
    [
        Settings(llm_base_url="", llm_api_key="", hf_token=""),
        Settings(llm_base_url=GROQ_URL, llm_api_key="", hf_token=""),
        # An HF token is never sent to a non-Hugging Face endpoint.
        Settings(llm_base_url=GROQ_URL, llm_api_key="", hf_token="hf_" + "x" * 30),
        # A Groq key is never sent to Hugging Face when LLM_BASE_URL is missing.
        Settings(llm_base_url="", llm_api_key=FAKE_KEY, hf_token=""),
        # Unknown endpoints need an explicit model.
        Settings(llm_base_url="https://llm.example/v1", llm_api_key="k", llm_model=""),
    ],
)
def test_not_configured(settings: Settings) -> None:
    with pytest.raises(LLMNotConfigured) as error:
        build_client(settings)
    assert error.value.message == "AI features are not configured on this server."


# ---------- calls ----------


def test_success_with_groq_style_output(transport) -> None:
    recorder = Recorder(_reply('```json\n{"summary": "Adds numbers."}\n```'))
    transport(recorder)

    result = _run(ask_json(_groq(), "system", "user", 400))

    assert result == {"summary": "Adds numbers."}
    request = recorder.requests[0]
    assert str(request.url) == f"{GROQ_URL}/chat/completions"
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
    body = recorder.bodies[0]
    assert body["model"] == GROQ_DEFAULT_MODEL
    assert body["max_tokens"] == 400
    assert body["response_format"] == {"type": "json_object"}
    assert body["reasoning_effort"] == "low"


def test_unreadable_reply_gets_one_repair_attempt(transport) -> None:
    recorder = Recorder(_reply("Sure! Here it is: {broken"), _reply('{"ok": true}'))
    transport(recorder)

    assert _run(ask_json(_groq(), "system", "user", 400)) == {"ok": True}
    assert len(recorder.requests) == 2
    assert "could not be read as JSON" in recorder.bodies[1]["messages"][1]["content"]


def test_model_without_json_mode_falls_back_to_prompt(transport) -> None:
    recorder = Recorder(
        _error(400, message="response_format is not supported by this model"),
        _reply('{"ok": 1}'),
    )
    transport(recorder)
    client = _groq()

    assert _run(ask_json(client, "system", "user", 400)) == {"ok": 1}
    assert "response_format" in recorder.bodies[0]
    assert "response_format" not in recorder.bodies[1]


def test_402_is_not_retried(transport, caplog: pytest.LogCaptureFixture) -> None:
    recorder = Recorder(_error(402))
    transport(recorder)
    sleeps = Sleeps()

    with caplog.at_level(logging.WARNING), pytest.raises(LLMQuotaExhausted) as error:
        _run(_groq(sleeps).complete("system", "user", 100))

    assert error.value.code == "llm_quota_exhausted"
    assert error.value.message == (
        "The AI provider's credit for this deployment is used up."
    )
    assert len(recorder.requests) == 1
    assert sleeps == []
    assert "402" in caplog.text
    assert FAKE_KEY not in caplog.text and "user" not in caplog.text


@pytest.mark.parametrize("status", [401, 403])
def test_auth_errors_are_not_retried(transport, status: int) -> None:
    recorder = Recorder(_error(status))
    transport(recorder)

    with pytest.raises(LLMAuthFailed) as error:
        _run(_groq().complete("system", "user", 100))

    assert error.value.code == "llm_auth_failed"
    assert error.value.message == "The AI provider rejected the API key."
    assert len(recorder.requests) == 1


def test_429_retries_once_honouring_retry_after(transport) -> None:
    recorder = Recorder(
        _error(429, headers={"retry-after": "3"}),
        _error(429, headers={"retry-after": "3"}),
    )
    transport(recorder)
    sleeps = Sleeps()

    with pytest.raises(LLMRateLimited) as error:
        _run(_groq(sleeps).complete("system", "user", 100))

    assert error.value.code == "llm_rate_limited"
    assert error.value.message == (
        "The AI provider is rate limiting requests. Try again in a minute."
    )
    assert len(recorder.requests) == 2
    assert sleeps == [3.0]


def test_429_then_success(transport) -> None:
    recorder = Recorder(_error(429), _reply('{"a": 1}'))
    transport(recorder)
    sleeps = Sleeps()

    assert _run(_groq(sleeps).complete("s", "u", 100)) == '{"a": 1}'
    assert len(sleeps) == 1


def test_long_retry_after_fails_at_once(transport) -> None:
    recorder = Recorder(_error(429, headers={"retry-after": "600"}))
    transport(recorder)

    with pytest.raises(LLMRateLimited):
        _run(_groq().complete("system", "user", 100))
    assert len(recorder.requests) == 1


def test_5xx_retries_once_then_unavailable(transport) -> None:
    recorder = Recorder(_error(503), _error(500))
    transport(recorder)

    with pytest.raises(LLMUnavailable) as error:
        _run(_groq().complete("system", "user", 100))
    assert error.value.message == "The AI provider did not respond."
    assert len(recorder.requests) == 2


def test_timeout_is_unavailable(transport) -> None:
    def slow(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow", request=request)

    transport(slow)
    with pytest.raises(LLMUnavailable):
        _run(_groq().complete("system", "user", 100))


# ---------- through the API ----------


@pytest.fixture
def groq_api(request: pytest.FixtureRequest, transport):
    """The API with a Groq client whose HTTP goes to the given recorder."""
    client = request.getfixturevalue("tour_api")
    from app.api.routes import repositories as repositories_route
    from app.main import app

    def use(recorder: Recorder):
        transport(recorder)
        app.dependency_overrides[repositories_route.get_llm_client] = lambda: _groq()
        return client

    return use


def test_tour_reports_exhausted_credit_without_retrying(groq_api) -> None:
    recorder = Recorder(*[_error(402) for _ in range(20)])
    api = groq_api(recorder)
    analysis_id = _analyze(api)

    response = api.post(f"/api/repositories/{analysis_id}/tour")

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "llm_quota_exhausted",
        "message": "The AI provider's credit for this deployment is used up.",
    }
    # One call per key file, none repeated, and never more files than the budget.
    assert 1 <= len(recorder.requests) <= COMPACT_BUDGET.tour_files
    assert FAKE_KEY not in response.text


def test_tour_with_groq_style_output(groq_api) -> None:
    file_reply = _reply('{"summary": "Does a thing.", "role": "module"}')
    repo_reply = _reply(
        json.dumps(
            {
                "overview": {"text": "A shop API.", "files": ["app/main.py"]},
                "how_it_works": [
                    {"title": "Start", "detail": "x", "files": ["app/main.py:4"]},
                    {"title": "Route", "detail": "y", "files": ["app/routes.py"]},
                ],
                "modules": [],
                "start_here": [{"path": "app/main.py", "reason": "entry"}],
            }
        )
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        prompt = json.loads(request.content)["messages"][1]["content"]
        if prompt.startswith("Write a guided tour"):
            return repo_reply
        if prompt.startswith("Describe what this folder"):
            return _reply('{"summary": "Holds the app.", "files": ["app/main.py"]}')
        return file_reply

    recorder = Recorder(handler=handler)
    api = groq_api(recorder)
    analysis_id = _analyze(api)

    body = api.post(f"/api/repositories/{analysis_id}/tour").json()

    assert body["model"] == GROQ_DEFAULT_MODEL
    assert [s["title"] for s in body["steps"]] == ["Start", "Route"]
    for request in recorder.bodies:
        assert request["max_tokens"] <= COMPACT_BUDGET.max_tokens_repo
        prompt = request["messages"][1]["content"]
        assert len(prompt) < COMPACT_BUDGET.tour_file_chars + 4_000

    calls = len(recorder.requests)
    again = api.post(f"/api/repositories/{_analyze(api)}/tour").json()
    assert again["cached"] is True
    assert len(recorder.requests) == calls  # the cache spares the provider

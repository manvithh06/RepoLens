import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes import repositories as repositories_route
from app.core.config import Settings, get_settings
from app.main import app
from app.schemas.chat import ChatTurn
from app.services.acquisition import repository as repository_module
from app.services.chat.chat import NOT_ANSWERABLE, NOTHING_FOUND, answer_question
from app.services.chat.chunks import build_chunks, chunk_file
from app.services.chat.index import ChatIndex, tokenize
from app.services.store import StoredAnalysis
from tests.fakerepo import make_reader, write_repo
from tests.test_tour import _fake_fetch

FAKE_KEY = "ghp_" + "Kq7" * 12
FILES = {
    "README.md": "# Shop\nA tiny shop.\n",
    "shop/payments.py": (
        "import stripe\n\n\n"
        "def charge_customer(customer_id, amount_cents):\n"
        '    """Charge a customer with Stripe."""\n'
        "    return stripe.Charge.create(customer=customer_id, amount=amount_cents)\n\n\n"
        "class RefundService:\n"
        "    def refund(self, charge_id):\n"
        "        return stripe.Refund.create(charge=charge_id)\n"
    ),
    "shop/config.py": f'GITHUB = "{FAKE_KEY}"\nDEBUG = True\n',
    "web/src/cart.ts": "export function addToCart(itemId: string) {\n  return itemId\n}\n",
    ".env": "STRIPE_KEY=sk_live_realsecret\n",
}


class ScriptedLLM:
    model = "fake/chat"

    def __init__(self, reply: dict) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    async def complete(self, system: str, user: str, max_tokens: int) -> str:
        self.prompts.append(user)
        return json.dumps(self.reply)


def _stored(tmp_path: Path) -> StoredAnalysis:
    reader = make_reader(tmp_path / "repo", FILES)
    return StoredAnalysis(
        analysis_id="a" * 32,
        full_name="octo/shop",
        description=None,
        branch="main",
        commit=None,
        line_counts={p: len((reader.text(p) or "").splitlines()) for p in reader.paths},
        chat_index=ChatIndex(build_chunks(reader)),
    )


def test_python_files_are_chunked_by_function_and_class() -> None:
    chunks = chunk_file("shop/payments.py", FILES["shop/payments.py"])
    spans = [(c.symbol, c.start_line, c.end_line) for c in chunks]
    assert spans == [
        (None, 1, 1),
        ("charge_customer", 4, 6),
        ("RefundService", 9, 11),
    ]


def test_long_files_use_overlapping_windows() -> None:
    text = "\n".join(f"line {i}" for i in range(1, 131))
    spans = [(c.start_line, c.end_line) for c in chunk_file("notes.md", text)]
    assert spans == [(1, 60), (51, 110), (101, 130)]


def test_chunks_skip_env_files_and_mask_secrets(tmp_path: Path) -> None:
    chunks = build_chunks(make_reader(tmp_path / "repo", FILES))
    assert all(c.path != ".env" for c in chunks)
    joined = "\n".join(c.text for c in chunks)
    assert FAKE_KEY not in joined
    assert "sk_live_realsecret" not in joined


def test_tokenize_splits_identifiers() -> None:
    tokens = tokenize("How does getUserById call charge_customer?")
    assert {"getuserbyid", "get", "user", "by", "id"} - {"by"} <= set(tokens)
    assert {"charge_customer", "charge", "customer"} <= set(tokens)
    assert "how" not in tokens and "does" not in tokens


def test_answers_with_verified_citations(tmp_path: Path) -> None:
    stored = _stored(tmp_path)
    llm = ScriptedLLM(
        {
            "answerable": True,
            "answer": "charge_customer in shop/payments.py calls Stripe.",
            "citations": ["S1", "[S1]", "S99", "shop/fake.py"],
        }
    )

    answer = asyncio.run(answer_question(stored, llm, "How is a customer charged?", []))

    assert answer.answerable
    assert [(c.id, c.path, c.symbol) for c in answer.citations] == [
        ("S1", "shop/payments.py", "charge_customer")
    ]
    assert "stripe.Charge.create" in answer.citations[0].snippet
    assert answer.retrieval == "bm25"
    assert "<repository_data>" in llm.prompts[0]


def test_refuses_without_calling_the_model_when_nothing_matches(
    tmp_path: Path,
) -> None:
    llm = ScriptedLLM({})
    answer = asyncio.run(
        answer_question(_stored(tmp_path), llm, "kubernetes helm ingress?", [])
    )
    assert not answer.answerable
    assert answer.answer == NOTHING_FOUND
    assert llm.prompts == []


@pytest.mark.parametrize(
    "reply",
    [
        {"answerable": False, "answer": "Not shown.", "citations": []},
        {"answerable": True, "answer": "Trust me.", "citations": []},
        {"answerable": True, "answer": "Made up.", "citations": ["S42"]},
    ],
)
def test_refuses_when_the_model_cannot_back_its_answer(
    tmp_path: Path, reply: dict
) -> None:
    answer = asyncio.run(
        answer_question(_stored(tmp_path), ScriptedLLM(reply), "refund a charge", [])
    )
    assert not answer.answerable
    assert answer.answer == NOT_ANSWERABLE
    assert answer.citations == []
    assert answer.related[0].path == "shop/payments.py"


def test_history_helps_follow_up_questions(tmp_path: Path) -> None:
    llm = ScriptedLLM({"answerable": True, "answer": "Yes.", "citations": ["S1"]})
    history = [ChatTurn(role="user", content="Where is the refund logic?")]
    answer = asyncio.run(
        answer_question(_stored(tmp_path), llm, "and what calls it?", history)
    )
    assert answer.answerable
    assert "Where is the refund logic?" in llm.prompts[0]


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    async def clone(url: str, branch: str, destination: Path) -> None:
        write_repo(destination, FILES)

    app.dependency_overrides[get_settings] = lambda: Settings(
        workspace_dir=tmp_path / "ws", hf_token="", llm_api_key="", llm_base_url=""
    )
    monkeypatch.setattr(repositories_route, "fetch_repo_info", _fake_fetch)
    monkeypatch.setattr(repository_module, "shallow_clone", clone)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_chat_endpoint(api: TestClient) -> None:
    analysis_id = api.post(
        "/api/repositories/analyze", json={"url": "https://github.com/octo/shop"}
    ).json()["analysis_id"]

    missing_token = api.post(
        f"/api/repositories/{analysis_id}/chat", json={"question": "charge?"}
    )
    assert missing_token.status_code == 503
    assert missing_token.json()["error"]["code"] == "llm_not_configured"

    llm = ScriptedLLM(
        {"answerable": True, "answer": "Via Stripe.", "citations": ["S1"]}
    )
    app.dependency_overrides[repositories_route.get_llm_client] = lambda: llm
    response = api.post(
        f"/api/repositories/{analysis_id}/chat",
        json={"question": "How do we charge a customer?"},
    )
    assert response.status_code == 200
    assert response.json()["citations"][0]["path"] == "shop/payments.py"

    assert (
        api.post(f"/api/repositories/{analysis_id}/chat", json={"question": ""})
    ).status_code == 422
    too_long = {"question": "x" * 1001}
    assert (
        api.post(f"/api/repositories/{analysis_id}/chat", json=too_long)
    ).status_code == 422

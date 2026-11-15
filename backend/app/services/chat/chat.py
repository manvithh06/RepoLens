"""Answer questions about a repository from retrieved code only, with verified citations."""

import re

from app.schemas.chat import ChatAnswer, ChatCitation, ChatTurn
from app.services.chat.index import ChatIndex, Hit
from app.services.llm.client import LLMClient, budget_of
from app.services.llm.errors import LLMBadOutput
from app.services.llm.output import ask_json
from app.services.store import StoredAnalysis
from app.services.tour.tour import SYSTEM_PROMPT, wrap_data

MAX_ANSWER_CHARS = 3_000
RELATED_ON_REFUSAL = 3

NOTHING_FOUND = (
    "I could not find code in this repository that relates to that question, so I "
    "cannot answer it from the source."
)
NOT_ANSWERABLE = (
    "The code I found does not contain enough to answer that reliably. The closest "
    "matches are listed below."
)

CHAT_RULES = (
    SYSTEM_PROMPT
    + """
5. Answer only from the numbered snippets. Do not use outside knowledge about this \
project. If the snippets do not answer the question, set answerable to false."""
)

_SNIPPET_ID = re.compile(r"^S(\d+)$")


def _citation(index: int, hit: Hit, max_chars: int) -> ChatCitation:
    chunk = hit.chunk
    return ChatCitation(
        id=f"S{index}",
        path=chunk.path,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        symbol=chunk.symbol,
        snippet=chunk.text[:max_chars],
    )


def _prompt(
    question: str, history: list[ChatTurn], snippets: list[ChatCitation]
) -> str:
    earlier = [t.content[:500] for t in history if t.role == "user"][-3:]
    blocks = "\n\n".join(
        f"[{s.id}] {s.path} lines {s.start_line}-{s.end_line}"
        f"{f' ({s.symbol})' if s.symbol else ''}\n{s.snippet}"
        for s in snippets
    )
    context = (
        "Earlier questions from the user, for context only:\n"
        + "\n".join(f"- {q}" for q in earlier)
        + "\n\n"
        if earlier
        else ""
    )
    return (
        f"{context}Question: {question}\n\n"
        "Answer using only the snippets below.\n"
        'Shape: {"answerable": true, "answer": "plain text, one to three short '
        'paragraphs, naming files by path", "citations": ["S1"]}\n'
        "Cite every snippet you rely on by its id. If the snippets do not contain "
        'the answer, reply {"answerable": false, "answer": "what is missing", '
        '"citations": []}.\n\n' + wrap_data(blocks)
    )


def _refusal(
    message: str, related: list[ChatCitation], index: ChatIndex, model: str | None
) -> ChatAnswer:
    return ChatAnswer(
        answerable=False,
        answer=message,
        citations=[],
        related=related[:RELATED_ON_REFUSAL],
        model=model,
        retrieval=index.retrieval,
    )


async def answer_question(
    stored: StoredAnalysis,
    client: LLMClient,
    question: str,
    history: list[ChatTurn],
) -> ChatAnswer:
    index: ChatIndex | None = stored.chat_index
    if index is None:
        raise LLMBadOutput("This repository has no readable files to search.")

    budget = budget_of(client)
    last_user = next((t.content for t in reversed(history) if t.role == "user"), "")
    hits = index.search(question, budget.chat_snippets) or index.search(
        f"{question} {last_user[:300]}", budget.chat_snippets
    )
    if not hits:
        return _refusal(NOTHING_FOUND, [], index, None)

    snippets = [
        _citation(number, hit, budget.chat_snippet_chars)
        for number, hit in enumerate(hits, start=1)
    ]
    raw = await ask_json(
        client, CHAT_RULES, _prompt(question, history, snippets), budget.max_tokens_chat
    )

    by_id = {s.id: s for s in snippets}
    cited: list[ChatCitation] = []
    for value in raw.get("citations") or []:
        match = _SNIPPET_ID.match(str(value).strip().strip("[]"))
        snippet = by_id.get(match.group(0)) if match else None
        if snippet and snippet not in cited and stored.has_file(snippet.path):
            cited.append(snippet)

    answer = " ".join(str(raw.get("answer") or "").split(" "))[
        :MAX_ANSWER_CHARS
    ].strip()
    if raw.get("answerable") is not True or not answer:
        return _refusal(NOT_ANSWERABLE, snippets, index, client.model)
    if not cited:
        # An answer that cites nothing it was given cannot be checked: do not show it.
        return _refusal(NOT_ANSWERABLE, snippets, index, client.model)
    return ChatAnswer(
        answerable=True,
        answer=answer,
        citations=cited,
        model=client.model,
        retrieval=index.retrieval,
    )

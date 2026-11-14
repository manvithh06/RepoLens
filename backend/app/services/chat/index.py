"""Keyword retrieval with BM25. Identifiers are split so `getUserById` matches 'user'."""

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.core.limits import CHAT_MIN_SCORE, CHAT_TOP_K
from app.services.chat.chunks import Chunk

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
_STOP = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "this",
        "to",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "you",
        "your",
        "there",
        "their",
        "its",
        "can",
        "was",
        "were",
    ]
)


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for word in _WORD.findall(text):
        lowered = word.lower()
        parts = [p.lower() for piece in word.split("_") for p in _CAMEL.findall(piece)]
        for token in {lowered, *parts}:
            if len(token) > 1 and token not in _STOP:
                tokens.append(token)
    return tokens


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class ChatIndex:
    retrieval = "bm25"

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        corpus = [
            tokenize(f"{c.path} {c.symbol or ''} {c.text}") or ["_empty_"]
            for c in chunks
        ]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    @property
    def size_bytes(self) -> int:
        return sum(len(c.text) + len(c.path) for c in self.chunks)

    def search(self, query: str, k: int = CHAT_TOP_K) -> list[Hit]:
        terms = tokenize(query)
        if self._bm25 is None or not terms:
            return []
        scores = self._bm25.get_scores(terms)
        ranked = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        return [
            Hit(self.chunks[i], float(scores[i]))
            for i in ranked
            if scores[i] >= CHAT_MIN_SCORE
        ]

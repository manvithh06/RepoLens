from typing import Literal

from pydantic import BaseModel, Field

from app.core.limits import MAX_CHAT_HISTORY, MAX_CHAT_QUESTION_CHARS


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4_000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_CHAT_QUESTION_CHARS)
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_CHAT_HISTORY)


class ChatCitation(BaseModel):
    id: str  # S1, S2, ... as used in the answer
    path: str
    start_line: int
    end_line: int
    symbol: str | None
    snippet: str  # the exact text the answer was based on (secrets masked)


class ChatAnswer(BaseModel):
    answerable: bool
    answer: str
    citations: list[ChatCitation]  # verified: each one was given to the model
    related: list[ChatCitation] = Field(default_factory=list)  # closest code on refusal
    model: str | None
    retrieval: str  # "bm25"

"""Read the JSON object out of a model reply, with one repair attempt."""

import json
import re
from typing import Any

from app.services.llm.client import LLMClient
from app.services.llm.errors import LLMBadOutput

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
MAX_REPAIR_ECHO_CHARS = 2_000

REPAIR_NOTE = (
    "\n\nYour previous reply could not be read as JSON. Reply again with only one "
    "valid JSON object in the requested shape: no markdown, no text before or after "
    "it, double quotes around every key and string. Your previous reply was:\n"
)


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


async def ask_json(
    client: LLMClient, system: str, user: str, max_tokens: int
) -> dict[str, Any]:
    """Ask for a JSON object. An unreadable reply gets exactly one repair attempt."""
    try:
        reply = await client.complete(system, user, max_tokens)
    except LLMBadOutput:
        reply = ""  # the provider itself rejected invalid JSON
    try:
        return parse_json_object(reply)
    except LLMBadOutput:
        pass
    echo = reply[:MAX_REPAIR_ECHO_CHARS] or "(empty)"
    repaired = await client.complete(system, user + REPAIR_NOTE + echo, max_tokens)
    return parse_json_object(repaired)

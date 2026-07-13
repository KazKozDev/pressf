"""General bot contract and extracting response from JSON via dotted path."""

from __future__ import annotations

import json
from typing import Any, Protocol


class BotError(RuntimeError):
    """Problem calling a bot - the command failed, timeout, empty response, etc."""


class Bot(Protocol):
    def ask(self, question: str) -> str:
        """Ask a question to the bot and return its answer as a string."""
        ...


def extract_answer(payload: str, answer_path: str | None) -> str:
    """Get the response text from the bot output.

    Without answer_path, the output is considered a ready-made answer (spaces are trimmed).
    With answer_path - the output is parsed as JSON and we follow the dotted path (object keys
    and list indexes): for example "choices.0.message.content"."""
    payload = payload.strip()
    if not answer_path:
        return payload
    try:
        node: Any = json.loads(payload)
    except json.JSONDecodeError as e:
        raise BotError(f"answer_path is set, but the bot's response is not JSON:{e}") from e
    for part in answer_path.split("."):
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError) as e:
                raise BotError(f"answer_path: index not found{part!r}on the list") from e
        elif isinstance(node, dict):
            if part not in node:
                raise BotError(f"answer_path: key not found{part!r}in the answer")
            node = node[part]
        else:
            raise BotError(f"answer_path: {part!r}- the path is deeper than the structure of the answer")
    if isinstance(node, (dict, list)):
        raise BotError(f"answer_path does not point to the text, but to{type(node).__name__}")
    return str(node).strip()

"""Connectors to the bot being tested: closes the regression loop.

Universal contract - Bot.ask(question) -> answer. User describes
your bot in one of two ways (command | http); pressf runs through it itself
Goldset's questions and collects fresh answers for re-checking."""

from __future__ import annotations

from ..config import BotConfig
from .base import Bot, BotError
from .command import CommandBot
from .http import HttpBot


def build_bot(cfg: BotConfig) -> Bot:
    if cfg.kind == "command":
        return CommandBot(cfg)
    if cfg.kind == "http":
        return HttpBot(cfg)
    raise BotError(f"Unknown type of bot:{cfg.kind!r}(expecting command | http)")


__all__ = ["Bot", "BotError", "CommandBot", "HttpBot", "build_bot"]

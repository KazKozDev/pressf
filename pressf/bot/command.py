"""A bot as a shell command is the most universal connector.

Works with any language/framework: pressf calls the command, the question goes away or
by substituting {question} into the arguments, or on stdin (if there is no placeholder),
the response is read from stdout. Command examples:
  - "python my_bot.py {question}"
  - "curl -s -X POST localhost:8000/ask -d {question}"
  - "./bot.sh" (the question will come to stdin)"""

from __future__ import annotations

import shlex
import subprocess

from ..config import BotConfig
from .base import BotError, extract_answer


class CommandBot:
    def __init__(self, cfg: BotConfig):
        self.timeout = cfg.timeout
        self.answer_path = cfg.answer_path
        template = getattr(cfg, "command", None)
        if not template:
            raise BotError("bot.kind=command requires a command field (shell command template)")
        self.template: str = template
        self._uses_placeholder = "{question}" in template

    def ask(self, question: str) -> str:
        if self._uses_placeholder:
            #safely insert the question as a separate argument, without concatenating strings
            argv = [part.replace("{question}", question) for part in shlex.split(self.template)]
            stdin_data = None
        else:
            argv = shlex.split(self.template)
            stdin_data = question
        try:
            proc = subprocess.run(
                argv,
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError as e:
            raise BotError(f"Bot command not found:{argv[0]!r}") from e
        except subprocess.TimeoutExpired as e:
            raise BotError(f"The bot did not respond for{self.timeout}s") from e
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-300:]
            raise BotError(f"The bot team returned the code{proc.returncode}: {tail}")
        answer = extract_answer(proc.stdout, self.answer_path)
        if not answer:
            raise BotError("The bot returned an empty response")
        return answer

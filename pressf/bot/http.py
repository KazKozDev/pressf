"""Bot like HTTP-endpoint. Only stdlib (urllib) - no unnecessary dependencies.

Example config:
  bot:
    kind: http
    url: http://localhost:8000/ask
    method: POST
    headers: {Content-Type: application/json}
    body: '{"question": "{question}"}'
    answer_path: answer"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..config import BotConfig
from .base import BotError, extract_answer


class HttpBot:
    def __init__(self, cfg: BotConfig):
        self.timeout = cfg.timeout
        self.answer_path = cfg.answer_path
        url = cfg.url
        if not url:
            raise BotError("bot.kind=http requires url field")
        self.url: str = url
        self.method = cfg.method.upper()
        self.headers = dict(cfg.headers or {})
        self.headers.setdefault("Content-Type", "application/json")
        #template body; if not specified, send {"question": "..."}
        self.body_template = cfg.body or '{"question": {question_json}}'

    def _build_body(self, question: str) -> bytes:
        body = self.body_template.replace("{question_json}", json.dumps(question, ensure_ascii=False))
        body = body.replace("{question}", question)
        return body.encode("utf-8")

    def ask(self, question: str) -> str:
        data = None if self.method == "GET" else self._build_body(question)
        req = urllib.request.Request(self.url, data=data, headers=self.headers, method=self.method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raise BotError(f"The bot returned HTTP{e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise BotError(f"Failed to reach the bot:{e.reason}") from e
        except TimeoutError as e:
            raise BotError(f"The bot did not respond for{self.timeout}s") from e
        answer = extract_answer(payload, self.answer_path)
        if not answer:
            raise BotError("The bot returned an empty response")
        return answer

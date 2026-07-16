"""Coverage for stdlib HTTP bot behavior and supported input formats."""

from __future__ import annotations

import sys
import urllib.error
from types import SimpleNamespace

import pytest

from pressf.bot.base import BotError
from pressf.bot.http import HttpBot
from pressf.config import BotConfig
from pressf.ingest.loaders import load_rows


class _Response:
    def __init__(self, body: str):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body.encode("utf-8")


def test_http_bot_sends_json_and_extracts_nested_answer(monkeypatch):
    seen = {}

    def urlopen(request, timeout):
        seen["method"] = request.method
        seen["body"] = request.data
        seen["timeout"] = timeout
        return _Response('{"data": {"answer": "hello"}}')

    monkeypatch.setattr("pressf.bot.http.urllib.request.urlopen", urlopen)
    bot = HttpBot(BotConfig(kind="http", url="https://bot.example/ask", timeout=4, answer_path="data.answer"))
    assert bot.ask('Say "hello"') == "hello"
    assert seen == {"method": "POST", "body": b'{"question": "Say \\"hello\\""}', "timeout": 4}


def test_http_bot_get_and_error_messages(monkeypatch):
    bot = HttpBot(BotConfig(kind="http", url="https://bot.example/ask", method="GET"))
    monkeypatch.setattr("pressf.bot.http.urllib.request.urlopen", lambda request, timeout: _Response("plain answer"))
    assert bot.ask("question") == "plain answer"

    errors = [
        urllib.error.HTTPError("https://bot.example", 503, "offline", {}, None),
        urllib.error.URLError("refused"),
        TimeoutError(),
    ]
    for error, message in zip(errors, ["HTTP503", "Failed to reach", "did not respond"]):
        monkeypatch.setattr("pressf.bot.http.urllib.request.urlopen", lambda *args, error=error, **kwargs: (_ for _ in ()).throw(error))
        with pytest.raises(BotError, match=message):
            bot.ask("question")

    monkeypatch.setattr("pressf.bot.http.urllib.request.urlopen", lambda request, timeout: _Response('{"answer": ""}'))
    with pytest.raises(BotError, match="empty response"):
        HttpBot(BotConfig(kind="http", url="https://bot.example/ask", answer_path="answer")).ask("question")
    with pytest.raises(BotError, match="requires url"):
        HttpBot(BotConfig(kind="http"))


def test_load_rows_handles_jsonl_json_csv_tsv_and_validation_errors(tmp_path):
    jsonl = tmp_path / "rows.jsonl"
    jsonl.write_text('{"name": "one"}\n\nnot json\n', encoding="utf-8")
    rows = load_rows(jsonl)
    assert rows[0] == {"name": "one"}
    assert rows[1]["_parse_error"].startswith("line3:")

    data = tmp_path / "rows.json"
    data.write_text('[{"name": "two"}]', encoding="utf-8")
    assert load_rows(data) == [{"name": "two"}]
    data.write_text('{"name": "wrong shape"}', encoding="utf-8")
    with pytest.raises(ValueError, match="expected JSON-array"):
        load_rows(data)

    csv = tmp_path / "rows.csv"
    csv.write_text("\ufeffname,answer\nthree,yes\n", encoding="utf-8")
    assert load_rows(csv) == [{"name": "three", "answer": "yes"}]
    tsv = tmp_path / "rows.tsv"
    tsv.write_text("name\tanswer\nfour\tno\n", encoding="utf-8")
    assert load_rows(tsv) == [{"name": "four", "answer": "no"}]
    with pytest.raises(FileNotFoundError):
        load_rows(tmp_path / "missing.jsonl")
    unknown = tmp_path / "rows.txt"
    unknown.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown format"):
        load_rows(unknown)


def test_load_rows_reads_excel_through_the_optional_adapter(monkeypatch, tmp_path):
    class Sheet:
        def iter_rows(self, values_only):
            return iter([("name", None), ("five", 5)])

    workbook = SimpleNamespace(active=Sheet())
    monkeypatch.setitem(sys.modules, "openpyxl", SimpleNamespace(load_workbook=lambda *args, **kwargs: workbook))
    path = tmp_path / "rows.xlsx"
    path.write_bytes(b"placeholder")
    assert load_rows(path) == [{"name": "five", "col_1": 5}]

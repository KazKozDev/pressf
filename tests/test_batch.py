"""Batch API: schema sanitizer, query assembly, results parsing, batch pipeline."""

from __future__ import annotations

import json
from types import SimpleNamespace

from pressf.config import Project
from pressf.llm.batch import BatchItem, BatchRunner, build_request, parse_result
from pressf.llm.schema_utils import structured_output_schema
from pressf.schemas import ExtractedClaims, VerificationResult


def _walk(node, fn):
    fn(node)
    if isinstance(node, dict):
        for v in node.values():
            _walk(v, fn)
    elif isinstance(node, list):
        for v in node:
            _walk(v, fn)


def test_schema_sanitized_for_structured_outputs():
    schema = structured_output_schema(VerificationResult)

    def check(node):
        if isinstance(node, dict):
            assert "minimum" not in node and "maximum" not in node
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False

    _walk(schema, check)


def test_build_request_shape():
    req = build_request(
        BatchItem(custom_id="e1", model="claude-haiku-4-5", system="sys", user="usr", schema=ExtractedClaims)
    )
    assert req["custom_id"] == "e1"
    params = req["params"]
    assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert params["output_config"]["format"]["type"] == "json_schema"


def _ok_result(custom_id: str, payload: dict, model="claude-haiku-4-5"):
    usage = SimpleNamespace(
        input_tokens=1000, output_tokens=100,
        cache_creation_input_tokens=0, cache_read_input_tokens=0,
    )
    message = SimpleNamespace(
        model=model, usage=usage,
        content=[SimpleNamespace(type="text", text=json.dumps(payload))],
    )
    return SimpleNamespace(custom_id=custom_id, result=SimpleNamespace(type="succeeded", message=message))


def test_parse_result_success_and_discount():
    payload = {"is_refusal": False, "claims": ["A"]}
    out = parse_result(_ok_result("e1", payload), ExtractedClaims)
    assert out.parsed.claims == ["A"]
    # haiku: (1000/1e6*1 + 100/1e6*5) * 0.5
    assert abs(out.cost_usd - 0.00075) < 1e-9


def test_parse_result_error():
    res = SimpleNamespace(
        custom_id="e1",
        result=SimpleNamespace(type="errored", error=SimpleNamespace(type="invalid_request")),
    )
    out = parse_result(res, ExtractedClaims)
    assert out.parsed is None and out.error == "invalid_request"


class FakeBatches:
    """Instant «batch»: create remembers requests, retrieve ended immediately."""

    def __init__(self, responder):
        self._responder = responder
        self._requests = None

    def create(self, requests):
        self._requests = requests
        return SimpleNamespace(id="batch_1", processing_status="ended",
                               request_counts=SimpleNamespace(processing=0, succeeded=len(requests)))

    def retrieve(self, batch_id):
        return SimpleNamespace(id=batch_id, processing_status="ended",
                               request_counts=SimpleNamespace(processing=0, succeeded=len(self._requests)))

    def results(self, batch_id):
        return [self._responder(r) for r in self._requests]


def _fake_anthropic(responder):
    return SimpleNamespace(messages=SimpleNamespace(batches=FakeBatches(responder)))


def test_batch_runner_roundtrip():
    def responder(req):
        return _ok_result(req["custom_id"], {"is_refusal": False, "claims": ["x"]})

    runner = BatchRunner(_fake_anthropic(responder), poll_seconds=0)
    out = runner.run([
        BatchItem(custom_id="a", model="claude-haiku-4-5", system="s", user="u", schema=ExtractedClaims),
        BatchItem(custom_id="b", model="claude-haiku-4-5", system="s", user="u", schema=ExtractedClaims),
    ])
    assert set(out) == {"a", "b"} and all(o.parsed for o in out.values())


def test_run_check_batch_end_to_end(project: Project):
    """Full batch pipeline on a fake anthropic client: A → B (+C is not needed)."""
    from pressf.judge.batch_check import run_check_batch

    project.verdicts_path.unlink()

    def responder(req):
        body = req["params"]["messages"][0]["content"]  #already a line
        schema_props = req["params"]["output_config"]["format"]["schema"].get("properties", {})
        if "is_refusal" in schema_props:  #phase A
            refusal = "not at the docks" in body  #marker only in response e3, not in the prompt template
            return _ok_result(req["custom_id"], {"is_refusal": refusal, "claims": [] if refusal else ["k1"]})
        if "answerable" in schema_props:  # answerability
            return _ok_result(req["custom_id"], {
                "answerable": False, "evidence": [], "confidence": 0.9, "reasoning": "not in the database"})
        return _ok_result(req["custom_id"], {  #verification
            "checks": [{"claim_index": 0, "status": "supported",
                        "evidence": [{"chunk_index": 0, "quote": "600"}]}],
            "confidence": 0.95, "reasoning": "OK"})

    llm_client = SimpleNamespace(anthropic=_fake_anthropic(responder))
    summary = run_check_batch(project, llm_client)
    assert summary.checked == 3
    verdicts = project.load_verdicts()
    assert verdicts["e3"].category == "correct_refusal"
    assert verdicts["e1"].category == "correct"
    assert all(v.cost_usd > 0 for v in verdicts.values())

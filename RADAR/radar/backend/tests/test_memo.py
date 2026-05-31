"""Trust-critical tests for the memo grounding backstop.

No pytest/network needed — run from backend/:  python3 tests/test_memo.py
Stubs the Claude client so the LLM output is fully controlled.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.memo import run, GENERALIST_TEMPLATE, _build_payload, _coerce_conf


class _StubClaude:
    """Returns a fixed (adversarial) memo regardless of input."""
    def __init__(self, response):
        self._response = response
    def generate_comparative_memo(self, payload, template):
        return self._response


def test_backstop_drops_fabricated_url_keeps_real():
    fake = {"subject": {"name": "Acme", "funding": {"totalEur": 12_000_000, "sourceUrl": "https://real.example/x"}}, "competitors": []}
    stub = _StubClaude({"sections": [{
        "id": "exec-summary", "title": "Exec", "body": "x", "confidence": "high", "hasGaps": False,
        "citations": [
            {"claim": "real fact", "sourceUrl": "https://real.example/x", "confidence": "high"},
            {"claim": "made up", "sourceUrl": "https://FAKE.invented/y", "confidence": "high"},
        ],
    }]})
    memo = run(fake, GENERALIST_TEMPLATE, stub)
    cits = memo.sections[0].citations
    assert len(cits) == 1, f"expected fabricated URL dropped, got {len(cits)}"
    assert cits[0].source_url == "https://real.example/x"


def test_drops_citation_without_claim():
    fake = {"subject": {"name": "Acme", "funding": {"sourceUrl": "https://real.example/x"}}, "competitors": []}
    stub = _StubClaude({"sections": [{
        "id": "exec-summary", "title": "Exec", "body": "x", "confidence": "high", "hasGaps": False,
        "citations": [{"sourceUrl": "https://real.example/x", "confidence": "high"}],  # no claim
    }]})
    memo = run(fake, GENERALIST_TEMPLATE, stub)
    assert memo.sections[0].citations == [], "citation without claim must be dropped"


def test_drifted_confidence_coerced_not_500():
    # An out-of-enum confidence must NOT raise — it coerces to "medium".
    assert _coerce_conf("très élevée") == "medium"
    assert _coerce_conf(None) == "medium"
    assert _coerce_conf("high") == "high"
    fake = {"subject": {"name": "Acme", "funding": {"sourceUrl": "https://real.example/x"}}, "competitors": []}
    stub = _StubClaude({"sections": [{
        "id": "exec-summary", "title": "Exec", "body": "x", "confidence": "ultra", "hasGaps": False,
        "citations": [{"claim": "f", "sourceUrl": "https://real.example/x", "confidence": "garbage"}],
    }]})
    memo = run(fake, GENERALIST_TEMPLATE, stub)  # must not raise
    assert memo.sections[0].confidence == "medium"
    assert memo.sections[0].citations[0].confidence == "medium"


def test_competitor_cap_and_url_whitelist():
    # 20 competitors → payload caps to _MAX_COMPETITORS; only emitted URLs whitelisted.
    comps = [{"name": f"C{i}", "threat": "low", "keyDifferentiator": {"value": "v", "sourceUrl": f"https://c/{i}"}} for i in range(20)]
    urls = set()
    payload = _build_payload({"subject": {"name": "S"}, "competitors": comps}, urls)
    assert len(payload["competitors"]) == 12, f"expected cap at 12, got {len(payload['competitors'])}"
    assert all(u.startswith("https://c/") for u in urls)
    assert len(urls) == 12


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

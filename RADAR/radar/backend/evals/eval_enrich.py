"""Eval Phase 3 — ENRICH.

Run: bt eval evals/eval_enrich.py
     (from backend/ with .env loaded)

Pipeline now caps enrichment at MAX_ENRICH (top-1 depth M + 4 depth S);
remaining competitors come back as stubs. Scorers only consider the
enriched head, since stubs by definition carry no pricing/signal payload.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import braintrust
from braintrust import Eval
from autoevals import ClosedQA

from clients.linkup_client import LinkupClient
from pipeline.enrich import MAX_ENRICH, run as enrich_run
from evals.datasets import ENRICH_COMPETITORS

braintrust.init_logger(project="RADAR")


async def task(competitors: list[dict]) -> list[dict]:
    linkup = LinkupClient()
    profiles = await enrich_run(competitors, linkup, run_id="eval")
    return [p.model_dump(mode="json") for p in profiles]


def score_pricing_coverage(input, expected, output):
    """Fraction of *enriched* competitors that have a pricing source URL.

    Only the first MAX_ENRICH entries are scored; stubs after the cap are skipped.
    """
    if not output or not isinstance(output, list):
        return 0.0
    head = output[:MAX_ENRICH]
    if not head:
        return 0.0
    with_pricing = sum(
        1 for p in head
        if p.get("pricing") and p["pricing"].get("source_url")
    )
    return with_pricing / len(head)


def score_signals_quality(input, expected, output):
    """LLM judge: recent_signals are meaningful, not empty or generic."""
    if not output or not isinstance(output, list):
        return 0.0
    head = output[:MAX_ENRICH]
    all_signals = []
    for p in head:
        all_signals.extend(p.get("recent_signals", []))
    if not all_signals:
        return 0.0
    return ClosedQA()(
        input="Enriching competitor profiles with recent news and signals.",
        output=f"Signals extracted: {all_signals[:6]}",
        criteria=(
            "The signals are specific, recent business events (product launches, funding rounds, "
            "partnerships, hiring surges, geographic expansion). Not empty strings. "
            "Not generic phrases like 'company growing'."
        ),
    )


def score_stub_shape(input, expected, output):
    """Verify the cap holds: stubs after MAX_ENRICH have no pricing payload."""
    if not output or not isinstance(output, list):
        return 0.0
    tail = output[MAX_ENRICH:]
    if not tail:
        return 1.0  # input was <= MAX_ENRICH, no stubs expected
    stubbed = sum(1 for p in tail if not p.get("pricing"))
    return stubbed / len(tail)


Eval(
    "RADAR",
    experiment_name="enrich-v2-research",
    data=[{"input": ENRICH_COMPETITORS}],
    task=task,
    scores=[score_pricing_coverage, score_signals_quality, score_stub_shape],
    metadata={"phase": "enrich", "model": "linkup+research", "max_enrich": MAX_ENRICH},
)

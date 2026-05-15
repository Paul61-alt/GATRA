"""Eval Phase 3 — ENRICH.

Run: bt eval evals/eval_enrich.py
     (from backend/ with .env loaded)

Uses hardcoded competitor stubs → no dependency on phases 1+2.
Each case = 2 Linkup tasks per competitor (pricing + signals).
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
from pipeline.enrich import run as enrich_run
from evals.datasets import ENRICH_COMPETITORS

braintrust.init_logger(project="RADAR")


async def task(competitors: list[dict]) -> list[dict]:
    linkup = LinkupClient()
    profiles = await enrich_run(competitors, linkup, run_id="eval")
    return [p.model_dump(mode="json") for p in profiles]


def score_pricing_coverage(input, expected, output):
    """Fraction of competitors that have a pricing source URL."""
    if not output or not isinstance(output, list):
        return 0.0
    with_pricing = sum(
        1 for p in output
        if p.get("pricing") and p["pricing"].get("source_url")
    )
    return with_pricing / len(output)


def score_signals_quality(input, expected, output):
    """LLM judge: recent_signals are meaningful, not empty or generic."""
    if not output or not isinstance(output, list):
        return 0.0
    all_signals = []
    for p in output:
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


Eval(
    "RADAR",
    experiment_name="enrich-v1",
    data=[{"input": ENRICH_COMPETITORS}],
    task=task,
    scores=[score_pricing_coverage, score_signals_quality],
    metadata={"phase": "enrich", "model": "linkup+tasks"},
)

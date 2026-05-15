"""Eval Phase 1 — UNDERSTAND.

Run: bt eval evals/eval_understand.py
     (from backend/ with .env loaded)
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
from pipeline.understand import run as understand_run
from evals.datasets import UNDERSTAND_DOMAINS

braintrust.init_logger(project="RADAR")


async def task(domain: str) -> dict:
    linkup = LinkupClient()
    profile = await understand_run(domain, linkup)
    return profile.model_dump(mode="json")


def score_completeness(input, expected, output):
    """LLM judge: profile has all key fields with plausible values."""
    return ClosedQA()(
        input=f"Domain analyzed: {input}",
        output=str(output),
        criteria=(
            "The company profile contains non-null values for: name, summary, hq_city, hq_country, "
            "positioning. The values are factually plausible for the given domain. "
            "No obviously hallucinated or generic placeholder data."
        ),
    )


def score_markets(input, expected, output):
    """LLM judge: at least one market/vertical identified."""
    markets = output.get("markets", []) if isinstance(output, dict) else []
    return 1.0 if len(markets) > 0 else 0.0


Eval(
    "RADAR",
    experiment_name="understand-v1",
    data=[{"input": domain} for domain in UNDERSTAND_DOMAINS],
    task=task,
    scores=[score_completeness, score_markets],
    metadata={"phase": "understand", "model": "linkup+extract"},
)

"""Eval Phase 2 — DISCOVER.

Run: bt eval evals/eval_discover.py
     (from backend/ with .env loaded)

Note: runs UNDERSTAND first to get a real CompanyProfile, then DISCOVER.
Each case = 2 Linkup API calls.
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
from pipeline.discover import run as discover_run
from evals.datasets import DISCOVER_DOMAINS

braintrust.init_logger(project="RADAR")


async def task(domain: str) -> list[dict]:
    linkup = LinkupClient()
    profile = await understand_run(domain, linkup)
    competitors = await discover_run(profile, linkup)
    return competitors


def score_count(input, expected, output):
    """At least 5 competitors found (target is 15)."""
    n = len(output) if isinstance(output, list) else 0
    if n >= 10:
        return 1.0
    if n >= 5:
        return 0.5
    return 0.0


def score_relevance(input, expected, output):
    """LLM judge: are discovered competitors real and market-relevant?"""
    if not output:
        return 0.0
    names = [c.get("name", "") for c in output[:5]] if isinstance(output, list) else []
    return ClosedQA()(
        input=f"Domain: {input}. Finding competitors.",
        output=f"Top competitors found: {', '.join(names)}",
        criteria=(
            "The companies listed are real, well-known competitors in the same market as the input domain. "
            "No made-up company names. No companies from completely unrelated industries."
        ),
    )


def score_data_quality(input, expected, output):
    """LLM judge: each competitor has website + one_liner fields."""
    if not output or not isinstance(output, list):
        return 0.0
    with_website = sum(1 for c in output if c.get("website"))
    with_oneliner = sum(1 for c in output if c.get("one_liner"))
    return (with_website + with_oneliner) / (2 * len(output))


Eval(
    "RADAR",
    experiment_name="discover-v1",
    data=[{"input": domain} for domain in DISCOVER_DOMAINS],
    task=task,
    scores=[score_count, score_relevance, score_data_quality],
    metadata={"phase": "discover", "model": "linkup+extract"},
)

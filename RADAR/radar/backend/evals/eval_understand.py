"""Eval Phase 1 — UNDERSTAND.

Run: braintrust eval evals/eval_understand.py
     (from backend/ with .venv activated and BRAINTRUST_API_KEY exported)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import anthropic
import braintrust
from braintrust import Eval

from clients.linkup_client import LinkupClient
from pipeline.understand import run as understand_run
from evals.datasets import UNDERSTAND_DOMAINS

braintrust.init_logger(project="RADAR")

_claude = anthropic.Anthropic()


async def task(domain: str) -> dict:
    linkup = LinkupClient()
    profile = await understand_run(domain, linkup)
    return profile.model_dump(mode="json")


def score_completeness(input, expected, output):
    """Claude judge: profile has all key fields with plausible values."""
    if not isinstance(output, dict):
        return 0.0

    prompt = f"""You are evaluating an AI-generated company profile for the domain: {input}

Profile JSON:
{output}

Criteria: Does the profile contain non-null, factually plausible values for ALL of these fields?
- name
- summary (a real paragraph, not generic)
- hq.city and hq.country
- positioning
- at least 1 market

Answer with ONLY "yes" or "no", nothing else."""

    response = _claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=5,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = response.content[0].text.strip().lower()
    return 1.0 if answer.startswith("yes") else 0.0


def score_markets(input, expected, output):
    """LLM judge: at least one market/vertical identified."""
    markets = output.get("markets", []) if isinstance(output, dict) else []
    return 1.0 if len(markets) > 0 else 0.0


Eval(
    "RADAR",
    experiment_name="understand-v3",
    data=[{"input": domain} for domain in UNDERSTAND_DOMAINS],
    task=task,
    scores=[score_completeness, score_markets],
    metadata={"phase": "understand", "model": "linkup+extract"},
)

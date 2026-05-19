import json
import logging
import os
from typing import Any, Optional, Type, TypeVar

import anthropic
from braintrust import traced
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"

T = TypeVar("T", bound=BaseModel)


class ClaudeClient:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self._client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    @traced
    def extract_json(self, system: str, user: str, max_tokens: int = 4096) -> dict:
        """Call Claude and parse JSON from the response."""
        message = self._client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = message.content[0].text

        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error("claude no JSON in response text=%s", text[:200])
            raise ValueError("No JSON found in Claude response")
        return json.loads(text[start:end])

    @traced
    def extract_model(self, model_cls: Type[T], system: str, user: str, max_tokens: int = 4096) -> T:
        data = self.extract_json(system, user, max_tokens)
        return model_cls.model_validate(data)

    @traced
    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        message = self._client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text

    @traced
    def generate_vc_memo(self, competitor: dict) -> str:
        """Analyse a CompetitorProfile dict and return a VC-style markdown memo."""
        system = (
            "You are a VC analyst writing a concise 1-page competitive intelligence memo. "
            "Structure your response in exactly 4 markdown sections: "
            "## Overview, ## Pricing & Monetisation, ## Recent Signals, ## Investment Thesis / Watch Points. "
            "Be specific, data-driven, and direct. No fluff."
        )
        slim = {
            k: competitor.get(k)
            for k in (
                "name", "website", "one_liner", "target_segment", "key_differentiators",
                "pricing", "recent_signals", "structured_signals", "funding_stage",
                "funding_total_usd", "last_round_amount_usd", "last_round_date",
                "last_round_type", "key_investors", "employee_count", "weaknesses",
                "notable_customers",
            )
            if competitor.get(k) is not None
        }
        user = f"Write a competitive intelligence memo for:\n\n{json.dumps(slim, ensure_ascii=False, indent=2, default=str)}"
        return self.complete(system, user, max_tokens=1500)

    @traced
    def score_threats(self, subject_summary: str, competitors: list[dict]) -> dict[str, int]:
        """Rank competitors by competitive threat to the subject.

        Returns {website: int 0-100}. 100 = head-on direct competitor (same ICP,
        product category, geo, pricing tier). 0 = adjacent/irrelevant.
        Falls back to empty dict on parse failure so the caller can keep discover order.
        """
        system = (
            "You are a competitive intelligence analyst. "
            "Given a subject company and a list of competitors, score each competitor 0-100 "
            "on how directly they threaten the subject's core business "
            "(same ICP, same product category, same geo, similar pricing). "
            "100 = head-on direct competitor. 0 = adjacent or irrelevant. "
            "Output strict JSON: an object mapping each competitor's website to its integer score. "
            "Example: {\"competitor-a.com\": 85, \"competitor-b.io\": 42}. "
            "No prose, no explanation, no markdown fences."
        )
        slim = [
            {
                "name": c.get("name", ""),
                "website": c.get("website", ""),
                "one_liner": c.get("one_liner", ""),
                "differentiator": c.get("differentiator", ""),
                "hq_country": c.get("hq_country", ""),
                "funding_stage": c.get("funding_stage", ""),
            }
            for c in competitors
        ]
        user = f"SUBJECT:\n{subject_summary}\n\nCOMPETITORS:\n{json.dumps(slim, ensure_ascii=False)}"
        try:
            raw = self.extract_json(system, user, max_tokens=1024)
        except Exception as e:
            logger.warning("score_threats parse failed error=%s", e)
            return {}
        out: dict[str, int] = {}
        for k, v in raw.items():
            try:
                out[str(k)] = max(0, min(100, int(v)))
            except (TypeError, ValueError):
                continue
        return out

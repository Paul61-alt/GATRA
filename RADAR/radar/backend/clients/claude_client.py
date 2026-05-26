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
    def enrich_company_profile(self, profile):
        """Post-process CompanyProfile: fill equity_story + customer segments/industry.

        Never overwrites existing values. Returns updated profile (immutable model_copy).
        Skips silently if no funding data and no customers.
        """
        import json as _json

        # Build compact input
        funding_data = None
        if profile.funding:
            funding_data = {
                "total_raised_eur": (
                    profile.funding.total_raised_eur.value
                    if profile.funding.total_raised_eur
                    else None
                ),
                "last_round": profile.funding.last_round,
                "rounds": [
                    {"round": r.round, "amount_eur": r.amount_eur, "date": r.date, "lead": r.lead}
                    for r in (profile.funding.rounds or [])
                ],
            }

        customer_names = [c.name for c in profile.notable_customers] if profile.notable_customers else []
        has_funding = bool(
            funding_data and (funding_data.get("rounds") or funding_data.get("total_raised_eur"))
        )
        has_customers = bool(customer_names)

        if not has_funding and not has_customers:
            logger.debug("enrich_company_profile: nothing to process for %s", profile.name)
            return profile

        # Serialize investors as plain names for Claude input
        investor_names = [
            i.name if hasattr(i, "name") else str(i)
            for i in (profile.notable_investors or [])
        ]

        system = (
            "You are a competitive intelligence analyst. Given raw company data, produce four outputs:\n"
            "1. equity_story: 2-3 sentences on the funding journey (when raised, from whom, stage, "
            "strategic rationale). null if no funding data.\n"
            "2. customer_segments: for each customer name, classify segment "
            "('Grand compte'=CAC40/Fortune500, 'ETI'=250-5000 employees, 'PME'=<250 employees, "
            "'Startup', 'Consumer') and industry (1-2 words, e.g. 'Consulting', 'Retail', 'Tech'), "
            "and domain (company website, e.g. 'openai.com'). null domain if unknown.\n"
            "3. investor_domains: map each investor name to their firm website domain "
            "(e.g. 'Sequoia Capital' → 'sequoiacap.com', 'Accel' → 'accel.com'). "
            "Only include domains you are confident about. Empty object if unknown.\n"
            "Return ONLY strict JSON. No prose, no markdown fences.\n"
            '{"equity_story": "...", '
            '"customer_segments": [{"name": "...", "domain": "...", "segment": "...", "industry": "..."}], '
            '"investor_domains": {"Investor Name": "domain.com"}}'
        )
        user = _json.dumps(
            {
                "company": profile.name,
                "funding": funding_data,
                "notable_investors": investor_names,
                "notable_customers": customer_names,
            },
            ensure_ascii=False,
            indent=2,
        )

        try:
            result = self.extract_json(system, user, max_tokens=1024)
        except Exception as e:
            logger.warning("enrich_company_profile failed for %s: %s", profile.name, e)
            return profile

        updates: dict = {}

        # equity_story: only fill if currently empty
        if not profile.equity_story and result.get("equity_story"):
            updates["equity_story"] = result["equity_story"]

        # customer segments + domain: fill missing fields, never overwrite
        seg_map = {
            s["name"]: s
            for s in (result.get("customer_segments") or [])
            if isinstance(s, dict) and s.get("name")
        }
        if seg_map and profile.notable_customers:
            from pipeline.understand import _norm_segment as _ns
            updated_customers = []
            for c in profile.notable_customers:
                seg = seg_map.get(c.name)
                if seg:
                    updated_customers.append(
                        c.model_copy(
                            update={
                                "domain":   c.domain   or seg.get("domain"),
                                "segment":  c.segment  or _ns(seg.get("segment")),
                                "industry": c.industry or seg.get("industry"),
                            }
                        )
                    )
                else:
                    updated_customers.append(c)
            updates["notable_customers"] = updated_customers

        # investor_domains: fill missing domain on Investor objects, never overwrite
        inv_domain_map: dict = result.get("investor_domains") or {}
        if inv_domain_map and profile.notable_investors:
            from models.company import Investor as _Investor
            updated_investors = []
            for inv in profile.notable_investors:
                inv_name = inv.name if hasattr(inv, "name") else str(inv)
                mapped_domain = inv_domain_map.get(inv_name)
                if hasattr(inv, "name"):
                    updated_investors.append(
                        inv.model_copy(update={"domain": inv.domain or mapped_domain})
                    )
                else:
                    updated_investors.append(_Investor(name=inv_name, domain=mapped_domain))
            updates["notable_investors"] = updated_investors

        if updates:
            profile = profile.model_copy(update=updates)

        return profile

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

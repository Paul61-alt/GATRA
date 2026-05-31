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
    def generate_comparative_memo(self, payload: dict, template: dict) -> dict:
        """Generate a comparative VC investment memo (subject vs competitors).

        `payload` is a CLOSED data object: the subject + competitors, each slimmed to
        citation-bearing fields with their source_url/confidence inline. The model may
        only cite URLs that physically appear in `payload` — there are no others.
        `template` is a TemplateSpec dict {id, name, sections:[{id,title,instruction}]}.
        Returns a Memo dict (camelCase) validated by the caller. Strict grounding:
        no prior knowledge, no invented numbers, gaps marked "Non disponible".
        """
        section_briefs = "\n".join(
            f'- id="{s.get("id")}" | title="{s.get("title")}" | instruction: {s.get("instruction")}'
            for s in template.get("sections", [])
        )
        system = (
            "You are a VC analyst writing a COMPARATIVE investment memo: the subject company "
            "versus its competitive landscape. You write in the language of the data provided "
            "(default French for UI labels like 'Non disponible').\n\n"
            "ABSOLUTE RULES — violating any of these makes the memo worthless to an investor:\n"
            "1. CLOSED WORLD: Use ONLY facts present in the DATA object. No prior knowledge, "
            "no estimation, no extrapolation, no rounding of unprovided numbers.\n"
            "2. NO INVENTED SOURCES: Every citation's `sourceUrl` MUST be copied verbatim from a "
            "`source_url` value present in DATA. NEVER write a URL that is not in DATA. If a claim "
            "has no source_url in DATA, omit the citation and lower the section confidence.\n"
            "3. EXPLICIT GAPS: If DATA lacks information a section needs, write exactly "
            "`Non disponible` for that point and set that section's `hasGaps` to true. Never guess.\n"
            "4. NO FABRICATED NUMBERS: funding amounts, employee counts, dates, ARR, customer counts "
            "— only those present in DATA. If absent → `Non disponible`.\n"
            "5. CONFIDENCE INHERITANCE: set each citation's `confidence` to the `confidence` value "
            "DATA carries for that fact (default 'medium' if none). Set each section's `confidence` "
            "to the LOWEST confidence among its load-bearing cited claims.\n"
            "6. Be specific, comparative and direct. Reference competitors by name. No fluff, no hedging.\n\n"
            "OUTPUT: Return ONLY strict JSON (no prose, no markdown fences) matching exactly:\n"
            '{"sections":[{"id":<section id>,"title":<section title>,"body":<markdown string>,'
            '"citations":[{"claim":<string>,"sourceUrl":<string from DATA>,"confidence":<"high"|"medium"|"low">,'
            '"company":<company name>}],"confidence":<"high"|"medium"|"low">,"hasGaps":<bool>}]}\n'
            "Produce exactly one object per requested section, in the given order, preserving each id."
        )
        user = (
            f"TEMPLATE SECTIONS (generate one memo section per line, in order):\n{section_briefs}\n\n"
            f"DATA (the only facts you may use):\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}"
        )
        return self.extract_json(system, user, max_tokens=8000)

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
    def discover_competitors_fallback(
        self,
        company_name: str,
        company_domain: str,
        positioning: str,
        markets_str: str,
        max_candidates: int = 20,
    ) -> list[dict]:
        """Fallback: use Claude training data to list competitors when Linkup returns nothing.

        Returns list of {name, domain, tagline} dicts. Zero Linkup cost.
        Falls back to [] on parse failure.
        """
        system = (
            "You are a competitive intelligence analyst. "
            f"Based on your training data, list up to {max_candidates} direct competitors "
            f"of {company_name} ({company_domain}). "
            f"Context: {positioning}. Market: {markets_str}. "
            f"Exclude {company_name} ({company_domain}) itself. "
            "For each competitor: name (string), domain (bare domain, no https/www), "
            "tagline (1-sentence elevator pitch). "
            "Return ONLY strict JSON with key 'competitors'. No prose, no markdown fences.\n"
            '{"competitors": [{"name": "...", "domain": "...", "tagline": "..."}, ...]}'
        )
        user = (
            f"List the main direct competitors of {company_name} ({company_domain}), "
            f"a {positioning} in the {markets_str} market."
        )
        try:
            result = self.extract_json(system, user, max_tokens=2048)
            raw_list = result.get("competitors", [])
            if not isinstance(raw_list, list):
                return []
            out = []
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                domain = str(item.get("domain", "")).strip()
                tagline = str(item.get("tagline", "")).strip()
                if name and domain:
                    out.append({"name": name, "domain": domain, "tagline": tagline})
            return out[:max_candidates]
        except Exception as e:
            logger.warning("discover_competitors_fallback failed error=%s", e)
            return []

    @traced
    def extract_discover_candidates(
        self,
        raw_texts: list[str],
        company_name: str,
        company_domain: str,
        max_candidates: int = 20,
    ) -> list[dict]:
        """Merge 3 search result texts into a deduped competitor list.

        Returns list of {name, domain, tagline} dicts.
        Falls back to [] on any parse failure.
        """
        combined = "\n\n---\n\n".join(
            f"[SOURCE {i + 1}]\n{t}" for i, t in enumerate(raw_texts) if t
        )
        system = (
            "You are a competitive intelligence analyst. "
            f"Extract the direct competitors of {company_name} ({company_domain}) "
            "from the search results below. "
            f"Return up to {max_candidates} unique companies. "
            f"Exclude {company_name} ({company_domain}) itself. "
            "Prioritise direct competitors (same target customer, overlapping core features). "
            "For each competitor return:\n"
            "  - name: company name (string)\n"
            "  - domain: bare domain, no https:// or www. (e.g. 'notion.so')\n"
            "  - tagline: 1-sentence elevator pitch (string)\n"
            "Output ONLY strict JSON with key 'competitors'. No prose, no markdown fences.\n"
            '{"competitors": [{"name": "...", "domain": "...", "tagline": "..."}, ...]}'
        )
        user = f"SEARCH RESULTS:\n\n{combined}"
        try:
            result = self.extract_json(system, user, max_tokens=2048)
            raw_list = result.get("competitors", [])
            if not isinstance(raw_list, list):
                logger.warning("extract_discover_candidates: 'competitors' not a list")
                return []
            out = []
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                domain = str(item.get("domain", "")).strip()
                tagline = str(item.get("tagline", "")).strip()
                if name and domain:
                    out.append({"name": name, "domain": domain, "tagline": tagline})
            return out[:max_candidates]
        except Exception as e:
            logger.warning("extract_discover_candidates failed error=%s", e)
            return []

    @traced
    def score_threats_candidates(
        self,
        subject_summary: str,
        candidates: list[dict],
    ) -> dict[str, int]:
        """Rank DiscoverCandidate dicts by competitive threat (0-100).

        Accepts {name, domain, tagline} dicts (HITL discover path).
        Returns {domain: score}. Falls back to {} on parse failure.
        """
        system = (
            "You are a competitive intelligence analyst. "
            "Score each competitor 0-100 on how directly they threaten the subject's core business "
            "(same ICP, same product category, same geo, similar pricing). "
            "100 = head-on direct competitor. 0 = adjacent or irrelevant. "
            "Output strict JSON mapping each competitor's domain to its integer score. "
            'Example: {"competitor-a.com": 85, "competitor-b.io": 42}. '
            "No prose, no explanation, no markdown fences."
        )
        slim = [
            {"name": c.get("name", ""), "domain": c.get("domain", ""), "tagline": c.get("tagline", "")}
            for c in candidates
        ]
        user = f"SUBJECT:\n{subject_summary}\n\nCOMPETITORS:\n{json.dumps(slim, ensure_ascii=False)}"
        try:
            raw = self.extract_json(system, user, max_tokens=1024)
        except Exception as e:
            logger.warning("score_threats_candidates parse failed error=%s", e)
            return {}
        out: dict[str, int] = {}
        for k, v in raw.items():
            try:
                out[str(k)] = max(0, min(100, int(v)))
            except (TypeError, ValueError):
                continue
        return out

    @traced
    def discover_competitors_fallback(
        self,
        name: str,
        domain: str,
        positioning: str,
        markets: str,
    ) -> list[dict]:
        """Fallback competitor discovery using Claude knowledge when Linkup returns empty.

        Returns list[dict] matching discover._SCHEMA competitor items.
        """
        system = (
            "You are a competitive intelligence analyst. "
            "Output ONLY strict JSON — no prose, no markdown fences.\n"
            "Return a JSON object with a 'competitors' array. "
            "Each item must have: name (string), website (full https:// URL), "
            "hq_city (string), hq_country (string), "
            "founded_year (integer), "
            "funding_stage (Seed/Series A/Series B/Series C+/Public/Bootstrapped), "
            "employee_count (approximate integer as string), "
            "one_liner (1 sentence describing what they do), "
            "differentiator (main difference vs the subject company)."
        )
        user = (
            f"List 10-15 direct competitors of {name} ({domain}).\n"
            f"Context: {positioning}. Market: {markets}.\n"
            "Prioritise companies with overlapping core features, same target segment, "
            f"similar pricing tier. Do NOT include {name} ({domain}) itself."
        )
        try:
            result = self.extract_json(system, user, max_tokens=2048)
            candidates = result.get("competitors", [])
            if isinstance(candidates, list):
                return [c for c in candidates if isinstance(c, dict) and c.get("name")]
            return []
        except Exception as e:
            logger.warning("discover_competitors_fallback failed: %s", e)
            return []

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

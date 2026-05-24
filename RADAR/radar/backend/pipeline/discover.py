"""Phase 2 — DISCOVER: find 15 competitors for a domain."""
import asyncio
import logging
import time
from typing import Awaitable, Callable, Optional

from clients.claude_client import ClaudeClient
from clients.linkup_client import LinkupClient
from models.company import CompanyProfile
from utils.dedup import dedup_by_website

logger = logging.getLogger(__name__)

EventCallback = Callable[[dict], Awaitable[None]]

_SCHEMA = {
    "type": "object",
    "properties": {
        "competitors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "website": {"type": "string"},
                    "hq_city": {"type": "string"},
                    "hq_country": {"type": "string"},
                    "founded_year": {"type": "integer"},
                    "funding_stage": {"type": "string"},
                    "employee_count": {"type": "string"},
                    "one_liner": {"type": "string"},
                    "differentiator": {"type": "string"},
                },
                "required": ["name", "website"],
            },
        }
    },
}


async def run(
    profile: CompanyProfile,
    linkup: LinkupClient,
    event_cb: Optional[EventCallback] = None,
) -> tuple[list[dict], list[str]]:
    """Return (competitor dicts, source URLs consulted)."""
    t0 = time.monotonic()
    domain = profile.domain
    logger.info("phase=DISCOVER company=%s status=start", domain)

    async def emit(event: dict) -> None:
        if event_cb:
            try:
                await event_cb(event)
            except Exception as _e:
                logger.debug("discover emit error ignored: %s", _e)

    markets = ", ".join(m.label for m in profile.markets) if profile.markets else "its market"
    positioning = profile.positioning or f"{profile.name} startup"

    def _discover_query(name: str, domain: str, positioning: str, markets: str) -> str:
        return (
            f"You are a competitive intelligence analyst. Find the 15 main direct competitors of {name} ({domain}).\n\n"
            f"Context: {positioning}. Market: {markets}.\n\n"
            f"Search G2, Capterra, AlternativeTo, ProductHunt, Crunchbase, Y Combinator, and industry news. "
            f"Run adjacent searches for '{name} alternatives', '{name} vs', "
            f"'best {markets} software', '{markets} startups 2024 2025'. "
            f"Do NOT include {name} ({domain}) itself in the results.\n\n"
            "For each competitor extract:\n"
            "- name: company name\n"
            "- website: full URL (https://...)\n"
            "- hq_city, hq_country: headquarters location\n"
            "- founded_year: integer\n"
            "- funding_stage: Seed/Series A/B/C+/Public/Bootstrapped\n"
            "- employee_count: approximate integer\n"
            "- one_liner: one sentence description\n"
            f"- differentiator: main differentiator vs {name} specifically\n\n"
            "Prioritize direct competitors (same target segment, overlapping core features, similar pricing tier). "
            "Exclude tools that are integrations, add-ons, or only tangentially related."
        )

    raw = await linkup.search(
        query=_discover_query(profile.name, domain, positioning, markets),
        depth="deep",
        schema=_SCHEMA,
    )

    raw_list: list[dict] = []
    data = raw.get("data") or raw.get("answer") or raw.get("output") or {}
    if isinstance(data, dict):
        raw_list = data.get("competitors", [])
    elif isinstance(data, list):
        raw_list = data

    # Capture source URLs Linkup consulted — dedup preserving order
    sources_raw: list = raw.get("sources", [])
    _seen: set[str] = set()
    source_urls: list[str] = []
    for s in sources_raw:
        if isinstance(s, dict):
            u = s.get("url")
            if u and u not in _seen:
                _seen.add(u)
                source_urls.append(u)

    competitors = dedup_by_website(raw_list)[:15]

    # Rank by competitive threat so enrich phase spends depth M on the top-1.
    if competitors:
        subject_summary = (
            f"{profile.name} ({profile.domain}) — "
            f"{profile.positioning or profile.summary or ''}"
        ).strip(" —")
        try:
            scores = await asyncio.to_thread(
                ClaudeClient().score_threats, subject_summary, competitors
            )
            if scores:
                competitors.sort(
                    key=lambda c: scores.get(str(c.get("website", "")), 0),
                    reverse=True,
                )
                logger.info(
                    "phase=DISCOVER threat_sort_top=%s score=%d",
                    competitors[0].get("website"),
                    scores.get(str(competitors[0].get("website", "")), 0),
                )
        except Exception as e:
            logger.warning("threat scoring failed, keeping discover order: %s", e)

    for c in competitors:
        c_name = str(c.get("name", ""))[:100]
        c_website = str(c.get("website", ""))[:100]
        if c_name or c_website:
            await emit({
                "phase": "DISCOVER",
                "status": "progress",
                "kind": "candidate_found",
                "payload": {"name": c_name, "website": c_website},
            })

    logger.info(
        "phase=DISCOVER company=%s status=ok count=%d sources=%d duration=%.1fs",
        domain, len(competitors), len(source_urls), time.monotonic() - t0,
    )
    return competitors, source_urls


if __name__ == "__main__":
    import asyncio
    import json
    import sys

    from dotenv import load_dotenv

    from models.company import CompanyProfile

    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.discover <domain>", file=sys.stderr)
        sys.exit(1)

    domain = sys.argv[1].strip().lower()
    stub = CompanyProfile(name=domain, domain=domain, pipeline_run_id="cli-test")
    client = LinkupClient()
    competitors, sources = asyncio.run(run(stub, client))
    print(json.dumps({"competitors": competitors, "source_urls": sources}, indent=2, ensure_ascii=False))

"""Phase 3 — ENRICH: build CompetitorProfile for each competitor."""
import asyncio
import logging
import time
from datetime import datetime, timezone

from clients.linkup_client import LinkupClient
from models.company import DataPoint, HQ
from models.competitor import CompetitorProfile, PricingSignal, PricingTier
from utils.geocoding import geocode

logger = logging.getLogger(__name__)


def _make_tasks_payload(competitors: list[dict]) -> list[dict]:
    tasks = []
    for c in competitors:
        website = c.get("website", "")
        name = c.get("name", website)

        tasks.append({
            "type": "search",
            "input": {
                "q": f"{name} pricing plans tiers cost 2025",
                "depth": "standard",
                "outputType": "sourcedAnswer",
            },
        })
        tasks.append({
            "type": "search",
            "input": {
                "q": f"{name} new features product launch funding news since 2024-11-01",
                "depth": "standard",
                "outputType": "sourcedAnswer",
                "fromDate": "2024-11-01",
            },
        })
    return tasks


def _parse_pricing(answer: str, sources: list, now: str) -> PricingSignal:
    src_url = sources[0].get("url") if sources else None
    return PricingSignal(
        tiers=[PricingTier(
            name="extracted",
            price_monthly_eur=DataPoint(value=None, confidence="low", source_url=src_url, extracted_at=now),
        )],
        source_url=src_url,
        extracted_at=now,
    )


async def run(competitors: list[dict], linkup: LinkupClient, run_id: str) -> list[CompetitorProfile]:
    t0 = time.monotonic()
    now = datetime.now(timezone.utc).isoformat()
    logger.info("phase=ENRICH status=start count=%d", len(competitors))

    tasks_payload = _make_tasks_payload(competitors)
    task_results = await linkup.tasks(tasks_payload)

    profiles: list[CompetitorProfile] = []

    async def _noop():
        return None

    geocode_tasks = []
    for c in competitors:
        city = c.get("hq_city", "")
        country = c.get("hq_country", "")
        geocode_tasks.append(geocode(city, country) if (city or country) else _noop())

    coords_list = await asyncio.gather(*geocode_tasks, return_exceptions=True)

    for i, c in enumerate(competitors):
        pricing_result = task_results[i * 2] if i * 2 < len(task_results) else {}
        signals_result = task_results[i * 2 + 1] if i * 2 + 1 < len(task_results) else {}

        pricing_output = pricing_result.get("output", {})
        signals_output = signals_result.get("output", {})

        pricing_answer = pricing_output.get("answer", "")
        pricing_sources = pricing_output.get("sources", [])

        signals_answer = signals_output.get("answer", "")

        coords = coords_list[i]
        hq = None
        if c.get("hq_city") or c.get("hq_country"):
            hq = HQ(
                city=c.get("hq_city"),
                country=c.get("hq_country"),
                lat=coords[0] if isinstance(coords, tuple) else None,
                lng=coords[1] if isinstance(coords, tuple) else None,
            )

        profile = CompetitorProfile(
            name=c.get("name", ""),
            website=c.get("website", ""),
            hq=hq,
            founded_year=c.get("founded_year"),
            funding_stage=DataPoint(
                value=c.get("funding_stage"),
                confidence="medium",
                extracted_at=now,
            ) if c.get("funding_stage") else None,
            employee_count=DataPoint(
                value=c.get("employee_count"),
                confidence="low",
                extracted_at=now,
            ) if c.get("employee_count") else None,
            one_liner=c.get("one_liner"),
            differentiator=c.get("differentiator"),
            pricing=_parse_pricing(pricing_answer, pricing_sources, now) if pricing_answer else None,
            recent_signals=[s.strip() for s in signals_answer.split("\n") if s.strip()][:5],
            pipeline_run_id=run_id,
        )
        profiles.append(profile)

    logger.info("phase=ENRICH status=ok count=%d duration=%.1fs", len(profiles), time.monotonic() - t0)
    return profiles


if __name__ == "__main__":
    import json
    import sys

    from dotenv import load_dotenv

    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.enrich '<json array of competitor dicts>'", file=sys.stderr)
        sys.exit(1)

    competitors_raw = json.loads(sys.argv[1])
    client = LinkupClient()
    result = asyncio.run(run(competitors_raw, client, run_id="cli-test"))
    print(json.dumps([p.model_dump() for p in result], indent=2, ensure_ascii=False, default=str))

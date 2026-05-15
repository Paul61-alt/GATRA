"""Phase 2 — DISCOVER: find 15 competitors for a domain."""
import logging
import time

from clients.linkup_client import LinkupClient
from models.company import CompanyProfile
from utils.dedup import dedup_by_website

logger = logging.getLogger(__name__)

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


async def run(profile: CompanyProfile, linkup: LinkupClient) -> list[dict]:
    """Return list of up to 15 deduplicated competitor dicts."""
    t0 = time.monotonic()
    domain = profile.domain
    logger.info("phase=DISCOVER company=%s status=start", domain)

    markets = ", ".join(m.label for m in profile.markets) if profile.markets else "its market"
    positioning = profile.positioning or f"{profile.name} startup"

    raw = await linkup.search(
        query=(
            f"Find the 15 main direct competitors of {profile.name} ({domain}). "
            f"Company description: {positioning}. Market: {markets}. "
            "For each competitor return: name, website URL, HQ city, HQ country, "
            "founding year, funding stage (Seed/Series A/B/C+/Public/Bootstrapped), "
            "approximate employee count, one-sentence description, "
            "and main differentiator vs the target company."
        ),
        depth="deep",
        schema=_SCHEMA,
    )

    raw_list: list[dict] = []
    data = raw.get("data") or raw.get("answer") or raw.get("output") or {}
    if isinstance(data, dict):
        raw_list = data.get("competitors", [])
    elif isinstance(data, list):
        raw_list = data

    competitors = dedup_by_website(raw_list)[:15]
    logger.info("phase=DISCOVER company=%s status=ok count=%d duration=%.1fs", domain, len(competitors), time.monotonic() - t0)
    return competitors


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
    result = asyncio.run(run(stub, client))
    print(json.dumps(result, indent=2, ensure_ascii=False))

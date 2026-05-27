"""Pre-warm radar output cache for a given domain.

Demo-day usage: run once before the show with the target domain so the
subsequent /scan call hits cache and returns instantly.

    cd RADAR/radar/backend && python -m scripts.warm_cache notion.so

Mirrors the /scan handler logic (main.py:171-217). Caps competitors at 10
to match the auto-enrich frontend flow.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("warm_cache")

# Make the backend package importable when run as a module from the backend/ dir.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from clients import ClaudeClient, LinkupClient  # noqa: E402
from models import PipelineRun, PipelineStatus  # noqa: E402
from pipeline import discover, enrich, synthesize, understand  # noqa: E402
from pipeline.transform import pipeline_run_to_radar_output  # noqa: E402
from utils import cache_set, normalize_domain  # noqa: E402

TOP_N = 10


def _candidates_to_enrich_dicts(candidates):
    return [
        {"name": c.name, "website": f"https://{c.domain}", "one_liner": c.tagline}
        for c in candidates
    ]


async def warm(raw_domain: str) -> None:
    domain = normalize_domain(raw_domain) or raw_domain
    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    linkup = LinkupClient()
    claude = ClaudeClient()

    logger.info("warm=start domain=%s top_n=%d", domain, TOP_N)

    company_profile = await understand.run(domain, linkup, run_id, claude=claude)
    candidates, sources, threat_scores = await discover.run(company_profile, linkup)

    top_candidates = candidates[:TOP_N]
    logger.info("warm=discover domain=%s candidates=%d kept=%d", domain, len(candidates), len(top_candidates))

    competitor_dicts = _candidates_to_enrich_dicts(top_candidates)
    competitor_profiles = await enrich.run(competitor_dicts, linkup, run_id)
    radar_scores = synthesize.run(company_profile, competitor_profiles)

    run = PipelineRun(
        id=run_id,
        company_domain=domain,
        status=PipelineStatus.COMPLETED,
        created_at=created_at,
        completed_at=datetime.now(timezone.utc).isoformat(),
        company_profile=company_profile,
        competitors=competitor_profiles,
        discover_source_urls=sources,
        radar_scores=radar_scores,
        threat_scores=threat_scores,
    )

    radar_output = pipeline_run_to_radar_output(run)
    result = radar_output.model_dump(by_alias=True, mode="json", exclude_none=True)

    cache_key = f"radar_{domain}"
    cache_set(cache_key, result)
    logger.info("warm=ok domain=%s cache_key=%s", domain, cache_key)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m scripts.warm_cache <domain>", file=sys.stderr)
        return 2
    asyncio.run(warm(sys.argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

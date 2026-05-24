"""One-shot recovery for the indy.fr scan interrupted by frontend refresh.

The /research job (8db76728-...) was billed €0.46 and continues at Linkup.
This script waits for it, re-runs understand+discover (~€0.10), parses the
research output, builds RadarOutput, injects into cache → frontend free hit.

Run from backend/:
    python evals/recover_indy.py
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

from clients.linkup_client import LinkupClient
from models.pipeline import PipelineRun, PipelineStatus
from pipeline import discover, synthesize, understand
from pipeline.enrich import _parse_result, _stub
from pipeline.transform import pipeline_run_to_radar_output
from utils import cache_set
from utils.geocoding import geocode

JOB_ID = "8db76728-7eb6-4e63-84fc-8e9bbbae3a4e"
DOMAIN = "indy.fr"
TOP_WEBSITE = "https://freebe.me/"  # from backend log: threat_sort_top=https://freebe.me/


async def main() -> None:
    linkup = LinkupClient()
    run_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    print(f"⏳ Waiting for job {JOB_ID} to complete (up to 15min)...")
    research = await linkup.wait_for_research(JOB_ID, max_wait=900, interval=15)
    if research.get("status") == "failed":
        print(f"❌ Job failed: {research.get('error')}", file=sys.stderr)
        sys.exit(1)
    print("✓ Research job completed.")

    print(f"\n⏳ Re-running understand({DOMAIN})...")
    company_profile = await understand.run(DOMAIN, linkup, run_id)
    print(f"✓ {company_profile.name}")

    print(f"\n⏳ Re-running discover...")
    competitors, discover_sources = await discover.run(company_profile, linkup)
    print(f"✓ {len(competitors)} competitors found, {len(discover_sources)} sources")

    top = next(
        (c for c in competitors if c.get("website", "").rstrip("/") == TOP_WEBSITE.rstrip("/")),
        None,
    )
    if top is None:
        print(f"⚠️  freebe.me not found in this discover run. Using competitors[0] = {competitors[0].get('name')}")
        top = competitors[0]
    print(f"→ Top competitor: {top.get('name')} ({top.get('website')})")

    print(f"\n⏳ Geocoding + parsing recovered research output...")
    coords = await geocode(top.get("hq_city", ""), top.get("hq_country", ""))
    top_profile = _parse_result(research, top, now, run_id, coords)

    print(f"\n⏳ Stubbing remaining {len(competitors) - 1} competitors...")
    tail_profiles = [_stub(c, run_id, now) for c in competitors[1:]]
    all_profiles = [top_profile] + tail_profiles

    radar_scores = synthesize.run(company_profile, all_profiles)

    run = PipelineRun(
        id=run_id,
        company_domain=DOMAIN,
        status=PipelineStatus.COMPLETED,
        created_at=now,
        completed_at=datetime.now(timezone.utc).isoformat(),
        company_profile=company_profile,
        competitors=all_profiles,
        discover_source_urls=discover_sources,
        radar_scores=radar_scores,
    )
    radar_output = pipeline_run_to_radar_output(run)
    radar_dict = radar_output.model_dump(by_alias=True, mode="json", exclude_none=True)
    cache_set(f"radar_{DOMAIN}", radar_dict)

    print(f"\n✓ Cache primed: radar_{DOMAIN}")
    print(f"✓ Open frontend, search '{DOMAIN}' — instant result (cache hit).")


if __name__ == "__main__":
    asyncio.run(main())

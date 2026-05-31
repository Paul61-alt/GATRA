"""Minimal E2E: URL → understand → discover → enrich 1 competitor → VC memo → cache → frontend.

Run from backend/:
    python evals/eval_e2e_simple.py [url]              # injects cache → frontend shows result for free
    python evals/eval_e2e_simple.py [url] --no-cache   # skips cache → frontend triggers live pipeline + animation

Cost: ~€0.65 total (1× understand search + 1× discover deep + 1× research M + 1× Claude memo).

For animation mode: start backend with RADAR_MAX_ENRICH=1 then search from frontend.

⚠️  Does NOT call POST /scan — that triggers a full 5-competitor parallel enrich (€1.38).
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

from clients.claude_client import ClaudeClient
from clients.linkup_client import BudgetExceededError, LinkupClient
from models.pipeline import PipelineRun, PipelineStatus
from pipeline import discover, enrich, understand
from pipeline.transform import pipeline_run_to_radar_output
from utils import cache_set


def _normalize_domain(url: str) -> str:
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    return parsed.netloc.lstrip("www.").rstrip("/") or parsed.path.lstrip("www.").rstrip("/")


def _sep(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


async def main(url: str, no_cache: bool = False) -> None:
    domain = _normalize_domain(url)
    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    linkup = LinkupClient()
    claude = ClaudeClient()

    try:
        # ── 1. UNDERSTAND ─────────────────────────────────────────
        _sep("PHASE 1 — UNDERSTAND")
        print(f"domain: {domain}")
        company_profile = await understand.run(domain, linkup, run_id)
        print(f"✓ {company_profile.name} | {company_profile.summary[:120] if company_profile.summary else ''}")

        # ── 2. DISCOVER ────────────────────────────────────────────
        _sep("PHASE 2 — DISCOVER")
        competitors, discover_sources = await discover.run(company_profile, linkup)
        print(f"✓ {len(competitors)} competitors found, {len(discover_sources)} sources")
        for i, c in enumerate(competitors[:5]):
            print(f"  [{i}] {c.get('name')} — {c.get('website')}")

        if not competitors:
            print("No competitors found — aborting.")
            return

        # ── 3. ENRICH — top 1 only ─────────────────────────────────
        _sep("PHASE 3 — ENRICH (1 competitor, depth=M)")
        top1 = competitors[:1]
        print(f"Enriching: {top1[0].get('name')} ({top1[0].get('website')})")
        profiles = await enrich.run(top1, linkup, run_id)
        competitor = profiles[0]

        _sep("PYDANTIC — CompetitorProfile")
        print(json.dumps(competitor.model_dump(mode="json"), indent=2, ensure_ascii=False, default=str))

        # ── 4. VC MEMO ─────────────────────────────────────────────
        _sep("PHASE 4 — VC MEMO (Claude)")
        memo = claude.generate_vc_memo(competitor.model_dump(mode="json"))
        print(memo)

        # ── 5. CACHE INJECT (skipped with --no-cache) ─────────────
        _sep("PHASE 5 — CACHE")
        run = PipelineRun(
            id=run_id,
            company_domain=domain,
            status=PipelineStatus.COMPLETED,
            created_at=created_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            company_profile=company_profile,
            competitors=profiles,
        )
        radar_output = pipeline_run_to_radar_output(run)
        radar_dict = radar_output.model_dump(by_alias=True, mode="json", exclude_none=True)

        if no_cache:
            print("⚡ --no-cache: skipping cache inject.")
            print()
            print("For animation — start backend with RADAR_MAX_ENRICH=1, then search:")
            print("  RADAR_MAX_ENRICH=1 uvicorn main:app --reload")
            print(f"  domain to search: {domain}")
        else:
            cache_key = f"radar_{domain}"
            cache_set(cache_key, radar_dict)
            print(f"✓ Cache primed: key=radar_{domain}")
            print()
            print("Frontend ready — start the backend + frontend, then search:")
            print(f"  domain: {domain}")
            print("  POST /scan → cache hit → €0, no new API calls.")

    except BudgetExceededError as e:
        print(f"\n⚠️  BUDGET EXCEEDED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]
    no_cache = "--no-cache" in args
    url_args = [a for a in args if not a.startswith("--")]
    url = url_args[0] if url_args else "linear.app"
    asyncio.run(main(url, no_cache=no_cache))

"""One-shot probe: re-run ENRICH lane1 (identity_funding) for Finary's 10
competitors at depth=L (same $1.50 cost as S) to test the 'depth too shallow'
hypothesis. Prints competitors[] funding/employee fields from the raw Linkup
output. ~1.5€. Run from backend/ dir.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from clients.linkup_client import LinkupClient
from pipeline.enrich import _lane1_query, LANE1_SCHEMA, _extract_competitors_list

COMPETITORS = [
    {"name": "Nalo", "website": "nalo.fr"},
    {"name": "Linxo", "website": "linxo.com"},
    {"name": "Grisbee", "website": "grisbee.com"},
    {"name": "Horiz.io", "website": "horiz.io"},
    {"name": "Sharesight", "website": "sharesight.com"},
    {"name": "InvMon", "website": "invmon.com"},
    {"name": "Wealthfolio", "website": "wealthfolio.app"},
    {"name": "Quicken", "website": "quicken.com"},
    {"name": "Merlin", "website": "merlin.com"},
    {"name": "Sure", "website": "sure.com"},
]

DEPTH = os.environ.get("PROBE_DEPTH", "L")


async def main() -> None:
    linkup = LinkupClient(api_key=os.environ["LINKUP_API_KEY"])
    query = _lane1_query(COMPETITORS)
    print(f"=== Running lane1 (identity_funding) depth={DEPTH} for {len(COMPETITORS)} competitors ===")
    raw = await linkup.research_and_wait(query, depth=DEPTH, structured_schema=LANE1_SCHEMA)
    print("=== RAW top-level keys ===", list(raw.keys()) if isinstance(raw, dict) else type(raw))
    items = _extract_competitors_list(raw)
    print(f"=== Parsed {len(items)} competitor items ===\n")
    for it in items:
        print(
            f"{it.get('name'):<14} emp={it.get('employee_count')!s:<6} "
            f"founded={it.get('founded_year')!s:<6} stage={it.get('funding_stage')!s:<12} "
            f"total_usd={it.get('funding_total_usd')!s:<12} rounds={len(it.get('funding_rounds') or [])}"
        )
    print("\n=== FULL first item ===")
    print(json.dumps(items[0] if items else {}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

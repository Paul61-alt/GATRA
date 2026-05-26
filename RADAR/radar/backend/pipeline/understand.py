"""Phase 1 — UNDERSTAND: build CompanyProfile for a domain.

Architecture v2 — "Fetch First":
  Step 1 — Parallel /fetch on 4 company pages (homepage, /about, /team, /pricing)
            → authoritative "what the company says about itself" — €0.020
  Step 2 — Claude parses all pages in ONE call → page-sourced fields — ~€0.003
  Step 3 — /search deep on EXTERNAL sources only (Crunchbase, LinkedIn, press)
            → "what the world says about this company" — €0.055
  Step 4 — Merge: page data wins for HQ/GTM/team/pricing; search wins for funding/news
  Step 5 — Claude enrich_company_profile: equity_story, domains, segments — ~€0.004

Total: ~€0.082/scan
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional
from urllib.parse import urlparse
from uuid import uuid4

from clients.claude_client import ClaudeClient
from clients.linkup_client import LinkupClient
from models.company import (
    AcquisitionInfo, CompanyProfile, CustomerExample, DataPoint,
    Funding, FundingRound, HQ, Investor, KeyPerson, Market, NewsItem,
    PricingDetail, PricingTier,
)
from utils.geocoding import geocode

logger = logging.getLogger(__name__)

EventCallback = Callable[[dict], Awaitable[None]]


# ── SEGMENT NORMALISATION ──────────────────────────────────────────────────────
# Claude and Linkup may return English segment names — map to our French taxonomy.
_SEGMENT_MAP: dict[str, str] = {
    "grand compte":     "Grand compte",
    "enterprise":       "Grand compte",
    "large enterprise": "Grand compte",
    "eti":              "ETI",
    "mid-market":       "ETI",
    "midmarket":        "ETI",
    "mid market":       "ETI",
    "pme":              "PME",
    "smb":              "PME",
    "small business":   "PME",
    "small":            "PME",
    "startup":          "Startup",
    "consumer":         "Consumer",
    "b2c":              "Consumer",
}
_VALID_SEGMENTS = {"Grand compte", "ETI", "PME", "Startup", "Consumer"}


def _norm_segment(raw: str | None) -> str | None:
    """Map any segment string to our enum. Returns None if not mappable."""
    if not raw:
        return None
    normalized = _SEGMENT_MAP.get(raw.strip().lower())
    if normalized:
        return normalized
    for v in _VALID_SEGMENTS:
        if raw.strip().lower() == v.lower():
            return v
    return None


# ── EXTERNAL SEARCH SCHEMA ─────────────────────────────────────────────────────
# Only fields sourced from external databases (Crunchbase, LinkedIn, press).
# Page-sourced fields (HQ, GTM, team…) come from _extract_from_pages() via Claude.
_EXTERNAL_SCHEMA = {
    "type": "object",
    "properties": {
        # ── COMPANY BASICS (fallback when page fetch fails) ───────────
        "hq_city":    {"type": "string"},
        "hq_country": {"type": "string"},
        "founded_year": {"type": "integer"},

        # ── SIZE ──────────────────────────────────────────────────────
        "employees": {
            "type": "object",
            "properties": {
                "value":      {"type": "integer"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
            },
        },
        "employee_growth_yoy": {"type": "number"},  # fraction: 0.12 = +12%

        # ── FUNDING ───────────────────────────────────────────────────
        "funding_total_eur": {
            "type": "object",
            "properties": {
                "value":      {"type": "integer"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
            },
        },
        "funding_stage":           {"type": "string"},
        "funding_last_round":      {"type": "string"},
        "funding_last_round_date": {"type": "string"},
        "funding_rounds": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "round":      {"type": "string"},
                    "amount_eur": {"type": "integer"},
                    "date":       {"type": "string"},
                    "lead":       {"type": "string"},
                },
            },
        },
        "notable_investors": {
            "type": "array",
            "items": {"type": "string"},
        },

        # ── TRACTION ──────────────────────────────────────────────────
        "arr_usd": {
            "type": "object",
            "properties": {
                "value":      {"type": "number"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
                "evidence":   {"type": "string"},
            },
        },
        "customer_count": {
            "type": "object",
            "properties": {
                "value":      {"type": "integer"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
                "evidence":   {"type": "string"},
            },
        },

        # ── ACQUISITION ───────────────────────────────────────────────
        "acquisition": {
            "type": "object",
            "properties": {
                "acquired":   {"type": "boolean"},
                "acquirer":   {"type": "string"},
                "amount_eur": {"type": "integer"},
                "year":       {"type": "integer"},
                "source_url": {"type": "string"},
            },
        },

        # ── TECH ──────────────────────────────────────────────────────
        "tech_stack": {
            "type": "array",
            "items": {"type": "string"},
        },

        # ── TEAM (supplement: LinkedIn URLs not on website) ────────────
        "key_people": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name":       {"type": "string"},
                    "role":       {"type": "string"},
                    "background": {"type": "string"},
                    "linkedin":   {"type": "string"},
                },
            },
        },

        # ── CUSTOMERS (from press/case studies — not on website) ───────
        "notable_customers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name":     {"type": "string"},
                    "domain":   {"type": "string"},
                    "segment":  {"type": "string", "enum": ["Grand compte", "ETI", "PME", "Startup", "Consumer"]},
                    "industry": {"type": "string"},
                    "evidence": {"type": "string"},
                },
            },
        },

        # ── SIGNALS ───────────────────────────────────────────────────
        "growth_signals": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recent_news": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date":       {"type": "string"},
                    "headline":   {"type": "string"},
                    "source_url": {"type": "string"},
                },
            },
        },
    },
}


# ── STEP 1: PARALLEL FETCH ─────────────────────────────────────────────────────

async def _fetch_company_pages(
    domain: str,
    linkup: LinkupClient,
    emit: Callable,
) -> dict[str, str]:
    """Fetch homepage, /about, /team, /pricing in parallel.

    Returns dict: page_slug → raw content string.
    Missing or empty pages are excluded silently (404, Cloudflare, JS-only).
    Cost: 4 × €0.005 = €0.020.
    """
    pages_to_fetch = {
        "homepage": f"https://{domain}",
        "about":    f"https://{domain}/about",
        "company":  f"https://{domain}/company",
        "team":     f"https://{domain}/team",
        "pricing":  f"https://{domain}/pricing",
    }

    async def fetch_one(slug: str, url: str) -> tuple[str, str]:
        try:
            result = await linkup.fetch(url, render_js=False)
            content = (
                result.get("markdown")
                or result.get("content")
                or result.get("answer")
                or result.get("output")
                or ""
            )
            if content and len(content) > 100:  # skip near-empty responses
                await emit({
                    "phase": "UNDERSTAND",
                    "status": "progress",
                    "kind": "source_consulted",
                    "payload": {"url": url, "domain": domain},
                })
                logger.debug("understand fetch_page slug=%s chars=%d", slug, len(content))
                return slug, content
        except Exception as e:
            logger.debug("understand fetch_page_failed slug=%s error=%s", slug, e)
        return slug, ""

    results = await asyncio.gather(*[
        fetch_one(slug, url) for slug, url in pages_to_fetch.items()
    ])
    return {slug: content for slug, content in results if content}


# ── STEP 2: CLAUDE PAGE EXTRACTION ────────────────────────────────────────────

_PAGE_EXTRACT_SYSTEM = """\
You are a company intelligence analyst reading a company's own website pages.
Extract structured company data from these pages.
Return ONLY strict JSON, no prose, no markdown fences.

Key rules:
- HQ: look for physical office address on /about. Prefer founding city over US commercial office.
  If address says "Paris" or any non-US city → use that. Ignore LinkedIn "New York" if /about says otherwise.
- GTM: find the PRIMARY call-to-action button on the homepage.
  "Request demo" / "Book a demo" / "Talk to sales" / "Contact us" → sales-led (return exact text as evidence).
  "Start free" / "Sign up" / "Try free" / "Get started" (no sales mention) → product-led.
- Customers: only include those explicitly shown on website (logos, testimonials, case studies visible on pages).
- Key people: extract from /team or /about. Include LinkedIn URL only if directly linked on the page.
- Pricing: extract from /pricing page only. null if page not available or enterprise/contact-sales only.
- Set any field to null if not found on these pages — do not guess or hallucinate."""

def _extract_from_pages(
    domain: str,
    pages: dict[str, str],
    claude: ClaudeClient,
) -> dict:
    """One Claude call to parse all fetched pages. Returns page-sourced fields dict."""
    if not pages:
        return {}

    sections = []
    if pages.get("homepage"):
        sections.append(f"=== HOMEPAGE ({domain}/) ===\n{pages['homepage'][:3000]}")
    if pages.get("about"):
        sections.append(f"=== ABOUT PAGE ({domain}/about) ===\n{pages['about'][:2500]}")
    if pages.get("team"):
        sections.append(f"=== TEAM PAGE ({domain}/team) ===\n{pages['team'][:2000]}")
    if pages.get("pricing"):
        sections.append(f"=== PRICING PAGE ({domain}/pricing) ===\n{pages['pricing'][:2000]}")

    user = (
        f"Company domain: {domain}\n\n"
        + "\n\n".join(sections)
        + """

Return this JSON (null for any field not found):
{
  "name": "...",
  "website": "https://...",
  "summary": "one paragraph description",
  "founded_year": N,
  "hq_city": "...",
  "hq_country": "...",
  "geo_coverage": "Local|National|Regional|Global",
  "positioning": "...",
  "markets": [{"id": "...", "label": "...", "primary": true}],
  "target_segment": {"value": "Enterprise|Mid-Market|SMB|Consumer|Mixed", "confidence": "high|medium|low", "evidence": "..."},
  "target_verticals": ["..."],
  "business_model": {"value": "B2B|B2C|B2B2C|Marketplace|API/Platform", "confidence": "high|medium|low"},
  "gtm_motion": {"value": "sales-led|product-led|marketing-led|community-led", "confidence": "high|medium|low", "evidence": "exact CTA text"},
  "pricing_model": {"value": "Freemium|Subscription|Usage-based|Enterprise/Sur devis|Hybrid", "confidence": "high|medium|low"},
  "key_differentiator": {"value": "max 20 words", "confidence": "high|medium|low"},
  "top_3_features": ["...", "...", "..."],
  "notable_customers": [{"name": "...", "domain": "domain.com", "segment": "Grand compte|ETI|PME|Startup|Consumer", "industry": "...", "evidence": "quote or context"}],
  "pricing": {"free_plan": true|false|null, "tiers": [{"name": "...", "price_monthly_usd": N, "price_annual_usd": N, "features": ["..."], "target": "..."}]},
  "key_people": [{"name": "...", "role": "...", "background": "...", "linkedin": "linkedin.com/in/..."}]
}"""
    )

    try:
        return claude.extract_json(_PAGE_EXTRACT_SYSTEM, user, max_tokens=2048)
    except Exception as e:
        logger.warning("understand extract_from_pages failed domain=%s error=%s", domain, e)
        return {}


# ── STEP 3: EXTERNAL SEARCH QUERY ─────────────────────────────────────────────

def _external_search_query(domain: str, company_name: str | None = None) -> str:
    """Focused external-only search. Company pages already fetched — don't re-crawl them."""
    name = company_name or domain
    return (
        f"Research {name} ({domain}) using ONLY external sources.\n"
        f"Do NOT crawl {domain} directly — those pages have already been read.\n\n"
        "Target high-quality sources (examples, not exclusive): "
        "Crunchbase, Pitchbook, Dealroom, LinkedIn company page, TechCrunch, "
        "EU Startups, Les Echos, VentureBeat, press releases, financial filings.\n\n"
        "Find:\n"
        "HQ: Founding city and country from Crunchbase or Dealroom (NOT LinkedIn office address).\n"
        "FOUNDED: Year the company was founded.\n"
        "EMPLOYEES: Current headcount and YoY growth percentage from LinkedIn company page.\n"
        f"FUNDING: All investment rounds for {name} — amount in EUR, date, lead investor, "
        "total raised, current stage (Seed/Series A/B/C+/Public/Bootstrapped).\n"
        "INVESTORS: All notable investors — VCs, angels, corporate funds.\n"
        "TRACTION: ARR or revenue milestones announced in press or interviews. "
        "Customer count if publicly announced.\n"
        "ACQUISITION: Whether the company has been acquired — acquirer, amount EUR, year.\n"
        "TECH STACK: Technologies inferred from job postings, BuiltWith, engineering blog.\n"
        "TEAM: Founders and executives — LinkedIn profile URLs (linkedin.com/in/...), background.\n"
        "NEWS: Last 3 significant news items (funding, product launch, partnership) with date and URL.\n"
        "SIGNALS: Growth indicators — new offices, hiring surges, geo expansion, product launches.\n"
        "CUSTOMERS: Enterprise customers mentioned in press, case studies, or analyst reports "
        "(complementing what is shown on the website)."
    )


# ── STEP 4: MERGE ─────────────────────────────────────────────────────────────

def _merge_data(page_data: dict, search_data: dict) -> dict:
    """Merge page-extracted and external-search data.

    Page data wins: HQ, GTM, founded_year, summary, positioning, markets,
                    key_people names/roles, pricing (tiers), customers visible on site.
    Search data wins: funding, investors, employees, tech_stack, news, ARR, acquisition.
    Merge: key_people (page names + search LinkedIn URLs), customers (union, page wins per-customer).
    """
    merged: dict = {}

    # Fields where page data is authoritative
    _PAGE_WINS = [
        "name", "website", "summary", "founded_year",
        "hq_city", "hq_country", "geo_coverage",
        "positioning", "markets", "target_segment", "target_verticals",
        "business_model", "gtm_motion", "pricing_model",
        "key_differentiator", "top_3_features", "pricing",
    ]
    # Fields where external search is authoritative
    _SEARCH_WINS = [
        "employees", "employee_growth_yoy",
        "funding_total_eur", "funding_stage", "funding_last_round",
        "funding_last_round_date", "funding_rounds", "notable_investors",
        "arr_usd", "customer_count", "acquisition",
        "tech_stack", "growth_signals", "recent_news",
    ]

    def _has_value(v) -> bool:
        return v is not None and v != [] and v != {} and v != ""

    for field in _PAGE_WINS:
        val = page_data.get(field)
        merged[field] = val if _has_value(val) else search_data.get(field)

    for field in _SEARCH_WINS:
        val = search_data.get(field)
        merged[field] = val if _has_value(val) else page_data.get(field)

    # key_people: page has names/roles → search adds LinkedIn URLs + background
    page_people = page_data.get("key_people") or []
    search_people = search_data.get("key_people") or []
    if page_people or search_people:
        people_map: dict[str, dict] = {}
        for p in page_people:
            if isinstance(p, dict) and p.get("name"):
                people_map[p["name"].lower()] = dict(p)
        for p in search_people:
            if not (isinstance(p, dict) and p.get("name")):
                continue
            key = p["name"].lower()
            if key in people_map:
                existing = people_map[key]
                if not existing.get("linkedin") and p.get("linkedin"):
                    existing["linkedin"] = p["linkedin"]
                if not existing.get("background") and p.get("background"):
                    existing["background"] = p["background"]
            else:
                people_map[key] = dict(p)
        merged["key_people"] = list(people_map.values())

    # notable_customers: union of page + search, page data wins per-customer field
    page_customers = page_data.get("notable_customers") or []
    search_customers = search_data.get("notable_customers") or []
    if page_customers or search_customers:
        cust_map: dict[str, dict] = {}
        for c in page_customers:
            if isinstance(c, dict) and c.get("name"):
                cust_map[c["name"].lower()] = dict(c)
        for c in search_customers:
            if not (isinstance(c, dict) and c.get("name")):
                continue
            key = c["name"].lower()
            if key not in cust_map:
                cust_map[key] = dict(c)
            else:
                existing = cust_map[key]
                for f in ("domain", "segment", "industry", "evidence"):
                    if not existing.get(f) and c.get(f):
                        existing[f] = c[f]
        merged["notable_customers"] = list(cust_map.values())

    return merged


# ── MAIN RUN ───────────────────────────────────────────────────────────────────

async def run(
    domain: str,
    linkup: LinkupClient,
    run_id: str | None = None,
    claude: Optional[ClaudeClient] = None,
    event_cb: Optional[EventCallback] = None,
) -> CompanyProfile:
    t0 = time.monotonic()
    run_id = run_id or str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    async def emit(event: dict) -> None:
        if event_cb:
            try:
                await event_cb(event)
            except Exception as _e:
                logger.debug("understand emit error ignored: %s", _e)

    logger.info("phase=UNDERSTAND company=%s status=start arch=fetch_first", domain)

    # ── STEP 1: Parallel fetch company pages ──────────────────────────────────
    pages = await _fetch_company_pages(domain, linkup, emit)
    logger.info("understand pages_fetched domain=%s pages=%s", domain, list(pages.keys()))

    # ── STEP 2: Claude extracts page-sourced fields ───────────────────────────
    page_data: dict = {}
    if claude and pages:
        page_data = await asyncio.to_thread(_extract_from_pages, domain, pages, claude)
        logger.info(
            "understand page_extract domain=%s fields=%d",
            domain, sum(1 for v in page_data.values() if v is not None),
        )

    # ── STEP 3: External search (funding, investors, news…) ───────────────────
    ext_raw = await linkup.search(
        depth="deep",
        query=_external_search_query(domain, page_data.get("name")),
        schema=_EXTERNAL_SCHEMA,
    )
    ext_data: dict = ext_raw.get("data") or ext_raw.get("answer") or ext_raw.get("output") or {}

    # Collect + dedup source URLs
    sources: list = ext_raw.get("sources", [])
    _seen: set[str] = set()
    source_urls: list[str] = []
    for s in sources:
        if isinstance(s, dict):
            u = s.get("url")
            if u and u not in _seen:
                _seen.add(u)
                source_urls.append(u)

    for src in sources:
        src_url = src.get("url", "")
        if src_url:
            try:
                src_domain = urlparse(src_url).netloc.lstrip("www.") or src_url[:100]
            except Exception:
                src_domain = src_url[:100]
            await emit({
                "phase": "UNDERSTAND",
                "status": "progress",
                "kind": "source_consulted",
                "payload": {"url": src_url[:100], "domain": src_domain[:100]},
            })

    # ── STEP 4: Merge page + search data ─────────────────────────────────────
    data = _merge_data(page_data, ext_data)
    first_src_url = source_urls[0] if source_urls else None

    # ── HELPERS ───────────────────────────────────────────────────────────────
    def _dp_obj(obj) -> DataPoint | None:
        if not isinstance(obj, dict):
            return None
        value = obj.get("value")
        if value is None:
            return None
        return DataPoint(
            value=value,
            confidence=obj.get("confidence", "medium"),
            source_url=obj.get("source_url") or first_src_url,
            evidence=obj.get("evidence"),
            extracted_at=now,
        )

    # ── EMIT field events ─────────────────────────────────────────────────────
    for _field, _value, _conf in [
        ("founded_year", data.get("founded_year"), 0.9),
        ("hq_city",      data.get("hq_city"),      0.95),  # from page → high confidence
        ("hq_country",   data.get("hq_country"),    0.95),
        ("funding_stage", data.get("funding_stage"), 0.85),
        ("geo_coverage",  data.get("geo_coverage"),  0.8),
    ]:
        if _value is not None:
            await emit({
                "phase": "UNDERSTAND",
                "status": "progress",
                "kind": "field_extracted",
                "payload": {"field": _field, "value": str(_value)[:100], "confidence": _conf},
            })
    for _field, _obj in [
        ("employees",         data.get("employees")),
        ("funding_total_eur", data.get("funding_total_eur")),
        ("target_segment",    data.get("target_segment")),
        ("business_model",    data.get("business_model")),
        ("pricing_model",     data.get("pricing_model")),
    ]:
        if isinstance(_obj, dict) and _obj.get("value") is not None:
            _conf_num = {"high": 0.95, "medium": 0.75, "low": 0.5}.get(
                str(_obj.get("confidence", "medium")), 0.75
            )
            await emit({
                "phase": "UNDERSTAND",
                "status": "progress",
                "kind": "field_extracted",
                "payload": {"field": _field, "value": str(_obj["value"])[:100], "confidence": _conf_num},
            })

    # ── BUILD SUB-OBJECTS ─────────────────────────────────────────────────────
    hq = None
    if data.get("hq_city") or data.get("hq_country"):
        city, country = data.get("hq_city"), data.get("hq_country")
        coords = await geocode(city or "", country or "")
        hq = HQ(
            city=city, country=country,
            lat=coords[0] if coords else None,
            lng=coords[1] if coords else None,
        )
        if coords:
            await emit({
                "phase": "UNDERSTAND",
                "status": "progress",
                "kind": "field_extracted",
                "payload": {"field": "hq.coords", "value": f"{coords[0]:.4f},{coords[1]:.4f}", "confidence": 0.99},
            })

    funding_rounds = [
        FundingRound(
            round=r.get("round"),
            amount_eur=r.get("amount_eur"),
            date=r.get("date"),
            lead=r.get("lead"),
        )
        for r in (data.get("funding_rounds") or [])
    ]
    funding = None
    if data.get("funding_total_eur") or data.get("funding_last_round") or funding_rounds:
        funding = Funding(
            total_raised_eur=_dp_obj(data.get("funding_total_eur")),
            last_round=data.get("funding_last_round"),
            last_round_date=data.get("funding_last_round_date"),
            rounds=funding_rounds,
        )

    markets = [
        Market(
            id=m.get("id", m.get("label", "unknown").lower().replace(" ", "_")),
            label=m.get("label", ""),
            primary=m.get("primary", False),
        )
        for m in (data.get("markets") or [])
    ] or [
        Market(id=v.lower().replace(" ", "_"), label=v, primary=i == 0)
        for i, v in enumerate(data.get("target_verticals") or [])
    ]

    def _valid_linkedin(url: str | None) -> str | None:
        """Accept only linkedin.com/in/... profile URLs."""
        if url and "linkedin.com/in/" in url:
            return url
        return None

    key_people = [
        KeyPerson(
            name=p.get("name", ""),
            role=p.get("role"),
            background=p.get("background"),
            linkedin=_valid_linkedin(p.get("linkedin")),
        )
        for p in (data.get("key_people") or [])
        if p.get("name")
    ]

    recent_news = [
        NewsItem(date=n.get("date"), headline=n.get("headline", ""), source_url=n.get("source_url"))
        for n in (data.get("recent_news") or [])
        if n.get("headline")
    ]

    def _valid_domain(raw: str | None) -> str | None:
        """Accept domain-like strings (contains '.', no spaces). Reject industry labels."""
        if raw and "." in raw and " " not in raw.strip():
            return raw.strip().lower().lstrip("www.")
        return None

    notable_customers = [
        CustomerExample(
            name=c.get("name", ""),
            domain=_valid_domain(c.get("domain")),
            segment=_norm_segment(c.get("segment")),
            industry=c.get("industry"),
            evidence=c.get("evidence"),
        )
        for c in (data.get("notable_customers") or [])
        if isinstance(c, dict) and c.get("name")
    ]

    # Pricing from page extraction (already parsed by Claude in Step 2)
    pricing_raw = data.get("pricing") or {}
    pricing_detail = None
    if pricing_raw:
        tiers = [
            PricingTier(
                name=t.get("name"),
                price_monthly_usd=t.get("price_monthly_usd"),
                price_annual_usd=t.get("price_annual_usd"),
                features=t.get("features") or [],
                target=t.get("target"),
            )
            for t in (pricing_raw.get("tiers") or [])
        ]
        pricing_detail = PricingDetail(
            free_plan=pricing_raw.get("free_plan"),
            tiers=tiers,
            recent_changes=pricing_raw.get("recent_changes"),
            source_url=f"https://{domain}/pricing",
            extracted_at=now,
        )

    acquisition_raw = data.get("acquisition") or {}
    acquisition = None
    if acquisition_raw and isinstance(acquisition_raw, dict):
        acquisition = AcquisitionInfo(
            acquired=acquisition_raw.get("acquired", False),
            acquirer=acquisition_raw.get("acquirer"),
            amount_eur=acquisition_raw.get("amount_eur"),
            year=acquisition_raw.get("year"),
            source_url=acquisition_raw.get("source_url"),
        )

    # Investors: Linkup returns list[str] → list[Investor(name, domain=None)]
    notable_investors = [
        Investor(name=i) if isinstance(i, str) else Investor(**i)
        for i in (data.get("notable_investors") or [])
        if i
    ]

    # Employee YoY growth: normalise to fraction (0.12 not 12.0)
    _emp_yoy_raw = data.get("employee_growth_yoy")
    employee_growth_yoy: float | None = None
    if _emp_yoy_raw is not None:
        try:
            _val = float(_emp_yoy_raw)
            employee_growth_yoy = _val / 100 if _val > 1 else _val
        except (TypeError, ValueError):
            pass

    profile = CompanyProfile(
        name=data.get("name") or domain,
        domain=domain,
        website=data.get("website"),
        summary=data.get("summary"),
        founded_year=data.get("founded_year"),
        hq=hq,
        geo_coverage=data.get("geo_coverage"),
        employees=_dp_obj(data.get("employees")),
        employee_growth_yoy=employee_growth_yoy,
        funding=funding,
        funding_stage=data.get("funding_stage"),
        notable_investors=notable_investors,
        arr_usd=_dp_obj(data.get("arr_usd")),
        customer_count=_dp_obj(data.get("customer_count")),
        positioning=data.get("positioning"),
        markets=markets,
        target_segment=_dp_obj(
            {**_ts, "value": _norm_segment(_ts.get("value")) or _ts.get("value")}
            if isinstance(_ts := data.get("target_segment"), dict) else _ts
        ),
        target_verticals=data.get("target_verticals") or [],
        business_model=_dp_obj(data.get("business_model")),
        gtm_motion=_dp_obj(data.get("gtm_motion")),
        pricing_model=_dp_obj(data.get("pricing_model")),
        key_differentiator=_dp_obj(data.get("key_differentiator")),
        top_3_features=data.get("top_3_features") or [],
        notable_customers=notable_customers,
        pricing=pricing_detail,
        equity_story=data.get("equity_story"),
        acquisition=acquisition,
        tech_stack=data.get("tech_stack") or [],
        key_people=key_people,
        growth_signals=data.get("growth_signals") or [],
        recent_news=recent_news,
        source_urls=source_urls,
        pipeline_run_id=run_id,
    )

    # ── STEP 5: Claude enrich — equity_story, segments, domains ──────────────
    if claude is not None:
        try:
            profile = await asyncio.to_thread(claude.enrich_company_profile, profile)
            if profile.equity_story:
                await emit({
                    "phase": "UNDERSTAND",
                    "status": "progress",
                    "kind": "field_extracted",
                    "payload": {"field": "equity_story", "value": profile.equity_story[:100], "confidence": 0.9},
                })
        except Exception as _e:
            logger.warning("understand claude_enrich error=%s", _e)

    logger.info(
        "phase=UNDERSTAND company=%s status=ok duration=%.1fs pages=%d ext_sources=%d",
        domain, time.monotonic() - t0, len(pages), len(source_urls),
    )
    return profile


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.understand <domain>", file=sys.stderr)
        sys.exit(1)

    client = LinkupClient()
    claude_client = ClaudeClient()
    result = asyncio.run(run(sys.argv[1].strip().lower(), client, claude=claude_client))
    print(result.model_dump_json(indent=2))

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


# ── LINKEDIN SCHEMA (Lane 2) ───────────────────────────────────────────────────
# LinkedIn = source of truth for employees, growth, key people, founded, HQ.
_LINKEDIN_SCHEMA = {
    "type": "object",
    "properties": {
        "employees": {
            "type": "object",
            "properties": {
                "value":      {"type": "integer"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
                "evidence":   {"type": "string"},
            },
        },
        "employee_growth_yoy": {"type": "number"},  # fraction: 0.12 = +12%
        "founded_year":        {"type": "integer"},
        "hq_city":             {"type": "string"},
        "hq_country":          {"type": "string"},
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
        "recent_posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date":       {"type": "string"},
                    "headline":   {"type": "string"},
                    "url":        {"type": "string"},
                },
            },
        },
    },
}


# ── NEWS / PRESS / CRUNCHBASE SCHEMA (Lane 3) ─────────────────────────────────
# Press, financial data, ARR, customers, recent news with full source attribution.
_NEWS_SCHEMA = {
    "type": "object",
    "properties": {
        # ── COMPANY BASICS (fallback if LinkedIn lane fails) ──────────
        "hq_city":      {"type": "string"},
        "hq_country":   {"type": "string"},
        "founded_year": {"type": "integer"},

        # ── SIZE (fallback) ───────────────────────────────────────────
        "employees": {
            "type": "object",
            "properties": {
                "value":      {"type": "integer"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_url": {"type": "string"},
            },
        },
        "employee_growth_yoy": {"type": "number"},

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
                    "source":     {"type": "string"},  # "TechCrunch", "Les Echos"…
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
- Customers: scan the entire page for customer mentions — look for image alt-text
  (e.g. ![H&M](...) or alt="Capgemini"), testimonials with company names, case study
  links, "Trusted by …" sections, customer success quotes. Include any company name
  found in these contexts even without an explicit logo description.
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
        # Customer logos / "Trusted by" sections often appear deep in the page (≥10k chars)
        sections.append(f"=== HOMEPAGE ({domain}/) ===\n{pages['homepage'][:18000]}")
    if pages.get("about"):
        sections.append(f"=== ABOUT PAGE ({domain}/about) ===\n{pages['about'][:6000]}")
    if pages.get("company"):
        sections.append(f"=== COMPANY PAGE ({domain}/company) ===\n{pages['company'][:6000]}")
    if pages.get("team"):
        sections.append(f"=== TEAM PAGE ({domain}/team) ===\n{pages['team'][:4000]}")
    if pages.get("pricing"):
        sections.append(f"=== PRICING PAGE ({domain}/pricing) ===\n{pages['pricing'][:4000]}")

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
        return claude.extract_json(_PAGE_EXTRACT_SYSTEM, user, max_tokens=3072)
    except Exception as e:
        logger.warning("understand extract_from_pages failed domain=%s error=%s", domain, e)
        return {}


# ── STEP 3: SEARCH QUERIES ────────────────────────────────────────────────────

def _linkedin_query(domain: str, company_name: str | None = None) -> str:
    """LinkedIn-focused search (Lane 2) — follows Linkup official LinkedIn pattern.

    Per docs.linkup.so/.../search/best-practices#linkedin-data-extraction:
    - /fetch fails on LinkedIn (login wall) — must use /search
    - Exact URL required: linkedin.com/company/{slug} or linkedin.com/in/{slug}
    - Multi-step pattern: 'First find URL, then scrape, return X'
    - Mode 'deep' handles URL discovery + extraction in a single call.
    """
    name = company_name or domain
    # Slug hint derived from domain (e.g. makipeople.com → makipeople, linear.app → linear)
    _slug_hint = domain.split(".")[0]
    return (
        f"First, find the exact LinkedIn company page URL for {name} ({domain}). "
        f"It likely follows the pattern linkedin.com/company/{_slug_hint} or a close variant. "
        f"Then scrape that URL and return the following structured data:\n\n"
        f"- EMPLOYEES: Total employee count shown in the company page header "
        f"(e.g. '122 employees'). Return as integer.\n"
        f"- EMPLOYEE_GROWTH_YOY: Year-over-year employee count change as decimal "
        f"(e.g. +12% → 0.12, -5% → -0.05). Compute from LinkedIn's 'Employee insights' "
        f"section if visible, or from headcount history if accessible.\n"
        f"- FOUNDED_YEAR: Year the company was founded, from the LinkedIn 'About' section.\n"
        f"- HQ_CITY, HQ_COUNTRY: Headquarters location from LinkedIn 'About'. "
        f"If multiple offices listed, prefer the original founding location.\n\n"
        f"Then, find the LinkedIn profile URLs (linkedin.com/in/...) for the top 5 "
        f"founders and executives at {name} (CEO, CTO, CPO, co-founders, VP-level). "
        f"Return for each: name, role, exact LinkedIn URL, short background (1 sentence).\n\n"
        f"Finally, return the 3-5 most recent public posts from the company page. "
        f"For each: date, headline (first 150 chars), and full post URL "
        f"(linkedin.com/posts/...).\n\n"
        f"If any field cannot be retrieved from LinkedIn, return null for that field. "
        f"Do not fabricate values or pull from other sources."
    )


def _news_query(domain: str, company_name: str | None = None) -> str:
    """News + press + financial data search (Lane 3). Source of truth for ARR + funding."""
    name = company_name or domain
    return (
        f"Find press coverage, financial data, and traction signals for {name} ({domain}).\n"
        f"Do NOT crawl {domain} (already fetched) or LinkedIn (handled separately).\n\n"
        "Target sources: Crunchbase, Pitchbook, Dealroom, TechCrunch, EU Startups, "
        "Les Echos, La Tribune, BFM Business, VentureBeat, Sifted, official press releases, "
        "financial filings, public earning calls.\n\n"
        "Find:\n"
        f"FUNDING: All investment rounds for {name} — amount in EUR, date, lead investor, "
        "total raised, current stage (Seed/Series A/B/C+/Public/Bootstrapped).\n"
        f"INVESTORS: All notable investors in {name} — VCs, angels, corporate funds. "
        "List of names only.\n"
        f"ARR: Annual Recurring Revenue for {name} ONLY if explicitly disclosed in a "
        "funding announcement, press release, podcast or interview "
        "(e.g. 'Linear hit $100M ARR before Series C', 'crossed €50M ARR'). "
        "Do NOT estimate from valuation or headcount. Return null if not publicly stated.\n"
        f"CUSTOMER COUNT: Total customer count for {name} if announced "
        "(e.g. '25,000 companies', '500 enterprise customers').\n"
        f"NOTABLE CUSTOMERS: List 5-10 enterprise customers of {name} mentioned in any "
        "press release, case study, blog post, analyst report, podcast, or LinkedIn post. "
        "Also check the company's own homepage 'Trusted by' section if cached in search results. "
        "For each: name + domain (e.g. {'name': 'OpenAI', 'domain': 'openai.com'}). "
        "Skip if no public customers can be confirmed.\n"
        f"ACQUISITION: Whether {name} has been acquired — acquirer, amount EUR, year.\n"
        f"TECH STACK: Technologies used by {name}, inferred from job postings, BuiltWith, engineering blog.\n"
        f"GROWTH SIGNALS: Hiring surges, new offices, product launches, milestones for {name} (3-5 items).\n"
        f"RECENT NEWS: 5-10 most significant news items about {name} — date, headline, "
        "source name (e.g. 'TechCrunch', 'Les Echos'), full source URL."
    )


# ── STEP 4: MERGE ─────────────────────────────────────────────────────────────

def _merge_data(page_data: dict, linkedin_data: dict, news_data: dict) -> dict:
    """3-source merge with explicit priority lanes.

    Priority order per field:
    - PAGES   wins for: HQ, GTM, positioning, summary, markets, pricing, key_differentiator
    - LINKEDIN wins for: employees, growth, founded_year (LinkedIn About > others)
    - NEWS    wins for: funding, ARR, recent_news, customers, signals
    Fallback: if winner has no value, fall back to other sources.
    """
    merged: dict = {}

    _PAGE_WINS = [
        "name", "website", "summary", "geo_coverage",
        "positioning", "markets", "target_segment", "target_verticals",
        "business_model", "gtm_motion", "pricing_model",
        "key_differentiator", "top_3_features", "pricing",
    ]
    _LI_WINS = [
        "employees", "employee_growth_yoy",
    ]
    _NEWS_WINS = [
        "funding_total_eur", "funding_stage", "funding_last_round",
        "funding_last_round_date", "funding_rounds", "notable_investors",
        "arr_usd", "customer_count", "acquisition",
        "tech_stack", "growth_signals", "recent_news",
        # HQ + founded: News (Crunchbase/press) more reliable than LinkedIn
        # (LinkedIn shows current office, may differ from founding city)
        "hq_city", "hq_country", "founded_year",
    ]

    def _has_value(v) -> bool:
        return v is not None and v != [] and v != {} and v != ""

    def _first_value(*sources):
        for s in sources:
            if _has_value(s):
                return s
        return None

    for field in _PAGE_WINS:
        merged[field] = _first_value(page_data.get(field), linkedin_data.get(field), news_data.get(field))

    for field in _LI_WINS:
        merged[field] = _first_value(linkedin_data.get(field), page_data.get(field), news_data.get(field))

    for field in _NEWS_WINS:
        merged[field] = _first_value(news_data.get(field), linkedin_data.get(field), page_data.get(field))

    # Carry through LinkedIn-only field
    if _has_value(linkedin_data.get("recent_posts")):
        merged["recent_posts"] = linkedin_data["recent_posts"]

    # Reframe: search_data for the union-merge sections below = LI ∪ News
    search_data = {**news_data, **{k: v for k, v in linkedin_data.items() if _has_value(v)}}
    page_data = page_data  # explicit

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

    logger.info("phase=UNDERSTAND company=%s status=start arch=3_lanes", domain)

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

    # ── STEP 3: TWO parallel deep searches — LinkedIn + News ──────────────────
    _company_name = page_data.get("name") or domain
    linkedin_raw, news_raw = await asyncio.gather(
        linkup.search(
            depth="deep",
            query=_linkedin_query(domain, _company_name),
            schema=_LINKEDIN_SCHEMA,
        ),
        linkup.search(
            depth="deep",
            query=_news_query(domain, _company_name),
            schema=_NEWS_SCHEMA,
        ),
    )
    linkedin_data: dict = linkedin_raw.get("data") or linkedin_raw.get("answer") or {}
    news_data: dict = news_raw.get("data") or news_raw.get("answer") or {}
    logger.info(
        "understand searches done linkedin_fields=%d news_fields=%d",
        sum(1 for v in linkedin_data.values() if v is not None),
        sum(1 for v in news_data.values() if v is not None),
    )

    # Collect + dedup source URLs from BOTH searches
    sources: list = (linkedin_raw.get("sources") or []) + (news_raw.get("sources") or [])
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

    # ── STEP 4: Merge 3 sources (pages + LinkedIn + news) ────────────────────
    data = _merge_data(page_data, linkedin_data, news_data)
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
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.understand <domain>", file=sys.stderr)
        sys.exit(1)

    _domain = sys.argv[1].strip().lower()
    client = LinkupClient()
    claude_client = ClaudeClient()
    result = asyncio.run(run(_domain, client, claude=claude_client))

    # 1. Print JSON to stdout (pipe-safe, unchanged)
    print(result.model_dump_json(indent=2))

    # 2. Save to cache/understand_{domain}.json (overwrite → always latest run)
    _cache_dir = Path(__file__).resolve().parents[2] / "cache"
    _cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_file = _cache_dir / f"understand_{_domain}.json"
    _cache_file.write_text(result.model_dump_json(indent=2))
    print(f"\n📁 Saved → {_cache_file}", file=sys.stderr)

    # 3. Fill summary table → stderr
    def _dp_val(dp):
        return str(dp.value)[:30] if dp and dp.value is not None else "null"

    _fields = {
        "name":            result.name or "null",
        "website":         result.website or "null",
        "summary":         f"({len(result.summary)} chars)" if result.summary else "null",
        "founded_year":    str(result.founded_year) if result.founded_year else "null",
        "hq.city":         result.hq.city if result.hq and result.hq.city else "null",
        "hq.country":      result.hq.country if result.hq and result.hq.country else "null",
        "geo_coverage":    result.geo_coverage or "null",
        "employees":       _dp_val(result.employees),
        "funding.total":   _dp_val(result.funding.total_raised_eur) if result.funding else "null",
        "funding.stage":   result.funding_stage or "null",
        "funding.rounds#": str(len(result.funding.rounds)) if result.funding else "0",
        "investors#":      str(len(result.notable_investors)),
        "arr_usd":         _dp_val(result.arr_usd),
        "customer_count":  _dp_val(result.customer_count),
        "positioning":     f"({len(result.positioning)} chars)" if result.positioning else "null",
        "markets#":        str(len(result.markets)),
        "target_segment":  _dp_val(result.target_segment),
        "business_model":  _dp_val(result.business_model),
        "gtm_motion":      _dp_val(result.gtm_motion),
        "pricing_model":   _dp_val(result.pricing_model),
        "differentiator":  _dp_val(result.key_differentiator),
        "features#":       str(len(result.top_3_features)),
        "customers#":      str(len(result.notable_customers)),
        "tech_stack#":     str(len(result.tech_stack)),
        "key_people#":     str(len(result.key_people)),
        "growth_signals#": str(len(result.growth_signals)),
        "recent_news#":    str(len(result.recent_news)),
        "equity_story":    f"({len(result.equity_story)} chars)" if result.equity_story else "null",
    }

    _null = ("null", "0", "—")
    _filled = sum(1 for v in _fields.values() if v not in _null)
    _total = len(_fields)

    print(f"\n─── fill: {_filled}/{_total} ({int(_filled / _total * 100)}%) ───", file=sys.stderr)
    for _f, _v in _fields.items():
        _icon = "✓" if _v not in _null else "✗"
        print(f"  {_icon} {_f:<20} {_v}", file=sys.stderr)
    print("─" * 45, file=sys.stderr)

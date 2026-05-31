"""Phase 2 — DISCOVER: find up to 20 competitor candidates for a domain.

Architecture v2 — "Parallel Standard Search":
  Step 1 — 3 parallel /search standard queries (intent-differentiated)
            → ~10-15s, €0.018 total (vs 59-132s + €0.055 previously)
  Step 2 — Claude merges + deduplicates → list[DiscoverCandidate] (name+domain+tagline)
  Step 3 — Optional: score_threats_candidates for display ordering (non-blocking)
  Fallback — If searches return no text, Claude knowledge-base fallback (€0 Linkup cost)

Output: lightweight list[DiscoverCandidate] — just enough for VC to select.
ENRICH phase receives selected subset and does deep profiling.
"""
import asyncio
import logging
import time
from typing import Awaitable, Callable, Optional

from clients.claude_client import ClaudeClient
from clients.linkup_client import LinkupClient
from models.company import CompanyProfile
from models.competitor import DiscoverCandidate

logger = logging.getLogger(__name__)

EventCallback = Callable[[dict], Awaitable[None]]

_MAX_CANDIDATES = 20


def _build_queries(profile: CompanyProfile) -> list[str]:
    """Build 3 intent-differentiated search queries from CompanyProfile context."""
    name = profile.name

    primary_market = ""
    markets_str = ""
    if profile.markets:
        labels = [m.label for m in profile.markets]
        markets_str = ", ".join(labels)
        primary_label = next(
            (m.label for m in profile.markets if m.primary),
            labels[0] if labels else "",
        )
        primary_market = primary_label

    positioning = profile.positioning or f"{name} SaaS"
    market_term = primary_market or markets_str or "software"

    return [
        # Intent 1: direct alternatives (G2, AlternativeTo, Capterra)
        (
            f'"{name}" alternatives competitors {market_term} '
            f"site:g2.com OR site:alternativeto.net OR site:capterra.com"
        ),
        # Intent 2: broad market landscape
        f"best {market_term} software tools startups 2024 2025",
        # Intent 3: VS-style comparisons + positioning context
        f'"{name}" vs {market_term} competitors {positioning}',
    ]


async def _claude_fallback(
    profile: CompanyProfile,
    claude: ClaudeClient,
) -> tuple[list[DiscoverCandidate], dict[str, int]]:
    """Claude training-data fallback when Linkup searches return no text.

    Returns (candidates, threat_scores) — zero Linkup cost.
    """
    positioning = profile.positioning or f"{profile.name} SaaS"
    markets_str = (
        ", ".join(m.label for m in profile.markets)
        if profile.markets
        else "software"
    )

    raw_list: list[dict] = []
    try:
        raw_list = await asyncio.to_thread(
            claude.discover_competitors_fallback,
            profile.name,
            profile.domain,
            positioning,
            markets_str,
        )
    except Exception as e:
        logger.error("phase=DISCOVER _claude_fallback failed: %s", e)
        return [], {}

    candidates: list[DiscoverCandidate] = []
    for item in raw_list:
        name = str(item.get("name", "")).strip()
        website = str(item.get("website", "")).strip()
        tagline = str(
            item.get("one_liner") or item.get("tagline") or item.get("differentiator") or ""
        ).strip()
        domain_raw = item.get("domain") or website
        if not (name and domain_raw):
            continue
        try:
            cand = DiscoverCandidate(
                name=name[:120],
                domain=str(domain_raw)[:120],
                tagline=tagline[:300],
            )
            if cand.name and cand.domain:
                candidates.append(cand)
        except Exception:
            pass

    candidates = candidates[:_MAX_CANDIDATES]

    # Best-effort threat-score ordering of fallback candidates
    threat_scores: dict[str, int] = {}
    if candidates:
        subject_summary = (
            f"{profile.name} ({profile.domain}) — "
            f"{profile.positioning or profile.summary or ''}"
        ).strip(" —")
        try:
            cand_dicts = [
                {"name": c.name, "domain": c.domain, "tagline": c.tagline}
                for c in candidates
            ]
            threat_scores = await asyncio.to_thread(
                claude.score_threats_candidates, subject_summary, cand_dicts
            )
            if threat_scores:
                candidates = sorted(
                    candidates,
                    key=lambda c: threat_scores.get(c.domain, 0),
                    reverse=True,
                )
        except Exception as e:
            logger.warning("_claude_fallback threat scoring failed: %s", e)

    logger.info(
        "phase=DISCOVER company=%s status=claude_fallback count=%d",
        profile.domain,
        len(candidates),
    )
    return candidates, threat_scores


async def run(
    profile: CompanyProfile,
    linkup: LinkupClient,
    event_cb: Optional[EventCallback] = None,
) -> tuple[list[DiscoverCandidate], list[str], dict[str, int]]:
    """Return (candidates, source URLs consulted, threat_scores).

    Candidates are DiscoverCandidate objects — lightweight (name+domain+tagline).
    threat_scores maps candidate domain → 0-100 competitive threat score.
    Ordered by approximate threat score (best-effort; falls back to Claude merge order).
    """
    t0 = time.monotonic()
    domain = profile.domain
    logger.info("phase=DISCOVER company=%s status=start", domain)
    # Instantiated once here — shared by Linkup path, merge, scoring, and fallback
    claude = ClaudeClient()

    async def emit(event: dict) -> None:
        if event_cb:
            try:
                await event_cb(event)
            except Exception as _e:
                logger.debug("discover emit error ignored: %s", _e)

    # ── Step 1: 3 parallel standard searches ──────────────────────────────────
    queries = _build_queries(profile)
    logger.info(
        "phase=DISCOVER company=%s queries=%d depth=standard",
        domain,
        len(queries),
    )

    try:
        results = await asyncio.gather(
            *[linkup.search(q, depth="standard") for q in queries],
            return_exceptions=True,
        )
    except Exception as e:
        logger.error("phase=DISCOVER company=%s search_gather_failed=%s", domain, e)
        results = []

    # ── Collect raw texts + sources from all results ───────────────────────────
    raw_texts: list[str] = []
    source_urls: list[str] = []
    _seen_urls: set[str] = set()

    for r in results:
        if isinstance(r, Exception):
            logger.warning("phase=DISCOVER search_partial_failure=%s", r)
            continue
        if not isinstance(r, dict):
            continue
        text = r.get("answer") or r.get("output") or r.get("content") or ""
        if isinstance(text, dict):
            text = str(text)
        if text:
            raw_texts.append(str(text))
        for s in r.get("sources", []):
            if isinstance(s, dict):
                u = s.get("url")
                if u and u not in _seen_urls:
                    _seen_urls.add(u)
                    source_urls.append(u)

    # ── Fallback: Linkup returned nothing ─────────────────────────────────────
    if not raw_texts:
        logger.warning(
            "phase=DISCOVER company=%s no_text_from_searches — using Claude fallback",
            domain,
        )
        fallback_candidates, fallback_scores = await _claude_fallback(profile, claude)
        for cand in fallback_candidates:
            await emit({
                "phase": "DISCOVER",
                "status": "progress",
                "kind": "candidate_found",
                "payload": {"name": cand.name, "domain": cand.domain},
            })
        logger.info(
            "phase=DISCOVER company=%s status=ok(fallback) count=%d duration=%.1fs",
            domain,
            len(fallback_candidates),
            time.monotonic() - t0,
        )
        return fallback_candidates, source_urls, fallback_scores

    # ── Step 2: Claude merge + dedup ──────────────────────────────────────────
    raw_candidates = await asyncio.to_thread(
        claude.extract_discover_candidates,
        raw_texts,
        profile.name,
        profile.domain,
        _MAX_CANDIDATES,
    )

    # ── Fallback: Claude returned nothing from searches ────────────────────────
    if not raw_candidates:
        logger.warning(
            "phase=DISCOVER company=%s claude_returned_empty — using Claude fallback",
            domain,
        )
        fallback_candidates, fallback_scores = await _claude_fallback(profile, claude)
        for cand in fallback_candidates:
            await emit({
                "phase": "DISCOVER",
                "status": "progress",
                "kind": "candidate_found",
                "payload": {"name": cand.name, "domain": cand.domain},
            })
        logger.info(
            "phase=DISCOVER company=%s status=ok(fallback) count=%d duration=%.1fs",
            domain,
            len(fallback_candidates),
            time.monotonic() - t0,
        )
        return fallback_candidates, source_urls, fallback_scores

    # ── Step 3: optional threat scoring for display order (non-blocking) ──────
    candidates_dicts = raw_candidates  # list[{name, domain, tagline}]
    discover_threat_scores: dict[str, int] = {}
    try:
        subject_summary = (
            f"{profile.name} ({profile.domain}) — "
            f"{profile.positioning or profile.summary or ''}"
        ).strip(" —")
        discover_threat_scores = await asyncio.to_thread(
            claude.score_threats_candidates,
            subject_summary,
            candidates_dicts,
        )
        if discover_threat_scores:
            candidates_dicts = sorted(
                candidates_dicts,
                key=lambda c: discover_threat_scores.get(c.get("domain", ""), 0),
                reverse=True,
            )
            top = candidates_dicts[0] if candidates_dicts else {}
            logger.info(
                "phase=DISCOVER threat_sort_top=%s score=%d",
                top.get("domain"),
                discover_threat_scores.get(top.get("domain", ""), 0),
            )
    except Exception as e:
        logger.warning("discover threat scoring skipped (non-blocking): %s", e)

    # ── Build DiscoverCandidate objects ────────────────────────────────────────
    candidates: list[DiscoverCandidate] = []
    for c in candidates_dicts:
        try:
            cand = DiscoverCandidate(
                name=str(c.get("name", ""))[:120],
                domain=str(c.get("domain", ""))[:120],
                tagline=str(c.get("tagline", ""))[:300],
            )
            if cand.name and cand.domain:
                candidates.append(cand)
        except Exception as parse_err:
            logger.debug("discover candidate parse skip: %s", parse_err)

    # Emit progress events for each candidate found
    for cand in candidates:
        await emit({
            "phase": "DISCOVER",
            "status": "progress",
            "kind": "candidate_found",
            "payload": {"name": cand.name, "domain": cand.domain},
        })

    logger.info(
        "phase=DISCOVER company=%s status=ok count=%d sources=%d duration=%.1fs",
        domain,
        len(candidates),
        len(source_urls),
        time.monotonic() - t0,
    )
    return candidates, source_urls, discover_threat_scores


if __name__ == "__main__":
    import json
    import sys

    from dotenv import load_dotenv

    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.discover <domain>", file=sys.stderr)
        sys.exit(1)

    domain_arg = sys.argv[1].strip().lower()
    stub = CompanyProfile(name=domain_arg, domain=domain_arg, pipeline_run_id="cli-test")
    client = LinkupClient()
    result_candidates, result_sources, result_scores = asyncio.run(run(stub, client))
    print(json.dumps(
        {
            "candidates": [c.model_dump() for c in result_candidates],
            "source_urls": result_sources,
            "threat_scores": result_scores,
        },
        indent=2,
        ensure_ascii=False,
    ))

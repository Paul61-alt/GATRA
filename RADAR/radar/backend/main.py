import asyncio
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

from clients import ClaudeClient, LinkupClient
from clients.linkup_client import estimate_today_cost_eur, record_scan_delta
from models import PipelineRun, PipelineStatus
from models.competitor import DiscoverCandidate, DiscoverResult
from models.memo import TemplateSpec
from pipeline import discover, enrich, memo as memo_pipeline, synthesize, understand
from pipeline.transform import pipeline_run_to_radar_output
from utils import (
    cache_get,
    cache_set,
    cache_get_discover,
    cache_set_discover,
    cache_get_progress,
    cache_set_progress,
    cache_get_latest,
    cache_list_all,
    normalize_domain as _norm_domain_util,
)


def _check_kill_switch() -> None:
    if os.environ.get("RADAR_KILL_SWITCH", "").lower() in ("1", "true", "on"):
        raise HTTPException(status_code=503, detail="Service temporarily disabled")


def _check_daily_budget_eur() -> None:
    """Refuse new scans when today's Linkup spend is over the EUR cap.

    Stops a single bad actor from running the budget to zero. Independent of the
    per-call ledger budget in linkup_client._check_daily_budget (which caps call
    count, not euro spend).
    """
    cap = float(os.environ.get("RADAR_DAILY_BUDGET_EUR", "30"))
    spent = estimate_today_cost_eur()
    if spent >= cap:
        logger.warning("daily_budget_eur_exceeded spent=%.2f cap=%.2f", spent, cap)
        raise HTTPException(
            status_code=429,
            detail={"error": "daily_budget_reached", "spent_eur": spent, "cap_eur": cap},
        )


def verify_token(authorization: str | None = Header(default=None)) -> None:
    """Bearer-token gate on /scan* endpoints.

    Token comes from RADAR_SHARED_TOKEN env var; if unset, auth is disabled
    (dev mode). In prod, MUST be set — boot will refuse with a clear error
    on first request if missing while RADAR_REQUIRE_AUTH=1.
    """
    expected = os.environ.get("RADAR_SHARED_TOKEN", "").strip()
    if not expected:
        if os.environ.get("RADAR_REQUIRE_AUTH", "").lower() in ("1", "true", "on"):
            raise HTTPException(status_code=500, detail="Server misconfigured: RADAR_SHARED_TOKEN unset")
        return  # dev mode, no auth
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid token")


# run_id is used as a filename in the cache (progress, discover). Reject anything that
# could escape the cache directory via path traversal or shell injection.
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _validate_run_id(run_id: str) -> str:
    if not run_id or not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=422, detail="Invalid run_id format")
    return run_id


limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute", "100/hour"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.linkup = LinkupClient()
    app.state.claude = ClaudeClient()
    app.state.pipeline_sem = asyncio.Semaphore(
        int(os.environ.get("RADAR_MAX_CONCURRENT", "2"))
    )
    # Running enrich pipelines keyed by run_id — used to dedupe concurrent POSTs after a refresh.
    app.state.enrich_jobs = {}
    yield


app = FastAPI(title="Radar API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(status_code=429, content={"detail": "Too Many Requests"}),
)
app.add_middleware(SlowAPIMiddleware)

_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://localhost:8731",  # static frontend-prototype dev server
    "http://127.0.0.1:8731",
    "https://frontend-prototype-opal.vercel.app",
    os.environ.get("FRONTEND_URL", ""),
]

# allow_origin_regex covers Vercel preview deploys (frontend-prototype-xxxx-paul-pietras-projects.vercel.app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in _ALLOWED_ORIGINS if o],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    url: str
    # Client-supplied run_id (UUID) — enables refresh recovery via /scan/status/{run_id}.
    # Optional for backwards compatibility; server generates one if absent.
    run_id: str | None = None


def _normalize_domain(url: str) -> str:
    from urllib.parse import urlparse
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    return parsed.netloc.lstrip("www.").rstrip("/") or parsed.path.lstrip("www.").rstrip("/")


@asynccontextmanager
async def _capture_scan_cost(linkup: LinkupClient, scan_id: str, phase: str):
    """Bracket a scan with GET /v1/credits/balance before/after to record true USD cost.

    Ground-truth cost recorded to cache/linkup_usage.jsonl + Supabase as endpoint=scan_delta.
    Independent of the per-call cost_eur estimates already logged by _record_call.

    Caveat: the delta reflects ACCOUNT-level spend during the bracketed window, not
    scan-level isolated spend. Any other consumer of the same Linkup API key (parallel
    scans gated by RADAR_MAX_CONCURRENT, other dev machines, prod) will pollute the
    measurement. For audit-grade precision, set RADAR_MAX_CONCURRENT=1 and avoid
    sharing the API key during the audit window.
    """
    balance_before = await linkup.balance()
    t0 = time.monotonic()
    try:
        yield
    finally:
        balance_after = await linkup.balance()
        try:
            record_scan_delta(
                scan_id=scan_id,
                phase=phase,
                balance_before_usd=balance_before,
                balance_after_usd=balance_after,
                duration_s=time.monotonic() - t0,
            )
        except Exception as e:
            logger.warning("scan delta record failed run_id=%s phase=%s error=%s", scan_id, phase, e)


def _candidates_to_enrich_dicts(candidates: list[DiscoverCandidate]) -> list[dict]:
    """Convert lightweight DiscoverCandidate objects to the dict format expected by enrich.run().

    Enrich uses 'website' (full URL) + 'name' + optionally 'one_liner' as seed fields.
    All other fields (pricing, funding, employees…) are fetched fresh via /research.
    """
    return [
        {
            "name": c.name,
            "website": f"https://{c.domain}",
            "one_liner": c.tagline,
        }
        for c in candidates
    ]


class EnrichRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    run_id: str
    selected: list[str]  # bare domains VC selected, e.g. ["notion.so", "coda.io"]


@app.post("/analyze")
@limiter.limit("3/minute")
async def analyze(request: Request, req: AnalyzeRequest, _auth: None = Depends(verify_token)) -> dict:
    _check_kill_switch()
    _check_daily_budget_eur()
    domain = _normalize_domain(req.url)
    if not domain:
        raise HTTPException(status_code=422, detail="Invalid URL")

    cached = cache_get(domain)
    if cached:
        cached["from_cache"] = True
        return cached

    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    try:
        linkup: LinkupClient = app.state.linkup

        async with app.state.pipeline_sem:
            company_profile = await understand.run(domain, linkup, run_id, claude=app.state.claude)

            candidates, discover_sources, discover_threat_scores = await discover.run(company_profile, linkup)
            competitor_dicts = _candidates_to_enrich_dicts(candidates)

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
            discover_source_urls=discover_sources,
            radar_scores=radar_scores,
            threat_scores=discover_threat_scores,
        )

        result = run.model_dump(mode="json")
        cache_set(domain, result)
        logger.info("pipeline=complete domain=%s duration=%.1fs", domain, time.monotonic() - t0)
        return result

    except Exception as e:
        logger.error("pipeline=error domain=%s error=%s", domain, e, exc_info=True)
        run = PipelineRun(
            id=run_id,
            company_domain=domain,
            status=PipelineStatus.FAILED,
            created_at=created_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=run.model_dump(mode="json"))


@app.post("/scan")
@limiter.limit("3/minute")
async def scan(request: Request, req: AnalyzeRequest, _auth: None = Depends(verify_token)) -> dict:
    """Like /analyze but returns RadarOutput (camelCase, frontend-ready)."""
    _check_kill_switch()
    _check_daily_budget_eur()
    domain = _normalize_domain(req.url)
    if not domain:
        raise HTTPException(status_code=422, detail="Invalid URL")

    cache_key = f"radar_{domain}"
    cached = cache_get(cache_key)
    if cached:
        cached["fromCache"] = True
        return cached

    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    try:
        linkup: LinkupClient = app.state.linkup

        async with app.state.pipeline_sem:
            async with _capture_scan_cost(linkup, run_id, "full_scan"):
                company_profile = await understand.run(domain, linkup, run_id, claude=app.state.claude)
                candidates, discover_sources, discover_threat_scores = await discover.run(company_profile, linkup)
                competitor_dicts = _candidates_to_enrich_dicts(candidates)
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
            discover_source_urls=discover_sources,
            radar_scores=radar_scores,
            threat_scores=discover_threat_scores,
        )

        radar_output = pipeline_run_to_radar_output(run)
        result = radar_output.model_dump(by_alias=True, mode="json", exclude_none=True)
        cache_set(cache_key, result)
        logger.info("scan=complete domain=%s duration=%.1fs", domain, time.monotonic() - t0)
        return result

    except Exception as e:
        logger.error("scan=error domain=%s error=%s", domain, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scan/stream")
@limiter.limit("3/minute")
async def scan_stream(request: Request, req: AnalyzeRequest, _auth: None = Depends(verify_token)) -> StreamingResponse:
    """SSE endpoint — emits fine-grained progress events then final result."""
    _check_kill_switch()
    _check_daily_budget_eur()
    domain = _normalize_domain(req.url)
    if not domain:
        raise HTTPException(status_code=422, detail="Invalid URL")

    async def event_stream():
        def _sse(data: dict) -> str:
            # Leading comment SSE event forces chunk flush before the data event.
            # Prevents Nagle/ASGI buffering of small chunks.
            return f": flush\n\ndata: {json.dumps(data)}\n\n"

        cached = cache_get(f"radar_{domain}")
        if cached:
            cached["from_cache"] = True
            yield _sse({"result": cached})
            return

        queue: asyncio.Queue = asyncio.Queue()

        async def emit(event: dict) -> None:
            await queue.put(event)

        async def run_pipeline() -> None:
            run_id = str(uuid4())
            created_at = datetime.now(timezone.utc).isoformat()
            t0 = time.monotonic()
            try:
                linkup: LinkupClient = app.state.linkup
                async with app.state.pipeline_sem:
                    async with _capture_scan_cost(linkup, run_id, "full_scan_stream"):
                        await queue.put({"phase": "UNDERSTAND", "status": "start"})
                        company_profile = await understand.run(domain, linkup, run_id, claude=app.state.claude, event_cb=emit)
                        await queue.put({"phase": "UNDERSTAND", "status": "ok", "name": company_profile.name})

                        await queue.put({"phase": "DISCOVER", "status": "start"})
                        candidates, discover_sources, _ = await discover.run(company_profile, linkup, event_cb=emit)
                        competitor_dicts = _candidates_to_enrich_dicts(candidates)
                        await queue.put({"phase": "DISCOVER", "status": "ok", "count": len(candidates)})

                        await queue.put({"phase": "ENRICH", "status": "start"})
                        competitor_profiles = await enrich.run(competitor_dicts, linkup, run_id, event_cb=emit)
                        await queue.put({"phase": "ENRICH", "status": "ok", "count": len(competitor_profiles)})

                        await queue.put({"phase": "SYNTHESIZE", "status": "start"})
                        radar_scores = synthesize.run(company_profile, competitor_profiles)
                        await queue.put({"phase": "SYNTHESIZE", "status": "ok", "count": len(radar_scores)})

                run = PipelineRun(
                    id=run_id,
                    company_domain=domain,
                    status=PipelineStatus.COMPLETED,
                    created_at=created_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    company_profile=company_profile,
                    competitors=competitor_profiles,
                    discover_source_urls=discover_sources,
                    radar_scores=radar_scores,
                )
                radar_output = pipeline_run_to_radar_output(run)
                result = radar_output.model_dump(by_alias=True, mode="json", exclude_none=True)
                cache_set(f"radar_{domain}", result)
                logger.info("scan_stream=complete domain=%s duration=%.1fs", domain, time.monotonic() - t0)
                await queue.put({"result": result})
            except Exception as e:
                logger.error("scan_stream=error domain=%s error=%s", domain, e, exc_info=True)
                await queue.put({"error": str(e)})
            finally:
                await queue.put(None)  # sentinel — signals end of stream

        pipeline_task = asyncio.create_task(run_pipeline())

        # Immediate ping confirms HTTP body open before first pipeline event.
        # Without this, frontend sees no bytes until run_pipeline emits, which
        # makes a stuck pipeline indistinguishable from a network hang.
        yield ": connected\n\n"

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Keepalive prevents proxy/browser idle timeouts and proves
                    # the stream is still alive during long phases.
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    break
                yield _sse(event)
        except (GeneratorExit, asyncio.CancelledError):
            # Client disconnected — cancel pipeline so it stops burning LinkUp credits.
            pipeline_task.cancel()
            try:
                await pipeline_task
            except (asyncio.CancelledError, Exception):
                pass
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/scan/discover")
@limiter.limit("3/minute")
async def scan_discover(request: Request, req: AnalyzeRequest, _auth: None = Depends(verify_token)) -> dict:
    """Phase 1+2: UNDERSTAND + DISCOVER only. Returns lightweight candidate list.

    Response cached by run_id for 2h so /scan/enrich can resume without re-running.
    Client can supply run_id for refresh recovery via /scan/status/{run_id}.
    """
    _check_kill_switch()
    _check_daily_budget_eur()
    domain = _normalize_domain(req.url)
    if not domain:
        raise HTTPException(status_code=422, detail="Invalid URL")

    run_id = _validate_run_id(req.run_id) if req.run_id else str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    cache_set_progress(run_id, {
        "runId": run_id, "domain": domain, "phase": "UNDERSTAND", "status": "start",
        "startedAt": created_at,
    })

    try:
        linkup: LinkupClient = app.state.linkup

        async with app.state.pipeline_sem:
            async with _capture_scan_cost(linkup, run_id, "discover_only"):
                company_profile = await understand.run(domain, linkup, run_id, claude=app.state.claude)
                cache_set_progress(run_id, {
                    "runId": run_id, "domain": domain, "phase": "DISCOVER", "status": "start",
                    "startedAt": created_at,
                })
                candidates, discover_sources, _ = await discover.run(company_profile, linkup)

        # Persist intermediate state so /scan/enrich can resume with selected subset
        run_id = company_profile.pipeline_run_id  # propagated UUID
        cache_set_discover(run_id, {
            "company_profile": company_profile.model_dump(mode="json"),
            "candidates": [c.model_dump() for c in candidates],
            "discover_sources": discover_sources,
        })

        result = DiscoverResult(
            run_id=run_id,
            company_name=company_profile.name,
            company_domain=company_profile.domain,
            company_tagline=company_profile.positioning or company_profile.summary or "",
            candidates=candidates,
            scanned_at=created_at,
            sources_count=len(discover_sources),
        )
        # Return camelCase via alias (model uses snake_case internally)
        result_json = result.model_dump(by_alias=True, mode="json")
        cache_set_progress(run_id, {
            "runId": run_id, "domain": domain, "phase": "DISCOVER", "status": "ok",
            "startedAt": created_at, "discoverResult": result_json,
        })
        logger.info(
            "scan_discover=complete domain=%s run_id=%s candidates=%d duration=%.1fs",
            domain, run_id, len(candidates), time.monotonic() - t0,
        )
        return result_json

    except Exception as e:
        logger.error("scan_discover=error domain=%s error=%s", domain, e, exc_info=True)
        cache_set_progress(run_id, {
            "runId": run_id, "domain": domain, "phase": "DISCOVER", "status": "error",
            "startedAt": created_at, "error": str(e),
        })
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scan/enrich")
@limiter.limit("3/minute")
async def scan_enrich_stream(request: Request, req: EnrichRequest, _auth: None = Depends(verify_token)) -> StreamingResponse:
    """Phase 3+4: ENRICH + SYNTHESIZE on VC-selected candidates. SSE stream → RadarOutput.

    Requires a valid run_id from a prior /scan/discover call (2h TTL).
    'selected' is a list of bare domains to enrich, e.g. ["notion.so", "coda.io"].
    """
    _check_kill_switch()
    _check_daily_budget_eur()
    _validate_run_id(req.run_id)

    cached_discover = cache_get_discover(req.run_id)
    if not cached_discover:
        raise HTTPException(
            status_code=404,
            detail=f"run_id '{req.run_id}' not found or expired (2h TTL). Re-run /scan/discover.",
        )

    if not req.selected:
        raise HTTPException(status_code=422, detail="'selected' list is empty — nothing to enrich.")

    # If a pipeline is already running for this run_id (e.g. user re-POSTed after a refresh
    # before the original finished), tell the client to poll /scan/status instead of spawning
    # a duplicate pipeline that would burn Linkup credits twice.
    jobs: dict = app.state.enrich_jobs
    existing = jobs.get(req.run_id)
    if existing is not None and not existing["task"].done():
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline already running for run_id '{req.run_id}'. Poll GET /scan/status/{{run_id}} instead.",
        )

    queue: asyncio.Queue = asyncio.Queue()
    domain = cached_discover.get("company_profile", {}).get("domain", "")
    created_at = datetime.now(timezone.utc).isoformat()

    async def emit(event: dict) -> None:
        await queue.put(event)

    async def run_enrich_pipeline() -> None:
        t0 = time.monotonic()
        run_id = req.run_id
        try:
            from models.company import CompanyProfile as _CompanyProfile
            company_profile = _CompanyProfile.model_validate(cached_discover["company_profile"])
            all_candidates = cached_discover.get("candidates", [])
            discover_sources = cached_discover.get("discover_sources", [])

            # Filter to VC-selected domains only
            selected_set = {_normalize_domain(d) for d in req.selected}
            selected_candidates = [
                DiscoverCandidate.model_validate(c)
                for c in all_candidates
                if _normalize_domain(c.get("domain", "")) in selected_set
            ]

            if not selected_candidates:
                cache_set_progress(run_id, {
                    "runId": run_id, "domain": company_profile.domain, "phase": "ENRICH",
                    "status": "error", "startedAt": created_at,
                    "error": "None of the selected domains matched discovered candidates.",
                })
                await queue.put({"error": "None of the selected domains matched discovered candidates."})
                return

            competitor_dicts = _candidates_to_enrich_dicts(selected_candidates)

            linkup: LinkupClient = app.state.linkup

            async with app.state.pipeline_sem:
                async with _capture_scan_cost(linkup, run_id, "enrich_only"):
                    cache_set_progress(run_id, {
                        "runId": run_id, "domain": company_profile.domain, "phase": "ENRICH",
                        "status": "start", "startedAt": created_at,
                    })
                    await queue.put({"phase": "ENRICH", "status": "start"})
                    competitor_profiles = await enrich.run(competitor_dicts, linkup, run_id, event_cb=emit)
                    cache_set_progress(run_id, {
                        "runId": run_id, "domain": company_profile.domain, "phase": "ENRICH",
                        "status": "ok", "startedAt": created_at, "count": len(competitor_profiles),
                    })
                    await queue.put({"phase": "ENRICH", "status": "ok", "count": len(competitor_profiles)})

                    cache_set_progress(run_id, {
                        "runId": run_id, "domain": company_profile.domain, "phase": "SYNTHESIZE",
                        "status": "start", "startedAt": created_at,
                    })
                    await queue.put({"phase": "SYNTHESIZE", "status": "start"})
                    radar_scores = synthesize.run(company_profile, competitor_profiles)
                    await queue.put({"phase": "SYNTHESIZE", "status": "ok", "count": len(radar_scores)})

            run = PipelineRun(
                id=run_id,
                company_domain=company_profile.domain,
                status=PipelineStatus.COMPLETED,
                created_at=created_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                company_profile=company_profile,
                competitors=competitor_profiles,
                discover_source_urls=discover_sources,
                radar_scores=radar_scores,
            )
            radar_output = pipeline_run_to_radar_output(run)
            result = radar_output.model_dump(by_alias=True, mode="json", exclude_none=True)
            # Cache full result under standard radar key + progress (with result) for refresh recovery
            cache_set(f"radar_{company_profile.domain}", result)
            cache_set_progress(run_id, {
                "runId": run_id, "domain": company_profile.domain, "phase": "SYNTHESIZE",
                "status": "ok", "startedAt": created_at, "result": result,
            })
            logger.info(
                "scan_enrich=complete domain=%s run_id=%s duration=%.1fs",
                company_profile.domain, run_id, time.monotonic() - t0,
            )
            await queue.put({"result": result})
        except Exception as e:
            logger.error("scan_enrich=error run_id=%s error=%s", run_id, e, exc_info=True)
            cache_set_progress(run_id, {
                "runId": run_id, "domain": domain, "phase": "ENRICH", "status": "error",
                "startedAt": created_at, "error": str(e),
            })
            await queue.put({"error": str(e)})
        finally:
            await queue.put(None)  # sentinel — end of stream

    pipeline_task = asyncio.create_task(run_enrich_pipeline())
    jobs[req.run_id] = {"task": pipeline_task}
    # GC when done so dict doesn't grow unbounded (2h TTL on progress cache covers reads)
    def _cleanup(_t: asyncio.Task, _rid: str = req.run_id) -> None:
        jobs.pop(_rid, None)
    pipeline_task.add_done_callback(_cleanup)

    async def event_stream():
        def _sse(data: dict) -> str:
            return f": flush\n\ndata: {json.dumps(data)}\n\n"

        yield ": connected\n\n"
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    break
                yield _sse(event)
        except (GeneratorExit, asyncio.CancelledError):
            # Client disconnected — DO NOT cancel the pipeline. It writes progress + final
            # result to cache so a reconnecting client (refresh) can recover via /scan/status.
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class MemoRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    domain: str
    template: dict  # TemplateSpec (built-in generalist or VC custom) from the frontend


@app.post("/scan/memo")
@limiter.limit("6/minute")
async def scan_memo(request: Request, req: MemoRequest, _auth: None = Depends(verify_token)) -> dict:
    """Generate a comparative VC memo from an already-cached scan + a template.

    On-demand, downstream of the pipeline. Re-reads the authoritative RadarOutput
    from cache by domain (never trusts a client-supplied blob), feeds a closed,
    citation-tagged payload to Claude, and returns a grounded Memo (camelCase).
    """
    _check_kill_switch()
    domain = _normalize_domain(req.domain)
    if not domain:
        raise HTTPException(status_code=422, detail="Invalid domain")

    cached = cache_get(f"radar_{domain}") or cache_get_latest(domain)
    if not cached:
        raise HTTPException(status_code=404, detail="No scan found for domain — run a scan first.")

    try:
        template = TemplateSpec.model_validate(req.template)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid template: {e}")

    try:
        memo = memo_pipeline.run(cached, template, app.state.claude)
    except Exception as e:
        logger.error("scan_memo=error domain=%s error=%s", domain, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return memo.model_dump(by_alias=True, mode="json", exclude_none=True)


@app.get("/scan/status/{run_id}")
@limiter.exempt
async def scan_status(request: Request, run_id: str, _auth: None = Depends(verify_token)) -> dict:
    """Return the latest progress snapshot for a run_id (refresh recovery).

    Frontend localStorage stashes run_id on scan start; after a refresh it polls
    this endpoint every 2s until phase=="SYNTHESIZE" && status=="ok" (result attached).
    Exempt from the global rate limit so polling (~30 req/min) doesn't trip 429.
    """
    _validate_run_id(run_id)
    progress = cache_get_progress(run_id)
    if not progress:
        raise HTTPException(
            status_code=404,
            detail=f"run_id '{run_id}' not found or expired (2h TTL).",
        )
    progress["running"] = run_id in app.state.enrich_jobs
    return progress


def _status_from_iso(iso: Optional[str]) -> str:
    """Derive Fresh/Stale/Archived from a scannedAt ISO timestamp.

    <7d → fresh, <30d → stale, otherwise → archived. Bad input → archived.
    """
    if not iso:
        return "archived"
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return "archived"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - ts
    if age.days < 7:
        return "fresh"
    if age.days < 30:
        return "stale"
    return "archived"


@app.get("/scans")
@limiter.exempt
async def list_scans(request: Request, _auth: None = Depends(verify_token)) -> list[dict]:
    """List all known scans (dedup by domain, most recent first).

    Reads Supabase first, file glob fallback. Read-only, never triggers Linkup.
    """
    items = cache_list_all()
    for it in items:
        it["status"] = _status_from_iso(it.get("scannedAt"))
    return items


@app.get("/scans/{domain}/latest")
@limiter.exempt
async def get_scan_latest(request: Request, domain: str, _auth: None = Depends(verify_token)) -> dict:
    """Return the most recent full RadarOutput for `domain`.

    404 if no cached scan exists. Read-only, never triggers Linkup.
    """
    bare = _norm_domain_util(domain) if domain else ""
    if not bare:
        raise HTTPException(status_code=422, detail="Invalid domain")
    payload = cache_get_latest(bare)
    if not payload:
        raise HTTPException(status_code=404, detail=f"No cached scan for domain '{bare}'.")
    return payload


@app.get("/health")
@limiter.exempt
async def health() -> dict:
    return {"status": "ok"}

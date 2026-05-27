import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

from clients import ClaudeClient, LinkupClient
from models import PipelineRun, PipelineStatus
from models.competitor import DiscoverCandidate, DiscoverResult
from pipeline import discover, enrich, synthesize, understand
from pipeline.transform import pipeline_run_to_radar_output
from utils import cache_get, cache_set, cache_get_discover, cache_set_discover, normalize_domain as _norm_domain_util


def _check_kill_switch() -> None:
    if os.environ.get("RADAR_KILL_SWITCH", "").lower() in ("1", "true", "on"):
        raise HTTPException(status_code=503, detail="Service temporarily disabled")


limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute", "100/hour"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.linkup = LinkupClient()
    app.state.claude = ClaudeClient()
    app.state.pipeline_sem = asyncio.Semaphore(
        int(os.environ.get("RADAR_MAX_CONCURRENT", "2"))
    )
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
    os.environ.get("FRONTEND_URL", ""),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in _ALLOWED_ORIGINS if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    url: str


def _normalize_domain(url: str) -> str:
    from urllib.parse import urlparse
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    return parsed.netloc.lstrip("www.").rstrip("/") or parsed.path.lstrip("www.").rstrip("/")


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
    run_id: str
    selected: list[str]  # bare domains VC selected, e.g. ["notion.so", "coda.io"]


@app.post("/analyze")
@limiter.limit("3/minute")
async def analyze(request: Request, req: AnalyzeRequest) -> dict:
    _check_kill_switch()
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
async def scan(request: Request, req: AnalyzeRequest) -> dict:
    """Like /analyze but returns RadarOutput (camelCase, frontend-ready)."""
    _check_kill_switch()
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
async def scan_stream(request: Request, req: AnalyzeRequest) -> StreamingResponse:
    """SSE endpoint — emits fine-grained progress events then final result."""
    _check_kill_switch()
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
async def scan_discover(request: Request, req: AnalyzeRequest) -> dict:
    """Phase 1+2: UNDERSTAND + DISCOVER only. Returns lightweight candidate list.

    Response cached by run_id for 2h so /scan/enrich can resume without re-running.
    """
    _check_kill_switch()
    domain = _normalize_domain(req.url)
    if not domain:
        raise HTTPException(status_code=422, detail="Invalid URL")

    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    try:
        linkup: LinkupClient = app.state.linkup

        async with app.state.pipeline_sem:
            company_profile = await understand.run(domain, linkup, run_id, claude=app.state.claude)
            candidates, discover_sources, _ = await discover.run(company_profile, linkup)

        # Persist intermediate state so /scan/enrich can resume with selected subset
        run_id = company_profile.pipeline_run_id  # use the profile's run_id (already a UUID)
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
        logger.info(
            "scan_discover=complete domain=%s run_id=%s candidates=%d duration=%.1fs",
            domain, run_id, len(candidates), time.monotonic() - t0,
        )
        # Return camelCase via alias (model uses snake_case internally)
        return result.model_dump(by_alias=True, mode="json")

    except Exception as e:
        logger.error("scan_discover=error domain=%s error=%s", domain, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scan/enrich")
@limiter.limit("3/minute")
async def scan_enrich_stream(request: Request, req: EnrichRequest) -> StreamingResponse:
    """Phase 3+4: ENRICH + SYNTHESIZE on VC-selected candidates. SSE stream → RadarOutput.

    Requires a valid run_id from a prior /scan/discover call (2h TTL).
    'selected' is a list of bare domains to enrich, e.g. ["notion.so", "coda.io"].
    """
    _check_kill_switch()

    cached_discover = cache_get_discover(req.run_id)
    if not cached_discover:
        raise HTTPException(
            status_code=404,
            detail=f"run_id '{req.run_id}' not found or expired (2h TTL). Re-run /scan/discover.",
        )

    if not req.selected:
        raise HTTPException(status_code=422, detail="'selected' list is empty — nothing to enrich.")

    async def event_stream():
        def _sse(data: dict) -> str:
            return f": flush\n\ndata: {json.dumps(data)}\n\n"

        queue: asyncio.Queue = asyncio.Queue()

        async def emit(event: dict) -> None:
            await queue.put(event)

        async def run_enrich_pipeline() -> None:
            t0 = time.monotonic()
            run_id = req.run_id
            created_at = datetime.now(timezone.utc).isoformat()
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
                    await queue.put({"error": "None of the selected domains matched discovered candidates."})
                    return

                competitor_dicts = _candidates_to_enrich_dicts(selected_candidates)

                linkup: LinkupClient = app.state.linkup

                async with app.state.pipeline_sem:
                    await queue.put({"phase": "ENRICH", "status": "start"})
                    competitor_profiles = await enrich.run(competitor_dicts, linkup, run_id, event_cb=emit)
                    await queue.put({"phase": "ENRICH", "status": "ok", "count": len(competitor_profiles)})

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
                # Cache full result under standard radar key for later retrieval
                cache_set(f"radar_{company_profile.domain}", result)
                logger.info(
                    "scan_enrich=complete domain=%s run_id=%s duration=%.1fs",
                    company_profile.domain, run_id, time.monotonic() - t0,
                )
                await queue.put({"result": result})
            except Exception as e:
                logger.error("scan_enrich=error run_id=%s error=%s", run_id, e, exc_info=True)
                await queue.put({"error": str(e)})
            finally:
                await queue.put(None)  # sentinel

        pipeline_task = asyncio.create_task(run_enrich_pipeline())
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


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

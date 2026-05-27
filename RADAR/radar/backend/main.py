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

from clients import LinkupClient
from generate_data_js import generate_data_js
from models import PipelineRun, PipelineStatus
from pipeline import discover, enrich, understand
from pipeline.transform import pipeline_run_to_radar_output
from utils import cache_get, cache_set


def _check_kill_switch() -> None:
    if os.environ.get("RADAR_KILL_SWITCH", "").lower() in ("1", "true", "on"):
        raise HTTPException(status_code=503, detail="Service temporarily disabled")


limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute", "100/hour"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.linkup = LinkupClient()
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
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "null",  # file:// origin
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
            company_profile = await understand.run(domain, linkup, run_id)

            competitor_dicts = await discover.run(company_profile, linkup)

            competitor_profiles = await enrich.run(competitor_dicts, linkup, run_id)

        run = PipelineRun(
            id=run_id,
            company_domain=domain,
            status=PipelineStatus.COMPLETED,
            created_at=created_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            company_profile=company_profile,
            competitors=competitor_profiles,
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
            company_profile = await understand.run(domain, linkup, run_id)
            competitor_dicts = await discover.run(company_profile, linkup)
            competitor_profiles = await enrich.run(competitor_dicts, linkup, run_id)

        run = PipelineRun(
            id=run_id,
            company_domain=domain,
            status=PipelineStatus.COMPLETED,
            created_at=created_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            company_profile=company_profile,
            competitors=competitor_profiles,
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
                    company_profile = await understand.run(domain, linkup, run_id, event_cb=emit)
                    await queue.put({"phase": "UNDERSTAND", "status": "ok", "name": company_profile.name})

                    await queue.put({"phase": "DISCOVER", "status": "start"})
                    competitor_dicts = await discover.run(company_profile, linkup, event_cb=emit)
                    await queue.put({"phase": "DISCOVER", "status": "ok", "count": len(competitor_dicts)})

                    await queue.put({"phase": "ENRICH", "status": "start"})
                    competitor_profiles = await enrich.run(competitor_dicts, linkup, run_id, event_cb=emit)
                    await queue.put({"phase": "ENRICH", "status": "ok", "count": len(competitor_profiles)})

                run = PipelineRun(
                    id=run_id,
                    company_domain=domain,
                    status=PipelineStatus.COMPLETED,
                    created_at=created_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    company_profile=company_profile,
                    competitors=competitor_profiles,
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
        except GeneratorExit:
            pipeline_task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class CopilotMessage(BaseModel):
    role: str  # "user" | "assistant"
    text: str


class CopilotRequest(BaseModel):
    query: str
    context: str = ""
    history: list[CopilotMessage] = []


@app.post("/copilot")
@limiter.limit("20/minute")
async def copilot(request: Request, req: CopilotRequest) -> dict:  # noqa: ARG001
    _check_kill_switch()
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query is required")

    # Build conversation history prefix so follow-up questions have context
    history_text = ""
    if req.history:
        lines = []
        for m in req.history[-6:]:  # last 6 messages max
            prefix = "User" if m.role == "user" else "Assistant"
            lines.append(f"{prefix}: {m.text}")
        history_text = "Previous conversation:\n" + "\n".join(lines) + "\n\n"

    full_query = (
        "You are a sharp VC analyst assistant. Answer in 2-4 sentences max. "
        "Be direct and specific — no filler, no long paragraphs. "
        "Use bullet points only if listing 3+ items. Lead with the insight, not the context.\n\n"
        f"{history_text}"
        f"Question: {query}"
        + (f"\n\nScan context: {req.context}" if req.context else "")
    )

    linkup: LinkupClient = app.state.linkup
    result = await linkup.search(query=full_query, depth="standard", output_type="sourcedAnswer")

    sources = [
        {
            "name": s.get("name", ""),
            "url": s.get("url", ""),
            "snippet": s.get("snippet", ""),
            "favicon": s.get("favicon", ""),
        }
        for s in (result.get("sources") or [])
    ]
    return {"answer": result.get("answer", ""), "sources": sources}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

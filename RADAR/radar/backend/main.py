import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

from clients import ClaudeClient, LinkupClient
from generate_data_js import generate_data_js
from models import PipelineRun, PipelineStatus
from pipeline import discover, enrich, understand
from pipeline.transform import pipeline_run_to_radar_output
from utils import cache_get, cache_set


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.linkup = LinkupClient()
    app.state.claude = ClaudeClient()
    yield


app = FastAPI(title="Radar API", version="1.0.0", lifespan=lifespan)

_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "null",  # file:// origin — browsers send "null" for local file access
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
async def analyze(req: AnalyzeRequest) -> dict:
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
async def scan(req: AnalyzeRequest) -> dict:
    """Like /analyze but returns RadarOutput (camelCase, frontend-ready)."""
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
async def scan_stream(req: AnalyzeRequest) -> StreamingResponse:
    """SSE endpoint — emits phase events then final result."""
    domain = _normalize_domain(req.url)
    if not domain:
        raise HTTPException(status_code=422, detail="Invalid URL")

    async def event_stream():
        def emit(data: dict) -> str:
            return f"data: {json.dumps(data)}\n\n"

        run_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        t0 = time.monotonic()
        linkup: LinkupClient = app.state.linkup

        try:
            yield emit({"phase": "UNDERSTAND", "status": "start"})
            company_profile = await understand.run(domain, linkup, run_id)
            yield emit({"phase": "UNDERSTAND", "status": "ok", "name": company_profile.name})

            yield emit({"phase": "DISCOVER", "status": "start"})
            competitor_dicts = await discover.run(company_profile, linkup)
            yield emit({"phase": "DISCOVER", "status": "ok", "count": len(competitor_dicts)})

            yield emit({"phase": "ENRICH", "status": "start"})
            competitor_profiles = await enrich.run(competitor_dicts, linkup, run_id)
            yield emit({"phase": "ENRICH", "status": "ok", "count": len(competitor_profiles)})

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
            yield emit({"result": result})

        except Exception as e:
            logger.error("scan_stream=error domain=%s error=%s", domain, e, exc_info=True)
            yield emit({"error": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

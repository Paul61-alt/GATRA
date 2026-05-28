import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).parent.parent.parent / "cache"

# ── DISCOVER intermediate cache (keyed by run_id, TTL-based not date-based) ──
_DISCOVER_CACHE_DIR = _CACHE_DIR / "discover"
_DISCOVER_TTL_SECONDS = 7200  # 2h — VC has time to select

# ── PROGRESS cache (keyed by run_id) — used for refresh recovery ──
_PROGRESS_CACHE_DIR = _CACHE_DIR / "progress"
_PROGRESS_TTL_SECONDS = 7200  # 2h aligned with discover


def get_discover(run_id: str) -> Optional[dict]:
    """Load cached discover result for run_id. Returns None if missing or expired."""
    p = _DISCOVER_CACHE_DIR / f"{run_id}.json"
    if not p.exists():
        return None
    age = time.time() - p.stat().st_mtime
    if age > _DISCOVER_TTL_SECONDS:
        logger.info("discover cache expired run_id=%s age=%.0fs", run_id, age)
        try:
            p.unlink()
        except OSError:
            pass
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("discover cache read error run_id=%s err=%s", run_id, e)
        return None


def set_discover(run_id: str, data: dict) -> None:
    """Persist discover result (CompanyProfile + candidates) keyed by run_id."""
    _DISCOVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _DISCOVER_CACHE_DIR / f"{run_id}.json"
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("discover cache write run_id=%s", run_id)
    except OSError as e:
        logger.warning("discover cache write error run_id=%s err=%s", run_id, e)


def get_progress(run_id: str) -> Optional[dict]:
    """Load cached progress snapshot for run_id. Returns None if missing or expired."""
    p = _PROGRESS_CACHE_DIR / f"{run_id}.json"
    if not p.exists():
        return None
    age = time.time() - p.stat().st_mtime
    if age > _PROGRESS_TTL_SECONDS:
        try:
            p.unlink()
        except OSError:
            pass
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def set_progress(run_id: str, data: dict) -> None:
    """Persist progress snapshot keyed by run_id. Overwrites previous snapshot."""
    _PROGRESS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _PROGRESS_CACHE_DIR / f"{run_id}.json"
    try:
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        logger.warning("progress cache write error run_id=%s err=%s", run_id, e)


# ── Supabase client (lazy, None if env vars absent or import fails) ──────────
_sb_client = None
_sb_init_attempted = False


def _sb():
    """Return cached Supabase client or None. Safe to call from anywhere."""
    global _sb_client, _sb_init_attempted
    if _sb_init_attempted:
        return _sb_client
    _sb_init_attempted = True
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        logger.info("Supabase not configured (SUPABASE_URL/SERVICE_KEY missing) — file cache only")
        return None
    try:
        from supabase import create_client
        _sb_client = create_client(url, key)
        logger.info("Supabase client initialized url=%s", url)
    except Exception as e:
        logger.warning("Supabase init failed, file-only mode: %s", e)
        _sb_client = None
    return _sb_client


def _strip_radar_prefix(cache_key: str) -> str:
    """Callers pass `radar_{domain}` as cache key. Strip the prefix to get the bare domain."""
    if cache_key.startswith("radar_"):
        return cache_key[len("radar_"):]
    return cache_key


def _key(domain: str) -> str:
    return f"{domain.lower().replace('/', '_')}_{date.today().isoformat()}"


def _path(domain: str) -> Path:
    return _CACHE_DIR / f"{_key(domain)}.json"


def _extract_duration_ms(data: dict) -> Optional[int]:
    """Best-effort extraction of durationMs from frontend RadarOutput or pipeline result."""
    q = data.get("query")
    if isinstance(q, dict):
        v = q.get("durationMs") or q.get("duration_ms")
        if isinstance(v, (int, float)):
            return int(v)
    v = data.get("durationMs") or data.get("duration_ms")
    if isinstance(v, (int, float)):
        return int(v)
    return None


def get(domain: str) -> Optional[dict]:
    # 1. Supabase (primary)
    sb = _sb()
    if sb is not None:
        bare = _strip_radar_prefix(domain).lower()
        try:
            res = sb.table("radar_scans") \
                .select("result_json") \
                .eq("domain", bare) \
                .eq("scanned_date", date.today().isoformat()) \
                .limit(1) \
                .execute()
            rows = getattr(res, "data", None) or []
            if rows:
                logger.info("supabase cache hit domain=%s", bare)
                return rows[0]["result_json"]
        except Exception as e:
            logger.warning("Supabase get failed, falling back to file: %s", e)

    # 2. File fallback
    p = _path(domain)
    if p.exists():
        logger.info("file cache hit domain=%s", domain)
        return json.loads(p.read_text())
    return None


def set(domain: str, data: dict) -> None:
    # 1. Supabase upsert (best effort)
    sb = _sb()
    if sb is not None:
        bare = _strip_radar_prefix(domain).lower()
        try:
            sb.table("radar_scans").upsert(
                {
                    "domain": bare,
                    "scanned_date": date.today().isoformat(),
                    "result_json": data,
                    "duration_ms": _extract_duration_ms(data),
                },
                on_conflict="domain,scanned_date",
            ).execute()
            logger.info("supabase cache write domain=%s", bare)
        except Exception as e:
            logger.warning("Supabase set failed: %s", e)

    # 2. File (belt + suspenders — always)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(domain)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    logger.info("file cache write domain=%s path=%s", domain, p)


def invalidate(domain: str) -> None:
    # 1. Supabase delete
    sb = _sb()
    if sb is not None:
        bare = _strip_radar_prefix(domain).lower()
        try:
            sb.table("radar_scans") \
                .delete() \
                .eq("domain", bare) \
                .eq("scanned_date", date.today().isoformat()) \
                .execute()
            logger.info("supabase cache invalidated domain=%s", bare)
        except Exception as e:
            logger.warning("Supabase invalidate failed: %s", e)

    # 2. File delete
    p = _path(domain)
    if p.exists():
        p.unlink()
        logger.info("file cache invalidated domain=%s", domain)

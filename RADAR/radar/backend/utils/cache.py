import json
import logging
import os
import re
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


_SB_MAX_RETRIES = 3
_SB_RETRY_BASE_S = 0.5  # backoff between attempts: 0.5s, 1.0s


def _sb_configured() -> bool:
    """True if Supabase env vars are set (i.e. the DB is *expected* to be used)."""
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


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
        # Env vars ARE set but the client could not be built (e.g. `supabase` not
        # installed). This is a real misconfiguration, NOT intentional file-only mode.
        # Loud ERROR so it can't silently degrade the way the Alan scan did.
        logger.error("Supabase configured but init FAILED (history persist disabled): %s", e)
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
    # 1. File first (belt + suspenders — always, so data is never lost even if the
    #    Supabase write below raises).
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(domain)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    logger.info("file cache write domain=%s path=%s", domain, p)

    # 2. Supabase — the source of truth the history (/scans) reads from.
    #    Fail LOUD if it was expected but didn't happen: a scan that doesn't reach
    #    Supabase is invisible in history (this is exactly what silently swallowed
    #    the Alan scan). We raise AFTER the file write so no data is lost.
    sb = _sb()
    if sb is None:
        if _sb_configured():
            raise RuntimeError(
                f"Supabase configured but client unavailable — '{domain}' NOT persisted "
                "to history (file written). Check `supabase` install / init logs."
            )
        logger.info("Supabase not configured — file-only persist domain=%s", domain)
        return

    # Retry the upsert: Supabase throws transient connection resets ([Errno 54])
    # that a short retry rides out. Only raise (loud) once all attempts fail, so a
    # network blip doesn't fail an otherwise-good scan. Data is already in the file.
    bare = _strip_radar_prefix(domain).lower()
    last_err = None
    for attempt in range(_SB_MAX_RETRIES):
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
            logger.info("supabase cache write domain=%s attempt=%d", bare, attempt + 1)
            return
        except Exception as e:
            last_err = e
            if attempt < _SB_MAX_RETRIES - 1:
                wait = _SB_RETRY_BASE_S * (2 ** attempt)
                logger.warning(
                    "supabase set retry=%d domain=%s wait=%.1fs err=%s",
                    attempt + 1, bare, wait, e,
                )
                time.sleep(wait)
    logger.error("Supabase set FAILED after %d attempts domain=%s: %s", _SB_MAX_RETRIES, bare, last_err)
    raise RuntimeError(
        f"Supabase persist failed for '{bare}' after {_SB_MAX_RETRIES} attempts: {last_err}"
    ) from last_err


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


# ── Listing / latest-by-domain (used by GET /scans + /scans/{domain}/latest) ──

_RADAR_FILE_RE = re.compile(r"^radar_(.+)_(\d{4}-\d{2}-\d{2})\.json$")


def _parse_radar_filename(name: str) -> Optional[tuple[str, str]]:
    """Parse `radar_{domain}_{YYYY-MM-DD}.json` → (domain, iso_date). None if invalid."""
    m = _RADAR_FILE_RE.match(name)
    if not m:
        return None
    return m.group(1), m.group(2)


def _file_summary(p: Path) -> Optional[dict]:
    """Read a radar_*.json file and extract listing fields. None if unreadable."""
    parsed = _parse_radar_filename(p.name)
    if not parsed:
        return None
    domain, file_date = parsed
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("file cache read error path=%s err=%s", p, e)
        return None
    subject = data.get("subject") or {}
    query = data.get("query") or {}
    return {
        "domain": domain,
        "name": subject.get("name") or domain,
        "category": subject.get("category"),
        "competitors": len(data.get("competitors") or []),
        # Prefer ISO from inside file; fall back to filename date.
        "scannedAt": query.get("scannedAt") or f"{file_date}T00:00:00+00:00",
        "scanned_date": file_date,
    }


def list_all() -> list[dict]:
    """List all known scans, most recent first, deduped by domain.

    Supabase first (richer), file glob fallback.
    """
    # 1. Supabase
    sb = _sb()
    if sb is not None:
        try:
            res = sb.table("radar_scans") \
                .select("domain, scanned_date, result_json") \
                .order("scanned_date", desc=True) \
                .execute()
            rows = getattr(res, "data", None) or []
            if rows:
                # NB: `set` is shadowed by this module's own `set()` function; use dict-as-ordered-set.
                seen: dict[str, None] = {}
                out: list[dict] = []
                for row in rows:
                    dom = (row.get("domain") or "").lower()
                    if not dom or dom in seen:
                        continue
                    seen[dom] = None
                    payload = row.get("result_json") or {}
                    subject = payload.get("subject") or {}
                    query = payload.get("query") or {}
                    out.append({
                        "domain": dom,
                        "name": subject.get("name") or dom,
                        "category": subject.get("category"),
                        "competitors": len(payload.get("competitors") or []),
                        "scannedAt": query.get("scannedAt") or f"{row['scanned_date']}T00:00:00+00:00",
                        "scanned_date": row.get("scanned_date"),
                    })
                logger.info("supabase list_all hit count=%d", len(out))
                return out
        except Exception as e:
            logger.warning("Supabase list_all failed, falling back to file glob: %s", e)

    # 2. File glob fallback
    if not _CACHE_DIR.exists():
        return []
    files: list[tuple[str, Path]] = []  # (scanned_date, path)
    for p in _CACHE_DIR.glob("radar_*.json"):
        parsed = _parse_radar_filename(p.name)
        if parsed:
            files.append((parsed[1], p))
    # Sort by date desc; later we dedup by domain keeping first (newest) seen.
    files.sort(key=lambda t: t[0], reverse=True)
    seen: dict[str, None] = {}
    out: list[dict] = []
    for _, p in files:
        summary = _file_summary(p)
        if summary is None:
            continue
        dom = summary["domain"].lower()
        if dom in seen:
            continue
        seen[dom] = None
        out.append(summary)
    return out


def get_latest(domain: str) -> Optional[dict]:
    """Return most recent radar payload for `domain` regardless of scan date.

    Supabase first, file glob fallback. Returns the full RadarOutput dict.
    """
    bare = _strip_radar_prefix(domain).lower()

    # 1. Supabase
    sb = _sb()
    if sb is not None:
        try:
            res = sb.table("radar_scans") \
                .select("result_json") \
                .eq("domain", bare) \
                .order("scanned_date", desc=True) \
                .limit(1) \
                .execute()
            rows = getattr(res, "data", None) or []
            if rows:
                logger.info("supabase get_latest hit domain=%s", bare)
                return rows[0]["result_json"]
        except Exception as e:
            logger.warning("Supabase get_latest failed, falling back to file: %s", e)

    # 2. File glob fallback
    if not _CACHE_DIR.exists():
        return None
    candidates: list[tuple[str, Path]] = []
    for p in _CACHE_DIR.glob(f"radar_{bare}_*.json"):
        parsed = _parse_radar_filename(p.name)
        if parsed and parsed[0].lower() == bare:
            candidates.append((parsed[1], p))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    latest = candidates[0][1]
    try:
        logger.info("file get_latest hit domain=%s path=%s", bare, latest)
        return json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("file get_latest read error domain=%s err=%s", bare, e)
        return None

import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).parent.parent.parent / "cache"

# ── DISCOVER intermediate cache (keyed by run_id, TTL-based not date-based) ──
_DISCOVER_CACHE_DIR = _CACHE_DIR / "discover"
_DISCOVER_TTL_SECONDS = 7200  # 2h — VC has time to select


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


def _key(domain: str) -> str:
    return f"{domain.lower().replace('/', '_')}_{date.today().isoformat()}"


def _path(domain: str) -> Path:
    return _CACHE_DIR / f"{_key(domain)}.json"


def get(domain: str) -> Optional[dict]:
    p = _path(domain)
    if p.exists():
        logger.info("cache hit domain=%s", domain)
        return json.loads(p.read_text())
    return None


def set(domain: str, data: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(domain)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    logger.info("cache write domain=%s path=%s", domain, p)


def invalidate(domain: str) -> None:
    p = _path(domain)
    if p.exists():
        p.unlink()
        logger.info("cache invalidated domain=%s", domain)

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).parent.parent.parent / "cache"


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

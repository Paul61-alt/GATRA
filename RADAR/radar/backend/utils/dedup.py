from typing import TypeVar
from urllib.parse import urlparse

T = TypeVar("T")


def normalize_domain(url: str) -> str:
    """Strip scheme, www, trailing slash — canonical domain for dedup."""
    if "://" not in url:
        url = "https://" + url
    return urlparse(url).netloc.lower().lstrip("www.")


def dedup_by_website(competitors: list[dict]) -> list[dict]:
    """Deduplicate competitor dicts by normalized `website` field."""
    seen: set[str] = set()
    result = []
    for c in competitors:
        domain = normalize_domain(c.get("website", ""))
        if domain and domain not in seen:
            seen.add(domain)
            result.append(c)
    return result

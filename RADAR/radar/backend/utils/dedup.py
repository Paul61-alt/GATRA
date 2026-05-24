import re
from typing import TypeVar
from urllib.parse import urlparse

T = TypeVar("T")


def normalize_domain(url: str) -> str:
    """Canonical domain for dedup: scheme stripped, www. prefix removed, path/port dropped, lowercased."""
    if not url:
        return ""
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    netloc = parsed.netloc.lower().split(":")[0]
    # Proper prefix strip — old code used .lstrip("www.") which removes any combination
    # of leading 'w'/'.' chars (buggy on edge cases like "wxw.foo.com").
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _normalize_name(name: str) -> str:
    """Lowercase, alphanumeric-only — second-pass dedup catches same brand with diverged URLs."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def dedup_by_website(competitors: list[dict]) -> list[dict]:
    """Deduplicate competitor dicts by normalized website OR normalized name.

    Two passes prevent dupes when Linkup returns the same brand with URL variants
    (TLD swap, subdomain, etc.) that survive domain normalization.
    """
    seen_domains: set[str] = set()
    seen_names: set[str] = set()
    result = []
    for c in competitors:
        domain = normalize_domain(c.get("website", ""))
        name_key = _normalize_name(c.get("name", ""))
        if domain and domain in seen_domains:
            continue
        if name_key and name_key in seen_names:
            continue
        if domain:
            seen_domains.add(domain)
        if name_key:
            seen_names.add(name_key)
        if domain or name_key:
            result.append(c)
    return result

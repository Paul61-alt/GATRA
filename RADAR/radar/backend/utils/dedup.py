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


if __name__ == "__main__":
    # Run: python -m utils.dedup
    tests = [
        # G9: Freebe appeared twice with https+trailing-slash vs bare domain
        (
            [{"name": "Freebe", "website": "https://freebe.me/"},
             {"name": "Freebe", "website": "freebe.me"}],
            1,
        ),
        # www prefix variation → same company
        (
            [{"name": "Stripe", "website": "https://stripe.com"},
             {"name": "Stripe", "website": "http://www.stripe.com"}],
            1,
        ),
        # Different companies → both survive
        (
            [{"name": "Alpha", "website": "alpha.io"},
             {"name": "Beta", "website": "beta.io"}],
            2,
        ),
        # Same name, different URLs → deduplicated by name pass
        (
            [{"name": "Freebe", "website": "freebe.me"},
             {"name": "Freebe", "website": "app.freebe.me"}],
            1,
        ),
    ]
    all_pass = True
    for i, (group, expected) in enumerate(tests, 1):
        result = dedup_by_website(group)
        ok = len(result) == expected
        status = "PASS" if ok else f"FAIL (got {len(result)}, want {expected})"
        print(f"Test {i}: {status}")
        if not ok:
            all_pass = False
    raise SystemExit(0 if all_pass else 1)

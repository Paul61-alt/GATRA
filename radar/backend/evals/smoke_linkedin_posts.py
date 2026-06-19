"""Smoke test for LinkedIn post previews — NO Linkup calls, runs in-process.

Locks the behavior hardened during review of the LinkedIn-posts feature:
  - excerpt capped at 300c at ingestion (frontend renders 220),
  - excerpt falls back to signal headline when excerpt is absent,
  - whitespace-only entries are skipped,
  - at most 5 posts kept,
  - both data paths (transform._linkedin_posts_out and eval_to_data_js._convert)
    agree and emit camelCase keys the frontend reads.

Run from backend/:
    python3 evals/smoke_linkedin_posts.py

Exit code 0 = all assertions passed; 1 = something is broken.
"""
import os
import sys

os.environ.setdefault("LINKUP_API_KEY", "fake-for-smoke")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.competitor import LinkedInSignal  # noqa: E402
from pipeline.transform import _linkedin_posts_out  # noqa: E402
from utils.eval_to_data_js import _convert  # noqa: E402


_PASS = 0
_FAIL = 0


def _check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    mark = "OK" if condition else "FAIL"
    print(f"[{mark}] {label} {detail}")
    _PASS += condition
    _FAIL += not condition


def _run() -> None:
    long_body = "x" * 900

    # ── transform._linkedin_posts_out ────────────────────────────────────────
    class _P:
        recent_linkedin_signals = [
            LinkedInSignal(date="2026-05-26", author="A", signal="hd",
                           excerpt=long_body, image_url=None, source_url="u"),  # cap 300
            LinkedInSignal(date="2026-05-20", author="B", signal="headline only",
                           source_url="v"),                                     # fallback to signal
            LinkedInSignal(date="2026-05-19", author="C", signal="   ",
                           excerpt="   ", source_url="w"),                      # whitespace -> skip
        ]
    out = _linkedin_posts_out(_P())
    _check("transform: whitespace entry skipped", len(out) == 2, f"(kept {len(out)})")
    _check("transform: excerpt capped at 300", len(out[0].excerpt) == 300)
    _check("transform: excerpt falls back to signal", out[1].excerpt == "headline only")

    # cap at 5 posts
    class _P6:
        recent_linkedin_signals = [
            LinkedInSignal(signal=f"post {i}", source_url=str(i)) for i in range(6)
        ]
    _check("transform: capped at 5 posts", len(_linkedin_posts_out(_P6())) == 5)

    # ── eval_to_data_js._convert (demo path) ─────────────────────────────────
    raw = {
        "name": "Acme",
        "recent_linkedin_signals": [
            {"date": "2026-05-26", "author": "A", "excerpt": long_body, "source_url": "u"},  # cap 300
            {"signal": "   "},          # whitespace -> skip (strip+skip parity)
            {"signal": "headline only"},  # fallback
        ],
    }
    posts = _convert(raw, is_subject=False, similarity=0.5, threat="low")["recentLinkedinPosts"]
    _check("eval: whitespace entry skipped", len(posts) == 2, f"(kept {len(posts)})")
    _check("eval: excerpt capped at 300", len(posts[0]["excerpt"]) == 300)
    _check("eval: excerpt falls back to signal", posts[1]["excerpt"] == "headline only")
    _check("eval: camelCase keys for frontend",
           set(posts[0]) == {"date", "author", "excerpt", "imageUrl", "sourceUrl"},
           f"(keys={sorted(posts[0])})")


if __name__ == "__main__":
    print("\n=== smoke: LinkedIn post previews (no Linkup calls) ===\n")
    try:
        _run()
    except Exception as e:  # noqa: BLE001
        print(f"\nFAIL — exception: {e}")
        sys.exit(1)
    print(f"\n{_PASS} passed, {_FAIL} failed")
    sys.exit(0 if _FAIL == 0 else 1)

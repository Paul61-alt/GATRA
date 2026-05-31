"""Smoke test for refresh-recovery feature — NO Linkup calls, runs in-process.

Validates the plumbing added for `radar:activeScan` refresh recovery without burning
Linkup credits. Designed to run *before* the expensive E2E (eval_e2e_simple.py).

Run from backend/:
    LINKUP_API_KEY=fake-for-smoke python3 evals/smoke_refresh_recovery.py

Exit code 0 = all assertions passed; 1 = something is broken (don't run the E2E).
"""
import os
import sys
import traceback

# Stub the Linkup key so `LinkupClient.__init__` doesn't raise during lifespan.
# Smoke test never touches /scan/discover or /scan/enrich with valid inputs, so
# no actual Linkup call ever happens.
os.environ.setdefault("LINKUP_API_KEY", "fake-for-smoke")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from utils import cache_set_progress  # noqa: E402


_PASS = 0
_FAIL = 0
_TOTAL = 12


def _check(case_num: int, label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    mark = "OK" if condition else "FAIL"
    print(f"[{case_num}/{_TOTAL}] {label} -> {mark} {detail}")
    if condition:
        _PASS += 1
    else:
        _FAIL += 1


def _run(client: TestClient) -> None:
    # ── 1. Health endpoint reachable ─────────────────────────────────────────
    r = client.get("/health")
    _check(1, "GET /health", r.status_code == 200 and r.json().get("status") == "ok",
           f"status={r.status_code} body={r.text[:60]}")

    # ── 2. Status with valid-format but unknown run_id → 404 ─────────────────
    r = client.get("/scan/status/aaaaaaaa")
    _check(2, "GET /scan/status/{unknown-but-valid}", r.status_code == 404,
           f"status={r.status_code}")

    # ── 3. Status with too-short run_id → 422 (regex enforces >=8) ───────────
    r = client.get("/scan/status/short")
    _check(3, "GET /scan/status/{too-short}", r.status_code == 422,
           f"status={r.status_code}")

    # ── 4. Path traversal attempt → blocked (422 from validator OR 404 from
    # Starlette path normalization). Either is safe — the attack cannot reach
    # the filesystem. We accept both.
    r = client.get("/scan/status/..%2F..%2Fetc%2Fpasswd")
    _check(4, "GET /scan/status/{path-traversal} blocked",
           r.status_code in (404, 422),
           f"status={r.status_code}")

    # ── 5. Run_id with embedded space → 422 (or 404 on some routing stacks) ──
    r = client.get("/scan/status/abc def gh")
    _check(5, "GET /scan/status/{spaces}", r.status_code in (404, 422),
           f"status={r.status_code}")

    # ── 6. Cache round-trip: write progress, read via API ─────────────────────
    rid = "smoke-test-roundtrip-001"
    payload = {
        "runId": rid, "domain": "smoke.example", "phase": "DISCOVER",
        "status": "start", "startedAt": "2025-01-01T00:00:00+00:00",
    }
    cache_set_progress(rid, payload)
    r = client.get(f"/scan/status/{rid}")
    ok = (
        r.status_code == 200
        and r.json().get("runId") == rid
        and r.json().get("phase") == "DISCOVER"
        and r.json().get("running") is False
    )
    _check(6, "cache_set_progress + GET /scan/status round-trip", ok,
           f"status={r.status_code} body={r.text[:120]}")

    # ── 7. POST /scan/discover with bad runId → 422 (no pipeline starts) ────
    r = client.post("/scan/discover", json={"url": "valid.com", "runId": "../../etc/passwd"})
    _check(7, "POST /scan/discover {runId: traversal}", r.status_code == 422,
           f"status={r.status_code}")

    # ── 8. POST /scan/discover with empty url → 422 ──────────────────────────
    r = client.post("/scan/discover", json={"url": ""})
    _check(8, "POST /scan/discover {url:''}", r.status_code == 422,
           f"status={r.status_code}")

    # ── 9. POST /scan/enrich with bad runId → 422 ────────────────────────────
    r = client.post("/scan/enrich", json={"runId": "bad..path", "selected": ["x.com"]})
    _check(9, "POST /scan/enrich {runId: traversal}", r.status_code == 422,
           f"status={r.status_code}")

    # ── 10. POST /scan/enrich, valid runId but no cached_discover → 404 ──────
    r = client.post(
        "/scan/enrich",
        json={"runId": "aaaaaaaa-nocache-bbbb", "selected": ["x.com"]},
    )
    _check(10, "POST /scan/enrich {runId: valid, no cache}", r.status_code == 404,
           f"status={r.status_code}")

    # ── 11. Rate-limit exempt: 60 fast polls all return 404, never 429 ──────
    codes = set()
    for _ in range(60):
        codes.add(client.get("/scan/status/aaaaaaaa-poll-bbbb").status_code)
    _check(11, "60× GET /scan/status — no 429 (exempt)", 429 not in codes,
           f"codes_seen={sorted(codes)}")

    # ── 12. Cache result-attached → status returns the result ───────────────
    rid2 = "smoke-test-result-002"
    cache_set_progress(rid2, {
        "runId": rid2, "domain": "smoke2.example", "phase": "SYNTHESIZE",
        "status": "ok", "startedAt": "2025-01-01T00:00:00+00:00",
        "result": {"subject": {"name": "Smoke Co"}, "competitors": []},
    })
    r = client.get(f"/scan/status/{rid2}")
    ok = (
        r.status_code == 200
        and r.json().get("result", {}).get("subject", {}).get("name") == "Smoke Co"
    )
    _check(12, "Cache with result → status hydrates", ok,
           f"status={r.status_code} body={r.text[:140]}")

    # ── Cleanup smoke cache entries ─────────────────────────────────────────
    from pathlib import Path
    for rid_clean in (rid, rid2):
        p = Path(__file__).resolve().parent.parent.parent / "cache" / "progress" / f"{rid_clean}.json"
        try:
            p.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    # Use `with` so FastAPI runs the lifespan (initializes app.state.enrich_jobs etc.).
    with TestClient(app) as client:
        _run(client)
    print("")
    if _FAIL == 0:
        print(f"SMOKE PASS — {_PASS}/{_TOTAL} green. Safe to run the E2E.")
        return 0
    print(f"SMOKE FAIL — {_FAIL}/{_TOTAL} broken. Fix before running the E2E.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)

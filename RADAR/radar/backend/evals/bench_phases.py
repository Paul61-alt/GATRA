"""Bench pipeline phase durations (Linkup latency).

Run from backend/:
    python -m evals.bench_phases [N_RUNS]

Default N_RUNS=1. Writes results to evals/bench_results.csv and prints summary.
"""
from __future__ import annotations

import asyncio
import csv
import logging
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

from clients.linkup_client import LinkupClient
from models.pipeline import PipelineRun, PipelineStatus
from pipeline import discover, enrich, understand
from pipeline.transform import pipeline_run_to_radar_output

BENCH_DOMAINS = [
    "linear.app",
    "pennylane.com",
    "mistral.ai",
    "cal.com",
]

PHASES = ["understand", "discover", "enrich", "transform"]


async def bench_one(domain: str, run_idx: int, linkup: LinkupClient) -> dict[str, float]:
    """Run full pipeline once, return per-phase durations in seconds."""
    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    timings: dict[str, float] = {}

    t = time.monotonic()
    company_profile = await understand.run(domain, linkup, run_id)
    timings["understand"] = time.monotonic() - t

    t = time.monotonic()
    competitor_dicts, _discover_sources = await discover.run(company_profile, linkup)
    timings["discover"] = time.monotonic() - t

    t = time.monotonic()
    competitor_profiles = await enrich.run(competitor_dicts, linkup, run_id)
    timings["enrich"] = time.monotonic() - t

    t = time.monotonic()
    run = PipelineRun(
        id=run_id,
        company_domain=domain,
        status=PipelineStatus.COMPLETED,
        created_at=created_at,
        completed_at=datetime.now(timezone.utc).isoformat(),
        company_profile=company_profile,
        competitors=competitor_profiles,
    )
    pipeline_run_to_radar_output(run)
    timings["transform"] = time.monotonic() - t

    print(
        f"  [run {run_idx}] {domain}: "
        + " ".join(f"{p}={timings[p]:.2f}s" for p in PHASES)
    )
    return timings


def summarize(rows: list[dict]) -> None:
    print("\n=== SUMMARY (seconds) ===")
    print(f"{'phase':<12} {'n':>4} {'mean':>8} {'p50':>8} {'p95':>8} {'min':>8} {'max':>8}")
    for phase in PHASES:
        vals = [r[phase] for r in rows]
        if not vals:
            continue
        vals_sorted = sorted(vals)
        n = len(vals)
        mean = statistics.fmean(vals)
        p50 = statistics.median(vals)
        p95 = vals_sorted[max(0, int(0.95 * n) - 1)] if n > 1 else vals[0]
        print(
            f"{phase:<12} {n:>4} {mean:>8.2f} {p50:>8.2f} {p95:>8.2f} "
            f"{min(vals):>8.2f} {max(vals):>8.2f}"
        )


async def main() -> None:
    n_runs = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"Bench: {len(BENCH_DOMAINS)} domains x {n_runs} runs = {len(BENCH_DOMAINS) * n_runs} pipelines\n")

    linkup = LinkupClient()
    rows: list[dict] = []

    for run_idx in range(1, n_runs + 1):
        for domain in BENCH_DOMAINS:
            try:
                timings = await bench_one(domain, run_idx, linkup)
                rows.append({"domain": domain, "run": run_idx, **timings})
            except Exception as e:
                print(f"  [run {run_idx}] {domain}: FAILED ({e})")
                rows.append({"domain": domain, "run": run_idx, "error": str(e)})

    out_path = Path(__file__).parent / "bench_results.csv"
    fieldnames = ["domain", "run"] + PHASES + ["error"]
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nCSV: {out_path}")

    ok_rows = [r for r in rows if "error" not in r]
    if ok_rows:
        summarize(ok_rows)


if __name__ == "__main__":
    asyncio.run(main())

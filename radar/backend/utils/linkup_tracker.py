"""Live progress tracker for parallel Linkup calls.

Generic — wraps any /research, /search, or /fetch call. Each job is identified
by a label (competitor name, phase name, etc.). Renders a single live table
that updates as poll callbacks fire and as jobs complete or fail. Optionally
writes incremental JSON output to disk so the user can `tail -f` it or open in
an IDE and watch it grow.

Usage (parallel /research):
    from utils.linkup_tracker import LinkupTracker

    tracker = LinkupTracker(
        title="ENRICH POC — 4 parallel /research",
        output_path=Path("evals/eval_enrich_4comp_result.json"),
    )
    for c in competitors:
        tracker.register_job(c["name"], endpoint="/research depth=M", cost_eur=1.40)

    async def run_one(comp):
        try:
            result = await linkup.research_and_wait(
                query=..., depth="M", structured_schema=...,
                on_poll=tracker.make_callback(comp["name"]),
            )
            tracker.mark_completed(comp["name"], (result.get("output") or {}))
        except Exception as e:
            tracker.mark_failed(comp["name"], repr(e))

    with tracker.live():
        await asyncio.gather(*[run_one(c) for c in competitors],
                             return_exceptions=True)
"""
from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

from rich.box import ROUNDED
from rich.console import Console
from rich.live import Live
from rich.table import Table


STATUS_ICONS: dict[str, str] = {
    "waiting":    "⏸ ",
    "pending":    "⏳",
    "processing": "⏳",
    "completed":  "✓ ",
    "failed":     "✗ ",
}

STATUS_STYLES: dict[str, str] = {
    "waiting":    "dim",
    "pending":    "yellow",
    "processing": "yellow",
    "completed":  "green",
    "failed":     "red",
}


class LinkupTracker:
    """Multi-job live progress tracker for Linkup endpoint calls."""

    def __init__(
        self,
        title: str = "Linkup calls",
        output_path: Optional[Path] = None,
    ):
        self.title = title
        self.output_path = output_path
        self.jobs: dict[str, dict[str, Any]] = {}
        self._console = Console()
        self._live: Optional[Live] = None
        self._lock = asyncio.Lock()
        self._results: dict[str, Any] = {}

    def register_job(
        self,
        label: str,
        endpoint: str,
        cost_eur: float = 0.0,
        meta: Optional[dict] = None,
    ) -> None:
        self.jobs[label] = {
            "label": label,
            "endpoint": endpoint,
            "cost_eur": cost_eur,
            "status": "waiting",
            "elapsed": 0,
            "job_id": "",
            "fields": 0,
            "output_keys": [],
            "error": None,
            **(meta or {}),
        }

    def make_callback(self, label: str):
        """Returns an async on_poll callback bound to this job."""
        async def cb(state: dict) -> None:
            async with self._lock:
                j = self.jobs.get(label)
                if not j:
                    return
                j["status"] = state.get("status") or "processing"
                j["elapsed"] = state.get("elapsed", j["elapsed"])
                if state.get("job_id"):
                    j["job_id"] = state["job_id"]
                self._refresh()
        return cb

    def mark_completed(self, label: str, output: Any) -> None:
        j = self.jobs.get(label)
        if not j:
            return
        j["status"] = "completed"
        if isinstance(output, dict):
            j["output_keys"] = list(output.keys())
            j["fields"] = sum(
                1 for v in output.values()
                if v not in (None, "", [], {})
            )
        self._results[label] = output
        self._write_incremental()
        self._refresh()

    def mark_failed(self, label: str, error: str) -> None:
        j = self.jobs.get(label)
        if not j:
            return
        j["status"] = "failed"
        j["error"] = (error or "")[:200]
        self._refresh()

    @contextmanager
    def live(self):
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=2,
            transient=False,
        )
        with self._live:
            yield self
        self._live = None

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render())

    def _render(self) -> Table:
        table = Table(title=self.title, box=ROUNDED, show_lines=False, expand=False)
        table.add_column("Job", style="bold cyan", no_wrap=True)
        table.add_column("Endpoint", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Elapsed", justify="right")
        table.add_column("Fields", justify="right")
        table.add_column("€", justify="right")
        table.add_column("Output keys / error", overflow="fold")

        total_cost = 0.0
        for j in self.jobs.values():
            icon = STATUS_ICONS.get(j["status"], "?")
            style = STATUS_STYLES.get(j["status"], "white")
            keys_or_err = j["error"] or ", ".join(j["output_keys"][:10]) or ""
            table.add_row(
                j["label"],
                j["endpoint"],
                f"[{style}]{icon}{j['status']}[/{style}]",
                f"{j['elapsed']:>4.0f}s",
                f"{j['fields']:>3}",
                f"€{j['cost_eur']:.2f}",
                keys_or_err,
            )
            if j["status"] != "waiting":
                total_cost += j["cost_eur"]

        completed = sum(1 for j in self.jobs.values() if j["status"] == "completed")
        failed = sum(1 for j in self.jobs.values() if j["status"] == "failed")
        total = len(self.jobs)
        table.caption = (
            f"Progress: {completed}/{total} done"
            + (f" · {failed} failed" if failed else "")
            + f" · Spent: €{total_cost:.2f}"
        )
        return table

    def _write_incremental(self) -> None:
        if not self.output_path:
            return
        snapshot = {
            "completed": {label: result for label, result in self._results.items()},
            "pending": [
                label for label, j in self.jobs.items()
                if j["status"] in {"waiting", "pending", "processing"}
            ],
            "failed": {
                label: j["error"]
                for label, j in self.jobs.items()
                if j["status"] == "failed"
            },
            "summary": {
                "total": len(self.jobs),
                "completed": sum(1 for j in self.jobs.values() if j["status"] == "completed"),
                "failed": sum(1 for j in self.jobs.values() if j["status"] == "failed"),
                "cost_eur_estimated": sum(
                    j["cost_eur"] for j in self.jobs.values()
                    if j["status"] != "waiting"
                ),
            },
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False, default=str)
        )

    def summary(self) -> dict:
        """Return a final summary dict — useful after the live context exits."""
        return {
            "total": len(self.jobs),
            "completed": sum(1 for j in self.jobs.values() if j["status"] == "completed"),
            "failed": sum(1 for j in self.jobs.values() if j["status"] == "failed"),
            "cost_eur_estimated": sum(
                j["cost_eur"] for j in self.jobs.values()
                if j["status"] != "waiting"
            ),
            "jobs": self.jobs,
        }

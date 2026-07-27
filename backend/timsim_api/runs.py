"""Durable run registry — the source of truth for run state and events.

Per Codex #2: SSE is a delivery channel, not the source of truth. Each run persists its state
(`state.json`) and a monotonically numbered event log (`events.jsonl`) under
`<workspace>/runs/<run_id>/`, so a client can reconnect with `?since=<seq>` and replay without gaps,
and a run interrupted by a backend restart is reconciled to a terminal state (`lost`).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Iterable

# Terminal + non-terminal states. `lost` = was running when the backend died.
NON_TERMINAL = {"queued", "running"}
TERMINAL = {"succeeded", "failed", "cancelled", "lost"}


class Run:
    """One run. Owns its persisted state + event log; thread-safe for concurrent append/read."""

    def __init__(self, run_id: str, project_id: str, run_dir: Path):
        self.run_id = run_id
        self.project_id = project_id
        self.dir = run_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []
        self._seq = 0
        self.state = "queued"
        self.error: str | None = None
        self.created_at = time.time()
        self.started_at: float | None = None
        self.finished_at: float | None = None
        # runtime-only (not persisted): cancellation flag + live process handles
        self.cancelled = threading.Event()
        self.live_procs: set = set()
        self._persist_state()

    # ── events ──
    @property
    def events_path(self) -> Path:
        return self.dir / "events.jsonl"

    @property
    def state_path(self) -> Path:
        return self.dir / "state.json"

    def append_event(self, **fields: Any) -> dict[str, Any]:
        with self._lock:
            self._seq += 1
            ev = {"seq": self._seq, "ts": time.time(), **fields}
            self._events.append(ev)
            with self.events_path.open("a") as f:
                f.write(json.dumps(ev) + "\n")
            return ev

    def events_since(self, since: int) -> list[dict[str, Any]]:
        with self._lock:
            return [e for e in self._events if e["seq"] > since]

    @property
    def last_seq(self) -> int:
        with self._lock:
            return self._seq

    # ── state ──
    def set_state(self, state: str, error: str | None = None) -> None:
        with self._lock:
            self.state = state
            if error is not None:
                self.error = error
            if state == "running" and self.started_at is None:
                self.started_at = time.time()
            if state in TERMINAL:
                self.finished_at = time.time()
        self.append_event(kind="state", state=state, error=error)
        self._persist_state()

    def _persist_state(self) -> None:
        self.state_path.write_text(json.dumps(self.snapshot()))

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "state": self.state,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "last_seq": self._seq,
        }

    # ── process bookkeeping (for cancellation) ──
    def register_proc(self, proc) -> None:
        with self._lock:
            self.live_procs.add(proc)

    def unregister_proc(self, proc) -> None:
        with self._lock:
            self.live_procs.discard(proc)

    def procs(self) -> list:
        with self._lock:
            return list(self.live_procs)


class RunRegistry:
    """In-memory index of runs, backed by disk; one active run per project (Codex #1: 409 otherwise)."""

    def __init__(self):
        self._runs: dict[str, Run] = {}
        self._active_by_project: dict[str, str] = {}
        self._lock = threading.Lock()

    def create(self, project_id: str, runs_dir: Path) -> Run:
        import uuid

        run_id = uuid.uuid4().hex[:12]
        run = Run(run_id, project_id, runs_dir / run_id)
        with self._lock:
            self._runs[run_id] = run
            self._active_by_project[project_id] = run_id
        return run

    def has_active(self, project_id: str) -> bool:
        with self._lock:
            rid = self._active_by_project.get(project_id)
            if rid is None:
                return False
            run = self._runs.get(rid)
            return run is not None and run.state in NON_TERMINAL

    def clear_active(self, run: Run) -> None:
        with self._lock:
            if self._active_by_project.get(run.project_id) == run.run_id:
                del self._active_by_project[run.project_id]

    def get(self, run_id: str) -> Run:
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(run_id)
            return self._runs[run_id]

    def reconcile_lost(self, project_workspaces: Iterable) -> None:
        """On startup, any persisted run left in a non-terminal state has no live thread → `lost`."""
        for ws in project_workspaces:
            if not ws.runs_dir.is_dir():
                continue
            for rd in ws.runs_dir.iterdir():
                sp = rd / "state.json"
                if not sp.is_file():
                    continue
                try:
                    snap = json.loads(sp.read_text())
                except (OSError, json.JSONDecodeError):
                    continue
                if snap.get("state") in NON_TERMINAL:
                    snap["state"] = "lost"
                    snap["finished_at"] = time.time()
                    sp.write_text(json.dumps(snap))

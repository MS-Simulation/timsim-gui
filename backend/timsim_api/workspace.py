"""Project workspaces — the backend owns the filesystem layout; the client never supplies a path.

A project is a durable, server-generated workspace. Runs execute into a single per-project necroflow
cache (`cache/`), so the content-addressed cache persists across runs and the plan preview can tell
the truth about reuse-vs-rerun. The three spec files live at stable paths and are overwritten each
run, so editing a parameter changes their *content* and necroflow's `hashes_file` invalidator marks
exactly the affected nodes stale.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import datasets


def default_data_root() -> Path:
    return Path(os.environ.get("TIMSIM_DATA_ROOT", "/tmp/timsim-data")).resolve()


@dataclass(frozen=True)
class Workspace:
    project_id: str
    root: Path

    @property
    def fasta_dir(self) -> Path:
        return self.root / "fasta"

    @property
    def specs_dir(self) -> Path:
        return self.root / "specs"

    @property
    def cache_dir(self) -> Path:
        # necroflow outdir — one per project, durable, shared across runs (so caching works).
        return self.root / "cache"

    @property
    def runs_dir(self) -> Path:
        return self.root / "runs"

    def spec_path(self, name: str) -> Path:
        return self.specs_dir / name


class ProjectManager:
    """Creates and resolves project workspaces under a data root."""

    def __init__(self, data_root: Path | None = None):
        self.data_root = (data_root or default_data_root())
        self.projects_root = self.data_root / "projects"
        self.datasets_root = self.data_root / "_datasets"
        self.projects_root.mkdir(parents=True, exist_ok=True)
        datasets.ensure_datasets(self.datasets_root)

    def create(self) -> Workspace:
        project_id = uuid.uuid4().hex[:12]
        ws = Workspace(project_id, self.projects_root / project_id)
        for d in (ws.fasta_dir, ws.specs_dir, ws.cache_dir, ws.runs_dir):
            d.mkdir(parents=True, exist_ok=True)
        return ws

    def get(self, project_id: str) -> Workspace:
        root = self.projects_root / project_id
        if not root.is_dir():
            raise KeyError(project_id)
        return Workspace(project_id, root)

    def dataset_path(self, dataset_id: str) -> Path:
        return datasets.dataset_path(self.datasets_root, dataset_id)

    def list_projects(self) -> list[str]:
        return sorted(p.name for p in self.projects_root.iterdir() if p.is_dir())

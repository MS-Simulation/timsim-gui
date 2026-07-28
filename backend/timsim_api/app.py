"""FastAPI app for the Sample & Experiment Designer slice.

The client never sends a filesystem path: proteome sources reference curated *dataset ids*, and the
backend resolves them. Runs are async jobs against a durable per-project workspace; one active run
per project (409 otherwise). SSE replays persisted, numbered events so a client can reconnect.
"""

from __future__ import annotations

import json
import os
import time
import warnings
from pathlib import Path

# Check the Rust binaries before importing the pipeline module (it reads $TIMSIM_BIN at import).
# This repo is a front-end and deliberately vendors no binaries, so there is no honest default:
# refuse to start with an actionable message instead of failing later with "command not found".
_STAGE_BINARIES = (
    "timsim-proteome",
    "timsim-digest",
    "timsim-modify",
    "timsim-design",
    "timsim-yield",
)
_TIMSIM_BIN = os.environ.get("TIMSIM_BIN", "").strip()
if not _TIMSIM_BIN:
    raise RuntimeError(
        "TIMSIM_BIN is not set. Point it at a timsim-cli checkout's target/release directory — "
        "the one holding " + ", ".join(_STAGE_BINARIES) + " — e.g.\n"
        "    export TIMSIM_BIN=/path/to/timsim-cli/target/release\n"
        "See https://github.com/theGreatHerrLebert/timsim-cli; this front-end does not vendor the "
        "Rust stage binaries."
    )
_MISSING_BINARIES = [b for b in _STAGE_BINARIES if not (Path(_TIMSIM_BIN) / b).exists()]
if _MISSING_BINARIES:
    warnings.warn(
        f"TIMSIM_BIN={_TIMSIM_BIN} is missing stage binaries: "
        f"{', '.join(_MISSING_BINARIES)}. Runs will fail until they are built "
        "(`cargo build --release` in the timsim-cli checkout).",
        RuntimeWarning,
        stacklevel=2,
    )

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field, ValidationError  # noqa: E402

from . import results, runner  # noqa: E402
from .datasets import CURATED  # noqa: E402
from .runs import RunRegistry  # noqa: E402
from .schema import DesignSpec, ModsSpec, ProteomeSpec, SampleDesignerParams  # noqa: E402
from .schema.sample import SCHEMA_VERSION  # noqa: E402
from .workspace import ProjectManager, Workspace  # noqa: E402

# ── request models (dataset-id based; the backend owns paths) ─────────────────


class ProteomeSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str
    organism: str | None = None
    is_contaminant: bool = False


class SampleDesignerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = SCHEMA_VERSION
    proteome_sources: list[ProteomeSourceRequest] = Field(min_length=1)
    mods: ModsSpec
    design: DesignSpec
    enzyme: str = "trypsin"
    max_missed_cleavages: int = 2
    min_length: int = 7
    max_length: int = 30
    modify_floor: float = 1e-3
    digestion_efficiency: float = 0.90


# ── app + singletons ──────────────────────────────────────────────────────────

app = FastAPI(title="timsim v2 — Sample & Experiment Designer")
projects = ProjectManager()
registry = RunRegistry()

# Reconcile any runs left non-terminal by a previous process → `lost`.
registry.reconcile_lost(projects.get(pid) for pid in projects.list_projects())


def _resolve(req: SampleDesignerRequest) -> SampleDesignerParams:
    """Map dataset ids to server-side FASTA paths and build the validated whole-slice params."""
    sources = []
    for s in req.proteome_sources:
        if s.dataset_id not in CURATED:
            raise HTTPException(400, f"unknown dataset id {s.dataset_id!r}")
        sources.append(
            {
                "path": str(projects.dataset_path(s.dataset_id)),
                "organism": s.organism or CURATED[s.dataset_id].organism,
                "is_contaminant": s.is_contaminant,
            }
        )
    return SampleDesignerParams(
        schema_version=req.schema_version,
        proteome=ProteomeSpec(sources=sources),
        mods=req.mods,
        design=req.design,
        enzyme=req.enzyme,
        max_missed_cleavages=req.max_missed_cleavages,
        min_length=req.min_length,
        max_length=req.max_length,
        modify_floor=req.modify_floor,
        digestion_efficiency=req.digestion_efficiency,
    )


def _workspace(project_id: str) -> Workspace:
    try:
        return projects.get(project_id)
    except KeyError:
        raise HTTPException(404, f"unknown project {project_id!r}")


def _run(run_id: str):
    try:
        return registry.get(run_id)
    except KeyError:
        raise HTTPException(404, f"unknown run {run_id!r}")


# ── metadata ──────────────────────────────────────────────────────────────────


@app.get("/api/health")
def health():
    return {"ok": True, "schema_version": SCHEMA_VERSION}


@app.get("/api/enums")
def enums():
    return {
        "enzymes": ["trypsin"],
        "abundance_sources": ["lognormal", "hockeystick", "table"],
        "sites": ["residue", "n_term", "c_term"],
        "stages": ["protein", "peptide"],
        "datasets": [
            {"id": d.id, "label": d.label, "organism": d.organism} for d in CURATED.values()
        ],
    }


@app.get("/api/schema/sample-designer")
def schema():
    return SampleDesignerRequest.model_json_schema()


# ── projects ──────────────────────────────────────────────────────────────────


@app.post("/api/projects")
def create_project():
    ws = projects.create()
    return {"project_id": ws.project_id}


@app.get("/api/projects")
def list_projects():
    return {"projects": projects.list_projects()}


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    ws = _workspace(project_id)
    return {"project_id": ws.project_id}


@app.post("/api/projects/{project_id}/validate")
def validate(project_id: str, req: SampleDesignerRequest):
    _workspace(project_id)
    try:
        params = _resolve(req)
    except ValidationError as e:
        raise HTTPException(422, e.errors())
    # Show the resolved mixture with the remainder made explicit (Codex #6: never silent "rest").
    derived = []
    for c in params.design.conditions:
        explicit = {k: v for k, v in c.mix.items() if v != "rest"}
        rest_org = next((k for k, v in c.mix.items() if v == "rest"), None)
        remainder = round(1.0 - sum(explicit.values()), 6) if rest_org else None
        resolved = dict(explicit)
        if rest_org is not None:
            resolved[rest_org] = remainder
        derived.append(
            {"name": c.name, "resolved_mix": resolved, "remainder_organism": rest_org,
             "remainder": remainder}
        )
    return {"ok": True, "conditions": derived}


@app.post("/api/projects/{project_id}/plan")
def plan(project_id: str, req: SampleDesignerRequest):
    ws = _workspace(project_id)
    try:
        params = _resolve(req)
    except ValidationError as e:
        raise HTTPException(422, e.errors())
    nodes = runner.plan(ws, params)
    to_run = [n for n in nodes if not n["cached"]]
    return {"nodes": nodes, "total": len(nodes), "to_run": len(to_run),
            "cached": len(nodes) - len(to_run)}


@app.post("/api/projects/{project_id}/runs")
def start_run(project_id: str, req: SampleDesignerRequest):
    ws = _workspace(project_id)
    if registry.has_active(project_id):
        raise HTTPException(409, f"project {project_id!r} already has a run in progress")
    try:
        params = _resolve(req)
    except ValidationError as e:
        raise HTTPException(422, e.errors())
    run = runner.launch(registry, ws, params)
    return {"run_id": run.run_id, "state": run.state}


# ── runs ──────────────────────────────────────────────────────────────────────


@app.get("/api/runs/{run_id}")
def run_snapshot(run_id: str):
    return _run(run_id).snapshot()


@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    run = _run(run_id)
    if run.state not in ("queued", "running"):
        raise HTTPException(409, f"run is {run.state}, not cancellable")
    runner.cancel(run)
    return {"ok": True, "state": run.state}


@app.get("/api/runs/{run_id}/events")
def run_events(run_id: str, since: int = 0):
    run = _run(run_id)

    def gen():
        last = since
        # Replay backlog, then poll for new events until the run is terminal and drained.
        while True:
            new = run.events_since(last)
            for ev in new:
                last = ev["seq"]
                yield f"data: {json.dumps(ev)}\n\n"
            if run.state not in ("queued", "running") and last >= run.last_seq:
                yield f"data: {json.dumps({'kind': 'eof', 'state': run.state})}\n\n"
                return
            time.sleep(0.1)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/runs/{run_id}/results")
def run_results(run_id: str):
    run = _run(run_id)
    if run.state != "succeeded":
        raise HTTPException(409, f"run is {run.state}; results are available once it succeeds")
    return results.compute(run.dir)


@app.get("/api/runs/{run_id}/artifacts/{label}")
def run_artifact(run_id: str, label: str, limit: int = 50, offset: int = 0):
    import polars as pl

    run = _run(run_id)
    artifacts = json.loads((run.dir / "artifacts.json").read_text())
    if label not in artifacts:
        raise HTTPException(404, f"unknown artifact {label!r}")
    path = Path(artifacts[label])
    if not path.exists() or path.suffix != ".parquet":
        raise HTTPException(404, f"artifact {label!r} is not a readable parquet")
    df = pl.read_parquet(path)
    total = df.height
    page = df.slice(offset, limit)
    return {"columns": page.columns, "rows": page.rows(), "total": total,
            "offset": offset, "limit": limit}

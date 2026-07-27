"""The necroflow driver: plan preview, run launch, streaming job control, cancellation.

Job control (Codex #2): each node command runs in its own process group (`start_new_session=True`),
so cancellation `SIGTERM`s the *group* (then `SIGKILL`s after a grace period) and cannot orphan
children. Output streams line-by-line into the run's persisted, numbered event log. A node failure
propagates through necroflow (`keep_going=False`) and stops the run; if it was a cancellation, the
run ends `cancelled` rather than `failed`.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from necroflow import DAG, Pipeline, classify_nodes
from necroflow import resolve_command

from .pipeline import REQUEST_LABELS, request_nodes, sample_designer_pipeline
from .runs import Run, RunRegistry
from .workspace import Workspace


@dataclass
class PipelineCfg:
    proteome_spec: str
    design_spec: str
    mods_spec: str
    max_missed_cleavages: int
    min_length: int
    max_length: int
    floor: float
    digestion_efficiency: float


def write_specs(ws: Workspace, params) -> PipelineCfg:
    """Write the three spec files to their stable per-project paths and return the pipeline config.

    Overwriting at a stable path is what makes necroflow's `hashes_file` invalidator fire on a
    parameter edit: same path, changed content -> the affected nodes go stale.
    """
    ws.specs_dir.mkdir(parents=True, exist_ok=True)
    for name, text in params.emit_specs().items():
        ws.spec_path(name).write_text(text)
    return PipelineCfg(
        proteome_spec=str(ws.spec_path("proteome.toml")),
        design_spec=str(ws.spec_path("design.toml")),
        mods_spec=str(ws.spec_path("mods.toml")),
        max_missed_cleavages=params.max_missed_cleavages,
        min_length=params.min_length,
        max_length=params.max_length,
        floor=params.modify_floor,
        digestion_efficiency=params.digestion_efficiency,
    )


def _build(ws: Workspace, cfg: PipelineCfg):
    # necroflow 0.0.4: the Pipeline owns the DAG, the factory fills it in place, and nodes carry final
    # fingerprints + paths on return (no dag.add / resolve_paths step).
    dag = DAG(ws.cache_dir)
    P = Pipeline(dag)
    sample_designer_pipeline(P, cfg)
    dag.require(request_nodes(P))
    return dag, P


def plan(ws: Workspace, params) -> list[dict]:
    """Truthful reuse-vs-rerun preview: classify against the project's *durable* cache."""
    cfg = write_specs(ws, params)
    dag, P = _build(ws, cfg)
    classify_nodes(dag.nodes, dag.required_nodes)
    out = []
    for node in dag.nodes:
        state = node.state.name if node.state is not None else "UNKNOWN"
        out.append(
            {
                # 0.0.4 removed Node.pipeline_label; labels now live on the DAG/Pipeline.
                "label": dag.label_for(node),
                "artifact": node.node_type.__name__,
                "state": state,
                "cached": state == "UP_TO_DATE",
                "command": resolve_command(node),
            }
        )
    return out


def _artifact_map(P) -> dict[str, str]:
    m = {label: str(getattr(P, label).path) for label in REQUEST_LABELS}
    # ancestors the results panel also reads (organism join, unique-peptide count)
    m["proteome"] = str(P.proteome.path)
    m["peptides"] = str(P.peptides.path)
    return m


def _user_safe(node_label: str | None, exc: BaseException) -> str:
    where = f" during '{node_label}'" if node_label else ""
    return f"A simulation stage failed{where}. See the run log for details. ({type(exc).__name__})"


def make_node_runner(run: Run, dag):
    """A necroflow `node_runner(node, log_path)` that streams output and honours cancellation."""

    def runner(node, log_path: Path) -> None:
        # 0.0.4 removed Node.pipeline_label; labels are looked up on the DAG.
        label = dag.label_for(node) or node.node_type.__name__
        cmd = resolve_command(node)
        run.append_event(kind="node", node=label, phase="start")
        node.path.parent.mkdir(parents=True, exist_ok=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,  # own process group -> cancellable without orphans
        )
        run.register_proc(proc)
        try:
            with open(log_path, "w") as log:
                assert proc.stdout is not None
                for line in proc.stdout:
                    log.write(line)
                    run.append_event(kind="log", node=label, line=line.rstrip("\n"))
            rc = proc.wait()
        finally:
            run.unregister_proc(proc)
        if run.cancelled.is_set():
            run.append_event(kind="node", node=label, phase="cancelled")
            raise RuntimeError(f"cancelled during {label}")
        if rc != 0:
            run.append_event(kind="node", node=label, phase="failed", exit_code=rc)
            raise subprocess.CalledProcessError(rc, cmd)
        run.append_event(kind="node", node=label, phase="done")

    return runner


def launch(registry: RunRegistry, ws: Workspace, params) -> Run:
    """Materialize specs, build the DAG, and run it in a background thread. Returns immediately."""
    cfg = write_specs(ws, params)
    dag, P = _build(ws, cfg)
    run = registry.create(ws.project_id, ws.runs_dir)
    # Persist the label -> artifact-path map so results can be read without rebuilding the pipeline,
    # and the params so the run is reproducible/auditable.
    (run.dir / "artifacts.json").write_text(json.dumps(_artifact_map(P)))
    (run.dir / "params.json").write_text(params.model_dump_json())

    def target() -> None:
        run.set_state("running")
        current = {"label": None}
        try:
            dag.execute(node_runner=make_node_runner(run, dag), keep_going=False)
        except BaseException as exc:  # noqa: BLE001 — we translate to a durable terminal state
            if run.cancelled.is_set():
                run.set_state("cancelled")
            else:
                run.set_state("failed", error=_user_safe(current["label"], exc))
            registry.clear_active(run)
            return
        run.set_state("succeeded")
        registry.clear_active(run)

    t = threading.Thread(target=target, name=f"run-{run.run_id}", daemon=True)
    t.start()
    return run


def cancel(run: Run, grace: float = 5.0) -> None:
    """Stop the run: SIGTERM each live process group now, SIGKILL survivors after `grace`."""
    run.cancelled.set()
    for proc in run.procs():
        _killpg(proc, signal.SIGTERM)

    def _hard_kill() -> None:
        deadline = time.time() + grace
        while time.time() < deadline:
            if not run.procs():
                return
            time.sleep(0.1)
        for proc in run.procs():
            _killpg(proc, signal.SIGKILL)

    threading.Thread(target=_hard_kill, name=f"kill-{run.run_id}", daemon=True).start()


def _killpg(proc, sig) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except (ProcessLookupError, PermissionError):
        pass

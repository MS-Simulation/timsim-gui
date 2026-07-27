# timsim v2 — Sample Designer (persona-1 GUI, vertical slice 1)

A task-first GUI for lab scientists. **Scope of this first slice: QC of one sample** — the
lowest-bar experiment for checking sim realism and how third-party tools (DIA-NN, Spectronaut) are
calibrated for FDR and quant. One proteome (a HeLa stand-in), a few biological × technical
replicates, and the variance set over those replicate sets. No conditioning, no mixtures.

It covers the STRUCTURE + QUANTITY + DESIGN axes (proteome → digest → modify → design → yield) with
**no `.d` render** — so it runs in seconds and produces scientific feedback: unique-peptide / modform
counts, dynamic range, digestion-yield accounting, and the **realized biological CV across replicates**
(the QC quant ground truth). Technical-replicate variance is measurement-axis and only appears in a
rendered `.d`, so it is declared but honestly not shown here.

Other experiment types (A/B differential, dilution/LOD series, PTM localization, method/window
optimization, MBR) are mapped out but out of scope for this slice. The backend keeps the
multi-condition fold-change path working (covered by a test) for the A/B slice to build on.

Design rationale and the Codex-review revisions live in
`~/.claude/plans/imperative-prancing-sutherland.md`.

## Layout

```
backend/
  timsim_api/
    schema/        one Pydantic boundary → emits the 3 tool TOMLs + JSON Schema (pinned to Rust spec.rs)
    pipeline.py    trimmed necroflow DAG; namespaced spec keys (fixes _accumulated_config collision)
    workspace.py   server-owned project workspaces (no client paths); durable per-project cache
    runs.py        durable run registry: persisted numbered events + terminal states (incl. `lost`)
    runner.py      necroflow driver: truthful plan preview, streaming job control, process-group cancel
    results.py     scientist-legible results computed from Parquet + the yield --report
    datasets.py    curated server-side FASTA (demo-human/yeast/ecoli)
    app.py         FastAPI endpoints + SSE
  tests/           schema round-trip, e2e pipeline, API integration, cancellation
frontend/          Vite + React + TS; four task sections + hand-written mixture/occupancy widgets
```

## Run it

Build the Rust tools once (if not already in `rustims/target/release`):

```bash
cd rustims && cargo build --release --bins && cd ..
```

Backend (needs the venv with `pip install -e necroflow` + `fastapi uvicorn pydantic tomlkit polars`):

```bash
export TIMSIM_BIN="$PWD/rustims/target/release"
export TIMSIM_DATA_ROOT=/tmp/timsim-data          # where project workspaces live
PYTHONPATH=backend .venv/bin/python -m uvicorn timsim_api.app:app --port 8000
```

Frontend (dev server proxies `/api` → :8000):

```bash
cd frontend && npm install && npm run dev        # http://localhost:5173
```

## Test

```bash
.venv/bin/python -m pytest backend/tests -q      # 20 tests; e2e/API skip if binaries unbuilt
cd frontend && npm run build                      # type-check + bundle
```

## Notes / deferred

- **Reports:** only `timsim-yield` writes a machine-readable `--report` today (wired as a guaranteed
  co-output). The other stages' summaries are computed from the Parquet artifacts in `results.py`.
  Adding versioned `--report` to proteome/digest/modify/design (and declaring them co-outputs *once
  the CLI guarantees them on every run*) is the incremental follow-up.
- **necroflow `Node.fingerprint`** recursion is a perf blocker only for the *grid-capable* UI (beyond
  this single-sample / A-B slice); raise upstream before building replicate grids.
- **Visualization** (DIA-window coverage, frame preview) is a later slice — embed the `tims-viewer`
  wasm canvas rather than rebuild a renderer.

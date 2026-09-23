# timsim-gui — Sample & Experiment Designer

A task-first web GUI for the [timsim v2](https://github.com/MS-Simulation/timsim-necro) proteomics
simulator: describe an experiment the way a lab scientist would, get a
[necroflow](https://github.com/MatteoLacki/necroflow) DAG planned, run it with live progress, and read the
scientific feedback back.

**FastAPI + Pydantic** backend, **React 19 + TypeScript + Vite** frontend.

## What the first slice does

**QC of one sample** — the lowest-bar experiment for checking simulation realism and how third-party tools
(DIA-NN, Spectronaut) are calibrated for FDR and quant. One proteome, a few biological × technical
replicates, and the variance over those replicate sets.

It covers the **structure → quantity → design** axes (proteome → digest → modify → design → yield) with
**no `.d` render**, so it runs in seconds and still produces real feedback: unique-peptide and modform
counts, dynamic range, digestion-yield accounting, and the **realized biological CV across replicates**.
Technical-replicate variance is a measurement-axis effect that only appears in a rendered `.d`, so it is
declared but honestly not shown here rather than faked.

Other experiment types (A/B differential, dilution/LOD series, PTM localization, window optimization, MBR)
are mapped out but out of scope for this slice — the backend keeps the multi-condition fold-change path
working (and tested) for the A/B slice to build on. See [`docs/SAMPLE_DESIGNER.md`](docs/SAMPLE_DESIGNER.md)
and the UX rationale + its Codex review in [`docs/`](docs/).

## Why it plans before it runs

The backend drives necroflow directly, so it can answer *"what would this cost?"* honestly:

- `POST /api/projects/{id}/plan` — a truthful **reuse-vs-rerun preview**, classified against the project's
  durable cache: every node with its artifact type, cached/stale state, and the exact command.
- `POST /api/projects/{id}/runs` + `GET /api/runs/{id}/events` — launch and stream, node by node.
- `POST /api/runs/{id}/cancel` — cancellation propagates through necroflow (`keep_going=False`) and kills
  the process group, so a cancelled run stops rather than draining.

Specs are written to stable paths so necroflow's content invalidator fires exactly when a spec's *contents*
change — editing a mixture restages the work it should, and nothing else.

## What else the backend gives you

- **Curated server-side datasets, no external data required.** `backend/timsim_api/datasets.py` holds a
  registry of datasets by id (`demo-hela`, `demo-human`, `demo-yeast`, `demo-ecoli`); their FASTAs are
  generated deterministically (fixed seed, tryptic sites and S/T/Y/M/C residues so the modification presets
  actually produce modforms) on first use. `GET /api/enums` lists them. Real curated proteomes (SwissProt
  HUMAN, …) slot into the same registry.
- **A path-free security model.** The client sends *dataset ids*, never filesystem paths — the backend
  resolves ids to files and owns the whole layout, so a served instance cannot be talked into reading
  arbitrary paths. Unknown ids are a 400.
- **Durable per-project workspaces + a run registry.** `POST /api/projects` mints a workspace under
  `$TIMSIM_DATA_ROOT` (default `/tmp/timsim-data`) with its own `specs/`, `cache/` and `runs/`, so the
  necroflow cache — and therefore the plan preview's reuse-vs-rerun answer — survives across runs. One
  active run per project: a second `POST /api/projects/{id}/runs` gets a **409**. Runs left non-terminal by
  a backend restart are reconciled to `lost` at startup instead of hanging as "running" forever.
- **SSE with replay, so a client can reconnect.** Every run persists a numbered event log
  (`events.jsonl`) alongside its state; `GET /api/runs/{id}/events?since=<seq>` replays from that sequence
  number and then tails, so a dropped connection resumes without gaps. SSE is the delivery channel, not the
  source of truth.
- **Results and artifacts endpoints.** `GET /api/runs/{id}/results` computes scientist-legible feedback
  (replicate structure, realized biological CV, unique-peptide/modform counts, dynamic range, digestion-yield
  accounting) from the Parquet artifacts with polars plus the `timsim-yield --report` TOML — never by
  scraping logs; `GET /api/runs/{id}/artifacts/{label}?limit=&offset=` pages any produced parquet directly.

## Running it

```bash
# backend (Python ≥ 3.11)
python -m venv .venv && source .venv/bin/activate
pip install -e backend      # fastapi, pydantic, uvicorn, necroflow ≥ 0.0.4, polars, tomlkit
export TIMSIM_BIN=/path/to/timsim-cli/target/release   # required: the Rust stage binaries
uvicorn timsim_api.app:app --reload

# frontend
cd frontend && npm install && npm run dev
```

`TIMSIM_BIN` points at a [timsim-cli](https://github.com/MS-Simulation/timsim-cli) checkout's
`target/release`; this repo is a front-end and deliberately does not vendor the binaries. There is no
default, so the backend refuses to start without it (and warns if the directory is missing stage
binaries) rather than failing later with a mysterious "command not found".

`TIMSIM_DATA_ROOT` (default `/tmp/timsim-data`) is where project workspaces and the curated FASTAs live —
set it to something durable if you want projects to outlive a reboot.

## Tests

```bash
pip install -e "backend[test]"    # adds pytest + httpx (the FastAPI test client)
TIMSIM_BIN=/path/to/timsim-cli/target/release PYTHONPATH=backend pytest backend/tests
```

21 tests: schema round-trips against vendored golden specs, the API surface, cancellation, and a real
**end-to-end necroflow run** that executes the stage binaries and checks every requested artifact exists.

## Requires necroflow ≥ 0.0.4

The backend targets the module-level rule API (`command` / `output`, `Pipeline(dag)`, `dag.require(...)`,
`dag.label_for(node)`). It does not work against the older `Rules()` registry.

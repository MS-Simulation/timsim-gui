"""End-to-end: emitted specs actually drive the Rust tools through the trimmed necroflow DAG.

This is the genuine Rust parse-acceptance the schema unit tests defer: the Pydantic models emit the
three TOMLs, the real `timsim-*` binaries consume them, and a full proteome -> digest -> modify ->
design -> yield run must succeed and produce the expected artifacts. It also pins the
`_accumulated_config` key-collision fix: the yield node's `dependencies.toml` must carry all three
namespaced specs.

Skipped automatically if the Rust binaries are not built.
"""

from __future__ import annotations

import os
import random
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
# Point TIMSIM_BIN at a timsim-cli checkout's target/release (this repo does not vendor
# the Rust binaries — it is an independent front-end).
BIN_DIR = Path(os.environ.get("TIMSIM_BIN", REPO / "rustims" / "target" / "release"))
os.environ.setdefault("TIMSIM_BIN", str(BIN_DIR))

from timsim_api.pipeline import (  # noqa: E402
    request_nodes,
    sample_designer_pipeline,
)
from timsim_api.schema import (  # noqa: E402
    DesignSpec,
    ModsSpec,
    ProteomeSpec,
    SampleDesignerParams,
)

from necroflow import DAG, Pipeline  # noqa: E402

REQUIRED_BINS = ["timsim-proteome", "timsim-digest", "timsim-modify", "timsim-design", "timsim-yield"]
pytestmark = pytest.mark.skipif(
    not all((BIN_DIR / b).exists() for b in REQUIRED_BINS),
    reason=f"timsim binaries not built in {BIN_DIR}",
)

_AA = "ACDEFGHIKLMNPQRSTVWY"


def _tiny_fasta(organism: str, n_proteins: int, seed: int) -> str:
    """A handful of short proteins with tryptic (K/R) sites ~every 12 residues.

    Includes S/T/Y/M/C/K so the mods spec (phospho/oxidation/carbamidomethyl/GG) actually produces
    modforms.
    """
    rng = random.Random(seed)
    lines = []
    for i in range(n_proteins):
        segments = []
        for _ in range(8):  # 8 peptides of ~11 aa -> in the [7, 50] window
            core = "".join(rng.choice(_AA) for _ in range(10))
            segments.append("STYMC"[rng.randrange(5)] + core + ("K" if rng.random() < 0.5 else "R"))
        seq = "M" + "".join(segments)
        lines.append(f">{organism}_{i:03d} {organism} test protein {i}")
        lines.append(seq)
    return "\n".join(lines) + "\n"


def test_sample_designer_end_to_end(tmp_path: Path):
    ws = tmp_path / "project"
    fasta_dir = ws / "fasta"
    fasta_dir.mkdir(parents=True)

    organisms = ["HUMAN", "YEAST", "ECOLI"]
    for k, org in enumerate(organisms):
        (fasta_dir / f"{org}.fasta").write_text(_tiny_fasta(org, n_proteins=6, seed=100 + k))

    # Build the whole slice through the Pydantic boundary, then emit the three specs.
    params = SampleDesignerParams(
        proteome=ProteomeSpec(
            sources=[{"path": str(fasta_dir / f"{org}.fasta"), "organism": org} for org in organisms]
        ),
        mods=ModsSpec.from_toml_str((Path(__file__).resolve().parent / "golden" / "mods.toml").read_text()),
        design=DesignSpec(
            design={"reference": "A", "load_ng": 200, "seed": 42},
            abundance={org: {"source": "hockeystick"} for org in organisms},
            conditions=[
                {"name": "A", "mix": {"HUMAN": 0.65, "YEAST": 0.30, "ECOLI": 0.05},
                 "replicates": 1, "technical_replicates": 1},
                {"name": "B", "mix": {"HUMAN": 0.65, "YEAST": 0.20, "ECOLI": "rest"},
                 "replicates": 1, "technical_replicates": 1},
            ],
            variance={"biological": 0.15, "biological_heterogeneity": 0.5},
        ),
    )
    for name, text in params.emit_specs().items():
        (ws / name).write_text(text)

    class Cfg:
        proteome_spec = str(ws / "proteome.toml")
        design_spec = str(ws / "design.toml")
        mods_spec = str(ws / "mods.toml")
        max_missed_cleavages = params.max_missed_cleavages
        min_length = params.min_length
        max_length = params.max_length
        floor = params.modify_floor
        digestion_efficiency = params.digestion_efficiency

    outdir = ws / "runs"
    dag = DAG(outdir)
    P = Pipeline(dag)
    sample_designer_pipeline(P, Cfg)
    dag.require(request_nodes(P))
    report = dag.execute()  # raises on first failure

    # Every requested artifact exists.
    for label in ("samples", "runs", "sample_run_map", "protein_quantities",
                  "peptide_quantities", "modforms", "yield_report"):
        node = getattr(P, label)
        assert node.path.exists(), f"missing output for {label}: {node.path}"

    # The yield report is real, machine-readable, and has the accounting the results panel needs.
    yr = tomllib.loads(P.yield_report.path.read_text())
    assert "missed_cleavages" in yr and yr["missed_cleavages"]
    assert "truncation_loss" in yr and "filter_loss" in yr

    # Regression for the _accumulated_config collision: the yield node's provenance must carry all
    # three namespaced specs, not a single overwritten `spec`.
    deps = tomllib.loads((P.peptide_quantities.path.parent / ".rip" / "dependencies.toml").read_text())
    cfg = deps.get("config", {})
    assert "proteome_spec" in cfg, f"proteome_spec missing from provenance: {cfg}"
    assert "design_spec" in cfg, f"design_spec missing from provenance: {cfg}"
    assert "mods_spec" in cfg, f"mods_spec missing from provenance: {cfg}"

    # The run classified and executed the required subgraph without error.
    assert report is not None

"""The trimmed necroflow pipeline for the Sample & Experiment Designer slice.

STRUCTURE + QUANTITY + DESIGN only — proteome -> digest -> modify -> design -> yield. The heavy
measurement render (precursors/ccs/rt/simulate) is deliberately absent: this slice must run in
seconds-to-minutes and produce scientific feedback without building a `.d`.

Two conventions worth calling out (both now shared with `flow/timsim_flow.py` upstream):

1. **Namespaced spec config keys** — `proteome_spec`, `design_spec`, `mods_spec`, never a bare
   `spec`. necroflow's `_accumulated_config` flattens ancestor configs into one namespace and
   assumes key names are unique, so naming both the proteome and the design spec `spec` makes them
   collide and one silently overwrites the other in the provenance record (`dependencies.toml`).
   Provenance is load-bearing for a scientific GUI, so we namespace here and assert all three
   survive (`backend/tests/test_pipeline_e2e.py`). This was once a divergence from
   `flow/timsim_flow.py`, which used a bare `spec` for both rules; upstream namespaces its spec
   keys the same way now (timsim-necro 49f0c65), so the test stands as a regression guard rather
   than a difference.
2. **`yield --report` is wired as a guaranteed co-output** (`YieldReport`) — the tool always writes
   the report when `--report` is passed, so it is safe to declare as a co-output (it cannot poison
   cache classification by sometimes being absent).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from necroflow import NodeType, Pipeline, command, output

BIN = os.environ.get("TIMSIM_BIN", "target/release")


def hashes_file(config_key: str):
    """Invalidate a node when the spec file named by `config_key` changes *content* (not just name)."""

    def token(node) -> str:
        path = Path(node.config[config_key])
        return hashlib.sha256(path.read_bytes()).hexdigest()

    return token


# ── typed artifacts ──────────────────────────────────────────────────────────


class Proteome(NodeType):
    filename = "proteome.parquet"
    invalidator = hashes_file("proteome_spec")


class Peptides(NodeType):
    filename = "peptides.parquet"


class Occurrences(NodeType):
    filename = "peptide_occurrences.parquet"


class CleavageSites(NodeType):
    filename = "cleavage_sites.parquet"


class Modforms(NodeType):
    filename = "modforms.parquet"
    invalidator = hashes_file("mods_spec")


class Modifications(NodeType):
    filename = "modifications.parquet"
    invalidator = hashes_file("mods_spec")


class Samples(NodeType):
    filename = "samples.parquet"
    invalidator = hashes_file("design_spec")


class Runs(NodeType):
    filename = "runs.parquet"
    invalidator = hashes_file("design_spec")


class SampleRunMap(NodeType):
    filename = "sample_run_map.parquet"
    invalidator = hashes_file("design_spec")


class ProteinQuantities(NodeType):
    filename = "protein_quantities.parquet"
    invalidator = hashes_file("design_spec")


class PeptideQuantities(NodeType):
    filename = "peptide_quantities.parquet"


class YieldReport(NodeType):
    """The `timsim-yield --report` accounting (missed-cleavage distribution, truncation/filter loss).

    A guaranteed co-output: yield always writes it when `--report` is passed."""

    filename = "yield_report.toml"


# ── rules ────────────────────────────────────────────────────────────────────



@command(f"{BIN}/timsim-proteome --spec {{proteome_spec}} --out {{proteome}}")
def proteome(proteome_spec: str):
    proteome = output(Proteome)
    return proteome


@command(
    f"{BIN}/timsim-digest --proteome {{proteome}} "
    "--out-peptides {peptides} --out-occurrences {occurrences} "
    "--out-cleavage-sites {cleavage_sites} "
    "--max-missed-cleavages {max_missed_cleavages} --min-length {min_length} "
    "--max-length {max_length}"
)
def digest(proteome: Proteome, max_missed_cleavages: int, min_length: int, max_length: int):
    peptides = output(Peptides)
    occurrences = output(Occurrences)
    cleavage_sites = output(CleavageSites)
    return peptides, occurrences, cleavage_sites


@command(
    f"{BIN}/timsim-modify --peptides {{peptides}} --mods {{mods_spec}} "
    "--out-modforms {modforms} --out-modifications {modifications} --floor {floor}"
)
def modify(peptides: Peptides, mods_spec: str, floor: float):
    modforms = output(Modforms)
    modifications = output(Modifications)
    return modforms, modifications


@command(
    f"{BIN}/timsim-design --proteome {{proteome}} --spec {{design_spec}} "
    "--out-samples {samples} --out-runs {runs} --out-sample-run-map {sample_run_map} "
    "--out-protein-quantities {protein_quantities}"
)
def design(proteome: Proteome, design_spec: str):
    samples = output(Samples)
    runs = output(Runs)
    sample_run_map = output(SampleRunMap)
    protein_quantities = output(ProteinQuantities)
    return samples, runs, sample_run_map, protein_quantities


@command(
    f"{BIN}/timsim-yield --proteome {{proteome}} --occurrences {{occurrences}} "
    "--cleavage-sites {cleavage_sites} --protein-quantities {protein_quantities} "
    "--modifications {modifications} "
    "--digestion-efficiency {digestion_efficiency} --out {peptide_quantities} "
    "--report {yield_report}"
)
def peptide_yield(
    proteome: Proteome,
    occurrences: Occurrences,
    cleavage_sites: CleavageSites,
    protein_quantities: ProteinQuantities,
    modifications: Modifications,
    digestion_efficiency: float,
):
    peptide_quantities = output(PeptideQuantities)
    yield_report = output(YieldReport)
    return peptide_quantities, yield_report


# ── the trimmed pipeline ──────────────────────────────────────────────────────

# The nodes that constitute a "sample defined, not yet rendered" state. Requesting peptide_quantities
# transitively pulls proteome -> digest -> modify -> design -> yield; modforms is requested explicitly
# so the results panel can report modform counts.
REQUEST_LABELS = (
    "samples",
    "runs",
    "sample_run_map",
    "protein_quantities",
    "peptide_quantities",
    "modforms",
    "yield_report",
)


def sample_designer_pipeline(P: Pipeline, cfg) -> None:
    """Build the trimmed pipeline. `cfg` exposes the namespaced spec paths + digest/modify/yield knobs.

    Required attributes: proteome_spec, design_spec, mods_spec (paths); max_missed_cleavages,
    min_length, max_length, floor, digestion_efficiency. The seed lives inside the design spec.
    """
    P.proteome = proteome(P, proteome_spec=cfg.proteome_spec)
    P.peptides, P.occurrences, P.cleavage_sites = digest(P, 
        P.proteome,
        max_missed_cleavages=cfg.max_missed_cleavages,
        min_length=cfg.min_length,
        max_length=cfg.max_length,
    )
    P.modforms, P.modifications = modify(P, 
        P.peptides, mods_spec=cfg.mods_spec, floor=cfg.floor
    )
    P.samples, P.runs, P.sample_run_map, P.protein_quantities = design(P, 
        P.proteome, design_spec=cfg.design_spec
    )
    P.peptide_quantities, P.yield_report = peptide_yield(P, 
        P.proteome,
        P.occurrences,
        P.cleavage_sites,
        P.protein_quantities,
        P.modifications,
        digestion_efficiency=cfg.digestion_efficiency,
    )


def request_nodes(P: Pipeline) -> list:
    """The terminal nodes to request from the DAG for a sample-designer run."""
    return [getattr(P, label) for label in REQUEST_LABELS]

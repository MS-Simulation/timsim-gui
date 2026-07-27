"""Curated, server-side FASTA datasets.

The GUI targets non-coding scientists who do not think in filesystem paths — and a served app must
never accept a client-supplied path anyway. So the API exposes *datasets by id*; the backend owns the
files. For the slice these are small deterministic FASTAs generated on first use, so the whole stack
runs and tests without external data. Real curated proteomes (SwissProt HUMAN, etc.) slot in here.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

_AA = "ACDEFGHIKLMNPQRSTVWY"


@dataclass(frozen=True)
class Dataset:
    id: str
    label: str
    organism: str
    n_proteins: int
    seed: int


CURATED: dict[str, Dataset] = {
    # The default single-sample QC proteome (a HeLa human lysate stand-in).
    "demo-hela": Dataset("demo-hela", "HeLa (demo, human)", "HUMAN", 16, 200),
    # The three HYE organisms, for the optional A/B mixture path.
    "demo-human": Dataset("demo-human", "Demo — HUMAN (6 proteins)", "HUMAN", 6, 101),
    "demo-yeast": Dataset("demo-yeast", "Demo — YEAST (6 proteins)", "YEAST", 6, 102),
    "demo-ecoli": Dataset("demo-ecoli", "Demo — ECOLI (6 proteins)", "ECOLI", 6, 103),
}


def _tiny_fasta(ds: Dataset) -> str:
    """Short proteins with tryptic (K/R) sites ~every 12 residues, seeded with S/T/Y/M/C/K so the
    modification presets (phospho/oxidation/carbamidomethyl/GG) actually produce modforms."""
    rng = random.Random(ds.seed)
    out: list[str] = []
    for i in range(ds.n_proteins):
        segments = []
        for _ in range(8):
            core = "".join(rng.choice(_AA) for _ in range(10))
            segments.append("STYMC"[rng.randrange(5)] + core + ("K" if rng.random() < 0.5 else "R"))
        out.append(f">{ds.organism}_{i:03d} {ds.organism} demo protein {i}")
        out.append("M" + "".join(segments))
    return "\n".join(out) + "\n"


def ensure_datasets(root: Path) -> None:
    """Materialize the curated FASTAs under `root` if absent."""
    root.mkdir(parents=True, exist_ok=True)
    for ds in CURATED.values():
        p = root / f"{ds.id}.fasta"
        if not p.exists():
            p.write_text(_tiny_fasta(ds))


def dataset_path(root: Path, dataset_id: str) -> Path:
    if dataset_id not in CURATED:
        raise KeyError(dataset_id)
    return root / f"{dataset_id}.fasta"

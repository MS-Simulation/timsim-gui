"""Scientist-legible results, computed from the produced Parquet artifacts (Codex #4).

Results do not block on the tools growing `--report` files: everything except the yield accounting is
derived here from the artifacts with polars. The `timsim-yield --report` TOML is read directly (it is
a guaranteed co-output). Prose `job.log` parsing is never a results source.
"""

from __future__ import annotations

import json
import math
import tomllib
from pathlib import Path
from typing import Any

import polars as pl


def _load_maps(run_dir: Path) -> tuple[dict[str, str], dict[str, Any]]:
    artifacts = json.loads((run_dir / "artifacts.json").read_text())
    params = json.loads((run_dir / "params.json").read_text())
    return artifacts, params


def compute(run_dir: Path) -> dict[str, Any]:
    artifacts, params = _load_maps(run_dir)
    p = {k: Path(v) for k, v in artifacts.items()}

    samples = pl.read_parquet(p["samples"])
    runs = pl.read_parquet(p["runs"])
    proteome = pl.read_parquet(p["proteome"])
    protein_q = pl.read_parquet(p["protein_quantities"])
    peptide_q = pl.read_parquet(p["peptide_quantities"])
    peptides = pl.read_parquet(p["peptides"])
    modforms = pl.read_parquet(p["modforms"])

    reference = params["design"]["design"]["reference"]
    variance = params["design"].get("variance", {})
    conds_meta = {c["name"]: c for c in params["design"]["conditions"]}

    # ── design summary: replicate structure per condition ──
    conditions = []
    for name, grp in samples.group_by("condition"):
        nm = name[0] if isinstance(name, tuple) else name
        meta = conds_meta.get(nm, {})
        conditions.append(
            {
                "name": nm,
                "biological_replicates": int(grp.height),
                "technical_replicates": int(meta.get("technical_replicates", 1)),
            }
        )

    # ── the QC ground truth: realized biological CV across the reference condition's replicates ──
    # Per-peptide CV of amount over the biological replicates, median across peptides. Technical
    # variance is measurement-axis (the same tube injected twice) and only appears in a rendered .d,
    # so it is NOT observable here — stated honestly rather than faked.
    realized_bio_cv = None
    ref_samples = samples.filter(pl.col("condition") == reference)["sample_id"].to_list()
    if len(ref_samples) >= 2:
        stats = (
            peptide_q.filter(pl.col("sample_id").is_in(ref_samples))
            .group_by("peptide_id")
            .agg(pl.col("amount_amol").mean().alias("m"), pl.col("amount_amol").std().alias("s"))
            .filter(pl.col("m") > 0)
        )
        if stats.height > 0:
            cvs = (stats["s"] / stats["m"]).drop_nulls()
            if cvs.len() > 0:
                realized_bio_cv = _round(float(cvs.median()))

    # ── fold-change answer key (only meaningful when there are non-reference conditions) ──
    non_ref_samples = samples.filter(pl.col("condition") != reference)["sample_id"].to_list()
    answer_key: list[dict[str, Any]] = []
    if non_ref_samples and "organism" in proteome.columns:
        joined = (
            protein_q.filter(pl.col("sample_id").is_in(non_ref_samples))
            .join(proteome.select(["protein_id", "organism"]), on="protein_id", how="left")
            .group_by("organism")
            .agg(
                pl.col("true_log2fc").median().alias("median_true_log2fc"),
                pl.col("protein_id").n_unique().alias("n_proteins"),
            )
            .sort("organism")
        )
        for row in joined.iter_rows(named=True):
            answer_key.append(
                {
                    "organism": row["organism"],
                    "median_true_log2fc": _round(row["median_true_log2fc"]),
                    "n_proteins": int(row["n_proteins"]),
                }
            )

    # ── structure summary + dynamic range ──
    amol = peptide_q["amount_amol"]
    positive = amol.filter(amol > 0)
    dyn = {}
    if positive.len() > 0:
        lo, hi = float(positive.min()), float(positive.max())
        dyn = {
            "min_amol": _round(lo),
            "max_amol": _round(hi),
            "orders_of_magnitude": _round(math.log10(hi / lo)) if lo > 0 else None,
        }

    # ── yield accounting (the one machine-readable tool report) ──
    yield_report = tomllib.loads(Path(artifacts["yield_report"]).read_text())

    return {
        "design": {
            "samples": int(samples.height),
            "runs": int(runs.height),
            "reference_condition": reference,
            "conditions": conditions,
            "set_biological_cv": variance.get("biological"),
            "set_technical_cv": variance.get("technical"),
            "realized_biological_cv": realized_bio_cv,
            "technical_note": (
                "Technical-replicate variance is applied on the measurement axis and only appears "
                "in a rendered .d, which this slice does not produce."
            ),
            "fold_change_answer_key": answer_key,
        },
        "structure": {
            "proteins": int(proteome.height),
            "unique_peptides": int(peptides.height),
            "peptide_sample_rows": int(peptide_q.height),
            "modforms": int(modforms.height),
            "peptides_with_modforms": int(modforms["peptide_id"].n_unique()),
            "dynamic_range": dyn,
        },
        "yield": yield_report,
    }


def _round(x: float | None, ndigits: int = 4) -> float | None:
    if x is None:
        return None
    return round(float(x), ndigits)

"""Integration test for the FastAPI backend against the real Rust pipeline.

Primary flow is single-sample QC: one proteome, biological × technical replicates, variance over the
sets, and results reporting the realized biological CV (the QC quant ground truth). A secondary test
keeps the backend's multi-condition path (fold-change answer key) honest.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

from conftest import timsim_bin_skip_reason  # noqa: E402

# TIMSIM_BIN must point at a timsim-cli checkout's target/release. This repo vendors no Rust
# binaries and deliberately has NO fallback path: the old default (<repo>/rustims/target/release)
# no longer exists, so with TIMSIM_BIN unset this whole file skipped silently — a false green.
# Now the skip is explicit, names the env var, and conftest reports it in the pytest header and
# terminal summary so a green run can never be mistaken for a run that exercised the pipeline.
_SKIP_REASON = timsim_bin_skip_reason()
if _SKIP_REASON is not None:
    # Module-level skip, not just a mark: importing timsim_api.app raises when TIMSIM_BIN is unset.
    pytest.skip(_SKIP_REASON, allow_module_level=True)

_TMP = tempfile.mkdtemp(prefix="timsim-api-test-")
os.environ["TIMSIM_DATA_ROOT"] = _TMP

from fastapi.testclient import TestClient  # noqa: E402

from timsim_api.app import app  # noqa: E402
from timsim_api.schema import DesignSpec, ModsSpec  # noqa: E402

client = TestClient(app)

MODS = {
    "modifications": [
        {"name": "Carbamidomethyl", "unimod_id": 4, "targets": "C", "site": "residue",
         "occupancy": 0.98, "mass_delta": 57.021464, "composition": "C2H3NO",
         "blocks_cleavage": False, "stage": "protein"},
        {"name": "Oxidation", "unimod_id": 35, "targets": "M", "site": "residue",
         "occupancy": 0.05, "mass_delta": 15.994915, "composition": "O",
         "blocks_cleavage": False, "stage": "peptide"},
    ]
}


def _qc_request(bio=3, tech=2, bio_cv=0.15):
    return {
        "proteome_sources": [{"dataset_id": "demo-hela"}],
        "mods": MODS,
        "design": {
            "design": {"reference": "HeLa", "load_ng": 200, "n_proteins": None, "seed": 42},
            "abundance": {"HUMAN": {"source": "hockeystick"}},
            "conditions": [
                {"name": "HeLa", "mix": {"HUMAN": 1.0}, "replicates": bio,
                 "technical_replicates": tech},
            ],
            "variance": {"biological": bio_cv, "biological_heterogeneity": 0.5, "technical": 0.05},
        },
    }


def _wait(run_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        snap = client.get(f"/api/runs/{run_id}").json()
        if snap["state"] in ("succeeded", "failed", "cancelled", "lost"):
            return snap
        time.sleep(0.05)
    raise TimeoutError(f"run {run_id} did not finish")


def test_qc_flow():
    assert client.get("/api/health").json()["ok"] is True
    pid = client.post("/api/projects").json()["project_id"]
    req = _qc_request(bio=3, tech=2, bio_cv=0.15)

    plan0 = client.post(f"/api/projects/{pid}/plan", json=req).json()
    assert plan0["cached"] == 0

    run_id = client.post(f"/api/projects/{pid}/runs", json=req).json()["run_id"]
    snap = _wait(run_id)
    assert snap["state"] == "succeeded", snap

    res = client.get(f"/api/runs/{run_id}/results").json()
    # 3 biological × 2 technical = 6 runs, no conditioning.
    assert res["design"]["samples"] == 3
    assert res["design"]["runs"] == 6
    assert res["design"]["fold_change_answer_key"] == []
    assert res["design"]["set_biological_cv"] == pytest.approx(0.15)
    # the realized biological CV is measured from the replicate amounts and should be positive.
    rcv = res["design"]["realized_biological_cv"]
    assert rcv is not None and 0.0 < rcv < 1.0, rcv
    # yield accounting still present.
    mc = res["yield"]["missed_cleavages"]
    assert abs(sum(mc.values()) - 1.0) < 1e-6
    assert res["structure"]["unique_peptides"] > 0

    # re-plan unchanged → all cached.
    plan1 = client.post(f"/api/projects/{pid}/plan", json=req).json()
    assert plan1["to_run"] == 0 and plan1["cached"] == plan1["total"]


def test_multicondition_still_supported():
    """The backend keeps the fold-change answer-key path even though the QC GUI does not use it."""
    pid = client.post("/api/projects").json()["project_id"]
    design = DesignSpec.from_toml_str((Path(__file__).resolve().parent / "golden" / "design.toml").read_text()).model_dump()
    design["design"]["n_proteins"] = None  # demo FASTAs have few proteins
    req = {
        "proteome_sources": [{"dataset_id": x} for x in ("demo-human", "demo-yeast", "demo-ecoli")],
        "mods": ModsSpec.from_toml_str((Path(__file__).resolve().parent / "golden" / "mods.toml").read_text()).model_dump(),
        "design": design,
    }
    run_id = client.post(f"/api/projects/{pid}/runs", json=req).json()["run_id"]
    assert _wait(run_id)["state"] == "succeeded"
    res = client.get(f"/api/runs/{run_id}/results").json()
    key = {r["organism"]: r["median_true_log2fc"] for r in res["design"]["fold_change_answer_key"]}
    assert key["YEAST"] == pytest.approx(-0.585, abs=0.25)
    assert key["ECOLI"] == pytest.approx(1.585, abs=0.25)


def test_one_active_run_per_project():
    pid = client.post("/api/projects").json()["project_id"]
    req = _qc_request()
    r1 = client.post(f"/api/projects/{pid}/runs", json=req)
    assert r1.status_code == 200
    r2 = client.post(f"/api/projects/{pid}/runs", json=req)
    assert r2.status_code in (200, 409)
    _wait(r1.json()["run_id"])

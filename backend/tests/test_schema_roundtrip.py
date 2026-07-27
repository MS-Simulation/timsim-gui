"""Pin the Pydantic parameter boundary to the Rust authority's TOML surface.

Genuine end-to-end Rust parse-acceptance (feeding an emitted spec to the actual `timsim-*` binaries)
lives in the pipeline integration test — the binaries validate CLI args before parsing the spec, so
acceptance is only meaningful when real artifacts flow through proteome -> digest -> modify -> design
-> yield. Here we cover: semantic (not textual) round-trips against the checked-in golden specs,
the cross-field validators, unknown-field rejection, and JSON-Schema emission.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from timsim_api.schema import (
    DesignSpec,
    Modification,
    ModsSpec,
    ProteomeSpec,
    SampleDesignerParams,
)

# The golden specs are vendored as test fixtures: this repo is independent, so it cannot reach into a
# sibling flow checkout for them. They are copies of the flow's configs — if the spec format changes there,
# refresh these.
FLOW = Path(__file__).resolve().parent / "golden"


# ── semantic round-trips against the checked-in golden specs ─────────────────────────────────────


@pytest.mark.parametrize(
    "filename, cls",
    [
        ("hye.toml", ProteomeSpec),
        ("design.toml", DesignSpec),
        ("mods.toml", ModsSpec),
    ],
)
def test_golden_semantic_roundtrip(filename, cls):
    """golden -> model -> toml -> model must be value-equal (ordering/whitespace/defaults ignored)."""
    text = (FLOW / filename).read_text()
    m1 = cls.from_toml_str(text)
    m2 = cls.from_toml_str(m1.to_toml_str())
    assert m1 == m2, f"round-trip changed values for {filename}"


def test_golden_parses_to_expected_values():
    """A few load-bearing values, so a silently-wrong mapping is caught, not just self-consistency."""
    design = DesignSpec.from_toml_str((FLOW / "design.toml").read_text())
    assert design.design.reference == "A"
    assert design.design.load_ng == 200
    assert design.design.n_proteins == 1200
    assert design.conditions[1].mix["ECOLI"] == "rest"
    assert design.variance.biological_heterogeneity == 0.5

    mods = ModsSpec.from_toml_str((FLOW / "mods.toml").read_text())
    gg = next(m for m in mods.modifications if m.name == "GG")
    assert gg.blocks_cleavage is True and gg.stage == "protein"


# ── cross-field validators (must mirror the Rust authority's checks) ─────────────────────────────


def test_blocks_cleavage_requires_protein_stage():
    with pytest.raises(ValidationError, match="blocks_cleavage requires stage='protein'"):
        Modification(
            name="X", unimod_id=1, targets="K", occupancy=0.5, mass_delta=1.0,
            composition="H", blocks_cleavage=True, stage="peptide",
        )


def test_residue_mod_requires_targets():
    with pytest.raises(ValidationError, match="needs target residues"):
        Modification(name="X", unimod_id=1, occupancy=0.5, mass_delta=1.0, composition="H")


def test_occupancy_bounds():
    with pytest.raises(ValidationError):
        Modification(
            name="X", unimod_id=1, targets="K", occupancy=1.5, mass_delta=1.0, composition="H"
        )


def test_unique_mod_names():
    m = dict(unimod_id=1, targets="K", occupancy=0.5, mass_delta=1.0, composition="H")
    with pytest.raises(ValidationError, match="names must be unique"):
        ModsSpec(modifications=[Modification(name="d", **m), Modification(name="d", **m)])


def test_mixture_must_sum_or_use_rest():
    from timsim_api.schema import Condition

    with pytest.raises(ValidationError, match="sum to"):
        Condition(name="A", mix={"HUMAN": 0.65, "YEAST": 0.20})  # sums to 0.85, no "rest"
    # with "rest" it is fine
    Condition(name="A", mix={"HUMAN": 0.65, "YEAST": "rest"})


def test_at_most_one_rest():
    from timsim_api.schema import Condition

    with pytest.raises(ValidationError, match="at most one"):
        Condition(name="A", mix={"HUMAN": "rest", "YEAST": "rest"})


def test_reference_must_be_a_condition():
    with pytest.raises(ValidationError, match="not one of the conditions"):
        DesignSpec(
            design={"reference": "Z", "load_ng": 200},
            abundance={"HUMAN": {"source": "lognormal", "sigma": 2.0}},
            conditions=[{"name": "A", "mix": {"HUMAN": 1.0}}],
        )


def test_mix_organism_needs_abundance():
    with pytest.raises(ValidationError, match="no \\[abundance\\] entry"):
        DesignSpec(
            design={"reference": "A", "load_ng": 200},
            abundance={"HUMAN": {"source": "lognormal", "sigma": 2.0}},
            conditions=[{"name": "A", "mix": {"HUMAN": 0.5, "YEAST": "rest"}}],
        )


# ── unknown-field rejection (must be consistent with the Rust parser) ────────────────────────────


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        Modification(
            name="X", unimod_id=1, targets="K", occupancy=0.5, mass_delta=1.0,
            composition="H", typo_field=3,
        )


# ── JSON Schema emission + the whole-slice model ─────────────────────────────────────────────────


def test_sample_params_emits_three_specs():
    params = SampleDesignerParams(
        proteome=ProteomeSpec.from_toml_str((FLOW / "hye.toml").read_text()),
        mods=ModsSpec.from_toml_str((FLOW / "mods.toml").read_text()),
        design=DesignSpec.from_toml_str((FLOW / "design.toml").read_text()),
    )
    specs = params.emit_specs()
    assert set(specs) == {"proteome.toml", "design.toml", "mods.toml"}
    # each emitted spec must re-parse
    ProteomeSpec.from_toml_str(specs["proteome.toml"])
    DesignSpec.from_toml_str(specs["design.toml"])
    ModsSpec.from_toml_str(specs["mods.toml"])


def test_min_length_le_max_length():
    with pytest.raises(ValidationError, match="min_length"):
        SampleDesignerParams(
            proteome=ProteomeSpec(sources=[{"path": "x.fasta"}]),
            mods=ModsSpec(modifications=[
                Modification(name="d", unimod_id=1, targets="K", occupancy=0.5,
                             mass_delta=1.0, composition="H")]),
            design=DesignSpec(
                design={"reference": "A", "load_ng": 200},
                abundance={"HUMAN": {"source": "lognormal", "sigma": 2.0}},
                conditions=[{"name": "A", "mix": {"HUMAN": 1.0}}],
            ),
            min_length=50, max_length=7,
        )


def test_json_schema_generates():
    schema = SampleDesignerParams.model_json_schema()
    assert schema["type"] == "object"
    assert "proteome" in schema["properties"]
    assert "design" in schema["properties"]
    assert "mods" in schema["properties"]

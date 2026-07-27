"""The modification spec — mirrors `timsim-cli/src/bin/modify.rs::ModSpec` (emitted as `mods.toml`).

`occupancy` is the fraction of *this site* carrying the mod — not "max N variable mods", which is a
search-engine parameter. See the module docstring in `modify.rs`.
"""

from __future__ import annotations

import tomllib
from typing import Literal

import tomlkit
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Modification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    unimod_id: int = Field(ge=0)
    targets: str = ""
    site: Literal["residue", "n_term", "c_term"] = "residue"
    occupancy: float = Field(ge=0.0, le=1.0)
    mass_delta: float
    # Elemental formula, e.g. "HO3P". The Rust tool cross-checks it against mass_delta (delta_mass
    # within 1e-4 Da) — that chemistry check stays in the Rust authority; we do not reimplement it.
    composition: str
    blocks_cleavage: bool = False
    stage: Literal["protein", "peptide"] = "protein"

    @model_validator(mode="after")
    def _check(self) -> Modification:
        if self.site == "residue" and not self.targets:
            raise ValueError(
                f"modification {self.name!r}: a residue modification needs target residues"
            )
        # A mod that forms AFTER digestion cannot have blocked the protease.
        if self.blocks_cleavage and self.stage != "protein":
            raise ValueError(
                f"modification {self.name!r}: blocks_cleavage requires stage='protein'"
            )
        return self


class ModsSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # An empty spec would silently produce one unmodified modform per peptide (looks like success),
    # so the Rust tool bails — require at least one here too.
    modifications: list[Modification] = Field(min_length=1)

    @classmethod
    def from_toml_str(cls, text: str) -> ModsSpec:
        # Rust names the array `modification` (`#[serde(rename = "modification")]`).
        raw = tomllib.loads(text)
        return cls(modifications=raw.get("modification", []))

    @model_validator(mode="after")
    def _unique_names(self) -> ModsSpec:
        names = [m.name for m in self.modifications]
        if len(names) != len(set(names)):
            # modform_id keys on the name, so duplicates would silently merge two mods into one id.
            raise ValueError(f"modification names must be unique, got {names}")
        return self

    def to_toml_str(self) -> str:
        doc = tomlkit.document()
        arr = tomlkit.aot()
        for m in self.modifications:
            t = tomlkit.table()
            t["name"] = m.name
            t["unimod_id"] = m.unimod_id
            t["targets"] = m.targets
            t["site"] = m.site
            t["occupancy"] = m.occupancy
            t["mass_delta"] = m.mass_delta
            t["composition"] = m.composition
            t["blocks_cleavage"] = m.blocks_cleavage
            t["stage"] = m.stage
            arr.append(t)
        doc["modification"] = arr
        return tomlkit.dumps(doc)

"""The proteome spec — mirrors `timsim-cli/src/spec.rs::ProteomeSpec` (emitted as `hye.toml`)."""

from __future__ import annotations

import tomllib

import tomlkit
from pydantic import BaseModel, ConfigDict, Field


class ProteomeSource(BaseModel):
    # `extra="forbid"` so an unknown/renamed field is rejected here exactly as the Rust parser
    # would reject it — the whole point is that the three surfaces agree.
    model_config = ConfigDict(extra="forbid")

    path: str
    # Organism is a *declared* column, never a substring match on the FASTA header. Optional in the
    # Rust spec (`Option<String>`), so `None` means "omit the key".
    organism: str | None = None
    is_contaminant: bool = False


class ProteomeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # `load_proteome_spec` bails on an empty `[[source]]` list, so require at least one.
    sources: list[ProteomeSource] = Field(min_length=1)

    @classmethod
    def from_toml_str(cls, text: str) -> ProteomeSpec:
        # Rust names the array `source` (`#[serde(rename = "source")]`).
        raw = tomllib.loads(text)
        return cls(sources=raw.get("source", []))

    def to_toml_str(self) -> str:
        doc = tomlkit.document()
        arr = tomlkit.aot()
        for src in self.sources:
            t = tomlkit.table()
            t["path"] = src.path
            if src.organism is not None:
                t["organism"] = src.organism
            if src.is_contaminant:
                t["is_contaminant"] = src.is_contaminant
            arr.append(t)
        doc["source"] = arr
        return tomlkit.dumps(doc)

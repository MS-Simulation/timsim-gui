"""`SampleDesignerParams` — the whole slice in one model.

Wraps the three tool specs plus the digest / modify / yield knobs the sample-designer flow exposes.
Emits the three TOML files the trimmed necroflow pipeline consumes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .design import DesignSpec
from .mods import ModsSpec
from .proteome import ProteomeSpec

# Bump on any breaking change to the parameter surface; the migration policy lives alongside.
SCHEMA_VERSION = "1.0"


class SampleDesignerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION

    proteome: ProteomeSpec
    mods: ModsSpec
    design: DesignSpec

    # ── digest knobs (timsim-digest CLI defaults) ──
    enzyme: str = "trypsin"
    max_missed_cleavages: int = Field(default=2, ge=0)
    min_length: int = Field(default=7, ge=1)
    max_length: int = Field(default=30, ge=1)

    # ── modify / yield knobs ──
    modify_floor: float = Field(default=1e-3, gt=0.0, le=1.0)
    digestion_efficiency: float = Field(default=0.90, gt=0.0, le=1.0)

    def emit_specs(self) -> dict[str, str]:
        """Return the three spec files as `{filename: toml_text}`, ready to write into a workspace."""
        return {
            "proteome.toml": self.proteome.to_toml_str(),
            "design.toml": self.design.to_toml_str(),
            "mods.toml": self.mods.to_toml_str(),
        }

    def model_post_init(self, _ctx) -> None:
        if self.min_length > self.max_length:
            raise ValueError(
                f"min_length ({self.min_length}) must be <= max_length ({self.max_length})"
            )

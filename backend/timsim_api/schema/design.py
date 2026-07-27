"""The design spec — mirrors `timsim-cli/src/spec.rs::DesignFile` (emitted as `design.toml`).

The mixture is the spec; `true_log2fc` is *derived* by `timsim-design`, never typed here.
"""

from __future__ import annotations

import tomllib
from typing import Annotated, Literal, Union

import tomlkit
from pydantic import BaseModel, ConfigDict, Field, model_validator

# ── abundance sources (Rust: `#[serde(tag = "source", rename_all = "lowercase")]`) ──────────────


class Lognormal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["lognormal"] = "lognormal"
    # Rust bails unless sigma is finite and >= 0.
    sigma: float = Field(ge=0.0)


class Hockeystick(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["hockeystick"] = "hockeystick"
    # Both have Rust serde defaults (decay=0.06, tail=1e-4); `None` means "omit, let Rust default".
    # When set, Rust requires decay > 0 and tail >= 0.
    decay: float | None = Field(default=None, gt=0.0)
    tail: float | None = Field(default=None, ge=0.0)


class Table(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["table"] = "table"
    path: str


AbundanceSource = Annotated[
    Union[Lognormal, Hockeystick, Table], Field(discriminator="source")
]

# ── regulation (Rust: `#[serde(untagged)]`) ─────────────────────────────────────────────────────


class RegulateExplicit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proteins: list[str]
    log2fc: float


class RegulateGenerative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fraction: float
    log2fc_sd: float


Regulate = Union[RegulateExplicit, RegulateGenerative]

MixShare = Union[float, Literal["rest"]]

# ── the pieces ──────────────────────────────────────────────────────────────────────────────────


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    # organism -> mass fraction, or the literal "rest" (fills to 1.0 so a mixture cannot be
    # mistyped into not summing).
    mix: dict[str, MixShare] = Field(min_length=1)
    replicates: int = Field(default=1, ge=1)
    technical_replicates: int = Field(default=1, ge=1)
    regulate: Regulate | None = None

    @model_validator(mode="after")
    def _check_mix(self) -> Condition:
        rests = [k for k, v in self.mix.items() if v == "rest"]
        if len(rests) > 1:
            raise ValueError(
                f'condition {self.name!r}: at most one organism may be "rest", got {rests}'
            )
        fracs = [v for v in self.mix.values() if not isinstance(v, str)]
        for v in fracs:
            if not (0.0 <= v <= 1.0):
                raise ValueError(
                    f"condition {self.name!r}: mass fractions must be in [0, 1], got {v}"
                )
        if not rests:
            total = sum(fracs)
            # Without a "rest" the fractions must sum to ~1.0 (the Rust design stage normalises but a
            # silently-not-summing mixture is almost always a typo).
            if abs(total - 1.0) > 1e-6:
                raise ValueError(
                    f"condition {self.name!r}: mass fractions sum to {total:.6f}, not 1.0; "
                    'add a "rest" organism or fix the fractions'
                )
        return self


class Variance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    biological: float = 0.0
    biological_heterogeneity: float = 0.0
    technical: float = 0.0


class DesignHeader(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: str
    load_ng: float = Field(gt=0.0)
    # Excluded proteins keep their place with amount 0; there is deliberately no peptide-count knob.
    n_proteins: int | None = Field(default=None, ge=1)
    seed: int = 42


class DesignSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design: DesignHeader
    abundance: dict[str, AbundanceSource] = Field(min_length=1)
    conditions: list[Condition] = Field(min_length=1)
    variance: Variance = Field(default_factory=Variance)

    @classmethod
    def from_toml_str(cls, text: str) -> DesignSpec:
        # Rust names the condition array `condition` (`#[serde(rename = "condition")]`) and the
        # top-level keys design/abundance/variance.
        raw = tomllib.loads(text)
        return cls(
            design=raw["design"],
            abundance=raw.get("abundance", {}),
            conditions=raw.get("condition", []),
            variance=raw.get("variance", {}),
        )

    @model_validator(mode="after")
    def _check_refs(self) -> DesignSpec:
        names = [c.name for c in self.conditions]
        if self.design.reference not in names:
            raise ValueError(
                f"design.reference {self.design.reference!r} is not one of the conditions {names}"
            )
        if len(names) != len(set(names)):
            raise ValueError(f"condition names must be unique, got {names}")
        # Every organism named in any mix must have an abundance profile.
        for c in self.conditions:
            missing = [org for org in c.mix if org not in self.abundance]
            if missing:
                raise ValueError(
                    f"condition {c.name!r}: organisms {missing} appear in mix but have no "
                    f"[abundance] entry"
                )
        return self

    def to_toml_str(self) -> str:
        doc = tomlkit.document()

        header = tomlkit.table()
        header["reference"] = self.design.reference
        header["load_ng"] = self.design.load_ng
        if self.design.n_proteins is not None:
            header["n_proteins"] = self.design.n_proteins
        header["seed"] = self.design.seed
        doc["design"] = header

        ab = tomlkit.table()
        for org, prof in self.abundance.items():
            it = tomlkit.inline_table()
            it["source"] = prof.source
            if isinstance(prof, Lognormal):
                it["sigma"] = prof.sigma
            elif isinstance(prof, Hockeystick):
                if prof.decay is not None:
                    it["decay"] = prof.decay
                if prof.tail is not None:
                    it["tail"] = prof.tail
            elif isinstance(prof, Table):
                it["path"] = prof.path
            ab[org] = it
        doc["abundance"] = ab

        conds = tomlkit.aot()
        for c in self.conditions:
            t = tomlkit.table()
            t["name"] = c.name
            mix = tomlkit.inline_table()
            for org, share in c.mix.items():
                mix[org] = share
            t["mix"] = mix
            t["replicates"] = c.replicates
            t["technical_replicates"] = c.technical_replicates
            if c.regulate is not None:
                reg = tomlkit.inline_table()
                if isinstance(c.regulate, RegulateExplicit):
                    reg["proteins"] = c.regulate.proteins
                    reg["log2fc"] = c.regulate.log2fc
                else:
                    reg["fraction"] = c.regulate.fraction
                    reg["log2fc_sd"] = c.regulate.log2fc_sd
                t["regulate"] = reg
            conds.append(t)
        doc["condition"] = conds

        var = tomlkit.table()
        var["biological"] = self.variance.biological
        var["biological_heterogeneity"] = self.variance.biological_heterogeneity
        var["technical"] = self.variance.technical
        doc["variance"] = var

        return tomlkit.dumps(doc)

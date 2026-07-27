"""The parameter schema for the Sample & Experiment Designer slice.

This is the GUI's typed boundary. It is a *second*, hand-maintained schema — the executable
semantic authority for what the tools accept is the Rust `timsim-cli/src/spec.rs` and
`bin/modify.rs::ModSpec`. The discipline here is: one Pydantic definition, two emitters
(`.to_toml_str()` for the tools, `model_json_schema()` for the form), pinned to the Rust authority
by the test suite in `backend/tests/`.

The Rust `timsim-schema` crate owns *artifact* (Parquet) schemas — a different thing. There is no
parameter schema exported from Rust today, which is why this boundary lives in Python for this slice.
"""

from .proteome import ProteomeSource, ProteomeSpec
from .design import (
    AbundanceSource,
    Condition,
    DesignHeader,
    DesignSpec,
    Hockeystick,
    Lognormal,
    RegulateExplicit,
    RegulateGenerative,
    Table,
    Variance,
)
from .mods import Modification, ModsSpec
from .sample import SampleDesignerParams, SCHEMA_VERSION

__all__ = [
    "ProteomeSource",
    "ProteomeSpec",
    "AbundanceSource",
    "Condition",
    "DesignHeader",
    "DesignSpec",
    "Hockeystick",
    "Lognormal",
    "RegulateExplicit",
    "RegulateGenerative",
    "Table",
    "Variance",
    "Modification",
    "ModsSpec",
    "SampleDesignerParams",
    "SCHEMA_VERSION",
]

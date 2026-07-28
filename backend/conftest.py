"""Put `backend/` on sys.path so tests can `import timsim_api` without PYTHONPATH.

Also owns the one honest answer to "where are the Rust stage binaries?", shared by the tests that
need them (`test_api.py`, `test_pipeline_e2e.py`).
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# The stage binaries an end-to-end run shells out to.
STAGE_BINARIES = (
    "timsim-proteome",
    "timsim-digest",
    "timsim-modify",
    "timsim-design",
    "timsim-yield",
)


def _is_runnable(path: Path) -> bool:
    """True only for a real, executable file — not a directory or a non-executable of that name."""
    try:
        st = path.stat()  # follows symlinks; raises if dangling/absent
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode) and bool(st.st_mode & stat.S_IXUSR)


def timsim_bin_skip_reason() -> str | None:
    """None if the real binaries are usable, else a reason naming exactly what is wrong.

    There is deliberately **no fallback path**. This repo is a self-contained front-end and vendors
    no binaries; the old default (`<repo>/rustims/target/release`) pointed at a directory that no
    longer exists, so with TIMSIM_BIN unset every end-to-end test skipped silently and the suite
    reported a false green. An unset TIMSIM_BIN is now an explicit, named skip.
    """
    raw = os.environ.get("TIMSIM_BIN", "").strip()
    if not raw:
        return (
            "TIMSIM_BIN is not set, so the END-TO-END TESTS DID NOT RUN. This repo vendors no Rust "
            "binaries and has no fallback path. Set it to a timsim-cli checkout's target/release, "
            "e.g. TIMSIM_BIN=/path/to/timsim-cli/target/release"
        )
    bin_dir = Path(raw)
    if not bin_dir.is_dir():
        return f"END-TO-END TESTS DID NOT RUN: TIMSIM_BIN={raw} is not a directory"
    missing = [b for b in STAGE_BINARIES if not _is_runnable(bin_dir / b)]
    if missing:
        return (
            f"END-TO-END TESTS DID NOT RUN: TIMSIM_BIN={raw} has no runnable binary for "
            f"{', '.join(missing)} (each must be an executable file; `cargo build --release`)"
        )
    return None


# A bare skip reason is invisible under plain `pytest -q` unless someone passes `-rs`, and a
# silently skipped e2e suite is exactly the false green being fixed here. These two reporting hooks
# put the verdict in the header *and* the final summary, at any verbosity. (A plain `print` does not
# work: pytest captures stdout/stderr from before conftest import and discards it on a green run.)


def pytest_report_header(config) -> str:
    reason = timsim_bin_skip_reason()
    if reason is None:
        return f"timsim e2e: ENABLED (TIMSIM_BIN={os.environ.get('TIMSIM_BIN', '').strip()})"
    return f"timsim e2e: DISABLED -- {reason}"


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    reason = timsim_bin_skip_reason()
    if reason is None:
        return
    terminalreporter.write_sep("=", "END-TO-END TESTS SKIPPED", red=True, bold=True)
    terminalreporter.write_line(reason)
    terminalreporter.write_line(
        "Everything that passed above is unit-level only; the Rust pipeline was never invoked."
    )

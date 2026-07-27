"""The cancellation guarantee (Codex #2): killing a run kills the whole process group, no orphans.

The real sample-designer pipeline finishes in well under a second, so cancellation can't be observed
through it. Here we drive `make_node_runner` directly on a node whose command spawns a background
child, cancel it, and assert (a) the runner unwinds fast (not after the 30s sleep) and (b) the entire
process group is gone — which is the orphaned-children failure mode `start_new_session=True` prevents.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from timsim_api import runner
from timsim_api.runs import Run


class _FakeNodeType:
    __name__ = "Slow"


class _FakeNode:
    pipeline_label = "slow"
    node_type = _FakeNodeType

    def __init__(self, out: Path):
        self.path = out


def test_cancel_kills_process_group(tmp_path, monkeypatch):
    # A command that spawns a background child and then waits — the classic orphan risk.
    monkeypatch.setattr(
        runner, "resolve_command", lambda node: "sleep 30 & echo started; wait"
    )

    run = Run("test-run", "proj", tmp_path / "run")
    node = _FakeNode(tmp_path / "art" / "out")
    log_path = tmp_path / "job.log"
    node_runner = runner.make_node_runner(run)

    raised: list[BaseException] = []

    def target():
        try:
            node_runner(node, log_path)
        except BaseException as e:  # noqa: BLE001
            raised.append(e)

    t = threading.Thread(target=target)
    t.start()

    # Wait until the process is live and its group is known.
    deadline = time.time() + 5
    while time.time() < deadline and not run.procs():
        time.sleep(0.02)
    procs = run.procs()
    assert procs, "process never started"
    pgid = os.getpgid(procs[0].pid)

    runner.cancel(run, grace=1.0)

    t.join(timeout=5)
    assert not t.is_alive(), "runner did not unwind after cancel (waited on the 30s sleep?)"
    assert raised and isinstance(raised[0], RuntimeError), raised

    # The whole process group must be gone — not just the shell, but the `sleep 30` child too.
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            os.killpg(pgid, 0)  # signal 0 = existence check
            time.sleep(0.05)
        except ProcessLookupError:
            break
    else:
        raise AssertionError(f"process group {pgid} still alive — child was orphaned")

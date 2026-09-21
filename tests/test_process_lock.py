"""Exercise supervisor death with real processes, without touching Kubernetes."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from cluster_guard import cluster_lock
from filelock import Timeout


@pytest.mark.skipif(os.name != "posix", reason="Production runner uses POSIX flock")
def test_killed_supervisor_cannot_release_a_live_evaluation_child(tmp_path, monkeypatch):
    monkeypatch.setenv("SRE_CLUSTER_LOCK", str(tmp_path / "cluster.lock"))
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1] / "scripts"))
    supervisor = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import subprocess,sys,time; "
            "from cluster_guard import cluster_lock,cluster_subprocess_options; "
            "lock=cluster_lock(); lock.__enter__(); "
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'], "
            "stdout=subprocess.DEVNULL, **cluster_subprocess_options()); "
            "print(child.pid,flush=True); time.sleep(30)",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    child_pid = None
    try:
        child_pid = int(supervisor.stdout.readline())
        supervisor.kill()
        supervisor.wait(timeout=5)
        with pytest.raises(Timeout):
            with cluster_lock():
                pass
        os.kill(child_pid, signal.SIGTERM)
        child_pid = None
        for _ in range(100):
            try:
                with cluster_lock():
                    return
            except Timeout:
                time.sleep(0.02)
        pytest.fail("Child exit did not release the cluster lock")
    finally:
        if child_pid is not None:
            os.kill(child_pid, signal.SIGKILL)
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.wait(timeout=5)

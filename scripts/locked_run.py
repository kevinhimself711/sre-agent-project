"""Apply the campaign's cluster lock and recovery guard to standalone runs."""

import os
import subprocess
import sys

from cluster_guard import cluster_lock, health_snapshot

if __name__ == "__main__":
    with cluster_lock():
        health_snapshot()
        result = subprocess.run(
            ["bash", *sys.argv[1:]], env={**os.environ, "SRE_CLUSTER_LOCK_HELD": "1"}
        )
        health_snapshot()
        raise SystemExit(result.returncode)

"""One host-wide lock and independent readiness checks for the dedicated cluster."""

import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock
from project_paths import kubeconfig

BUSINESS_NAMESPACES = {"hotel-reservation", "social-network", "astronomy-shop", "observe"}


@contextmanager
def cluster_lock():
    path = Path(
        os.environ.get(
            "SRE_CLUSTER_LOCK", str(Path.home() / ".local/state/sre-agent/sre-agent-dev.lock")
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(path, timeout=0)
    with lock:
        previous = os.environ.get("SRE_CLUSTER_LOCK_FD")
        if os.name == "posix":
            # filelock is pinned in uv.lock. Its flock descriptor must outlive a
            # killed supervisor whenever an evaluation child is still running.
            os.environ["SRE_CLUSTER_LOCK_FD"] = str(lock._context.lock_file_fd)
        try:
            yield lock
        finally:
            if previous is None:
                os.environ.pop("SRE_CLUSTER_LOCK_FD", None)
            else:
                os.environ["SRE_CLUSTER_LOCK_FD"] = previous


def cluster_subprocess_options():
    descriptor = os.environ.get("SRE_CLUSTER_LOCK_FD")
    if os.name != "posix" or descriptor is None:
        return {}
    fd = int(descriptor)
    os.fstat(fd)
    return {"pass_fds": (fd,)}


def health_snapshot():
    k = ["kubectl", "--kubeconfig", str(kubeconfig())]
    context = subprocess.check_output(
        [*k, "config", "current-context"], text=True, timeout=20
    ).strip()
    if context != "kind-sre-agent-dev":
        raise RuntimeError("Refusing non-project Kubernetes context")
    nodes = json.loads(subprocess.check_output([*k, "get", "nodes", "-o", "json"], timeout=30))[
        "items"
    ]
    namespaces = json.loads(
        subprocess.check_output([*k, "get", "namespaces", "-o", "json"], timeout=30)
    )["items"]
    policies = json.loads(
        subprocess.check_output([*k, "get", "networkpolicy", "-A", "-o", "json"], timeout=30)
    )["items"]
    ready = len(nodes) == 4 and all(
        any(c["type"] == "Ready" and c["status"] == "True" for c in n["status"]["conditions"])
        for n in nodes
    )
    residual = sorted(
        n["metadata"]["name"] for n in namespaces if n["metadata"]["name"] in BUSINESS_NAMESPACES
    )
    bad_policies = [
        p["metadata"]["name"] for p in policies if p["metadata"]["namespace"] in BUSINESS_NAMESPACES
    ]
    snapshot = {
        "context": context,
        "four_nodes_ready": ready,
        "residual_namespaces": residual,
        "residual_policies": bad_policies,
    }
    if not ready or residual or bad_policies:
        raise RuntimeError(f"Cluster is not clean: {snapshot}")
    return snapshot


if __name__ == "__main__":
    print(json.dumps(health_snapshot()))

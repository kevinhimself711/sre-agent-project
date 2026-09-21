"""Bounded image preloading for our KIND cluster on a network with blocked registries."""

import json
import subprocess
import sys
import time

from project_paths import kubeconfig, project_root

root = project_root()
k = ["kubectl", "--kubeconfig", str(kubeconfig())]
assert (
    subprocess.check_output([*k, "config", "current-context"], text=True).strip()
    == "kind-sre-agent-dev"
)
deadline = time.monotonic() + 1800
seen = set()
last_work = time.monotonic()
while time.monotonic() < deadline:
    pods = json.loads(subprocess.check_output([*k, "get", "pods", "-A", "-o", "json"]))["items"]
    images = set()
    for pod in pods:
        for key in ("containerStatuses", "initContainerStatuses"):
            for status in pod.get("status", {}).get(key, []):
                if "waiting" in status.get("state", {}):
                    images.add(status["image"])
        if pod.get("status", {}).get("phase") == "Pending":
            for key in ("containers", "initContainers"):
                images.update(x["image"] for x in pod["spec"].get(key, []))
    # GHCR is reachable directly from these nodes. Let kubelet pull its pinned
    # multi-platform images; preload only registries blocked on this network.
    images = {image for image in images - seen if not image.startswith("ghcr.io/")}
    if images:
        print("Preloading", sorted(images), flush=True)
        result = subprocess.run(
            [sys.executable, str(root / "scripts/preload_images.py"), *sorted(images)],
            timeout=900,
        )
        if result.returncode:
            raise SystemExit(result.returncode)
        seen.update(images)
        last_work = time.monotonic()
    elif time.monotonic() - last_work > 180:
        break
    time.sleep(10)

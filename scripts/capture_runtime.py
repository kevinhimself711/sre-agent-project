"""Record observed images/charts and independent reset checks for our cluster."""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--after-reset", action="store_true")
    args = parser.parse_args()
    root = Path.home() / "sre-agent-project"
    kubectl = [
        str(root / "bin/kubectl"),
        "--kubeconfig",
        str(root / "configs/kubeconfig"),
    ]

    def get(resource):
        return json.loads(
            subprocess.check_output([*kubectl, "get", resource, "-A", "-o", "json"])
        )["items"]

    assert (
        subprocess.check_output(
            [*kubectl, "config", "current-context"], text=True
        ).strip()
        == "kind-sre-agent-dev"
    )
    pods = get("pods")
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "after_reset": args.after_reset,
        "namespaces": [n["metadata"]["name"] for n in get("namespaces")],
        "networkpolicies": [
            p["metadata"]["namespace"] + "/" + p["metadata"]["name"]
            for p in get("networkpolicies")
        ],
        "helm": json.loads(
            subprocess.check_output(["helm", "list", "-A", "-o", "json"])
        ),
        "pods": [
            {
                "namespace": p["metadata"]["namespace"],
                "name": p["metadata"]["name"],
                "uid": p["metadata"]["uid"],
                "node": p["spec"].get("nodeName"),
                "images": [
                    {
                        k: s.get(k)
                        for k in ("name", "image", "imageID", "ready", "restartCount")
                    }
                    for s in p.get("status", {}).get("containerStatuses", [])
                ],
            }
            for p in pods
        ],
        "docker_containers": subprocess.check_output(
            ["docker", "ps", "--format", "{{.Names}}"], text=True
        ).splitlines(),
        "k3s": subprocess.run(
            ["systemctl", "is-active", "k3s"], capture_output=True, text=True
        ).stdout.strip(),
        "inotify": subprocess.check_output(
            ["sysctl", "fs.inotify.max_user_instances", "fs.inotify.max_user_watches"],
            text=True,
        ),
    }
    if args.after_reset:
        assert not set(data["namespaces"]) & {
            "hotel-reservation",
            "social-network",
            "observe",
        }, "Workload namespaces remain"
        assert not data["networkpolicies"], "NetworkPolicy remains"
        assert "fw-coexistence" in data["docker_containers"] and data["k3s"] == "active"
        assert all(
            p["images"] and all(i["ready"] for i in p["images"]) for p in data["pods"]
        ), "Pods not ready"
    name = "runtime-after-reset.json" if args.after_reset else "runtime-deployed.json"
    (root / "artifacts" / name).write_text(json.dumps(data, indent=2) + "\n")
    with (root / "artifacts/mcp-server.log").open("w") as handle:
        subprocess.run(
            [*kubectl, "logs", "-n", "sregym", "deployment/mcp-server"],
            stdout=handle,
            check=True,
        )
    print(name)


if __name__ == "__main__":
    main()

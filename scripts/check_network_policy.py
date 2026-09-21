"""Verify traffic is allowed, then denied, then restored in an isolated namespace."""

import json
import subprocess
import time

NS = "sre-network-probe"


def k(*args, check=True, data=None):
    return subprocess.run(
        ["kubectl", *args], input=data, text=True, capture_output=True, check=check
    )


def apply(resource):
    k("apply", "-f", "-", data=json.dumps(resource))


def main():
    assert k("config", "current-context").stdout.strip() == "kind-sre-agent-dev"
    if k("get", "namespace", NS, check=False).returncode == 0:
        raise RuntimeError("Probe namespace already exists; inspect before reusing")
    k("create", "namespace", NS)
    try:
        for name, image, command in [
            ("server", "nginx:alpine", None),
            ("client", "busybox:latest", ["sleep", "600"]),
        ]:
            container = {
                "name": name,
                "image": image,
                "imagePullPolicy": "IfNotPresent",
            }
            if command:
                container["command"] = command
            apply(
                {
                    "apiVersion": "v1",
                    "kind": "Pod",
                    "metadata": {
                        "name": name,
                        "namespace": NS,
                        "labels": {"app": name},
                    },
                    "spec": {"containers": [container]},
                }
            )
        k("wait", "-n", NS, "--for=condition=Ready", "pod", "--all", "--timeout=90s")
        ip = k(
            "get", "pod", "server", "-n", NS, "-o", "jsonpath={.status.podIP}"
        ).stdout

        def reachable():
            return (
                k(
                    "exec",
                    "-n",
                    NS,
                    "client",
                    "--",
                    "wget",
                    "-q",
                    "-T",
                    "2",
                    "-O",
                    "/dev/null",
                    f"http://{ip}",
                    check=False,
                ).returncode
                == 0
            )

        deadline = time.monotonic() + 30
        while not reachable() and time.monotonic() < deadline:
            time.sleep(1)
        assert reachable(), "Baseline connectivity failed"
        apply(
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {"name": "deny", "namespace": NS},
                "spec": {
                    "podSelector": {"matchLabels": {"app": "server"}},
                    "policyTypes": ["Ingress"],
                    "ingress": [],
                },
            }
        )
        deadline = time.monotonic() + 20
        while reachable() and time.monotonic() < deadline:
            time.sleep(1)
        assert not reachable(), "NetworkPolicy was not enforced"
        k("delete", "networkpolicy", "deny", "-n", NS)
        deadline = time.monotonic() + 20
        while not reachable() and time.monotonic() < deadline:
            time.sleep(1)
        assert reachable(), "Connectivity did not recover"
        print(
            json.dumps(
                {
                    "healthy_before": True,
                    "blocked_during": True,
                    "recovered_after": True,
                }
            )
        )
    finally:
        k("delete", "namespace", NS, "--wait=true", "--timeout=90s")


if __name__ == "__main__":
    main()

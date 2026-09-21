"""Temporarily expose the SSH proxy to two upstream Git-cloning init containers.

Run via remote.py --proxy, after the Social Network deployments exist and before
fault injection. The listener binds only the dedicated KIND bridge gateway.
"""

import ipaddress
import json
import os
import select
import socket
import socketserver
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


def main():
    root = Path.home() / "sre-agent-project"
    k = [str(root / "bin/kubectl"), "--kubeconfig", str(root / "configs/kubeconfig")]
    assert (
        subprocess.check_output([*k, "config", "current-context"], text=True).strip()
        == "kind-sre-agent-dev"
    )
    with urlopen(
        f"http://127.0.0.1:{os.environ.get('API_PORT', '18000')}/status", timeout=10
    ) as response:
        assert json.load(response)["stage"] == "setup", (
            "Do not modify initialization after fault injection"
        )
    proxy = urlparse(os.environ["https_proxy"])
    assert proxy.hostname == "127.0.0.1"
    network = json.loads(subprocess.check_output(["docker", "network", "inspect", "kind"]))[0]
    gateway = next(
        c["Gateway"]
        for c in network["IPAM"]["Config"]
        if ipaddress.ip_address(c["Gateway"]).version == 4
    )
    source_url = "https://github.com/delimitrou/DeathStarBench.git"
    revision = os.environ["SREGYM_SOCIAL_SOURCE_REV"]
    assert len(revision) == 40 and all(c in "0123456789abcdef" for c in revision)

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            with socket.create_connection((proxy.hostname, proxy.port), timeout=15) as upstream:
                while True:
                    readable, _, _ = select.select([self.request, upstream], [], [], 30)
                    if not readable:
                        return
                    for source in readable:
                        data = source.recv(65536)
                        if not data:
                            return
                        (upstream if source is self.request else self.request).sendall(data)

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True

    with Server((gateway, 0), Handler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        address = f"http://{gateway}:{server.server_address[1]}"
        for name in ("media-frontend", "nginx-thrift"):
            deployment = json.loads(
                subprocess.check_output(
                    [
                        *k,
                        "get",
                        "deployment",
                        name,
                        "-n",
                        "social-network",
                        "-o",
                        "json",
                    ]
                )
            )
            init = next(
                c
                for c in deployment["spec"]["template"]["spec"]["initContainers"]
                if c["name"] == "alpine-container"
            )
            assert source_url in init["args"][-1], "Unexpected init command"
            command = init["args"][-1].replace(
                " && ",
                f" && git -C /DeathStarBench fetch --depth 1 origin {revision} && git -C /DeathStarBench checkout --detach {revision} && ",
                1,
            )
            patch = {
                "spec": {
                    "template": {
                        "spec": {
                            "initContainers": [
                                {
                                    "name": init["name"],
                                    "args": ["-c", command],
                                    "env": [
                                        {"name": "HTTPS_PROXY", "value": address},
                                        {"name": "HTTP_PROXY", "value": address},
                                    ],
                                }
                            ]
                        }
                    }
                }
            }
            subprocess.run(
                [
                    *k,
                    "patch",
                    "deployment",
                    name,
                    "-n",
                    "social-network",
                    "--type=strategic",
                    "-p",
                    json.dumps(patch),
                ],
                check=True,
            )
        (root / "artifacts/social-init-proxy.json").write_text(
            json.dumps(
                {
                    "source": source_url,
                    "revision": revision,
                    "deployments": ["media-frontend", "nginx-thrift"],
                    "scope": "init containers only",
                    "proxy": address,
                },
                indent=2,
            )
            + "\n"
        )
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            ready = True
            for name in ("media-frontend", "nginx-thrift"):
                d = json.loads(
                    subprocess.check_output(
                        [
                            *k,
                            "get",
                            "deployment",
                            name,
                            "-n",
                            "social-network",
                            "-o",
                            "json",
                        ]
                    )
                )
                s = d.get("status", {})
                ready &= (
                    s.get("observedGeneration", 0) >= d["metadata"]["generation"]
                    and s.get("updatedReplicas") == 1
                    and s.get("readyReplicas") == 1
                )
            if ready:
                print(
                    "Both init containers finished at recorded source revision; temporary proxy closing.",
                    flush=True,
                )
                server.shutdown()
                return
            time.sleep(3)
        server.shutdown()
        raise TimeoutError("Social Network initialization did not finish within 600 seconds")


if __name__ == "__main__":
    main()

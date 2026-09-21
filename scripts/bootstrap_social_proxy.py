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
import sys
import threading
import time
from urllib.parse import urlparse
from urllib.request import urlopen

from project_paths import project_root


def archive_init_command(command: str, source_url: str, revision: str) -> str:
    """Replace the upstream Git clone with an immutable source archive download."""
    archive_url = "https://codeload.github.com/delimitrou/DeathStarBench/tar.gz/" + revision
    if archive_url in command and command.startswith("wget -q -O /tmp/deathstarbench.tar.gz "):
        return command
    prefixes = (
        f"git clone {source_url} /DeathStarBench && ",
        f"git clone --depth 1 {source_url} /DeathStarBench && ",
    )
    tail = next((command[len(prefix) :] for prefix in prefixes if command.startswith(prefix)), None)
    if tail is None:
        raise ValueError("Unexpected DeathStarBench init command")
    setup = (
        f"wget -q -O /tmp/deathstarbench.tar.gz {archive_url}"
        " && mkdir -p /DeathStarBench"
        " && tar -xzf /tmp/deathstarbench.tar.gz --strip-components=1 -C /DeathStarBench"
    )
    return f"{setup} && {tail}"


def stable_rollout_count(deployments, complete, previous: int) -> int:
    """Require stable current-generation readiness before closing the proxy."""
    return previous + 1 if all(complete(deployment) for deployment in deployments) else 0


def main():
    root = project_root()
    sys.path.insert(0, str(root / "repos/sregym"))
    from sregym.service.rollout import deployment_rollout_complete

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
                        continue
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
            command = archive_init_command(init["args"][-1], source_url, revision)
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
                    "transport": "github-source-archive",
                    "deployments": ["media-frontend", "nginx-thrift"],
                    "scope": "init containers only",
                    "proxy": address,
                },
                indent=2,
            )
            + "\n"
        )
        deadline = time.monotonic() + 600
        stable_polls = 0
        while time.monotonic() < deadline:
            deployments = []
            for name in ("media-frontend", "nginx-thrift"):
                deployments.append(
                    json.loads(
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
                )
            stable_polls = stable_rollout_count(
                deployments, deployment_rollout_complete, stable_polls
            )
            if stable_polls >= 3:
                print(
                    "Both init containers finished at the recorded source revision; "
                    "temporary proxy closing.",
                    flush=True,
                )
                server.shutdown()
                return
            time.sleep(3)
        server.shutdown()
        raise TimeoutError("Social Network initialization did not finish within 600 seconds")


if __name__ == "__main__":
    main()

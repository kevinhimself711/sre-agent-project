"""Bounded setup-only support for the existing image cache and Social Network init."""

import json
import os
import subprocess
import sys
import time
from urllib.request import urlopen

from project_paths import kubeconfig, project_root


def main():
    root = project_root()
    env = os.environ.copy()
    warm = subprocess.Popen([sys.executable, str(root / "scripts/warm_cluster_images.py")], env=env)
    deadline = time.monotonic() + 1800
    social_done = False
    while time.monotonic() < deadline:
        try:
            with urlopen(
                f"http://127.0.0.1:{os.environ.get('API_PORT', '18000')}/status", timeout=3
            ) as response:
                stage = json.load(response)["stage"]
            if stage not in {"setup", "initializing"}:
                if stage in {"diagnosis", "done", "tearing_down"}:
                    break
            elif not social_done and os.environ.get("https_proxy"):
                result = subprocess.run(
                    [
                        "kubectl",
                        "--kubeconfig",
                        str(kubeconfig()),
                        "get",
                        "deployment",
                        "media-frontend",
                        "nginx-thrift",
                        "-n",
                        "social-network",
                        "-o",
                        "json",
                    ],
                    capture_output=True,
                )
                if result.returncode == 0:
                    subprocess.run(
                        [sys.executable, str(root / "scripts/bootstrap_social_proxy.py")],
                        env=env,
                        check=True,
                        timeout=900,
                    )
                    social_done = True
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(3)
    if warm.poll() is None:
        warm.terminate()
        warm.wait(timeout=20)


if __name__ == "__main__":
    main()

"""Write non-secret source/config/runtime provenance before a benchmark launch."""

import hashlib
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

root = Path.home() / "sre-agent-project"
timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
data = {
    "schema_version": 1,
    "timestamp": timestamp,
    "sources": {},
    "configuration": {},
    "case_splits": {
        "network_policy_block": "dev",
        "wrong_service_selector_social_network": "dev",
    },
}
for name in ("holmesgpt", "sregym"):
    repo = root / "repos" / name

    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args])

    changes = {}
    names = set(
        git("diff", "HEAD", "--name-only").decode().splitlines()
        + git("ls-files", "--others", "--exclude-standard").decode().splitlines()
    )
    for rel in sorted(names):
        path = repo / rel
        if path.is_file():
            changes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    data["sources"][name] = {
        "base_commit": git("rev-parse", "HEAD").decode().strip(),
        "changed_files_sha256": changes,
    }
for path in (root / "configs").glob("*"):
    if path.is_file() and path.name != "kubeconfig":
        data["configuration"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
data["agent_image"] = json.loads(
    subprocess.check_output(
        [
            "docker",
            "image",
            "inspect",
            "sre-holmes-agent:baseline",
            "--format",
            "{{json .Id}}",
        ]
    )
)
data["nodes"] = json.loads(
    subprocess.check_output(
        [
            str(root / "bin/kubectl"),
            "--kubeconfig",
            str(root / "configs/kubeconfig"),
            "get",
            "nodes",
            "-o",
            "json",
        ]
    )
)
destination = root / "artifacts" / f"provenance-{timestamp}.json"
destination.write_text(json.dumps(data, indent=2) + "\n")
print(destination)

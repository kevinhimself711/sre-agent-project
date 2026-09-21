"""Archive both forks, including new source files, without staging their contents."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    upstreams = json.loads((ROOT / "configs/upstreams.json").read_text())
    destination = ROOT / "patches"
    destination.mkdir(exist_ok=True)
    manifest = {}
    for name, upstream in upstreams.items():
        repo = ROOT / "repos" / name
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        if head != upstream["commit"]:
            raise RuntimeError(
                f"{name}: base commit changed; update provenance explicitly"
            )
        files = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=repo
        )
        new_files = [x.decode() for x in files.split(b"\0") if x]
        if new_files:
            subprocess.run(
                ["git", "add", "--intent-to-add", "--", *new_files],
                cwd=repo,
                check=True,
            )
        patch = subprocess.check_output(
            ["git", "diff", "--binary", "HEAD", "--"], cwd=repo
        )
        (destination / f"{name}.patch").write_bytes(patch)
        with tempfile.TemporaryDirectory(prefix="sre-patch-check-") as temporary:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(temporary) / "index")}
            subprocess.run(["git", "read-tree", head], cwd=repo, env=env, check=True)
            subprocess.run(
                [
                    "git",
                    "apply",
                    "--cached",
                    "--check",
                    str(destination / f"{name}.patch"),
                ],
                cwd=repo,
                env=env,
                check=True,
            )
        manifest[name] = {
            "base_commit": head,
            "patch_sha256": hashlib.sha256(patch).hexdigest(),
        }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Saved reproducible patches for both forks, including new files.")


if __name__ == "__main__":
    main()

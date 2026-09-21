"""Check archived patch integrity and, optionally, local source completeness."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(root=ROOT, worktree=False):
    upstreams = json.loads((root / "configs/upstreams.json").read_text())
    manifest = json.loads((root / "patches/manifest.json").read_text())
    if set(upstreams) != set(manifest):
        raise ValueError("Patch manifest does not cover exactly the pinned upstreams")
    for name, upstream in upstreams.items():
        patch = root / "patches" / f"{name}.patch"
        metadata = manifest[name]
        if metadata["base_commit"] != upstream["commit"]:
            raise ValueError(f"{name}: inconsistent base commit")
        if hashlib.sha256(patch.read_bytes()).hexdigest() != metadata["patch_sha256"]:
            raise ValueError(f"{name}: patch checksum mismatch")
        if worktree:
            repo = root / "repos" / name
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo).decode().strip()
            if head != upstream["commit"]:
                raise ValueError(f"{name}: checkout is not at the pinned base")
            with tempfile.TemporaryDirectory(prefix="sre-verify-") as temporary:
                env = {**os.environ, "GIT_INDEX_FILE": str(Path(temporary) / "index")}
                subprocess.run(["git", "read-tree", head], cwd=repo, env=env, check=True)
                subprocess.run(
                    ["git", "apply", "--cached", "--check", str(patch)],
                    cwd=repo,
                    env=env,
                    check=True,
                )
                subprocess.run(["git", "add", "-A", "--", "."], cwd=repo, env=env, check=True)
                actual = subprocess.check_output(
                    ["git", "diff", "--cached", "--binary", "HEAD", "--"], cwd=repo, env=env
                )
                if actual != patch.read_bytes():
                    raise ValueError(
                        f"{name}: source differs from archived patch; run save_patches.py"
                    )
        print(f"{name}: patch verified" + (" against current source" if worktree else ""))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--worktree", action="store_true")
    args = parser.parse_args()
    verify(worktree=args.worktree)


if __name__ == "__main__":
    main()

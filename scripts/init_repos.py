"""Clone exact upstream revisions and apply archived implementation patches."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args, check=True):
    return subprocess.run(["git", *args], cwd=repo, check=check)


def main():
    repos = ROOT / "repos"
    repos.mkdir(exist_ok=True)
    for name, info in json.loads((ROOT / "configs/upstreams.json").read_text()).items():
        repo = repos / name
        if repo.exists():
            raise RuntimeError(
                f"{repo} already exists; leave the existing checkout untouched"
            )
        git(ROOT, "clone", info["url"], str(repo))
        git(repo, "checkout", "-b", info["branch"], info["commit"])
        git(repo, "apply", "--check", str(ROOT / "patches" / f"{name}.patch"))
        git(repo, "apply", str(ROOT / "patches" / f"{name}.patch"))
        if name == "sregym":
            git(repo, "submodule", "update", "--init")


if __name__ == "__main__":
    main()

"""Clone exact upstream revisions and apply archived implementation patches."""

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args, check=True):
    return subprocess.run(["git", *args], cwd=repo, check=check)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--only", choices=("holmesgpt", "sregym"))
    parser.add_argument("--skip-applications", action="store_true")
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()
    from verify_patches import verify

    verify()
    repos = ROOT / "repos"
    repos.mkdir(exist_ok=True)
    for name, info in json.loads((ROOT / "configs/upstreams.json").read_text()).items():
        if args.only and name != args.only:
            continue
        repo = repos / name
        if repo.exists():
            raise RuntimeError(f"{repo} already exists; leave the existing checkout untouched")
        source = str(args.cache / name) if args.cache else info["url"]
        git(ROOT, "clone", source, str(repo))
        # This is a newly created clone. A local cache can already have this branch.
        git(repo, "checkout", "-B", info["branch"], info["commit"])
        git(repo, "apply", "--check", str(ROOT / "patches" / f"{name}.patch"))
        git(repo, "apply", str(ROOT / "patches" / f"{name}.patch"))
        if name == "sregym" and not args.skip_applications:
            git(repo, "submodule", "update", "--init")


if __name__ == "__main__":
    main()

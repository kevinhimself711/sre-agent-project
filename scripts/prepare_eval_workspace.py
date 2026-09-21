"""Reconstruct an isolated, persistent evaluation checkout for an exact project SHA."""

import hashlib
import os
import subprocess
from pathlib import Path


def main():
    source = Path(__file__).resolve().parents[1]
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    destination = Path.home() / "sre-agent-eval/workspaces" / sha
    cache = Path.home() / "sre-agent-project"
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--local", "--no-hardlinks", str(source), str(destination)], check=True
        )
        subprocess.run(["git", "checkout", "--detach", sha], cwd=destination, check=True)
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=destination).strip():
        raise RuntimeError("Evaluation checkout has uncommitted project changes")
    env = {**os.environ, "SRE_PROJECT_ROOT": str(destination)}
    subprocess.run(["uv", "sync", "--frozen", "--project", str(destination)], check=True)
    for name in ("holmesgpt", "sregym"):
        target = destination / "repos" / name
        if not target.exists():
            subprocess.run(
                [
                    str(destination / ".venv/bin/python"),
                    str(destination / "scripts/init_repos.py"),
                    "--only",
                    name,
                    "--skip-applications",
                    "--cache",
                    str(cache / "repos"),
                ],
                check=True,
            )
        lockfile = "poetry.lock" if name == "holmesgpt" else "uv.lock"
        old = cache / "repos" / name
        if (
            hashlib.sha256((old / lockfile).read_bytes()).digest()
            != hashlib.sha256((target / lockfile).read_bytes()).digest()
        ):
            raise RuntimeError(
                "Dependency lock changed; install a new isolated upstream environment"
            )
        if not (target / ".venv").exists():
            (target / ".venv").symlink_to(old / ".venv", target_is_directory=True)
        if name == "sregym" and not (target / "SREGym-applications/.git").exists():
            subprocess.run(
                [
                    "git",
                    "submodule",
                    "update",
                    "--init",
                    "--reference",
                    str(old / "SREGym-applications"),
                ],
                cwd=target,
                check=True,
            )
    for directory in ("artifacts", "cache"):
        (destination / directory).mkdir(exist_ok=True)
    for directory in ("bin", "tools-venv"):
        if not (destination / directory).exists():
            (destination / directory).symlink_to(cache / directory, target_is_directory=True)
    kubeconfig = destination / "configs/kubeconfig"
    if not kubeconfig.exists():
        kubeconfig.symlink_to(cache / "configs/kubeconfig")
    subprocess.run(
        [
            str(destination / ".venv/bin/python"),
            str(destination / "scripts/verify_patches.py"),
            "--worktree",
        ],
        env=env,
        check=True,
    )
    if os.environ.get("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a") as output:
            output.write(f"SRE_PROJECT_ROOT={destination}\n")
            output.write(f"SRE_AGENT_IMAGE=sre-holmes-agent:{sha[:12]}\n")
    print(destination)


if __name__ == "__main__":
    main()

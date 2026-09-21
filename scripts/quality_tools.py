"""Run pinned, checksum-verified CLI tools against tracked project files only."""

import argparse
import hashlib
import io
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = {
    "gitleaks": (
        "gitleaks/gitleaks",
        "v8.30.1",
        {
            "Linux": (
                "gitleaks_8.30.1_linux_x64.tar.gz",
                "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
            ),
            "Windows": (
                "gitleaks_8.30.1_windows_x64.zip",
                "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e",
            ),
        },
    ),
    "actionlint": (
        "rhysd/actionlint",
        "v1.7.12",
        {
            "Linux": (
                "actionlint_1.7.12_linux_amd64.tar.gz",
                "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
            ),
            "Windows": (
                "actionlint_1.7.12_windows_amd64.zip",
                "6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9",
            ),
        },
    ),
    "shellcheck": (
        "koalaman/shellcheck",
        "v0.11.0",
        {
            "Linux": (
                "shellcheck-v0.11.0.linux.x86_64.tar.xz",
                "8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198",
            ),
            "Windows": (
                "shellcheck-v0.11.0.zip",
                "8a4e35ab0b331c85d73567b12f2a444df187f483e5079ceffa6bda1faa2e740e",
            ),
        },
    ),
}


def binary(name):
    repo, version, systems = TOOLS[name]
    archive_name, expected = systems[platform.system()]
    destination = ROOT / "cache" / "quality-tools" / version / archive_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        url = f"https://github.com/{repo}/releases/download/{version}/{archive_name}"
        urllib.request.urlretrieve(url, destination)
    data = destination.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError(f"Checksum mismatch for {archive_name}")
    filename = name + (".exe" if platform.system() == "Windows" else "")
    executable = destination.parent / filename
    if archive_name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            member = next(n for n in archive.namelist() if Path(n).name == filename)
            payload = archive.read(member)
    else:
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            member = next(m for m in archive.getmembers() if Path(m.name).name == filename)
            payload = archive.extractfile(member).read()
    executable.write_bytes(payload)
    executable.chmod(0o755)
    return str(executable)


def run(name):
    executable = binary(name)
    if name == "actionlint":
        env = {
            **os.environ,
            "PATH": str(Path(binary("shellcheck")).parent) + os.pathsep + os.environ["PATH"],
        }
        subprocess.run([executable, "-color"], cwd=ROOT, env=env, check=True)
    elif name == "shellcheck":
        subprocess.run(
            [
                executable,
                "-S",
                "warning",
                "-e",
                "SC1091",
                *map(str, (ROOT / "scripts").glob("*.sh")),
            ],
            check=True,
        )
    else:
        # Never recursively scan ignored credential files or raw artifacts.
        files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
        with tempfile.TemporaryDirectory(prefix="sre-gitleaks-") as temporary:
            for relative in filter(None, files):
                source = ROOT / relative
                if source.is_file():
                    target = Path(temporary) / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
            subprocess.run(
                [
                    executable,
                    "dir",
                    temporary,
                    "--config",
                    str(ROOT / ".gitleaks.toml"),
                    "--redact",
                    "--no-banner",
                ],
                check=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("tool", choices=TOOLS)
    run(parser.parse_args().tool)

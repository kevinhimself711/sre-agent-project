"""Upload only local upstream changes and project scripts/configs, never credentials."""

import io
import subprocess
from pathlib import Path, PurePosixPath

from remote import ROOT, connect


def main():
    client, _ = connect("pci-2")
    try:
        with client.open_sftp() as sftp:
            remote_root = PurePosixPath(sftp.normalize(".")) / "sre-agent-project"
            files = set()
            for name in ("holmesgpt", "sregym"):
                repo = ROOT / "repos" / name
                for args in (
                    ["diff", "HEAD", "--name-only"],
                    ["ls-files", "--others", "--exclude-standard"],
                ):
                    for rel in subprocess.check_output(
                        ["git", "-C", str(repo), *args],
                        text=True,
                        stderr=subprocess.DEVNULL,
                    ).splitlines():
                        file = repo / rel
                        if file.is_file():
                            files.add(file)
            for directory in ("scripts", "configs"):
                files.update(
                    p
                    for p in (ROOT / directory).rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts
                )
            created = set()
            for file in sorted(files):
                rel = file.relative_to(ROOT).as_posix()
                destination = remote_root / rel
                for parent in reversed(destination.parents):
                    if str(parent) in created:
                        continue
                    try:
                        sftp.stat(str(parent))
                    except FileNotFoundError:
                        sftp.mkdir(str(parent))
                    created.add(str(parent))
                content = file.read_bytes()
                try:
                    content.decode("utf-8")
                    if b"\0" not in content:
                        content = content.replace(b"\r\n", b"\n")
                        parts = file.relative_to(ROOT).parts
                        if parts[0] == "repos":
                            original = subprocess.run(
                                [
                                    "git",
                                    "-C",
                                    str(ROOT / "repos" / parts[1]),
                                    "show",
                                    "HEAD:" + Path(*parts[2:]).as_posix(),
                                ],
                                capture_output=True,
                            ).stdout
                            if original.count(b"\n") and original.count(b"\r\n") == original.count(
                                b"\n"
                            ):
                                content = content.replace(b"\n", b"\r\n")
                except UnicodeDecodeError:
                    pass
                sftp.putfo(io.BytesIO(content), str(destination))
            print(f"Uploaded {len(files)} changed source/config/script files")
    finally:
        client.close()


if __name__ == "__main__":
    main()

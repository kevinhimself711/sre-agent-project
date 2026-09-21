"""Download run evidence only; omit credentials, image archives and build contexts."""

import argparse
import re
import stat
from pathlib import Path, PurePosixPath

from remote import ROOT, connect


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--remote-root", help="Absolute evaluation workspace on pci-2")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/pci-2")
    parser.add_argument("--campaign", action="store_true")
    args = parser.parse_args()
    client, password = connect("pci-2")
    secrets = [password.encode()]
    key_file = ROOT / "Bailian API.txt"
    if key_file.exists():
        secrets.extend(
            x.encode()
            for x in re.findall(r"sk-[A-Za-z0-9_-]+", key_file.read_text(encoding="utf-8-sig"))
        )
    count = 0
    try:
        with client.open_sftp() as sftp:
            base = (
                PurePosixPath(args.remote_root)
                if args.remote_root
                else PurePosixPath(sftp.normalize(".")) / "sre-agent-project"
            )
            local = args.output

            def download(remote, target):
                nonlocal count
                data = sftp.open(str(remote), "rb").read()
                if any(secret in data for secret in secrets):
                    raise RuntimeError(f"Credential detected; refusing local copy: {remote.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                count += 1

            def tree(remote, target):
                for entry in sftp.listdir_attr(str(remote)):
                    path = remote / entry.filename
                    if stat.S_ISDIR(entry.st_mode):
                        tree(path, target / entry.filename)
                    elif stat.S_ISREG(entry.st_mode):
                        download(path, target / entry.filename)

            for entry in sftp.listdir_attr(str(base / "artifacts")):
                if stat.S_ISREG(entry.st_mode) and Path(entry.filename).suffix in {
                    ".log",
                    ".json",
                    ".xml",
                    ".txt",
                }:
                    download(base / "artifacts" / entry.filename, local / entry.filename)
            if args.campaign:
                tree(base / "artifacts/campaigns", local / "campaigns")
                print(f"Downloaded {count} campaign evidence files without known credentials.")
                return
            tree(base / "repos/sregym/results", local / "results")
            try:
                sftp.stat(str(base / "artifacts/trace-export"))
            except FileNotFoundError:
                pass
            else:
                tree(base / "artifacts/trace-export", local / "trace-export")
            for name in ("kind.yaml", "calico-v3.27.0.yaml"):
                download(base / "configs" / name, local / "runtime-configs" / name)
    finally:
        client.close()
    print(f"Downloaded {count} evidence files without known credentials.")


if __name__ == "__main__":
    main()

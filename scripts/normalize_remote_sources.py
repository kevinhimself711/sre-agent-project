"""Repair transport-only CRLF differences without reverting semantic changes."""

import subprocess

from project_paths import project_root

root = project_root()
for name in ("holmesgpt", "sregym"):
    repo = root / "repos" / name
    files = subprocess.check_output(
        ["git", "-C", str(repo), "diff", "--name-only"], text=True
    ).splitlines()
    normalized = 0
    for rel in files:
        path = repo / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        original = subprocess.check_output(["git", "-C", str(repo), "show", "HEAD:" + rel])
        normalized_data = data.replace(b"\r\n", b"\n")
        if original.count(b"\n") and original.count(b"\r\n") == original.count(b"\n"):
            normalized_data = normalized_data.replace(b"\n", b"\r\n")
        if b"\0" not in data and normalized_data != data:
            path.write_bytes(normalized_data)
            normalized += 1
    print(name, "normalized CRLF files:", normalized)

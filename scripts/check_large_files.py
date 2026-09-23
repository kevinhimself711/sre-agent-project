import subprocess

EVIDENCE_LIMIT = 5 * 1024 * 1024


if __name__ == "__main__":
    files = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "-z"]
    )
    for name in filter(None, files.decode().split("\0")):
        size = int(subprocess.check_output(["git", "cat-file", "-s", ":" + name]))
        if name.startswith("evidence/"):
            if size > EVIDENCE_LIMIT:
                raise SystemExit(f"Evidence file exceeds 5 MiB: {name}")
            continue
        if size > 1024 * 1024:
            raise SystemExit(f"File exceeds 1 MiB: {name}; keep raw artifacts outside Git")

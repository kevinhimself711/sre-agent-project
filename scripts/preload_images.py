"""Pull through the process proxy, then import into our named KIND cluster only."""

import argparse
import concurrent.futures
import hashlib
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="+")
    parser.add_argument("--destination", choices=["kind", "host"], default="kind")
    args = parser.parse_args()
    root = Path.home() / "sre-agent-project"
    cache = root / "artifacts/images"
    cache.mkdir(parents=True, exist_ok=True)

    def fetch(image):
        pinned = "@sha256:" in image
        archive = cache / (
            hashlib.sha256(image.encode()).hexdigest()[:16] + (".oci.tar" if pinned else ".tar")
        )
        if not archive.exists():
            temporary = archive.with_suffix(".partial.tar")
            if pinned:
                repository, digest = image.split("@", 1)
                if ":" in repository.rsplit("/", 1)[-1]:
                    repository = repository.rsplit(":", 1)[0]
                # Preserve the manifest index and digest. A single-platform
                # Docker archive cannot satisfy kind's --all-platforms import.
                subprocess.run(
                    [
                        "skopeo",
                        "copy",
                        "--retry-times",
                        "2",
                        "--all",
                        "docker://" + repository + "@" + digest,
                        "oci-archive:" + str(temporary),
                    ],
                    check=True,
                )
            else:
                subprocess.run(
                    [
                        "skopeo",
                        "copy",
                        "--retry-times",
                        "2",
                        "--override-os",
                        "linux",
                        "--override-arch",
                        "amd64",
                        "docker://" + image,
                        "docker-archive:" + str(temporary) + ":" + image,
                    ],
                    check=True,
                )
            temporary.replace(archive)
        return archive

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(fetch, image) for image in args.images]
        for future in concurrent.futures.as_completed(futures):
            archive = future.result()
            if args.destination == "host":
                subprocess.run(["docker", "load", "-i", str(archive)], check=True)
            else:
                subprocess.run(
                    [
                        str(root / "bin/kind"),
                        "load",
                        "image-archive",
                        "--name",
                        "sre-agent-dev",
                        str(archive),
                    ],
                    check=True,
                )


if __name__ == "__main__":
    main()

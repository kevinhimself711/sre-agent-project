"""Build one local image with isolated Holmes dependencies and current drivers."""

import json
import os
import subprocess
import sys
import tarfile

from project_paths import project_root

root = project_root()
revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
image_name = os.environ.get("SRE_AGENT_IMAGE", "sre-holmes-agent:baseline")
# Once measurements exist, rebuilding would change the frozen runtime identity.
states = list((root / "artifacts/campaigns").glob("*/state.json"))
if states:
    image_id = subprocess.check_output(
        ["docker", "image", "inspect", image_name, "--format", "{{.Id}}"], text=True
    ).strip()
    for state_path in states:
        provenance = json.loads(state_path.read_text())["provenance"]
        if provenance["commit"] != revision or provenance["image_id"] != image_id:
            raise RuntimeError("Frozen campaign image or source changed; refusing to rebuild")
    print(f"Reusing frozen agent image {image_id}")
    sys.exit(0)
build = root / "artifacts/agent-build"
build.mkdir(exist_ok=True)
with tarfile.open(build / "holmes-runtime.tar", "w") as archive:
    archive.add((root / "repos/holmesgpt/.venv").resolve(), arcname=".venv")
    archive.add(root / "repos/holmesgpt/holmes", arcname="holmes")
with tarfile.open(build / "sregym-runtime.tar", "w") as archive:
    for name in (
        "clients",
        "logger",
        "llm_backend",
        "sregym/__init__.py",
        "sregym/paths.py",
        "sregym/service/__init__.py",
        "sregym/service/kubectl.py",
        "sregym/service/helm.py",
        "sregym/service/apps/base.py",
        "sregym/service/apps/helpers.py",
    ):
        archive.add(root / "repos/sregym" / name, arcname=name)
(build / "Dockerfile").write_text(
    """FROM ghcr.io/sregym/agent-base:sha-b97d6810e994bb7354b4bc15c6bc81cb66e816b9@sha256:92e8b52af763c6e165144d314ec25b1ad3ba0e0f1b0a28ffa4a1760e92ec6b61
ADD holmes-runtime.tar /opt/holmes/
ADD sregym-runtime.tar /opt/sregym/
ENV PYTHONPATH=/opt/holmes:/opt/sregym
ENV LITELLM_LOCAL_MODEL_COST_MAP=True
ENV OVERRIDE_MAX_OUTPUT_TOKEN=8192
ENV LLM_REQUEST_TIMEOUT=120
ENV HOLMES_SOURCE_REV=__PROJECT_REVISION__
RUN /opt/holmes/.venv/bin/python -c "from holmes.config import Config; from clients.holmes.driver import create_config"
""".replace("__PROJECT_REVISION__", revision)
)
subprocess.run(
    ["docker", "build", "--pull=false", "-t", image_name, str(build)],
    check=True,
)

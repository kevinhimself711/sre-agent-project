"""Build one local image with isolated Holmes dependencies and current drivers."""

import subprocess
import tarfile
from pathlib import Path

root = Path.home() / "sre-agent-project"
build = root / "artifacts/agent-build"
build.mkdir(exist_ok=True)
with tarfile.open(build / "holmes-runtime.tar", "w") as archive:
    archive.add(root / "repos/holmesgpt/.venv", arcname=".venv")
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
ENV HOLMES_SOURCE_REV=3bd44edf04f9587c778ee8e9b244965190c40fdf+local
RUN /opt/holmes/.venv/bin/python -c "from holmes.config import Config; from clients.holmes.driver import create_config"
"""
)
subprocess.run(
    ["docker", "build", "--pull=false", "-t", "sre-holmes-agent:baseline", str(build)],
    check=True,
)

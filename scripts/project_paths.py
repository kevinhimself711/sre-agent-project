"""Non-secret locations shared by local scripts and the dedicated evaluation worker."""

import os
from pathlib import Path


def project_root():
    return Path(
        os.environ.get("SRE_PROJECT_ROOT", str(Path(__file__).resolve().parents[1]))
    ).resolve()


def kubeconfig():
    return Path(
        os.environ.get("SREGYM_ADMIN_KUBECONFIG", str(project_root() / "configs/kubeconfig"))
    )

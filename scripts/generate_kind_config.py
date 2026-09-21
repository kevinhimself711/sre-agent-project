"""Adapt only cgroup driver for pci-2's existing cgroup-v1 Docker host."""

from pathlib import Path

import yaml

root = Path.home() / "sre-agent-project"
config = yaml.safe_load((root / "repos/sregym/kind/kind-config.yaml").read_text())
config["kubeadmConfigPatches"] = ["kind: KubeletConfiguration\ncgroupDriver: cgroupfs\n"]
config["containerdConfigPatches"] = [
    '[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options]\nSystemdCgroup = false\n'
]
(root / "configs/kind.yaml").write_text(yaml.safe_dump(config, sort_keys=False))

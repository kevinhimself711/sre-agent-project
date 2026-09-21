#!/usr/bin/env bash
set -euo pipefail
SRE_ROOT="$HOME/sre-agent-project"
export PATH="$SRE_ROOT/bin:$SRE_ROOT/tools-venv/bin:$PATH"
mkdir -p "$SRE_ROOT/bin" "$SRE_ROOT/artifacts" "$SRE_ROOT/configs"
if ! test -x "$SRE_ROOT/tools-venv/bin/poetry"; then
  python3.12 -m venv "$SRE_ROOT/tools-venv"
  "$SRE_ROOT/tools-venv/bin/pip" install uv==0.12.17 poetry==2.4.3
fi

if ! test -x "$SRE_ROOT/bin/kind"; then
  curl --fail --location --retry 2 https://github.com/kubernetes-sigs/kind/releases/download/v0.27.0/kind-linux-amd64 -o "$SRE_ROOT/bin/kind"
  chmod +x "$SRE_ROOT/bin/kind"
fi
if ! test -x "$SRE_ROOT/bin/kubectl"; then
  curl --fail --location --retry 2 https://dl.k8s.io/release/v1.32.1/bin/linux/amd64/kubectl -o "$SRE_ROOT/bin/kubectl"
  chmod +x "$SRE_ROOT/bin/kubectl"
fi
cd "$SRE_ROOT/repos/sregym"
git submodule update --init --depth 1
uv sync --frozen --python /usr/bin/python3.12
cd "$SRE_ROOT/repos/holmesgpt"
POETRY_VIRTUALENVS_IN_PROJECT=true poetry env use /usr/bin/python3.12
POETRY_VIRTUALENVS_IN_PROJECT=true poetry install --with dev --no-interaction
{
  python3 --version
  kind version
  kubectl version --client
  helm version --short
  uv --version
  poetry --version
  git -C "$SRE_ROOT/repos/holmesgpt" rev-parse HEAD
  git -C "$SRE_ROOT/repos/sregym" rev-parse HEAD
} > "$SRE_ROOT/artifacts/runtime-versions.txt"

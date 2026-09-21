#!/usr/bin/env bash
set -euo pipefail
SRE_ROOT="$HOME/sre-agent-project"
export PATH="$SRE_ROOT/bin:$PATH"
export KUBECONFIG="$SRE_ROOT/configs/kubeconfig"
if ! test -f "$SRE_ROOT/configs/kind.yaml"; then
  "$SRE_ROOT/repos/sregym/.venv/bin/python" "$SRE_ROOT/scripts/generate_kind_config.py"
fi
if ! test -f "$SRE_ROOT/configs/calico-v3.27.0.yaml"; then
  curl --fail --location --retry 2 https://raw.githubusercontent.com/projectcalico/calico/v3.27.0/manifests/calico.yaml -o "$SRE_ROOT/configs/calico-v3.27.0.yaml"
fi
printf '%s  %s\n' dbc4d6fdb5ca87978f6d67a43b09094852cd375398cad5c1650c1c462dd58d8b "$SRE_ROOT/configs/calico-v3.27.0.yaml" | sha256sum --check --status
if ! kind get clusters | grep -Fxq sre-agent-dev; then
  kind create cluster --name sre-agent-dev --config "$SRE_ROOT/configs/kind.yaml" --kubeconfig "$KUBECONFIG" --retain
fi
test "$(kubectl config current-context)" = kind-sre-agent-dev
kubectl apply -f "$SRE_ROOT/configs/calico-v3.27.0.yaml"
kubectl rollout status daemonset/calico-node -n kube-system --timeout=600s
kubectl wait --for=condition=Ready nodes --all --timeout=180s
kubectl get nodes -o wide

#!/usr/bin/env bash
set -euo pipefail
SRE_PROJECT_ROOT="${SRE_PROJECT_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
export SRE_PROJECT_ROOT
source "$SRE_PROJECT_ROOT/configs/baseline.env"
test "$(kubectl --kubeconfig "$KUBECONFIG" config current-context)" = kind-sre-agent-dev
if [ "${SRE_CLUSTER_LOCK_HELD:-0}" != 1 ]; then
  exec "$SRE_PROJECT_ROOT/.venv/bin/python" "$SRE_PROJECT_ROOT/scripts/locked_run.py" "$0" "$@"
fi
export MODEL_LIST_FILE_LOCATION="$SRE_PROJECT_ROOT/configs/holmes-models.yaml"
export RUN_LIVE=true ITERATIONS=1
export LITELLM_LOCAL_MODEL_COST_MAP=True
cd "$SRE_PROJECT_ROOT/repos/holmesgpt"
.venv/bin/python -m pytest tests/llm/test_ask_holmes.py -k '01_how_many_pods or 80_pvc_storage_class_mismatch' \
  -n 0 --no-cov --junitxml=../../artifacts/native-evals.xml

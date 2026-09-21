#!/usr/bin/env bash
set -euo pipefail
SRE_PROJECT_ROOT="${SRE_PROJECT_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
export SRE_PROJECT_ROOT
source "$SRE_PROJECT_ROOT/configs/baseline.env"
test "$(kubectl --kubeconfig "$KUBECONFIG" config current-context)" = kind-sre-agent-dev
export LITELLM_LOCAL_MODEL_COST_MAP=True
export WAIT_FOR_POD_READY_TIMEOUT=900
if [ "${SRE_CLUSTER_LOCK_HELD:-0}" != 1 ]; then
  exec "$SRE_PROJECT_ROOT/.venv/bin/python" "$SRE_PROJECT_ROOT/scripts/locked_run.py" "$0" "$@"
fi
python3 "$SRE_PROJECT_ROOT/scripts/capture_provenance.py"
cd "$SRE_PROJECT_ROOT/repos/sregym"
exec .venv/bin/python main.py --agent "$1" --problem "$2" --n-attempts "${3:-1}" \
  --model "$AGENT_MODEL_ID" --judge-model "$JUDGE_MODEL_ID" --stages diagnosis \
  --profile full --agent-timeout 1800 --agent-image "${SRE_AGENT_IMAGE:-sre-holmes-agent:baseline}"

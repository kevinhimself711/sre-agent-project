#!/usr/bin/env bash
set -euo pipefail
source "$HOME/sre-agent-project/configs/baseline.env"
test "$(kubectl config current-context)" = kind-sre-agent-dev
export LITELLM_LOCAL_MODEL_COST_MAP=True
export WAIT_FOR_POD_READY_TIMEOUT=900
python3 "$HOME/sre-agent-project/scripts/capture_provenance.py"
cd "$HOME/sre-agent-project/repos/sregym"
exec .venv/bin/python main.py --agent "$1" --problem "$2" --n-attempts "${3:-1}" \
  --model "$AGENT_MODEL_ID" --judge-model "$JUDGE_MODEL_ID" --stages diagnosis \
  --profile full --agent-timeout 1800 --agent-image sre-holmes-agent:baseline

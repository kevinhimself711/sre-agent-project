#!/usr/bin/env bash
set -euo pipefail
source "$HOME/sre-agent-project/configs/baseline.env"
test "$(kubectl config current-context)" = kind-sre-agent-dev
export MODEL_LIST_FILE_LOCATION="$HOME/sre-agent-project/configs/holmes-models.yaml"
export RUN_LIVE=true ITERATIONS=1
export LITELLM_LOCAL_MODEL_COST_MAP=True
cd "$HOME/sre-agent-project/repos/holmesgpt"
.venv/bin/python -m pytest tests/llm/test_ask_holmes.py -k '01_how_many_pods or 80_pvc_storage_class_mismatch' \
  -n 0 --no-cov --junitxml=../../artifacts/native-evals.xml

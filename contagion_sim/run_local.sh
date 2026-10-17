#!/usr/bin/env bash
# End-to-end on one scenario without Daytona. Usage: ./run_local.sh data/svb 400
set -euo pipefail
SCN=${1:-data/svb}; RUNS=${2:-400}
cd "$(dirname "$0")"
# 1) pre-run LLM stage (skip if the JSONs are already in the folder, as for data/svb and data/cs)
[ -f "$SCN/rumour_scores.json" ] || python -m pipeline.pre_run "$SCN"
# 2) Monte Carlo (same batching as Daytona, run locally)
python -m pipeline.daytona_sweep "$SCN" --runs "$RUNS" --local
# 3) evidence pack (code only) -> verdicts + ranking (LLM, number-checked)
python condense.py "$SCN"
python -m pipeline.droid_analyst "$SCN"
echo "Done: $SCN/ranking.md"

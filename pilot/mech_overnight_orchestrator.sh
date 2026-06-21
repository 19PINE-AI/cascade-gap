#!/usr/bin/env bash
# Overnight orchestrator: waits for V2 (API) and the GPU runner to finish, then runs
# stats + regenerates figures + writes VALIDATION_REPORT.md. Idempotent steps; logs throughout.
set -u
cd /home/ubuntu/cascade-gap
LOG=runs/mechanism/orchestrator.log
ts() { date -u +%H:%M:%S; }
say() { echo "[$(ts)] $*" | tee -a "$LOG"; }

say "===== ORCHESTRATOR START ====="

# 1. Wait for V2 multi-seed to finish, then run stats.
say "waiting for V2 (mech_multiseed) to finish..."
while pgrep -f mech_multiseed.py >/dev/null 2>&1; do sleep 60; done
say "V2 done. running multiseed stats..."
python3 pilot/mech_multiseed_stats.py >> "$LOG" 2>&1 && say "stats ok" || say "stats FAILED"

# 2. Wait for GPU runner to finish (writes ALL_GPU_DONE).
say "waiting for GPU runner to finish..."
while ! grep -q "ALL_GPU_DONE" runs/mechanism/gpu_runner.log 2>/dev/null; do
  pgrep -f mech_gpu_runner.sh >/dev/null 2>&1 || { say "gpu runner process gone"; break; }
  sleep 60
done
say "GPU runner finished (or exited)."

# 3. Regenerate figures (best-effort) and write the validation report.
python3 pilot/mech_figs.py >> "$LOG" 2>&1 && say "figs ok" || say "figs FAILED"
python3 pilot/mech_validation_report.py >> "$LOG" 2>&1 && say "report ok" || say "report FAILED"

say "===== ORCHESTRATOR DONE ====="
echo "ALL_VALIDATION_DONE"

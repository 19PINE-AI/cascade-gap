#!/usr/bin/env bash
# Sequential, GPU-memory-gated runner for the GPU validation jobs (V1 audio, V3 vision ladder).
# Shared GPU: each job waits until enough memory is free, then grabs it. Jobs run one at a
# time (each frees its memory on process exit). Failures/timeouts are logged and skipped.
set -u
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/ubuntu/cascade-gap
LOG=runs/mechanism/gpu_runner.log
ts() { date -u +%H:%M:%S; }
say() { echo "[$(ts)] $*" | tee -a "$LOG"; }

free_mb() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1 | tr -d ' '; }

# wait_gpu <min_free_mb> <max_wait_sec>  -> returns 0 if available, 1 if timed out
wait_gpu() {
  local need=$1 maxw=${2:-10800} waited=0
  while :; do
    local f; f=$(free_mb)
    if [ "${f:-0}" -ge "$need" ]; then say "GPU ok: ${f}MB free >= ${need}MB"; return 0; fi
    if [ "$waited" -ge "$maxw" ]; then say "GPU wait TIMED OUT after ${waited}s (need ${need}MB, have ${f}MB)"; return 1; fi
    say "waiting for GPU: ${f}MB free < ${need}MB (waited ${waited}s)"
    sleep 30; waited=$((waited+30))
  done
}

run_job() { # <name> <timeout_sec> <cmd...>
  local name=$1 to=$2; shift 2
  say "START $name : $*"
  if timeout "$to" "$@" >> "$LOG" 2>&1; then say "DONE  $name (exit 0)"; else say "FAIL  $name (exit $?)"; fi
}

say "===== GPU RUNNER START ====="

MAXW=18000   # up to 5h waiting per gate (overnight shared GPU)

# ---- V1: audio substrate logit-lens (Qwen2.5-Omni thinker) ----
if wait_gpu 32000 "$MAXW"; then
  say "V1 preflight..."
  PFLOG=runs/mechanism/v1_preflight_runner.log
  if timeout 900 python3 pilot/mech_e7_audio.py --preflight > "$PFLOG" 2>&1 && grep -q PREFLIGHT_OK "$PFLOG"; then
    say "V1 preflight OK"
    run_job "V1-audio" 3600 python3 pilot/mech_e7_audio.py
  else
    say "SKIP V1-audio: preflight failed (see $PFLOG):"; tail -5 "$PFLOG" | tee -a "$LOG"
  fi
else
  say "SKIP V1-audio: GPU never freed to 32GB"
fi

# ---- V3: vision ladder (3B, 7B fit in modest memory; 32B needs the big block) ----
for M in "Qwen/Qwen2.5-VL-3B-Instruct:16000:2400" "Qwen/Qwen2.5-VL-7B-Instruct:28000:2400" "Qwen/Qwen2.5-VL-32B-Instruct:72000:7200"; do
  model="${M%%:*}"; rest="${M#*:}"; need="${rest%%:*}"; to="${rest##*:}"
  if wait_gpu "$need" "$MAXW"; then
    run_job "V3-${model##*/}" "$to" python3 pilot/mech_e6_ladder.py --model "$model" --ks 1,4,8,16,24 --trials 16
  else
    say "SKIP V3-${model##*/}: GPU never freed to ${need}MB"
  fi
done

say "===== ALL_GPU_DONE ====="

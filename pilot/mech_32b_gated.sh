#!/usr/bin/env bash
set -u; cd /home/ubuntu/cascade-gap
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
LOG=runs/mechanism/v3_32b_clean.log
ts(){ date -u +%H:%M:%S; }
say(){ echo "[$(ts)] $*" >> "$LOG"; }
say "32B gated rerun start (clean answer-matching)"
waited=0
while :; do
  f=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1 | tr -d ' ')
  if [ "${f:-0}" -ge 74000 ]; then say "GPU ok ${f}MB; launching 32B"; break; fi
  if [ "$waited" -ge 25200 ]; then say "TIMEOUT waiting for 74GB (have ${f}MB); skip 32B"; echo "SKIP_32B"; exit 0; fi
  say "waiting ${f}MB<74GB (${waited}s)"; sleep 60; waited=$((waited+60))
done
if timeout 7200 python3 pilot/mech_e6_ladder.py --model Qwen/Qwen2.5-VL-32B-Instruct --ks 1,4,8,16,24 --trials 16 >> "$LOG" 2>&1; then
  say "32B DONE"
else
  say "32B FAIL (exit $?)"
fi
echo "DONE_32B"

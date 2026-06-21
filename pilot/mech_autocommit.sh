#!/usr/bin/env bash
# Waits for V2 (multi-seed) to finish and the validation report to be written, then
# commits the refreshed results + report and pushes to origin (19PINE-AI/cascade-gap).
# Self-sufficient: if the orchestrator hasn't produced stats/report, generates them.
set -u
cd /home/ubuntu/cascade-gap
LOG=runs/mechanism/autocommit.log
ts(){ date -u +%H:%M:%S; }
say(){ echo "[$(ts)] $*" | tee -a "$LOG"; }

say "===== AUTOCOMMIT WATCHER START ====="

# 1. Wait for V2 to finish (max ~4h).
waited=0
while pgrep -f mech_multiseed.py >/dev/null 2>&1; do
  [ "$waited" -ge 14400 ] && { say "V2 still running after 4h; proceeding with snapshot"; break; }
  sleep 60; waited=$((waited+60))
done
say "V2 finished (or timed out)."

# 2. Give the orchestrator up to 10 min to write the report; else generate it ourselves.
w2=0
while [ ! -f runs/mechanism/VALIDATION_REPORT.md ]; do
  [ "$w2" -ge 600 ] && { say "report not produced by orchestrator; generating"; \
     python3 pilot/mech_multiseed_stats.py >> "$LOG" 2>&1; \
     python3 pilot/mech_figs.py >> "$LOG" 2>&1; \
     python3 pilot/mech_validation_report.py >> "$LOG" 2>&1; break; }
  sleep 30; w2=$((w2+30))
done
# Always refresh stats once V2 is truly done (idempotent), so committed numbers are final.
if ! pgrep -f mech_multiseed.py >/dev/null 2>&1; then
  python3 pilot/mech_multiseed_stats.py >> "$LOG" 2>&1 && say "stats refreshed"
  python3 pilot/mech_validation_report.py >> "$LOG" 2>&1 && say "report refreshed"
fi

# 3. Stage refreshed evidence + report + figures + the report-generator edit.
git add -f runs/mechanism/multiseed_summary.json runs/mechanism/multiseed_stats.json \
            runs/mechanism/e6_ladder_summary.json runs/mechanism/VALIDATION_REPORT.md 2>/dev/null
git add paper/figures/fig_mech_conditions.pdf pilot/mech_validation_report.py 2>/dev/null
git add -f runs/mechanism/e6_summary.json runs/mechanism/e6_load_summary.json 2>/dev/null

if git diff --cached --quiet; then
  say "no changes to commit"; echo "AUTOCOMMIT_DONE"; exit 0
fi

NSCORED=$(python3 -c "import json;print(len([r for r in json.load(open('runs/mechanism/multiseed_summary.json')) if 'coverage' in r]))" 2>/dev/null)
git commit -q -F - <<MSG
Validation results: final multi-seed stats + report (V2/V3)

Final V2 multi-seed sweep (${NSCORED} scored cells across C1/E1/E2 x seeds) with
paired Wilcoxon + bootstrap CIs + mixed-effects + TOST, the validation report, and
the cleaned vision ladder (3B+7B; 32B dropped as an answer-format artifact).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
MSG
say "committed: $(git log --oneline -1)"
if git push origin main >> "$LOG" 2>&1; then say "pushed to origin"; else say "PUSH FAILED (see log)"; fi
echo "AUTOCOMMIT_DONE"

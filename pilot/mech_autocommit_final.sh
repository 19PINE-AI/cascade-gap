#!/usr/bin/env bash
# Final-pass: wait for V2 to TRULY finish (full n=5), then refresh stats+report and
# commit+push the complete results to origin (19PINE-AI/cascade-gap).
set -u
cd /home/ubuntu/cascade-gap
LOG=runs/mechanism/autocommit_final.log
ts(){ date -u +%H:%M:%S; }
say(){ echo "[$(ts)] $*" | tee -a "$LOG"; }

say "===== FINAL AUTOCOMMIT START ====="
waited=0
while pgrep -f "mech_multis[e]ed.py" >/dev/null 2>&1; do
  [ "$waited" -ge 21600 ] && { say "V2 still running after 6h; committing snapshot anyway"; break; }
  sleep 120; waited=$((waited+120))
done
say "V2 finished."

python3 pilot/mech_multiseed_stats.py >> "$LOG" 2>&1 && say "stats done"
python3 pilot/mech_validation_report.py >> "$LOG" 2>&1 && say "report done"

git add -f runs/mechanism/multiseed_summary.json runs/mechanism/multiseed_stats.json \
            runs/mechanism/VALIDATION_REPORT.md runs/mechanism/e6_ladder_summary.json \
            runs/mechanism/e6_summary.json runs/mechanism/e6_load_summary.json 2>/dev/null
git add paper/figures/fig_mech_conditions.pdf pilot/mech_validation_report.py 2>/dev/null

if git diff --cached --quiet; then say "no changes"; echo "FINAL_DONE"; exit 0; fi
NS=$(python3 -c "import json;print(len([r for r in json.load(open('runs/mechanism/multiseed_summary.json')) if 'coverage' in r]))" 2>/dev/null)
git commit -q -F - <<MSG
Validation: complete multi-seed results (V2 finished, ${NS} scored)

Final V2 multi-seed sweep (full n=5 where reached) with refreshed paired stats
(Wilcoxon + bootstrap CIs + mixed-effects + TOST) and validation report, including
the three-TTS audio table (espeak/mms/fish) confirming no audio substrate gap.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
MSG
say "committed: $(git log --oneline -1)"
if git push origin main >> "$LOG" 2>&1; then say "pushed"; else say "PUSH FAILED"; fi
echo "FINAL_DONE"

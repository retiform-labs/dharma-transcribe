#!/usr/bin/env bash
set -uo pipefail
cd /home/guan/src/dharma-transcribe
source venv/bin/activate
export DHARMA_BATCH_LOG=/home/guan/src/dharma-transcribe/logs/smoke-2026-11-08.log
rm -f "$DHARMA_BATCH_LOG"
python scripts/batch_2026_11_08.py staging/filelist_smoke.json
rc=$?
echo "SMOKE_EXIT=$rc" >> "$DHARMA_BATCH_LOG"

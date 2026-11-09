#!/usr/bin/env bash
set -uo pipefail
cd /home/guan/src/dharma-transcribe
source venv/bin/activate
export DHARMA_BATCH_LOG=/home/guan/src/dharma-transcribe/logs/batch-2026-11-08.log
python scripts/batch_2026_11_08.py staging/filelist.json
rc=$?
echo "BATCH_EXIT=$rc" >> "$DHARMA_BATCH_LOG"

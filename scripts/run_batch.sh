#!/usr/bin/env bash
#
# Run the dharma transcription pipeline over a corpus, under tmux, with live
# output AND a durable log.
#
# Why a script: the previous ad-hoc tmux one-liners redirected stdout to a file
# (`> log 2>&1`), which left the tmux pane empty and unusable for live watching.
# `tee` gives both. This also centralises the environment ritual that is easy to
# get wrong:
#
#   * .env is NOT auto-loaded by the package — `set -a; . ./.env; set +a`.
#   * HF_TOKEN must be exported for Stage 4 diarization; without it the stage is
#     skipped (not failed) and transcripts come out un-diarized.
#   * the venv must be active for whisperx/pyannote to import.
#
# Usage:
#   scripts/run_batch.sh <input-path> [log-name] [extra python args...]
#
# Example:
#   scripts/run_batch.sh "/media/.../Kongokai Mandala Series" kongokai
#   scripts/run_batch.sh "/media/.../Vajra Mandala" vajra --skip-llm
#
# SAMAYA GATE — read before changing the defaults:
#   Restricted tantra (Vajra Mandala, Dakini Land, any restricted-tantra batch)
#   MUST be transcribed locally only.  Stage 6 (LLM post-correction) sends
#   transcript text to an EXTERNAL API and is therefore FORBIDDEN for that
#   material.  A failover provider does NOT inherit permission.
#   => this launcher passes --skip-llm by default; pass --allow-llm explicitly
#      only for unrestricted material.  (Historically this script passed no
#      flag, so invoking it would have silently routed restricted transcripts
#      off-box — the gate was inert whenever the launcher was used.)
#
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

INPUT="${1:?usage: run_batch.sh <input-path> [log-name] [extra args...]}"
LOG_NAME="${2:-batch}"
shift 2 2>/dev/null || shift $#   # remaining args are forwarded to python
LOG="logs/${LOG_NAME}.log"
LOG_DIR="logs"
SESSION="${LOG_NAME}"

mkdir -p "$LOG_DIR"

# --- Environment ritual -------------------------------------------------------
set -a
# shellcheck disable=SC1091
. ./.env
set +a

# Prefer the cached HF token file; fall back to whatever .env provided.
if [[ -f "$HOME/.cache/huggingface/token" ]]; then
  HF_TOKEN="$(cat "$HOME/.cache/huggingface/token")"
  export HF_TOKEN
fi

# shellcheck disable=SC1091
source venv/bin/activate

# --- Pre-flight ---------------------------------------------------------------
# Downloads and diarization both need external reachability. A dropped default
# route has silently broken download batches before (route-guard should
# self-heal within ~2 min, but fail loudly rather than mysteriously).
if [[ -z "$(ip route show default 2>/dev/null)" ]]; then
  echo "WARNING: no default route — model downloads may fail" >&2
fi

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "WARNING: HF_TOKEN unset — Stage 4 diarization will be SKIPPED" >&2
else
  echo "HF_TOKEN: present (diarization enabled)"
fi

# --- Launch -------------------------------------------------------------------
# ${PIPESTATUS[0]} captures python's exit code, NOT tee's — a pipe makes `$?`
# report the last command in the pipeline.
echo "Logging to $LOG (tail -f to watch live)"
echo "tmux session: $SESSION"
echo "---"

# --- Samaya gate --------------------------------------------------------------
# Stage 6 posts transcript text to an external API. For restricted tantra that is
# a samaya violation, so the DEFAULT here is to skip it. Callers opt in for
# unrestricted material with an explicit --allow-llm; if any other --skip-llm /
# --allow-llm was already passed in "$@", that choice wins.
SKIP_LLM=1
EXTRA_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --allow-llm) SKIP_LLM=0 ;;
    --skip-llm)  SKIP_LLM=1 ;;
    *)           EXTRA_ARGS+=("$arg") ;;
  esac
done
if [[ "$SKIP_LLM" -eq 1 ]]; then
  EXTRA_ARGS+=(--skip-llm)
  echo "SAMAYA GATE: stage 6 (LLM correction) DISABLED — pass --allow-llm to enable"
else
  echo "SAMAYA GATE: stage 6 ENABLED — only for UNRESTRICTED material"
fi

python -m dharma_transcribe "$INPUT" "${EXTRA_ARGS[@]}" 2>&1 | tee "$LOG"
echo "DONE=${PIPESTATUS[0]}" >> "$LOG"

"""Probe: diarize the FULL S1 file with the guard applied (reproduce the hang)."""

import sys
import time

sys.path.insert(0, "/home/guan/src/dharma-transcribe/src")
from whisperx.diarize import DiarizationPipeline

from dharma_transcribe.pyannote_compat import apply_patch

WAV = (
    "/home/guan/src/dharma-transcribe/output/wav/"
    "Kongokai Seminar with Jim McFarland Session 1 [C1xEPh9oBCQ]_bff89467.wav"
)
print(f"[probe] apply_patch -> {apply_patch()}", flush=True)
with open("/home/guan/.cache/huggingface/token") as fh:
    token = fh.read().strip()
p = DiarizationPipeline(token=token, device="cuda")
t = time.time()
df = p(WAV)
print(f"[probe] DONE {time.time() - t:.1f}s rows={len(df)}", flush=True)

"""Probe: diarize a chunk with the StatsPool guard applied."""

import sys
import time

sys.path.insert(0, "/home/guan/src/dharma-transcribe/src")

from whisperx.diarize import DiarizationPipeline

from dharma_transcribe.pyannote_compat import apply_patch

wav = sys.argv[1]
print("[probe] applying patch...", flush=True)
print(f"[probe] apply_patch() -> {apply_patch()}", flush=True)

with open("/home/guan/.cache/huggingface/token") as fh:
    token = fh.read().strip()
p = DiarizationPipeline(token=token, device="cuda")
t = time.time()
df = p(wav)
spk = sorted(df.speaker.unique().tolist()) if len(df) else []
print(f"[probe] DONE in {time.time() - t:.1f}s rows={len(df)} speakers={spk}", flush=True)

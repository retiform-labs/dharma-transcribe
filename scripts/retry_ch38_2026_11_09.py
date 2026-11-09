"""Retry ch38 using the audio track Freeman pulled from the course site.

The source video genuinely carries no audio stream, so the batch recorded a
`failed` manifest entry for it.  The audio file is a separate artefact whose
duration matches the video to the millisecond (1715.583 vs 1715.581 s), which
is what identifies it as the same chapter.

The output stem is forced to the batch name rather than the yt-dlp artefact
name, so the transcript sits beside its 68 siblings in output/txt/.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, "/home/guan/src/dharma-transcribe/src")

from dharma_transcribe.pipeline import (  # noqa: E402
    load_manifest,
    process_file,
    save_manifest,
)

MODULE = Path(
    "/media/mononofu/Samsung 990 EVO/home/mononofu/Shared/Library/"
    "Intuitive Specialists/Practical Remote Viewing/Module 6: Home Stretch"
)
AUDIO = MODULE / "audio-und-mp4a.40.2-[audio-und-mp4a.40.2].mp4"
OUT_NAME = "lori-m6-ch38-chapter-38-it-s-your-turn"
MANIFEST_KEY = OUT_NAME + ".mp4"

if not AUDIO.is_file():
    sys.exit(f"audio file not found: {AUDIO}")

hf_token = os.environ.get("HF_TOKEN", "")
print(f"source: {AUDIO.name}")
print(f"out_name: {OUT_NAME}")
print(f"hf_token present: {bool(hf_token)}", flush=True)

manifest = load_manifest()
prior = manifest["files"].get(MANIFEST_KEY, {})
print(f"prior status for {MANIFEST_KEY}: {prior.get('status')!r}", flush=True)

result = process_file(AUDIO, hf_token, skip_llm=True, out_name=OUT_NAME)

result["staged_from"] = str(AUDIO)
result["batch"] = "2026-11-08"
result["retry_reason"] = "source video has no audio stream; audio pulled from course site"
manifest["files"][MANIFEST_KEY] = result
save_manifest(manifest)

print(f"\nSTATUS: {result.get('status')}", flush=True)
print(f"STAGES: {result.get('stages')}", flush=True)
if result.get("status") != "completed":
    print(f"ERROR: {result.get('error')}", flush=True)
    sys.exit(1)
print("OUTPUTS:", flush=True)
for k, v in result.get("outputs", {}).items():
    print(f"  {k}: {v}", flush=True)

"""Stage 2: Primary transcription via WhisperX large-v3."""

from datetime import datetime

from . import config
from .config import BATCH_SIZE, COMPUTE_TYPE, WHISPER_LANGUAGE, WHISPER_MODEL
from .gpu import flush_gpu, vram_free_mb


def transcribe_audio(wav_path: str) -> dict | None:
    """
    Transcribe audio file with WhisperX large-v3.
    Returns dict with segments, language info.
    """
    import whisperx

    print(f"  [stage2] Loading WhisperX {WHISPER_MODEL} ({COMPUTE_TYPE})...", flush=True)
    if config.DEVICE != "cpu":
        print(f"  [stage2] VRAM free: {vram_free_mb()}MB", flush=True)

    model = whisperx.load_model(
        WHISPER_MODEL,
        device=config.DEVICE,
        compute_type=COMPUTE_TYPE,
    )

    print("  [stage2] Model loaded. Transcribing...", flush=True)

    # Load audio
    audio = whisperx.load_audio(wav_path)

    # Transcribe with auto language detection
    # WhisperX 3.8.x API: VAD is built-in, returns TranscriptionResult (TypedDict)
    result = model.transcribe(
        audio,
        batch_size=BATCH_SIZE,
        language=WHISPER_LANGUAGE,  # None = auto-detect; env DHARMA_WHISPER_LANGUAGE forces
    )

    # TranscriptionResult is a TypedDict — access as dict
    language = result.get("language", "unknown")
    segments = result.get("segments", [])

    print(f"  [stage2] Detected language: {language}", flush=True)
    print(f"  [stage2] Segments: {len(segments)}", flush=True)

    # Free the ASR model
    del model
    flush_gpu()

    if config.DEVICE != "cpu":
        print(f"  [stage2] ASR model flushed. VRAM free: {vram_free_mb()}MB", flush=True)

    return {
        "language": language,
        "segments": segments,
    }


def transcribe_with_metadata(wav_path: str, source_name: str) -> dict | None:
    """Transcribe and wrap with metadata."""
    asr_result = transcribe_audio(wav_path)
    if asr_result is None:
        return None

    return {
        "source_file": source_name,
        "wav_path": wav_path,
        "transcribed_at": datetime.utcnow().isoformat() + "Z",
        "model": f"whisperx-{WHISPER_MODEL}",
        "compute_type": COMPUTE_TYPE,
        "detected_language": asr_result["language"],
        "segment_count": len(asr_result["segments"]),
        "segments": asr_result["segments"],
    }

"""Command-line interface for the dharma transcription pipeline.

Entry point: dharma-transcribe (installed via pip) or python -m dharma_transcribe.cli
"""

import os
import sys

# Force CPU mode before any torch/whisperx imports if --device cpu is specified.
# This must happen before ANY import that touches CUDA, otherwise PyTorch
# initializes the GPU context even when models are later moved to CPU.
if "--device" in sys.argv:
    _idx = sys.argv.index("--device")
    if _idx + 1 < len(sys.argv) and sys.argv[_idx + 1] == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""

import argparse
import hashlib
from pathlib import Path

from . import config
from .config import DEVICE as DEFAULT_DEVICE
from .config import HF_TOKEN_ENV
from .gpu import flush_gpu, vram_free_mb, vram_total_mb
from .ingest import find_media_files
from .pipeline import load_manifest, process_file, save_manifest


def main():
    """Parse CLI arguments and run the pipeline."""
    parser = argparse.ArgumentParser(
        description="Dharma Audio Transcription Pipeline — "
        "multilingual transcription for Buddhist teachings",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Single file or directory to process",
    )
    parser.add_argument(
        "--source-dir",
        default=None,
        help="Default source directory (overrides DHARMA_SOURCE_DIR env var)",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM correction stage (ASR transcription only)",
    )
    parser.add_argument(
        "--hf-token",
        default=os.environ.get(HF_TOKEN_ENV, ""),
        help="HuggingFace token (for pyannote diarization + model downloads)",
    )
    parser.add_argument(
        "--device",
        choices=["cuda", "cpu"],
        default=DEFAULT_DEVICE,
        help="Compute device: cuda (GPU) or cpu",
    )
    args = parser.parse_args()

    # Override device at runtime so all modules pick it up
    config.DEVICE = args.device

    # Print startup info
    print("Dharma Transcription Pipeline", flush=True)
    print(f"Device: {args.device}", flush=True)
    if args.device == "cpu":
        print("GPU: disabled (CPU mode)", flush=True)
    else:
        print(f"GPU: {vram_total_mb()}MB total, {vram_free_mb()}MB free", flush=True)
    print(f"LLM: {config.LLM_MODEL or 'disabled'}", flush=True)
    print(
        f"HF Token: {'provided' if args.hf_token else 'MISSING (diarization will be skipped)'}",
        flush=True,
    )

    # Determine input files
    if args.input:
        input_path = Path(args.input)
        if input_path.is_file():
            media_files = [input_path]
        elif input_path.is_dir():
            media_files = find_media_files(input_path)
        else:
            print(f"Error: {args.input} not found", file=sys.stderr)
            sys.exit(1)
    elif args.source_dir:
        media_files = find_media_files(Path(args.source_dir))
    else:
        print(
            "Error: no input specified. Provide a file/directory path or --source-dir.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not media_files:
        print("No media files found", flush=True)
        sys.exit(0)

    print(f"\nFound {len(media_files)} media file(s) to process", flush=True)

    # Load manifest for idempotency
    manifest = load_manifest()

    # Output-name collisions are fatal: two distinct source files sharing a
    # basename would overwrite each other's transcripts with no error. Detect
    # the whole set up front and fall back to a path-derived name per file.
    out_names = _resolve_output_names(media_files)

    failures: list[tuple[str, str]] = []
    for media_path in media_files:
        out_name = out_names[media_path]
        # Manifest key is the output name, NOT the bare filename: several source
        # files are literally `final.mp4`, and a basename key made them look like
        # one already-processed file.
        manifest_key = out_name

        # Skip already-processed files
        existing = manifest["files"].get(manifest_key, {})
        if existing.get("status") == "completed":
            print(f"\nSKIP (already processed): {out_name}", flush=True)
            continue

        # One bad file must not abort the batch — record it and continue.
        try:
            result = process_file(media_path, args.hf_token, args.skip_llm, out_name)
        except Exception as exc:  # noqa: BLE001 - deliberately broad; batch resilience
            print(f"\nERROR: {out_name} raised {type(exc).__name__}: {exc}", flush=True)
            result = {
                "status": "failed",
                "stage": "unhandled",
                "error": f"{type(exc).__name__}: {exc}",
                "source_file": media_path.name,
            }

        if result.get("status") == "failed":
            failures.append((out_name, str(result.get("error", "unknown"))))

        manifest["files"][manifest_key] = result
        save_manifest(manifest)

        # Flush GPU between files
        flush_gpu()

    # Summary
    print(f"\n{'=' * 60}", flush=True)
    print("PIPELINE COMPLETE", flush=True)
    print(f"{'=' * 60}", flush=True)
    completed = sum(1 for f in manifest["files"].values() if f.get("status") == "completed")
    failed = sum(1 for f in manifest["files"].values() if f.get("status") == "failed")
    print(f"  Completed: {completed}", flush=True)
    print(f"  Failed: {failed}", flush=True)

    if failures:
        print("\n  FAILURES THIS RUN:", flush=True)
        for name, err in failures:
            print(f"    {name}: {err}", flush=True)


def _resolve_output_names(media_files: list[Path]) -> dict[Path, str]:
    """Map each source file to a unique output-name stem.

    Two distinct source files can share a basename — e.g. a course that stores
    every lesson as ``<vimeo-id>/final.mp4``.  Keying outputs (or the manifest)
    on the bare filename makes those files collide: the second silently
    overwrites the first, and the manifest reports the first as already done.

    For each basename used by more than one file, prepend the parent directory
    name(s) until the stems are unique.  When even that cannot disambiguate, fall
    back to a short hash of the absolute path so correctness never depends on
    directory naming.
    """
    by_basename: dict[str, list[Path]] = {}
    for path in media_files:
        by_basename.setdefault(path.name, []).append(path)

    resolved: dict[Path, str] = {}
    for basename, paths in by_basename.items():
        if len(paths) == 1:
            resolved[paths[0]] = Path(basename).stem
            continue

        # Collision: widen the disambiguator until every stem is unique.
        for depth in range(1, 5):
            stems: dict[str, list[Path]] = {}
            for path in paths:
                parts = list(path.parent.parts[-depth:])
                stems.setdefault("-".join(parts + [Path(basename).stem]), []).append(path)
            if all(len(v) == 1 for v in stems.values()):
                for stem, (path,) in ((s, v) for s, v in stems.items()):
                    resolved[path] = stem
                break
        else:
            # Directory names were not enough — guarantee uniqueness by hash.
            for path in paths:
                digest = hashlib.sha256(str(path).encode()).hexdigest()[:8]
                resolved[path] = f"{Path(basename).stem}-{digest}"

    collisions = len(media_files) - len(set(resolved.values()))
    if collisions:
        raise RuntimeError(
            f"output-name resolution still produced {collisions} collision(s); "
            "refusing to run rather than overwrite transcripts"
        )
    return resolved


if __name__ == "__main__":
    main()

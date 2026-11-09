"""Batch driver for the 2026-11-08 transcription run.

Why a driver instead of `python -m dharma_transcribe <dir>`:

1. PER-FILE FAULT ISOLATION. cli.py calls process_file() with no try/except —
   one unreadable-but-probeable file aborts the entire batch. Over 70 files and
   ~33 h of audio that is unacceptable, so each file is wrapped here.
2. EXPLICIT skip_llm=True. The samaya gate requires Stage 6 (LLM post-correction
   via an external API) to be OFF for restricted lineage material. .env is
   currently inert, but a swapped .env must not silently re-enable it.
   Belt: this flag. Braces: DHARMA_LLM_* cleared in the environment below.
3. DHARMA_WHISPER_LANGUAGE=en. Recorded scar (2026-10-07 Shugendo): whisperx
   detects ONE language for the whole file from the opening seconds, and a
   Tibetan/Japanese narrator intro latched the full file into the wrong
   language, producing repetition loops. Sowa Rigpa 1.1 opens with ~2 minutes
   of Tibetan prayer before 40+ minutes of English teaching, so auto-detect is
   a live hazard here. Known cost, accepted: Tibetan prayer segments will be
   mangled as English — the teaching is what we need, and prayer text is
   already available in the archive as separate documents.
4. A driver-level log with an explicit per-file DONE marker, so "did it finish"
   is answerable from a file rather than from an impression.
"""

import contextlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# --- Gate everything BEFORE importing the pipeline ---------------------------
os.environ["DHARMA_WHISPER_LANGUAGE"] = "en"
os.environ["DHARMA_LLM_API_URL"] = ""
os.environ["DHARMA_LLM_API_KEY"] = ""
os.environ["DHARMA_LLM_MODEL"] = ""

PROJECT = Path("/home/guan/src/dharma-transcribe")
sys.path.insert(0, str(PROJECT / "src"))

from dharma_transcribe import config  # noqa: E402
from dharma_transcribe.gpu import flush_gpu  # noqa: E402
from dharma_transcribe.pipeline import load_manifest, process_file, save_manifest  # noqa: E402

LOG = Path(
    os.environ.get("DHARMA_BATCH_LOG", "/home/guan/src/dharma-transcribe/logs/batch-2026-11-08.log")
)


def say(msg: str):
    line = f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as fh:
        fh.write(line + "\n")


def main():
    # Optional argv[1]: alternate filelist, used for smoke tests.
    list_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (PROJECT / "staging" / "filelist.json")
    records = json.loads(list_path.read_text())
    hf_token = ""
    tokfile = Path.home() / ".cache" / "huggingface" / "token"
    if tokfile.exists():
        hf_token = tokfile.read_text().strip()

    say("=" * 70)
    say(f"BATCH START — {len(records)} files")
    say(
        f"  device={config.DEVICE} model={config.WHISPER_MODEL} "
        f"compute={config.COMPUTE_TYPE} batch={config.BATCH_SIZE}"
    )
    say(f"  whisper_language={config.WHISPER_LANGUAGE!r}  (forced 'en')")
    say(f"  LLM correction: DISABLED (model={config.LLM_MODEL!r}) — samaya gate")
    hf_note = "present (diarization on)" if hf_token else "MISSING (diarization skipped)"
    say(f"  HF token: {hf_note}")
    say("=" * 70)

    manifest = load_manifest()
    results = {"completed": [], "skipped": [], "failed": []}
    t0 = time.time()

    for i, rec in enumerate(records, 1):
        staged = Path(rec["staged"])
        key = staged.name
        say(f"\n--- [{i}/{len(records)}] {rec['set']}: {key}")

        if manifest["files"].get(key, {}).get("status") == "completed":
            say(f"    SKIP (manifest says completed): {key}")
            results["skipped"].append(key)
            continue

        try:
            result = process_file(staged, hf_token, skip_llm=True)
            manifest["files"][key] = result
            manifest["files"][key]["staged_from"] = rec["source"]
            manifest["files"][key]["batch"] = "2026-11-08"
            save_manifest(manifest)
            status = result.get("status")
            if status == "completed":
                dur = result.get("duration") or 0
                pt = result.get("processing_time") or 0
                say(
                    f"    COMPLETED {dur / 60:.1f} min audio in {pt / 60:.1f} min "
                    f"(ratio {pt / dur if dur else 0:.3f})"
                )
                results["completed"].append(key)
            else:
                say(f"    FAILED at stage {result.get('stage')}: {result.get('error')}")
                results["failed"].append((key, result.get("error")))
        except Exception as exc:  # noqa: BLE001 — deliberate: isolate one file
            say(f"    EXCEPTION — file skipped, batch continues: {exc}")
            say(traceback.format_exc())
            manifest["files"][key] = {
                "status": "failed",
                "stage": "driver-exception",
                "error": f"{type(exc).__name__}: {exc}",
                "staged_from": rec["source"],
                "batch": "2026-11-08",
            }
            save_manifest(manifest)
            results["failed"].append((key, str(exc)))
        finally:
            with contextlib.suppress(Exception):
                flush_gpu()

        # Progress heartbeat in wall-clock terms measured from this run only.
        elapsed = time.time() - t0
        done = len(results["completed"]) + len(results["failed"])
        if done and elapsed > 0:
            say(
                f"    [progress] {done}/{len(records)} attempted, "
                f"{elapsed / 60:.0f} min elapsed this run"
            )

    say("\n" + "=" * 70)
    say("BATCH COMPLETE")
    say(f"  completed: {len(results['completed'])}")
    say(f"  skipped  : {len(results['skipped'])}")
    say(f"  failed   : {len(results['failed'])}")
    for k, e in results["failed"]:
        say(f"    FAILED {k}: {e}")
    say(f"  total wall time this run: {(time.time() - t0) / 60:.1f} min")
    say("=" * 70)
    Path("/home/guan/src/dharma-transcribe/logs/batch-2026-11-08-result.json").write_text(
        json.dumps(results, indent=2)
    )
    say("DONE=0")


if __name__ == "__main__":
    main()

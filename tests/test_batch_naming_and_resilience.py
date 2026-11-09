"""Regression tests for the batch-resilience and naming-collision fixes.

Each test pins a defect that was found the hard way on the 2026-11-08 batch:

  * a source corpus where every lesson is stored as ``<vimeo-id>/final.mp4``
    produced colliding output filenames and a colliding manifest key, so the
    second file silently overwrote the first and the rest were "already done";
  * ``process_file`` was called with no guard, so one bad file aborted the run
    (a file with no audio stream killed the batch instead of being skipped);
  * ``scripts/run_batch.sh`` passed no ``--skip-llm``, leaving the samaya gate
    inert whenever the launcher was used.
"""

import re
from pathlib import Path

from dharma_transcribe.cli import _resolve_output_names


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


# --- output-name resolution ---------------------------------------------------


def test_unique_basenames_keep_their_stem(tmp_path):
    """Ordinary files must not be renamed — only collisions get disambiguated."""
    f = _touch(tmp_path / "course" / "1.+Introduction-480p.mp4")
    assert _resolve_output_names([f]) == {f: "1.+Introduction-480p"}


def test_colliding_final_mp4_files_get_distinct_stems(tmp_path):
    """The real corpus shape: one `final.mp4` per Vimeo directory."""
    files = [
        _touch(tmp_path / "videos" / "865789357.mp4" / "final.mp4"),
        _touch(tmp_path / "videos" / "865767813.mp4" / "final.mp4"),
        _touch(tmp_path / "videos" / "865790499.mp4" / "final.mp4"),
    ]
    names = _resolve_output_names(files)

    stems = list(names.values())
    assert len(set(stems)) == 3, f"stems collide: {stems}"
    # The vid directory is the natural discriminator and must survive in the name.
    assert "865789357" in names[files[0]]
    assert "865767813" in names[files[1]]
    assert "865790499" in names[files[2]]


def test_two_same_named_files_in_same_dir_still_differ(tmp_path):
    """Pathological case: identical basename AND parent name — must not collapse."""
    a = _touch(tmp_path / "one" / "final.mp4")
    b = _touch(tmp_path / "two" / "final.mp4")
    names = _resolve_output_names([a, b])
    assert len(set(names.values())) == 2


def test_resolution_is_total_and_collision_free(tmp_path):
    """Every input must map to exactly one unique stem."""
    # Distinct directories, each holding one same-named file — the real shape.
    files = [_touch(tmp_path / f"lesson{i}" / "final.mp4") for i in range(6)]
    files.append(_touch(tmp_path / "unique.mp4"))

    names = _resolve_output_names(files)

    assert set(names) == set(files)
    assert len(set(names.values())) == len(files), f"collisions: {sorted(names.values())}"


def test_outputs_are_written_under_the_override_name(tmp_path, monkeypatch, sample_transcript):
    """`out_name` must change the FILENAME only, never the provenance field."""
    from dharma_transcribe import output as out

    for attr in ("JSON_DIR", "SRT_DIR", "VTT_DIR", "TXT_DIR", "REVIEW_DIR"):
        d = tmp_path / attr
        d.mkdir()
        monkeypatch.setattr(out, attr, d)
    monkeypatch.setattr(out, "CONFIDENCE_THRESHOLD", 0.5)

    result = out.generate_all_outputs(
        sample_transcript, "final.mp4", "865789357-final"
    )

    assert Path(result["txt"]).name == "865789357-final.txt"
    assert Path(result["srt"]).name == "865789357-final.srt"
    assert Path(result["json"]).name == "865789357-final.json"
    # The override is FILENAME-ONLY: the transcript body (including whatever
    # provenance the caller put in it) is written through untouched.
    import json as _json

    data = _json.loads(Path(result["json"]).read_text())
    assert data["source_file"] == sample_transcript["source_file"]


# --- cli failure isolation ----------------------------------------------------


def test_cli_continues_after_an_exception(tmp_path, monkeypatch):
    """One raising file must be recorded as failed, not abort the batch."""
    import dharma_transcribe.cli as cli

    batch = tmp_path / "batch"
    batch.mkdir()
    good = _touch(batch / "good.mp4")
    bad = _touch(batch / "bad.mp4")

    monkeypatch.setattr(cli, "find_media_files", lambda _p: [bad, good])
    monkeypatch.setattr(cli, "vram_total_mb", lambda: 0)
    monkeypatch.setattr(cli, "vram_free_mb", lambda: 0)
    monkeypatch.setattr(cli, "flush_gpu", lambda: None)
    monkeypatch.setattr(cli, "load_manifest", lambda: {"files": {}})
    saved: dict = {}
    monkeypatch.setattr(cli, "save_manifest", lambda m: saved.update(m["files"]))

    def fake_process(media_path, hf_token="", skip_llm=False, out_name=None):
        if media_path.name == "bad.mp4":
            raise RuntimeError("boom")
        return {"status": "completed", "source_file": media_path.name}

    monkeypatch.setattr(cli, "process_file", fake_process)
    monkeypatch.setattr("sys.argv", ["dharma-transcribe", str(batch)])

    cli.main()

    assert saved["good"]["status"] == "completed"
    assert saved["bad"]["status"] == "failed"
    assert "RuntimeError" in saved["bad"]["error"]


# --- launcher samaya gate -----------------------------------------------------

def test_run_batch_script_skips_llm_by_default():
    """The launcher must never route restricted transcripts off-box by default."""
    script = Path(__file__).resolve().parent.parent / "scripts" / "run_batch.sh"
    text = script.read_text()

    assert "SKIP_LLM=1" in text, "launcher no longer defaults to skipping stage 6"
    assert "--allow-llm" in text, "launcher has no explicit opt-in for stage 6"
    # The flag must actually be forwarded to the python invocation.
    assert re.search(r'dharma_transcribe "\$INPUT".*EXTRA_ARGS', text), (
        "launcher does not forward accumulated args to the pipeline"
    )

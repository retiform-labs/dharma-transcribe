"""Place transcript sidecars next to each source video, then report.

NAMING RULE (stated deliberately, because it is a real choice):
  * default: <source video stem>.txt / .srt — the subtitle sidecar convention.
    `2.+Rin-480p.mp4` -> `2.+Rin-480p.txt` beside it. Predictable, and it
    survives someone re-ordering or re-filing the videos.
  * EXCEPTION: the three Sowa Rigpa 1.1 videos are each literally named
    `final.mp4` inside `videos/<vimeo-id>.mp4/`. `final.txt` conveys nothing,
    so those get the canonical descriptive stem instead
    (`sowarigpa-1-1-01-main-introduction.txt`). The directory keeps them apart,
    and the label makes them usable.

OWNERSHIP: sidecars are installed as mononofu:mononofu 0644, NOT root. The
library is Freeman's; a root-owned file dropped in it is a small act of
disrespect that he would have to clean up later.

RUN AS: sudo -n python3 scripts/sidecar_2026_11_09.py [--apply]
"""

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path("/home/guan/src/dharma-transcribe")
OUT_TXT = ROOT / "output" / "txt"
OUT_SRT = ROOT / "output" / "srt"

SOWA_DESCRIPTIVE = {
    "865789357": "sowarigpa-1-1-01-main-introduction",
    "865767813": "sowarigpa-1-1-02-learnworlds-platform-tour",
    "865790499": "sowarigpa-1-1-03-module-1-teaching-and-qa",
}

APPLY = "--apply" in sys.argv
OWNER = "mononofu"


def sidecar_stem(source: Path) -> str:
    """Decide the sidecar name for one source video."""
    if source.name == "final.mp4":
        vimeo = source.parent.name.split(".")[0]  # "865789357.mp4" -> "865789357"
        return SOWA_DESCRIPTIVE.get(vimeo, f"final-{vimeo}")
    return source.stem


def main():
    records = json.loads((ROOT / "staging" / "filelist.json").read_text())
    result = json.loads((ROOT / "logs" / "batch-2026-11-08-result.json").read_text())
    done = set(result["completed"]) | set(result["skipped"])

    plan, problems = [], []
    for rec in records:
        staged = Path(rec["staged"])
        if staged.name not in done:
            continue  # the one failure — nothing to place
        stem = staged.stem
        txt = OUT_TXT / f"{stem}.txt"
        srt = OUT_SRT / f"{stem}.srt"
        if not txt.exists() or txt.stat().st_size == 0:
            problems.append(f"MISSING TXT {stem}")
            continue
        source = Path(rec["source"])
        if not source.exists():
            problems.append(f"MISSING SOURCE {source}")
            continue
        dest_stem = sidecar_stem(source)
        plan.append(
            {
                "set": rec["set"],
                "source": str(source),
                "stem": dest_stem,
                "txt_from": str(txt),
                "srt_from": str(srt) if srt.exists() else None,
            }
        )

    print(f"sources to receive sidecars: {len(plan)}")
    print(f"problems: {len(problems)}")
    for p in problems:
        print("   ", p)

    # collision check within each destination directory
    seen = {}
    for item in plan:
        d = Path(item["source"]).parent
        for ext in (".txt", ".srt"):
            key = (str(d), item["stem"] + ext)
            seen.setdefault(key, []).append(item["source"])
    dups = {k: v for k, v in seen.items() if len(v) > 1}
    print(f"destination collisions: {dups or 'NONE'}")
    if dups:
        sys.exit("COLLISION — refusing")

    # naming sample
    print("\nsample mapping:")
    for item in plan[:3]:
        print(f"   {Path(item['source']).name}  ->  {item['stem']}.txt")
    for item in plan:
        if item["set"] == "sowarigpa-1-1":
            rel = Path(item["source"]).parent.relative_to(
                Path("/media/mononofu/wd20tb/home/mononofu/shared/Library/sowarigpa/archive")
            )
            print(f"   [sowa] {rel}/final.mp4  ->  {item['stem']}.txt")

    with (ROOT / "logs" / "sidecar_plan.json").open("w") as fh:
        json.dump(plan, fh, indent=2)
    print("\nplan written to logs/sidecar_plan.json")

    if not APPLY:
        print("\nDRY RUN — pass --apply to write")
        return

    written = 0
    for item in plan:
        dest_dir = Path(item["source"]).parent
        for src_key, ext in (("txt_from", ".txt"), ("srt_from", ".srt")):
            src = item[src_key]
            if not src:
                continue
            dest = dest_dir / (item["stem"] + ext)
            tmp = dest_dir / (".guan_tmp_" + item["stem"] + ext)
            shutil.copyfile(src, tmp)
            os.chmod(tmp, 0o644)
            shutil.chown(tmp, user=OWNER, group=OWNER)
            os.replace(tmp, dest)
            written += 1

    print(f"\nWROTE {written} sidecar files")
    print("DONE=0")


if __name__ == "__main__":
    main()

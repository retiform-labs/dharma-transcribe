"""Stage symlinks with canonical unique names for the 2026-11-08 batch.

Why this exists rather than a code change: the pipeline keys BOTH the manifest
entry and every output file on the bare basename/stem. Three Sowa Rigpa videos
are each named final.mp4, so they collapse to one manifest key (already marked
completed -> all three would be SKIPPED) and one output stem (each would
overwrite the last). Staging via symlink fixes naming with zero code change to
the shipped pipeline and zero risk to the 196-entry manifest.
"""

import json
import os
import re
import sys
from pathlib import Path

KJ = Path(
    "/media/mononofu/Samsung 990 EVO/home/mononofu/Shared/Library/"
    "Blue Lotus Assembly/Kuji Remote Learning Workshops/1 - Kuji-In"
)
IS = Path("/media/mononofu/Samsung 990 EVO/home/mononofu/Shared/Library/Intuitive Specialists")
SW = Path("/media/mononofu/wd20tb/home/mononofu/shared/Library/sowarigpa/archive")
STAGE = Path("/home/guan/src/dharma-transcribe/staging")
EXT = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4a", ".mp3", ".wav"}

SOWA_MAP = {
    "865789357": "01-main-introduction",
    "865767813": "02-learnworlds-platform-tour",
    "865790499": "03-module-1-teaching-and-qa",
}


def slug(text: str) -> str:
    text = text.replace("+", " ")
    text = re.sub(r"[^A-Za-z0-9]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-").lower()


def walk(root: Path):
    for dirpath, _, filenames in os.walk(root):
        for f in sorted(filenames):
            if Path(f).suffix.lower() in EXT:
                yield Path(dirpath) / f


def stage(src: Path, dest_dir: Path, name: str, setname: str, records: list):
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (name + src.suffix.lower())
    if dest.exists() or dest.is_symlink():
        dest.unlink()
    dest.symlink_to(src)
    records.append({"set": setname, "staged": str(dest), "source": str(src)})


def main():
    records = []

    # --- Kuji-In workshops: 15 numbered segments ---
    for p in walk(KJ):
        m = re.match(r"^(\d+)\.\s*(.+?)-480p$", p.stem)
        if not m:
            print("UNPARSED kuji:", p.name, file=sys.stderr)
            continue
        num, title = m.group(1), m.group(2)
        stage(p, STAGE / "kuji-in", f"kuji-in-{int(num):02d}-{slug(title)}", "kuji-in", records)

    # --- Lori Williams / Intuitive Specialists: 51 videos, keep module/chapter ---
    for p in walk(IS):
        rel = p.relative_to(IS)
        parts = list(rel.parts)
        if parts[0] == "CRV Masterclass":
            name = "lori-masterclass-" + slug(p.stem)
        else:
            mod = re.search(r"Module\s*(\d+)", parts[1]) if len(parts) > 2 else None
            mnum = mod.group(1) if mod else "0"
            chap = ""
            if len(parts) >= 3:
                ch = re.match(r"^Chapter\s*(\d+)([ab]?)", parts[2])
                if ch:
                    chap = f"ch{int(ch.group(1)):02d}{ch.group(2)}-"
            name = f"lori-m{mnum}-{chap}{slug(p.stem)}"
        stage(p, STAGE / "lori-williams", name, "lori-williams", records)

    # --- Sowa Rigpa 1.1: 3 numbered videos use the SAME basename; map explicitly ---
    for p in walk(SW / "18-module-1-1-intro" / "videos"):
        vid = p.parent.name.split(".")[0]
        label = SOWA_MAP.get(vid)
        if not label:
            print("UNMAPPED sowa video:", vid, file=sys.stderr)
            continue
        stage(p, STAGE / "sowarigpa-1-1", f"sowarigpa-1-1-{label}", "sowarigpa-1-1", records)
    for p in walk(SW / "18-module-1-1-mentor-meeting-2025-10-18"):
        stage(
            p,
            STAGE / "sowarigpa-1-1",
            "sowarigpa-1-1-04-mentor-meeting-2025-10-18",
            "sowarigpa-1-1",
            records,
        )

    # --- verify: unique staged basenames AND unique stems, globally ---
    byname, bystem = {}, {}
    for r in records:
        b = Path(r["staged"]).name
        s = Path(r["staged"]).stem
        byname.setdefault(b, []).append(r["source"])
        bystem.setdefault(s, []).append(r["source"])
    dupn = {k: v for k, v in byname.items() if len(v) > 1}
    dups = {k: v for k, v in bystem.items() if len(v) > 1}
    print(f"staged {len(records)} files")
    print(f"duplicate basenames: {dupn or 'NONE'}")
    print(f"duplicate stems:     {dups or 'NONE'}")
    if dupn or dups:
        sys.exit("COLLISION — refusing to write the list")

    # --- verify no staged stem already has an output/txt (would overwrite) ---
    txtdir = Path("/home/guan/src/dharma-transcribe/output/txt")
    existing = {q.stem for q in txtdir.glob("*.txt")}
    clash = sorted(s for s in bystem if s in existing)
    print(f"stems colliding with existing output/txt: {clash or 'NONE'}")

    out = Path("/home/guan/src/dharma-transcribe/staging/filelist.json")
    out.write_text(json.dumps(records, indent=2))
    print("wrote", out)

    # mark bad chars for shell safety awareness (driver uses argv list, so advisory only)
    odd = [Path(r["staged"]).name for r in records if re.search(r"[:\'\"]", Path(r["staged"]).name)]
    print(f"staged names containing : or quotes: {odd or 'NONE'}")


if __name__ == "__main__":
    main()

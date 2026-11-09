import shutil
from pathlib import Path

MODULE = Path(
    "/media/mononofu/Samsung 990 EVO/home/mononofu/Shared/Library/"
    "Intuitive Specialists/Practical Remote Viewing/Module 6: Home Stretch"
)
SOURCE_STEM = "Chapter 38: It\u2019s Your Turn"   # U+2019, exact video stem
WORK_STEM = "lori-m6-ch38-chapter-38-it-s-your-turn"

SIDE_STEM = "Chapter 38: It\u2019s Your Turn"

pairs = [
    (Path(f"output/txt/{WORK_STEM}.txt"), MODULE / f"{SIDE_STEM}.txt"),
    (Path(f"output/srt/{WORK_STEM}.srt"), MODULE / f"{SIDE_STEM}.srt"),
]
for src, dest in pairs:
    if not src.is_file():
        raise SystemExit(f"MISSING SOURCE: {src}")
    if dest.exists():
        raise SystemExit(f"REFUSING TO OVERWRITE: {dest}")
    shutil.copyfile(src, dest)
    print(f"{src.name}  ->  {dest.name}  ({dest.stat().st_size} B)")

# verify video stem matches exactly
vids = [p for p in MODULE.glob("*.mp4") if "Chapter 38" in p.name]
print("\nvideo:", [p.name for p in vids])
print("sidecars now present:", sorted(p.name for p in MODULE.glob("Chapter 38*")))

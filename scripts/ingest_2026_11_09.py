#!/usr/bin/env python3
"""Ingest the 2026-11-08 batch transcripts into paperless-ngx.

DRY RUN by default; --apply posts.  --only <stem> restricts to one stem.
Idempotent: any transcript whose sha256 already exists in paperless is skipped.

Kuji ordinals are MEASURED from the transcript text, not inferred from the
filename (file numbers are workshop sequence, not kuji number).
"""
import json, hashlib, sys, urllib.request, urllib.error, uuid
from pathlib import Path

URL  = "http://127.0.0.1:65316"
KEY  = "1798b37a9edbe3c1a900bafe65d46a57f048c836"
PROJ = Path("/home/guan/src/dharma-transcribe")
CREATED = "2026-11-08"

DT_TRANSCRIPT = 3
T_DHARMA, T_BLA, T_LINEAGE, T_KUJI, T_SOWA, T_PERCEPTION = 1, 2, 3, 11, 14, 17
C_HAYES, C_SOWA, C_LORI = 1, 59, 118

# stem-key -> (short name, kuji ordinal or None)
# ordinal evidence: grep of the transcript for "Kuji N" / "Nth kuji"
KUJI = {
    "01-introduction": ("Introduction", None),
    "02-rin":  ("Rin", 1),   # "very brief view of Kuji 1"
    "03-pyo":  ("Pyo", 2),   # "let's dive into kuji 2"
    "04-toh":  ("Toh", 3),   # "Kuji 3 is riding, I call it riding the dragon"
    "05-a-word-about-our-internal-state": ("A Word About Our Internal State", None),
    "06-sha":  ("Sha", 4),   # "Kuji 4 is restoration of health"
    "07-kai":  ("Kai", 5),   # "fifth kuji"
    "08-jin":  ("Jin", 6),   # "sixth kuji"
    "09-on-changing-our-brain": ("On Changing Our Brain", None),
    "10-on-beliefs-resistance-and-experience": ("On Beliefs, Resistance and Experience", None),
    "11-retsu": ("Retsu", 7),   # "Kuji 7, seeing another place, another time"
    "12-zai":  ("Zai", 8),      # "kuji number eight"
    "13-on-how-systems-evolve-over-time": ("On How Systems Evolve Over Time", None),
    "14-zen":  ("Zen", 9),      # "Ninth Kuji"
    "15-closing-thoughts": ("Closing Thoughts", None),
}

SOWA = {
    "sowarigpa-1-1-01-main-introduction": ("Video 01", "Main Introduction"),
    "sowarigpa-1-1-02-learnworlds-platform-tour": ("Video 02", "LearnWorlds Platform Tour"),
    "sowarigpa-1-1-03-module-1-teaching-and-qa": ("Video 03", "Module 1 Teaching and Q&A"),
    "sowarigpa-1-1-04-mentor-meeting-2025-10-18": ("Video 04", "Mentor Meeting 2025-10-18"),
}

LORI_CH = {
 "m1-ch01-0-introduction": "Introduction",
 "m1-ch02-chapter-2-what-is-crv": "What Is CRV",
 "m1-ch03-basic-definitions-part-i": "Basic Definitions, Part I",
 "m1-ch04-basic-definitions-part-ii": "Basic Definitions, Part II",
 "m1-ch05-chapter-5-lining-up-your-thinking": "Lining Up Your Thinking",
 "m1-ch06-chapter-6-a-martial-art-of-the-mind": "A Martial Art of the Mind",
 "m1-ch07-chapter-7-prepping-for-your-session": "Prepping for Your Session",
 "m2-ch08-coordinate-elements": "Coordinate Elements",
 "m2-ch09-ideograms-the-secret-language-of-the-subconscious": "Ideograms: The Secret Language of the Subconscious",
 "m2-ch10-ideograms-part-2": "Ideograms, Part 2",
 "m2-ch11-ideograms-part-3": "Ideograms, Part 3",
 "m2-ch12-ideograms-part-4": "Ideograms, Part 4",
 "m2-ch13-ideograms-part-5": "Ideograms, Part 5",
 "m2-ch14-p1-practice": "P1 Practice",
 "m3-ch15-review-of-section-1-and-2": "Review of Sections 1 and 2",
 "m3-ch16-the-full-phase-one-session": "The Full Phase One Session",
 "m3-ch17a-the-rules-of-taking-breaks": "The Rules of Taking Breaks",
 "m3-ch17b-complete-demo-session-summary-scoring": "Complete Demo Session: Summary and Scoring",
 "m3-ch18-doing-your-own-p1-target": "Doing Your Own P1 Target",
 "m3-ch19-what-to-do-now": "What to Do Now",
 "m3-ch20-how-to-squeeze-in-time-to-practice-part-1": "How to Squeeze in Time to Practice, Part 1",
 "m3-ch21-how-to-squeeze-in-time-to-practice-part-2": "How to Squeeze in Time to Practice, Part 2",
 "m4-ch22-chapter-22-viewing-for-yourself": "Viewing for Yourself",
 "m4-ch23-chapter-23-how-to-squeeze-in-time-to-practice": "How to Squeeze in Time to Practice",
 "m4-ch24-chapter-24-your-magical-senses": "Your Magical Senses",
 "m4-ch25-chapter-25-dimensions-of-the-target": "Dimensions of the Target",
 "m4-ch26-chapter-26-warnings-and-detoxing": "Warnings and Detoxing",
 "m4-ch27-chapter-27-everything-is-important": "Everything Is Important",
 "m4-ch28-chapter-28-do-a-p2-target": "Do a P2 Target",
 "m5-ch29-chapter-29-review-of-sections-one-through-four": "Review of Sections One Through Four",
 "m5-ch30-chapter-30-time-loops-and-other-obstacles": "Time Loops and Other Obstacles",
 "m5-ch31-chapter-31-the-turning-point-in-every-session": "The Turning Point in Every Session",
 "m5-ch32-chapter-32-more-about-the-ai": "More About the AI",
 "m5-ch33-chapter-33-helpful-exercises-and-tips-part-1": "Helpful Exercises and Tips, Part 1",
 "m5-ch34-chapter-34-helpful-exercises-and-tips-part-2": "Helpful Exercises and Tips, Part 2",
 "m5-ch35-chapter-35-your-turn": "Your Turn",
 "m6-ch36-chapter-36-phase-3-part-1": "Phase 3, Part 1",
 "m6-ch37-chapter-37-phase-3-part-2": "Phase 3, Part 2",
 "m6-ch38-chapter-38-it-s-your-turn": "It’s Your Turn!",
 "m6-ch39-chapter-39-summary-writing": "Summary Writing",
 "m6-ch40-chapter-40-scoring-and-datasheets": "Scoring and Datasheets",
 "m6-ch41-chapter-41-psychometry-and-detoxing": "Psychometry and Detoxing",
 "m6-ch42-chapter-42-post-session-analysis-and-where-do-we-go-from-here":
     "Post-Session Analysis and Where Do We Go From Here",
}

def api(path, data=None, method=None, headers=None):
    r = urllib.request.Request(URL + path, data=data, method=method,
                               headers={"Authorization": f"Token {KEY}", **(headers or {})})
    return json.load(urllib.request.urlopen(r, timeout=300))

def build_meta(stem):
    """(title, correspondent_id, [tag_ids])"""
    if stem.startswith("kuji-in-"):
        key = stem[len("kuji-in-"):]
        name, ordn = KUJI[key]
        num = key[:2]
        suffix = f" (Kuji {ordn})" if ordn else ""
        return (f"Blue Lotus Assembly — Kuji-In Workshop {num}: {name}{suffix} — lineage teaching",
                C_HAYES, [T_DHARMA, T_BLA, T_LINEAGE, T_KUJI])
    if stem.startswith("sowarigpa-"):
        lab, name = SOWA[stem]
        return (f"Sowa Rigpa — Foundations Module 1.1, {lab}: {name} — transcript",
                C_SOWA, [T_DHARMA, T_SOWA])
    if stem.startswith("lori-masterclass-"):
        seg = stem[len("lori-masterclass-"):]
        if seg.startswith("coordinates"):
            t = "Lori Williams — CRV Masterclass: Coordinates Introduction — transcript"
        elif seg.startswith("qa-"):
            t = f"Lori Williams — CRV Masterclass, Q&A {seg[-1]} — transcript"
        elif seg.startswith("part-"):
            t = f"Lori Williams — CRV Masterclass, Part {seg[-1]} — transcript"
        else:
            raise ValueError(stem)
        return (t, C_LORI, [T_PERCEPTION])
    if stem.startswith("lori-"):
        key = stem[len("lori-"):]                       # e.g. m1-ch01-0-introduction
        if key not in LORI_CH:
            raise KeyError(f"no chapter title mapped for {key}")
        mod, ch = key.split("-", 1)                     # mod="m1", ch="ch01-0-introduction"
        chid = ch.split("-", 1)[0].replace("ch", "")    # "01", "17a"
        title = (f"Lori Williams — Practical Remote Viewing, "
                 f"{mod.upper()} Ch{chid}: {LORI_CH[key]} — transcript")
        return (title, C_LORI, [T_PERCEPTION])
    raise ValueError(f"unmapped stem: {stem}")

def main():
    apply = "--apply" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    res = json.load(open(PROJ / "logs/batch-2026-11-08-result.json"))
    stems = [n.rsplit(".", 1)[0] for n in res["completed"]] + \
            [n.rsplit(".", 1)[0] for n in res["skipped"]]
    if only:
        if only in stems:
            stems = [only]
        elif (PROJ / "output/txt" / (only + ".txt")).is_file():
            # A retry produced a transcript the batch result never recorded.
            print(f"-- {only} is not in the batch result but its .txt exists; "
                  f"ingesting it anyway")
            stems = [only]
        else:
            print(f"!! stem not in batch result and no transcript on disk: {only}")
            return 1

    existing = set()
    page = 1
    while True:
        d = api(f"/api/documents/?page={page}&page_size=200")
        for doc in d["results"]:
            vs = doc.get("versions") or []
            if vs and vs[0].get("checksum"):
                existing.add(vs[0]["checksum"])
        if not d["next"]:
            break
        page += 1
    print(f"existing docs scanned: {len(existing)} distinct checksums")

    plan, dup, bad = [], [], []
    for stem in sorted(stems):
        p = PROJ / "output/txt" / (stem + ".txt")
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        try:
            title, corr, tags = build_meta(stem)
        except (KeyError, ValueError) as e:
            bad.append((stem, str(e))); continue
        if len(title) > 128:
            bad.append((stem, f"title {len(title)} chars > 128: {title}")); continue
        row = dict(stem=stem, path=str(p), sha256=h, title=title,
                   correspondent=corr, tags=tags, created=CREATED)
        (dup if h in existing else plan).append(row)

    print(f"\nALREADY PRESENT: {len(dup)}")
    for r in dup: print(f"   {r['stem']}")
    if bad:
        print(f"\n!! UNMAPPED / INVALID: {len(bad)}")
        for s, e in bad: print(f"   {s}: {e}")
    print(f"\nTO POST: {len(plan)}")
    for r in plan: print(f"   [{len(r['title']):3}] corr={r['correspondent']:<3} {r['title']}")
    json.dump(plan, open(PROJ / "logs/ingest_plan_2026_11_09.json", "w"), indent=1)

    if bad:
        print("\nREFUSING: unmapped stems or over-length titles must be fixed first.")
        return 1
    if not apply:
        print("\nDRY RUN — nothing posted. Re-run with --apply.")
        return 0

    ok, fail = [], []
    for i, r in enumerate(plan, 1):
        body = Path(r["path"]).read_bytes()
        b = uuid.uuid4().hex
        parts = []
        for k, v in (("title", r["title"]), ("created", r["created"]),
                     ("correspondent", str(r["correspondent"])),
                     ("document_type", str(DT_TRANSCRIPT))):
            parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        for t in r["tags"]:
            parts.append(f'--{b}\r\nContent-Disposition: form-data; name="tags"\r\n\r\n{t}\r\n'.encode())
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="document"; '
                     f'filename="{r["stem"]}.txt"\r\nContent-Type: text/plain\r\n\r\n'.encode()
                     + body + b"\r\n")
        parts.append(f"--{b}--\r\n".encode())
        try:
            api("/api/documents/post_document/", data=b"".join(parts), method="POST",
                headers={"Content-Type": f"multipart/form-data; boundary={b}"})
            ok.append(r["stem"]); print(f"  [{i}/{len(plan)}] posted {r['stem']}")
        except urllib.error.HTTPError as e:
            fail.append((r["stem"], f"HTTP {e.code}: {e.read()[:200]}"))
            print(f"  [{i}/{len(plan)}] FAILED {r['stem']} HTTP {e.code}")
        except Exception as e:
            fail.append((r["stem"], repr(e)))
            print(f"  [{i}/{len(plan)}] FAILED {r['stem']} {e!r}")

    print(f"\n=== POSTED {len(ok)}/{len(plan)}   FAILED {len(fail)} ===")
    for s, e in fail: print("  FAIL", s, e)
    json.dump({"ok": ok, "fail": fail},
              open(PROJ / "logs/ingest_result_2026_11_09.json", "w"), indent=1)
    return 0 if not fail else 2

if __name__ == "__main__":
    sys.exit(main())

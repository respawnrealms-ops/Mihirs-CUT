"""Check saved template choices, speech timing, and real libass output for every look."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, ".")

WORDS = [{"w": "Lets", "s": 0.5, "e": 0.9}, {"w": "clip", "s": 1.0, "e": 1.4},
         {"w": "this!", "s": 1.5, "e": 2.1}]
LEGACY = {"bounce": "467824ba0223c3b4e5e5296f91845f45ff5707174e7863669892da82fd1302fe",
          "hype": "4f637b72ff5656d061bafd185c95ae71cb5815f841efa7a16f022cc2fc45836d",
          "clean": "a3d066f37401862f9d10e318371963b42e309851c87d75da319a29d8c927a9ad"}


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS " + name)


def frame(folder, subtitle, at=1.6):
    proc = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=0x243545:s=360x640:r=20",
                           "-vf", f"setpts=PTS+{at}/TB,ass={subtitle}:fontsdir=f", "-frames:v", "1",
                           "-threads", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                          cwd=folder, capture_output=True, timeout=30)
    if proc.returncode:
        raise AssertionError(proc.stderr.decode(errors="replace")[-1000:])
    return np.frombuffer(proc.stdout, dtype=np.uint8).reshape(640, 360, 3)


def main(folder):
    os.environ.update(PEAKCUT_DATA=str(folder / "data"), DATABASE_URL="", PEAKCUT_ACCOUNTS="0")
    from studio import auth, creators, ctx, db, jobs, render

    render.install_fonts()
    (folder / "f").mkdir()
    import shutil
    for font in (Path(render.__file__).parent / "fonts").glob("*.ttf"):
        shutil.copyfile(font, folder / "f" / font.name)
    check("fifteen caption templates are available", len(render.STYLES) >= 15)
    previews = render.style_previews()
    check("every template has a picker preview", previews.keys() == render.STYLES.keys())
    check("preview colours match the video colours", previews["neon"]["active"] == "#44EEFF")
    for style, expected in LEGACY.items():
        text = render.build_ass(WORDS, 0, 3, "GO TIME", style, ["clip"], 300, 1350)
        check(f"{style}: original captions are unchanged", hashlib.sha256(text.encode()).hexdigest() == expected)

    (folder / "blank.ass").write_text(render.build_ass([], 0, 3, "", "bounce", [], 300, 1350), encoding="utf-8")
    blank = frame(folder, "blank.ass")
    pictures = {}
    for style in render.STYLES:
        subtitle = folder / (style + ".ass")
        subtitle.write_text(render.build_ass(WORDS, 0, 3, "", style, [], 300, 1350), encoding="utf-8")
        image = frame(folder, subtitle.name)
        changed = np.any(np.abs(image.astype(int) - blank.astype(int)) > 12, axis=2)
        yy, xx = np.where(changed)
        check(f"{style}: real captions render inside the safe frame",
              len(xx) > 60 and xx.min() >= 3 and xx.max() < 357 and yy.min() > 350 and yy.max() < 550)
        check(f"{style}: nothing appears before speech or after the phrase",
              np.array_equal(frame(folder, subtitle.name, 0.2), blank)
              and np.array_equal(frame(folder, subtitle.name, 2.7), blank))
        pictures[style] = hashlib.sha256(image.tobytes()).hexdigest()
    check("the fifteen templates have distinct rendered looks", len(set(pictures.values())) == len(pictures))

    typewriter = render.build_ass(WORDS, 0, 3, "", "typewriter", [], 300, 1350)
    check("typewriter reveals letters without showing future words", "}L\n" in typewriter and "}Le\n" in typewriter
          and not any(",0:00:00.50," in line and line.endswith("clip") for line in typewriter.splitlines()))
    check("karaoke uses timed word fills", "\\kf40" in render.build_ass(WORDS, 0, 3, "", "karaoke", [], 300, 1350))
    long = [{"w": "EXTRAORDINARILYLONGGAMINGREACTION", "s": 0.5, "e": 2.1}]
    for style in ("boxed", "marker", "neon", "one_word"):
        name = style + "-long.ass"
        (folder / name).write_text(render.build_ass(long, 0, 3, "", style, [], 300, 1350), encoding="utf-8")
        image = frame(folder, name)
        xx = np.where(np.any(np.abs(image.astype(int) - blank.astype(int)) > 12, axis=2))[1]
        check(f"{style}: long words fit without touching the frame edge", len(xx) > 60 and xx.min() > 1 and xx.max() < 358)

    db.init()
    try:
        with ctx.as_user(auth.local_user().id):
            for style in render.STYLES:
                creator = creators.create({"name": "Template " + style, "style": style})
                source = {"type": "file", "name": "Template check"}
                video = jobs.create(source, {}, enqueue=False, creator=creator["id"])
                live = jobs.create(source, {}, enqueue=False, creator=creator["id"], kind="live")
                check(f"{style}: saved creator choice reaches videos and live clips",
                      creators.get(creator["id"])["style"] == style
                      and video["options"]["style"] == style and live["options"]["style"] == style)
    finally:
        db.engine.dispose()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="pc-looks-") as path:
        main(Path(path))

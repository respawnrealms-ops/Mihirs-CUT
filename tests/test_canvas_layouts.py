"""Render centred videos on plain canvases and check the title/caption bands."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import numpy as np

sys.path.insert(0, ".")
WORDS = [{"w": "WORDS", "s": 0.1, "e": 0.6}, {"w": "BELOW", "s": 0.65, "e": 1.1}]


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS " + name)


def command(args, **kwargs):
    proc = subprocess.run(args, capture_output=True, timeout=90, **kwargs)
    if proc.returncode:
        raise AssertionError(proc.stderr.decode(errors="replace")[-1200:])
    return proc.stdout


def decode(path):
    raw = command(["ffmpeg", "-v", "error", "-ss", "0.8", "-i", str(path), "-frames:v", "1",
                   "-threads", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
    return np.frombuffer(raw, dtype=np.uint8).reshape(1920, 1080, 3)


def main(work):
    os.environ.update(PEAKCUT_DATA=str(work / "data"), DATABASE_URL="", PEAKCUT_ACCOUNTS="0")
    from studio import auth, config, creators, ctx, db, jobs, render

    render.install_fonts()
    source = work / "source.mp4"
    command(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "color=c=red:s=640x360:r=8,drawbox=x=320:y=0:w=320:h=180:c=blue:t=fill,"
             "drawbox=x=0:y=180:w=320:h=180:c=lime:t=fill,drawbox=x=320:y=180:w=320:h=180:c=yellow:t=fill",
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000", "-t", "1.3", "-c:v", "libx264",
             "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)])
    before = copy.deepcopy(render.STYLES)
    with patch.object(config, "OUT_FPS", 8), patch.object(render, "_qsv_ok", False):
        for layout, theme in render.CANVASES.items():
            got, height, title_y, caption_y = render.geometry(640, 360, layout)
            check(f"{layout}: title and captions sit outside the video", got == layout and title_y < (1920-height)//2
                  and caption_y > (1920+height)//2)
            clip = {"start": 0, "end": 1.2, "hook": "TITLE ABOVE", "style": "bounce", "layout": layout}
            result = render.render_clip(source, work / "clips", layout, clip, WORDS, 640, 360)
            image = decode(work / "clips" / result["file"])
            expected = np.array([int(theme["color"][i:i+2], 16) for i in (0,2,4)])
            check(f"{layout}: the background is the selected plain colour", np.max(np.abs(image[40,40].astype(int)-expected)) < 10)
            tl, tr, bl, br = (image[y,x].astype(int) for x,y in [(180,790),(900,790),(180,1120),(900,1120)])
            check(f"{layout}: all four source corners are kept", tl[0] > 180 and tl[1] < 60 and tr[2] > 180
                  and bl[1] > 180 and br[0] > 180 and br[1] > 180)
            title = image[title_y-110:title_y+110, 100:980].astype(int)
            captions = image[caption_y-100:caption_y+100, 100:980].astype(int)
            check(f"{layout}: readable title above and captions below are encoded",
                  np.count_nonzero(np.max(np.abs(title-expected), axis=2) > 45) > 500
                  and np.count_nonzero(np.max(np.abs(captions-expected), axis=2) > 45) > 500)
            info = json.loads(command(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json", str(work / "clips" / result["file"])]))
            check(f"{layout}: output retains portrait video and audio", any(s.get("width") == 1080 and s.get("height") == 1920 for s in info["streams"])
                  and any(s.get("codec_type") == "audio" for s in info["streams"]))
            check(f"{layout}: saved choice is preserved", result["layout"] == layout and result["rendered_layout"] == layout)
            for width, height in [(360,640),(640,640)]:
                check(f"{layout}: portrait and square inputs keep the canvas {width}x{height}", render.geometry(width,height,layout)[0] == layout)

        portrait = work / "portrait.mp4"
        command(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-vf", "transpose=1", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy", str(portrait)])
        result = render.render_clip(portrait, work / "clips", "portrait", {"start":0,"end":1,"hook":"TITLE ABOVE","layout":"canvas_white","captions":False}, [], 360, 640)
        image = decode(work / "clips" / result["file"])
        check("portrait footage is centred with plain side margins", np.all(image[960,50] > 240) and np.all(image[960,1030] > 240)
              and image[960,400].min() < 80)
        check("captions off keeps the title and the lower band empty", np.all(image[1500:1750] > 240)
              and np.any(image[200:400] < 80))

    (work / "f").mkdir()
    import shutil
    for font in (Path(render.__file__).parent / "fonts").glob("*.ttf"):
        shutil.copyfile(font, work / "f" / font.name)
    for style in render.STYLES:
        ass = render.build_ass(WORDS,0,1.3,"TITLE ABOVE",style,[],400,1400,canvas=render.CANVASES["canvas_white"])
        (work / "contrast.ass").write_text(ass,encoding="utf-8")
        raw=command(["ffmpeg","-v","error","-f","lavfi","-i","color=white:s=360x640:r=8","-vf","setpts=PTS+0.8/TB,ass=contrast.ass:fontsdir=f","-frames:v","1","-threads","1","-pix_fmt","rgb24","-f","rawvideo","-"],cwd=work)
        frame=np.frombuffer(raw,dtype=np.uint8).reshape(640,360,3)
        check(f"{style}: captions stay readable on white", np.count_nonzero(frame[420:520].max(axis=2)<160)>30)
    check("canvas contrast does not change the other templates", render.STYLES == before)

    db.init()
    try:
        with ctx.as_user(auth.local_user().id):
            for layout in render.CANVASES:
                creator = creators.create({"name":"Canvas "+layout,"layout":layout})
                for kind in ("video","live"):
                    job=jobs.create({"type":"file","name":"Canvas test"},{},enqueue=False,creator=creator["id"],kind=kind)
                    check(f"{layout}: saved choice reaches {kind} clips",job["options"]["layout"] == layout)
    finally:
        db.engine.dispose()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="pc-canvas-") as folder:
        main(Path(folder))

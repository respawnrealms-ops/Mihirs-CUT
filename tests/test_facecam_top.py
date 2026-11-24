"""Render the requested 50/50 camera/gameplay layout with a known source picture."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

work = Path(tempfile.mkdtemp(prefix="pc-face-top-"))
os.environ.update(PEAKCUT_DATA=str(work / "data"), DATABASE_URL="")
sys.path.insert(0, ".")
from studio import jobs, render, tools
import numpy as np


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS " + name)


try:
    render.install_fonts()
    check("the 50/50 layout is available to the app and video options",
          "facecam_top" in render.LAYOUTS and jobs.clean_options({"layout": "facecam_top"})["layout"] == "facecam_top")
    check("facecam detection covers the 50/50 layout", "facecam_top" in render.FACE_LAYOUTS)
    layout, height, hook_y, cap_y = render.geometry(640, 360, "facecam_top")
    check("text stays in the gameplay half", layout == "facecam_top" and 960 < hook_y < cap_y < 1920)
    check("portrait sources retain the chosen facecam split", render.geometry(720, 1280, "facecam_top")[0] == "facecam_top")
    src = work / "source.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x104020:s=640x360:r=10",
                    "-f", "lavfi", "-i", "color=c=red:s=160x90:r=10,drawbox=x=80:y=0:w=80:h=90:color=blue:t=fill",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
                    "-filter_complex", "[0:v][1:v]overlay=0:120[v]", "-map", "[v]", "-map", "2:a",
                    "-t", "2", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)],
                   check=True, capture_output=True)
    clip = {"start": 0, "end": 1.2, "layout": "facecam_top", "facecam": [0, 120, 160, 90], "captions": False}
    result = render.render_clip(src, work / "clips", "split", clip, [], 640, 360)
    out = work / "clips" / result["file"]
    info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                              "stream=codec_type,width,height", "-of", "json", str(out)]))
    check("the output is a vertical video with sound", any(s.get("width") == 1080 and s.get("height") == 1920 for s in info["streams"])
          and any(s.get("codec_type") == "audio" for s in info["streams"]))
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(out), "-frames:v", "1",
                                   "-vf", "scale=54:96", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
    picture = np.frombuffer(raw, dtype=np.uint8).reshape(96, 54, 3)
    left, right, lower = picture[24, 13].astype(int), picture[24, 40].astype(int), picture[72, 27].astype(int)
    check("both sides of the camera appear in the top half", left[0] > 150 and left[0] > 2 * left[2] and right[2] > 150 and right[2] > 2 * right[0])
    check("gameplay appears in the bottom half", lower[1] > 2 * lower[0] and lower[1] > 1.5 * lower[2])
    upper = picture[:48].astype(int)
    green = (upper[:, :, 1] > 160) & (upper[:, :, 1] > 2 * upper[:, :, 0]) & (upper[:, :, 1] > 2 * upper[:, :, 2])
    check("the camera background has no green encoding blocks", float(green.mean()) < 0.01)
    check("the selected layout is retained", result["layout"] == "facecam_top")
    try:
        render.render_clip(src, work / "clips", "missing", dict(clip, facecam=None), [], 640, 360)
        raise AssertionError("A missing facecam was accepted")
    except ValueError as e:
        check("a missing camera is explained instead of drawing an empty panel", "facecam" in str(e).lower())
    print("ALL PASSED")
finally:
    assert work.resolve().parent == Path(tempfile.gettempdir()).resolve()
    shutil.rmtree(work, ignore_errors=True)

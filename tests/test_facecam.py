"""Where the webcam is in a gaming stream.

The webcam is found by the one thing a webcam always has and a game almost never has: a straight
border that stays in the same place in every frame.

Runs against the code directly, with its own empty data folder."""
import os, shutil, subprocess, sys, tempfile
os.environ["PEAKCUT_DATA"] = tempfile.mkdtemp(prefix="pc-facecam-")
sys.path.insert(0, ".")
from studio import facecam, render
fails = []
def check(n, got, want=True):
    ok = want(got) if callable(want) else got == want
    print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"   got {got!r}")); ok or fails.append(n)

work = tempfile.mkdtemp(prefix="pc-facecam-work-")
FRAMES = "100"          # four seconds at 25 frames. Noise does not compress, so the picture stays small.
NOISE = "nullsrc=s=1280x720:r=25,noise=alls=24:allf=t"


def make(name, extra, where="0:0"):
    """A video with a moving background and one still box in it.

    The background is noise, which never repeats, so the only straight line that stays in the
    same place is the edge of the box."""
    path = os.path.join(work, name)
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", NOISE,
                    "-f", "lavfi", "-i", extra,
                    "-filter_complex", f"[0:v][1:v]overlay={where}[v]", "-map", "[v]",
                    "-frames:v", FRAMES,
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", path], check=True)
    return path


try:
    # ---- a webcam in the top-left: a still, lit box
    cam = make("cam.mp4", "color=c=0xC08050:size=300x170:rate=25")
    box = facecam.detect(cam)
    check("a webcam in the top-left is found", (box or {}).get("corner"), "top-left")
    # the border lies between two pixels, so the box is a pixel short of the drawn one
    check("its size is right", abs((box or {}).get("w", 0) - 300) <= 1, True)
    check("its height is right", abs((box or {}).get("h", 0) - 170) <= 1, True)
    check("it is sure of it", (box or {}).get("conf"), "high")

    # ---- the same box in another corner
    cam_br = make("cam_br.mp4", "color=c=0xC08050:size=300x170:rate=25", where="980:500")
    box = facecam.detect(cam_br)
    check("a webcam in the bottom-right is found too", (box or {}).get("corner"), "bottom-right")
    check("its position is right", abs((box or {}).get("x", 0) - 980) <= 1, True)

    # A compilation can put its camera in a different place for each clip.
    compilation = os.path.join(work, "compilation.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", cam, "-i", cam_br,
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]",
                    "-c:v", "libx264", "-preset", "ultrafast", compilation], check=True)
    first = facecam.detect_span(compilation, 0, 3)
    second = facecam.detect_span(compilation, 4, 7)
    check("the first clip uses its own camera position", (first or {}).get("corner"), "top-left")
    check("a later clip uses its changed camera position", (second or {}).get("corner"), "bottom-right")

    # ---- a video with no webcam in it: nothing that stays still, so nothing is found
    plain = os.path.join(work, "plain.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", NOISE, "-frames:v", FRAMES,
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", plain], check=True)
    check("a video with nothing still in it finds no webcam", (facecam.detect(plain) or {}).get("conf", "none"), "none")

    # ---- a file that cannot be read must not stop a job
    check("a file that cannot be read gives nothing, not an error",
          facecam.detect(os.path.join(work, "nope.mp4")), None)

    # ---- the job hands the webcam on to the render
    from studio import jobs
    job = {"source_path": cam}
    box = jobs._facecam(job)
    check("the job finds the webcam for its clips", bool(box), True)
    check("the job keeps it on the job", "facecam" in job, True)
    check("the box is the right size", abs(box[2] - 300) <= 1 and abs(box[3] - 170) <= 1, True)
    check("a job with no video finds no webcam", jobs._facecam({"source_path": os.path.join(work, "nope.mp4")}), None)

    # ---- a webcam that is square and runs along one edge, not into a corner
    sq = make("cam_sq.mp4", "color=c=0xC08050:size=360x355:rate=25", where="920:165")
    box = facecam.detect(sq)
    check("a square webcam along an edge is found", (box or {}).get("corner"), "right")
    check("it starts where the picture starts", abs((box or {}).get("x", 0) - 920) <= 3, True)
    check("it is as tall as the picture", abs((box or {}).get("h", 0) - 355) <= 6, True)

    # ---- one frame goes to the AI, and its answer is measured again before it is used
    def say(looked, box=None):
        return lambda jpeg: {"looked": looked, "box": box}

    box = facecam.detect(sq, ask=say(True, (0.71, 0.22, 0.29, 0.44)))      # rough, as a model gives it
    check("the box the AI suggests is put onto the borders", abs((box or {}).get("x", 0) - 920) <= 3, True)
    check("a rough box is corrected to the picture's real size", abs((box or {}).get("h", 0) - 355) <= 6, True)
    check("it is still sure of it", (box or {}).get("conf"), "high")
    check("the AI saying there is no webcam is believed", facecam.detect(sq, ask=say(True, None)), None)
    box = facecam.detect(sq, ask=say(True, (0.02, 0.02, 0.06, 0.06)))      # a box on nothing at all
    check("a box that lands on nothing is thrown away and the search carries on",
          abs((box or {}).get("x", 0) - 920) <= 3, True)
    box = facecam.detect(sq, ask=say(False))                              # a model that only reads text
    check("a model that cannot look at pictures changes nothing", abs((box or {}).get("x", 0) - 920) <= 3, True)

    # ---- what the model's one line is turned into
    from unittest.mock import patch
    from studio import brain, ai as _ai
    with patch.object(_ai, "see", return_value=("CAME x=71% y=20% w=29% h=38%", 0, 0)):
        got = brain.look_for_facecam(b"jpeg")
    check("the box in the model's answer is read", [round(v, 2) for v in (got["box"] or ())],
          [0.71, 0.20, 0.29, 0.38])
    with patch.object(_ai, "see", return_value=("NO CAM", 0, 0)):
        check("'no cam' is read as no webcam", brain.look_for_facecam(b"jpeg"), {"looked": True, "box": None})
    with patch.object(_ai, "see", return_value=("I am a text model.", 0, 0)):
        check("an answer that is neither is not believed", brain.look_for_facecam(b"jpeg")["looked"], False)

    # ---- a webcam's short side is hidden by edges elsewhere in the full frame
    import numpy as np
    light = np.full((facecam.H, facecam.W), 30, dtype=np.float32)
    light[76:116, :64] = 150
    still = np.full_like(light, 35)
    still[76:116, :64] = 11
    still[76:92, :64] = 15      # people move in part of the camera, while its box stays put
    horizontal = np.ones(facecam.H - 1, dtype=np.float32)
    horizontal[76], horizontal[116] = 3.0, 3.6
    with (patch.object(facecam, "_frames", return_value=np.repeat(light.astype(np.uint8)[None], 8, axis=0)),
          patch.object(facecam, "_size", return_value=(1280, 720)),
          patch.object(facecam, "_stillness", return_value=still),
          patch.object(facecam, "_profiles", return_value=(np.ones(facecam.W - 1), horizontal)),
          patch.object(facecam, "_snap", return_value=(0, 306, 258, 467))):
        found = facecam.detect("short-camera-border.ts")
    check("a short camera border is found without an image-capable AI", (found or {}).get("conf"), "high")
    check("the whole camera is kept when the people inside move", [(found or {}).get(k) for k in ("x", "y", "w", "h")], [0, 306, 258, 161])

    # Moving faces can confirm a bordered camera that is not still enough for the old heuristic.
    moving = np.full_like(light, 35)
    repeated = [(0, (20, 80, 12, 16), 1.0), (1, (21, 80, 12, 16), 2.0)]
    with patch.object(facecam, "_face_hints", return_value=repeated):
        candidates = facecam._human_local("moving-camera", [], facecam._peaks(horizontal, 40), moving, light)
    check("moving faces confirm the camera's measured borders", bool(candidates) and candidates[0].get("human_verified"))
    with patch.object(facecam, "_face_hints", return_value=repeated[:1]):
        check("one face sighting alone does not invent a camera", facecam._human_local("one-face", [], facecam._peaks(horizontal, 40), moving, light), [])
    with patch.object(facecam, "_face_hints", return_value=[]):
        check("a moving HUD without faces is not a camera", facecam._human_local("hud", [], facecam._peaks(horizontal, 40), moving, light), [])

    # ---- changing an existing live clip's layout must detect its saved camera picture
    from studio import ctx
    from pathlib import Path
    output = Path(work) / "rerender"
    (output / "clips").mkdir(parents=True)
    clip = {"id": "clip1", "src": cam_br, "src_offset": 0, "start": 0, "end": 3,
            "layout": "gameplay", "captions": False, "style": "bounce", "score": 80,
            "hook": "", "title": "", "description": "", "hashtags": [], "version": 1}
    job = {"dir": str(output), "source_path": cam, "duration": 4, "width": 1280, "height": 720, "creator": None}
    detected = {"x": 980, "y": 500, "w": 300, "h": 170, "conf": "high"}
    with (ctx.as_user("u_test"), patch.object(jobs, "save"),
          patch.object(facecam, "detect_span", return_value=detected) as find,
          patch.object(render, "render_clip", return_value={"file": "clip1.mp4", "layout": "gameplay"}) as encode):
        jobs.render_one(job, clip, [])
        check("changing to gameplay checks the saved live piece", find.call_args.args[0], Path(cam_br))
        check("the facecam reaches the rerendered video", encode.call_args.args[3].get("facecam"), [980, 500, 300, 170])
        find.reset_mock()
        jobs.render_one(job, clip, [])
        check("remaking it again reuses the detected facecam", find.called, False)

    # A missing camera must not rewrite the user's selected layout.
    with patch.object(render, "_render_in", return_value={"file": "fallback.mp4", "cover": "fallback.jpg", "layout": "crop"}):
        result = render.render_clip(Path(cam), output / "fallback", "fallback",
                                    {"start": 0, "end": 3, "layout": "gameplay", "captions": False}, [], 1280, 720)
    check("a missing camera keeps the selected facecam layout", result["layout"], "gameplay")
    check("the rendered fallback is recorded separately", result["rendered_layout"], "crop")
    check("a missing camera is explained to the user", "No facecam" in result["layout_warning"])
    check("portrait clips also retain their camera layout", render.geometry(720, 1280, "gameplay")[0], "gameplay")
    job.update(id="facecam-edit-test", clips=[clip])
    clip["src_end"] = 4
    with (ctx.as_user("u_test"), patch.dict(jobs._jobs, {job["id"]: job}),
          patch.object(jobs, "save"), patch.object(jobs._q, "put")):
        jobs.request_render(job["id"], clip["id"], {"end": 3.5})
    check("trimming a clip checks for its camera again", "facecam" not in clip)

    # ---- the layout: the game fills the screen and the webcam sits in the corner
    f = render._filter("gameplay", 1920, [0, 0, 300, 170])
    check("the game fills the screen", "scale=1080:1920" in f and "crop=1080:1920" in f, True)
    check("the webcam is cropped out of the source", "crop=300:170:0:0" in f, True)
    check("the webcam is put in the corner", "overlay=" in f, True)
    check("without a webcam the game simply fills the screen",
          "scale=1080:1920" in render._filter("gameplay", 1920, None) and "overlay=" not in render._filter("gameplay", 1920, None), True)
    check("the layout is offered to the user", "gameplay" in render.LAYOUTS, True)
    # the heading must not run under the webcam picture
    pip_h = 380 * 376 / 363
    check("the heading goes below the webcam picture", render._hook_y("gameplay", 300, [0, 0, 363, 376]) > 26 + pip_h, True)
    check("another picture moves the heading with it",
          render._hook_y("gameplay", 300, [0, 0, 300, 170]) < render._hook_y("gameplay", 300, [0, 0, 363, 376]), True)
    check("without a webcam the heading stays at the top", render._hook_y("crop", 300, None), 300)
finally:
    shutil.rmtree(work, ignore_errors=True)      # the pictures are big; they must not be left behind

print("ALL PASSED" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)

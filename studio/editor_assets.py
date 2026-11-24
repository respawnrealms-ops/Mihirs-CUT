"""The signed-in person's reusable images, music, and B-roll."""
import json
import uuid
from pathlib import Path

from PIL import Image

from . import config, ctx, editor
from .media import run

TYPES = {".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image",
         ".mp3": "audio", ".wav": "audio", ".m4a": "audio", ".ogg": "audio", ".flac": "audio",
         ".mp4": "video", ".mov": "video", ".webm": "video", ".mkv": "video"}
MAX_BYTES = 100 * 1024 * 1024


def root():
    d = config.user_dir(ctx.uid()) / "editor-assets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get(aid):
    editor.asset_id(aid)
    try:
        row = json.loads((root() / f"{aid}.json").read_text(encoding="utf-8"))
        path = root() / f"{aid}{row['ext']}"
        if path.parent != root() or row["ext"] not in (".png", *TYPES) or not path.is_file():
            raise ValueError()
        return row, path
    except (OSError, ValueError, KeyError):
        raise ValueError("That media file is not in your library.") from None


def path(aid, kinds=None):
    row, p = get(aid)
    if kinds and row["kind"] not in kinds:
        raise ValueError("Choose the right kind of media for this control.")
    return p


def listing():
    rows = []
    for f in root().glob("*.json"):
        try:
            row, _ = get(f.stem)
            rows.append(row)
        except ValueError:
            pass
    return rows


def inspect(source, original_name):
    ext = Path(original_name).suffix.lower()
    if ext not in TYPES:
        raise ValueError("Upload a PNG, JPEG, WebP, audio file, or video.")
    kind, aid = TYPES[ext], uuid.uuid4().hex
    row = {"id": aid, "kind": kind, "name": editor.text(Path(original_name).name, 100)}
    if kind == "image":
        with Image.open(source) as im:
            if im.width * im.height > 40000000:
                raise ValueError("Choose an image smaller than 40 megapixels.")
            im = im.convert("RGBA")
            im.thumbnail((4096, 4096))
            row.update(width=im.width, height=im.height, ext=".png")
            im.save(root() / f"{aid}.png")
    else:
        probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)], timeout=30))
        streams = probe.get("streams", [])
        if not any(s.get("codec_type") == kind for s in streams):
            raise ValueError("That file does not contain the expected audio or video.")
        duration = editor.number(probe.get("format", {}).get("duration", 0), 0.1, 36000)
        row.update(duration=duration, ext=ext)
        import shutil
        shutil.copyfile(source, root() / f"{aid}{ext}")
    (root() / f"{aid}.json").write_text(json.dumps(row), encoding="utf-8")
    ctx.bump()
    return row


def validate_profile(profile):
    for k, kinds in (("background_asset", ("image",)), ("avatar", ("image",)), ("logo", ("image",)), ("music", ("audio",))):
        if profile.get(k):
            path(profile[k], kinds)
    for key in ("slots", "broll", "stickers", "sfx"):
        for row in profile.get(key, []):
            if row.get("asset"):
                path(row["asset"], ("audio",) if key == "sfx" else ("image", "video") if key != "stickers" else ("image",))

"""Saved editing choices. Paths and account details never belong in an editing profile."""
import math
import re

RATIOS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350),
          "16:9": (1920, 1080), "3:4": (1080, 1440)}
LAYOUTS = {"solo": "Solo · manual framing", "duo": "Split · two framed shots",
           "pip": "Picture in picture", "trio": "Trio · three framed shots",
           "split_top": "Split · wide shot above", "split_bottom": "Split · wide shot below"}
MOTIONS = {"auto": "Use caption style", "pop_in": "Pop-In", "pop_line": "Pop-In Line",
           "one_by_one": "One-by-One", "build_up": "Build Up", "highlight": "Highlight", "full_line": "Full Line"}
TEMPLATES = {"none": "No frame", "x_light": "X Light · profile card", "x_dark": "X Dark · profile card",
             "tiktok_hook": "TikTok Hook", "breaking_news": "Breaking News", "poll": "Poll card",
             "comment": "Comment reply", "quote": "Quote", "code": "Code card",
             "headline": "Editorial", "podcast": "Podcast", "gaming": "Gaming",
             "spotlight": "Spotlight", "review": "Review", "announcement": "Announcement", "youtube_video": "YouTube video · widescreen"}
DEFAULTS = {"ratio": "9:16", "resolution": "1080", "fps": "source", "encoder": "auto",
            "template": "none", "motion": "auto", "background": "layout", "color": "#ffffff",
            "color2": "#ff8b2b", "background_asset": "", "blur": 25, "dim": 0.15,
            "padding": 24, "radius": 0, "shadow": False, "panel_light": False, "panel_light_color": "#d9efff", "panel_light_strength": 0.65, "divider": 0, "divider_color": "#ffffff",
            "pip_shape": "rounded", "pip_corner": "bottom_right", "pip_size": 0.3, "swap": False,
            "headline": "", "hook_label": "WAIT FOR IT", "news_label": "BREAKING NEWS", "news_strap": "SPECIAL COVERAGE · DEVELOPING STORY", "news_live": False, "gradient_angle": 90,
            "placements": {}, "regions": [], "profile_source": "source", "name": "", "handle": "", "subline": "", "ticker": "",
            "badge": False, "poll_a": "Option A", "poll_b": "Option B", "code_text": "", "avatar": "", "logo": "", "logo_corner": "top_right",
            "logo_size": 0.12, "logo_opacity": 1, "watermark": "", "follow": "", "outro": 0,
            "caption_y": 0, "caption_size": 1, "headline_y": 0, "music": "", "music_volume": 0.15,
            "music_peak": 0.25, "music_riser": False, "duck": True, "voice_volume": 1,
            "cuts": [], "slots": [], "broll": [], "sfx": [], "stickers": []}
ENUMS = {"ratio": RATIOS, "resolution": ("720", "1080", "2160"), "fps": ("source", "24", "30", "60"),
         "encoder": ("auto", "cpu", "nvenc", "amf", "qsv"), "template": TEMPLATES, "motion": MOTIONS,
         "background": ("layout", "blur", "solid", "gradient", "image"), "profile_source": ("source", "custom"),
         "pip_shape": ("rectangle", "rounded", "circle"),
         "pip_corner": ("top_left", "top_right", "bottom_left", "bottom_right"),
         "logo_corner": ("top_left", "top_right", "bottom_left", "bottom_right")}
NUMBERS = {"panel_light_strength": (0, 1), "gradient_angle": (0, 360),"blur": (0, 60), "dim": (0, 0.9), "padding": (0, 160), "radius": (0, 160), "divider": (0, 30),
           "pip_size": (0.15, 0.5), "logo_size": (0.04, 0.4), "logo_opacity": (0.1, 1), "outro": (0, 5),
           "caption_y": (0, 0.95), "headline_y": (0, 0.9), "caption_size": (0.5, 1.8),
           "music_volume": (0, 1), "music_peak": (0, 1), "voice_volume": (0, 2)}
ASSETS = ("background_asset", "avatar", "logo", "music")


def number(value, low, high):
    n = float(value)
    if not math.isfinite(n) or not low <= n <= high:
        raise ValueError(f"Choose a number between {low} and {high}.")
    return round(n, 4)


def asset_id(value):
    if value and not re.fullmatch(r"[a-f0-9]{32}", str(value)):
        raise ValueError("Choose a file from your media library.")
    return str(value or "")


def text(value, length=300):
    return " ".join(str(value or "").split())[:length]


def color(value):
    if not re.fullmatch(r"#[a-fA-F0-9]{6}", str(value)):
        raise ValueError("Use a six-digit colour, such as #ffffff.")
    return value.lower()


def clean(value):
    if not isinstance(value, dict):
        raise ValueError("Editing settings must be an object.")
    out = {}
    for key, val in value.items():
        if key not in DEFAULTS:
            continue
        if key == "placements":
            val = clean_placements(val)
        elif key in ENUMS:
            if val not in ENUMS[key]:
                raise ValueError(f"Choose a supported {key.replace('_', ' ')}.")
        elif key in NUMBERS:
            val = number(val, *NUMBERS[key])
        elif key in ASSETS:
            val = asset_id(val)
        elif key in ("color", "color2", "divider_color", "panel_light_color"):
            val = color(val)
        elif isinstance(DEFAULTS[key], bool):
            if not isinstance(val, bool):
                raise ValueError(f"{key} must be on or off.")
        elif key in ("regions", "cuts", "slots", "broll", "sfx", "stickers"):
            val = _rows(key, val)
        else:
            val = text(val, 500 if key == "subline" else 200)
        if val != DEFAULTS[key]:
            out[key] = val
    return out


PLACED_ELEMENTS = {"video0", "video1", "video2", "profile", "headline", "caption", "subline",
                   "news", "hook_label", "news_strap", "ticker", "watermark", "logo"}


def clean_placements(value):
    if not isinstance(value, dict) or len(value) > len(PLACED_ELEMENTS):
        raise ValueError("Canvas positions must be an object of supported elements.")
    out = {}
    for key, row in value.items():
        if key not in PLACED_ELEMENTS or not isinstance(row, dict):
            raise ValueError("Choose a supported canvas element.")
        r = {k: number(row.get(k), 0, 1) for k in ("x", "y", "w", "h")}
        if r["w"] < .02 or r["h"] < .02 or r["x"] + r["w"] > 1.0001 or r["y"] + r["h"] > 1.0001:
            raise ValueError("Keep each canvas element inside the picture, with a width and height of at least 2%.")
        if "enabled" in row:
            if not isinstance(row["enabled"], bool) or (key.startswith("video") and not row["enabled"]):
                raise ValueError("Video panels must stay visible. Other elements can be hidden.")
            r["enabled"] = row["enabled"]
        out[key] = r
    return out


def _rows(key, value):
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list.")
    out = []
    for row in value[:{"regions": 3, "cuts": 12, "slots": 3}.get(key, 20)]:
        if not isinstance(row, dict):
            raise ValueError("Each editing row must be an object.")
        if key == "regions":
            r = {k: number(row.get(k, d), 0, 1) for k, d in (("x", 0), ("y", 0), ("w", 1), ("h", 1))}
            if r["w"] < 0.02 or r["h"] < 0.02 or r["x"] + r["w"] > 1.0001 or r["y"] + r["h"] > 1.0001:
                raise ValueError("A framing box must stay inside the source picture.")
        elif key == "cuts":
            r = {"start": number(row.get("start"), 0, 2410), "end": number(row.get("end"), 0, 2410)}
            if r["end"] <= r["start"]:
                raise ValueError("A keep range must end after it starts.")
            if out and r["start"] < out[-1]["end"]:
                raise ValueError("Keep ranges must be in order and cannot overlap.")
        elif key == "slots":
            r = {"slot": int(number(row.get("slot", 0), 0, 2)), "asset": asset_id(row.get("asset")),
                 "offset": number(row.get("offset", 0), 0, 36000)}
        else:
            r = {"time": number(row.get("time", 0), 0, 180), "duration": number(row.get("duration", 3), 0.1, 180)}
            if key == "sfx":
                r.update(asset=asset_id(row.get("asset")), sound=text(row.get("sound", "pop"), 20),
                         volume=number(row.get("volume", 0.5), 0, 1))
                if r["sound"] not in ("pop", "ping", "whoosh", "click"):
                    raise ValueError("Choose a supported sound effect.")
            else:
                r.update(asset=asset_id(row.get("asset")), x=number(row.get("x", 0.5), 0, 1),
                         y=number(row.get("y", 0.5), 0, 1), size=number(row.get("size", 0.25), 0.05, 1))
                if key == "stickers":
                    r["text"] = text(row.get("text"), 30)
        out.append(r)
    return out


def settings(clip):
    return {**DEFAULTS, **clean(clip.get("studio") or {})}


def catalog():
    return {"version": 3, "brand": "Mihis Cut", "ratios": list(RATIOS), "motions": MOTIONS,
            "templates": TEMPLATES, "defaults": DEFAULTS, "layouts": LAYOUTS}


def clean_words(rows, max_words=2000):
    if not isinstance(rows, list) or len(rows) > max_words:
        raise ValueError(f"Captions can contain up to {max_words:,} timed words.")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each caption word needs text and start/end times.")
        s, e = number(row.get("s"), 0, 1000000), number(row.get("e"), 0, 1000000)
        if e <= s:
            raise ValueError("Each caption word must end after it starts.")
        r = {"w": text(row.get("w"), 100), "s": s, "e": e}
        for k in ("bold", "italic", "box"):
            if row.get(k) is True:
                r[k] = True
        if row.get("color"):
            r["color"] = color(row["color"])
        if r["w"]:
            out.append(r)
    return sorted(out, key=lambda w: w["s"])


def import_subtitles(content, offset=0):
    """SRT or ASS lines become words with estimated timing inside each line."""
    if len(content) > 500000:
        raise ValueError("That subtitle file is too large.")
    def stamp(t):
        a, b, c = t.strip().replace(",", ".").split(":")
        return int(a) * 3600 + int(b) * 60 + float(c)
    lines = []
    if "Dialogue:" in content:
        for line in content.splitlines():
            if line.startswith("Dialogue:"):
                p = line.split(",", 9)
                if len(p) == 10:
                    lines.append((stamp(p[1]), stamp(p[2]), re.sub(r"\{[^}]*\}", "", p[9]).replace(r"\N", " ")))
    else:
        for block in re.split(r"\n\s*\n", content.replace("\r", "").strip()):
            m = re.search(r"(\d+:\d+:\d+[.,]\d+)\s*-->\s*(\d+:\d+:\d+[.,]\d+)[^\n]*\n(.+)", block, re.S)
            if m:
                lines.append((stamp(m[1]), stamp(m[2]), re.sub(r"<[^>]*>", "", m[3])))
    words = []
    for a, b, line in lines:
        tokens = line.split()
        for i, token in enumerate(tokens):
            words.append({"w": token, "s": offset + a + (b-a)*i/len(tokens), "e": offset + a + (b-a)*(i+1)/len(tokens)})
    if not words:
        raise ValueError("No SRT or ASS caption lines were found.")
    return clean_words(words)


def keep_ranges(opts, duration):
    cuts = opts.get("cuts") or [{"start": 0, "end": duration}]
    out = [(r["start"], min(duration, r["end"])) for r in cuts if r["start"] < duration]
    if not out or sum(b-a for a, b in out) < 0.1:
        raise ValueError("The keep ranges do not include any video inside this clip.")
    return out


def remap_words(words, start, ranges):
    out, shift = [], 0
    for a, b in ranges:
        for w in words:
            s, e = max(a, w["s"]-start), min(b, w["e"]-start)
            if e > s:
                out.append(dict(w, s=s-a+shift, e=e-a+shift))
        shift += b-a
    return out

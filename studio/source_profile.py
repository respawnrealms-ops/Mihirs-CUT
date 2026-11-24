"""Credit the source channel on video cards, independently of the posting account."""
import io
import threading
import time
from urllib.parse import unquote, urlparse

from . import creators, editor, editor_assets, media, profiles

_lock = threading.Lock()


def channel_url(value):
    """Only platform channel addresses supplied by video metadata are fetched."""
    try:
        u = urlparse(value or "")
        host = (u.hostname or "").lower()
        parts = u.path.strip("/").split("/")
        if u.scheme != "https" or u.username or u.password or u.port:
            return ""
        if host in ("youtube.com", "www.youtube.com", "m.youtube.com"):
            if not (parts[0].startswith("@") or (parts[0] in ("channel", "c", "user") and len(parts) > 1)):
                return ""
        elif host in ("twitch.tv", "www.twitch.tv", "kick.com", "www.kick.com"):
            if len(parts) != 1 or not parts[0] or parts[0] in ("videos", "clips", "directory"):
                return ""
        else:
            return ""
        return f"https://{host}{u.path}".rstrip("/")
    except ValueError:
        return ""


def resolve(job, refresh=False):
    """Fetch once per video, cache a private reusable avatar, and keep failures harmless."""
    from . import jobs
    with _lock:
        saved = job.get("source_profile") or {}
        if saved and not refresh and time.time() - job.get("source_profile_at", 0) < (86400 if saved.get("avatar") else 900):
            return saved
        identity = {"name": editor.text(job.get("uploader"), 120), "handle": "", "avatar": "", "channel": ""}
        url = channel_url(job.get("channel_url"))
        src = job.get("source") or {}
        try:
            if not url and src.get("type") == "url" and media.site_allowed(src.get("url", "")):
                info = media.info(src["url"])
                url = channel_url(info.get("channel_url"))
                identity["name"] = editor.text(info.get("uploader") or identity["name"], 120)
                job.update(channel_url=url, channel_handle=info.get("channel_handle") or "")
            if not url and job.get("kind") == "live":
                url = channel_url(src.get("url"))
            # An uploaded file has no platform identity; its assigned source creator is the fallback.
            if not url and src.get("type") == "file" and job.get("creator"):
                c = creators.get(job["creator"]) or {}
                url = channel_url(c.get("channel"))
                identity["name"] = identity["name"] or editor.text(c.get("name"), 120)
            if url:
                identity["channel"] = url
                handle = job.get("channel_handle") or unquote(urlparse(url).path.strip("/").split("/")[0])
                identity["handle"] = editor.text(handle if handle.startswith("@") else "", 100)
                public = profiles.fetch(url)
                identity["name"] = editor.text(public.get("name") or identity["name"], 120)
                picture = public.get("pic")
                if picture:
                    row = editor_assets.inspect(io.BytesIO(picture[0]), "Source channel photo.png")
                    identity["avatar"] = row["id"]
        except Exception:
            # Do not substitute a posting account or a different creator when lookup fails.
            pass
        if saved.get("channel") == identity["channel"] and not identity["avatar"]:
            identity["avatar"] = saved.get("avatar", "")
        job.update(source_profile=identity, source_profile_at=time.time())
        jobs.save(job)
        return identity


def apply(job, clip):
    """Source mode replaces legacy destination-account defaults; custom mode stays editable."""
    profile = dict(clip.get("studio") or {})
    if profile.get("template", "none") == "none" or profile.get("profile_source", "source") == "custom":
        return profile
    identity = resolve(job)
    return {**profile, **{k: identity.get(k, "") for k in ("name", "handle", "avatar")}}

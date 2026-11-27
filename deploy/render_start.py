"""Start the existing single-process app with Render's address and port."""
import os
from pathlib import Path
import runpy
import sys
from urllib.parse import urlparse


def prepare(env):
    public_url = (env.get("PEAKCUT_PUBLIC_URL") or env.get("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
    parsed = urlparse(public_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        raise ValueError("Render must provide RENDER_EXTERNAL_URL, or set PEAKCUT_PUBLIC_URL to your HTTPS site address.")
    port = str(env.get("PORT") or "8765")
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("PORT must be a valid listening port.")
    if env.get("PEAKCUT_ACCOUNTS", "1") != "1":
        raise ValueError("Keep PEAKCUT_ACCOUNTS=1 on this public Render deployment.")
    env.update(PEAKCUT_HOST="0.0.0.0", PEAKCUT_PORT=port, PEAKCUT_PUBLIC_URL=public_url,
               PEAKCUT_ACCOUNTS="1", PEAKCUT_TRUST_PROXY="1", PEAKCUT_AUTO_RELOAD="0")
    env.setdefault("PEAKCUT_DATA", "/data")
    env.setdefault("PEAKCUT_JOB_WORKERS", "1")
    env.setdefault("PEAKCUT_ASR_COPIES", "1")
    env.setdefault("PEAKCUT_ASR_THREADS", "2")


if __name__ == "__main__":
    try:
        prepare(os.environ)
    except ValueError as error:
        raise SystemExit(str(error))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    # Do not use multiple Uvicorn workers: each would also start a posting/recording worker.
    runpy.run_module("studio.server", run_name="__main__")

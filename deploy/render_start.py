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


def setup_owner(env):
    """Provision an owner only from credentials supplied through the hosting control panel."""
    email = (env.get("PEAKCUT_OWNER_EMAIL") or "").strip().lower()
    password = env.get("PEAKCUT_OWNER_PASSWORD") or ""
    if not email and not password:
        return
    if not email or not password:
        raise ValueError("Set both PEAKCUT_OWNER_EMAIL and PEAKCUT_OWNER_PASSWORD in Render's environment settings.")
    from studio import admin, auth, db
    if not auth.EMAIL_RE.fullmatch(email):
        raise ValueError("PEAKCUT_OWNER_EMAIL must be a valid email address.")
    auth._check_password_rules(password)
    db.init()
    # A signup with an unverified email must not be able to claim the configured owner's role.
    # If this account already exists, the control-panel password must match it.
    with db.engine.connect() as connection:
        user = connection.execute(db.users.select().where(db.users.c.email == email)).first()
    if user:
        if user.disabled or not user.password_hash or not auth.verify_password(password, user.password_hash):
            raise ValueError("The configured owner password does not match the existing account. No role was changed.")
    else:
        user, _ = auth.signup(email, password, "Owner")
    if not user.is_admin:
        admin.set_admin(email, True)
        auth.forget(user.id)
    print("Mihis Cut owner account is ready. Sign in with the password set in Render.", flush=True)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        prepare(os.environ)
        setup_owner(os.environ)
    except ValueError as error:
        raise SystemExit(str(error))
    # Do not use multiple Uvicorn workers: each would also start a posting/recording worker.
    runpy.run_module("studio.server", run_name="__main__")

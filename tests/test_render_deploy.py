"""Render's dynamic address, sign-in gate and persisted database; no external services."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render_start", ROOT / "deploy" / "render_start.py")
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


def check(name, ok):
    if not ok:
        raise AssertionError(name)
    print("PASS " + name, flush=True)


for bad in ({}, {"RENDER_EXTERNAL_URL":"http://example.onrender.com"},
            {"RENDER_EXTERNAL_URL":"https://example.onrender.com", "PORT":"bad"},
            {"RENDER_EXTERNAL_URL":"https://example.onrender.com", "PEAKCUT_ACCOUNTS":"0"}):
    try:
        entry.prepare(bad)
    except ValueError:
        continue
    raise AssertionError("Invalid public configuration was accepted")
check("deployment refuses a missing HTTPS address, invalid port or disabled login", True)
env = {"RENDER_EXTERNAL_URL":"https://example.onrender.com", "PEAKCUT_PUBLIC_URL":"https://custom.example/"}
entry.prepare(env)
check("a later custom domain overrides Render's generated URL", env["PEAKCUT_PUBLIC_URL"] == "https://custom.example")

scratch = ROOT / "data" / "test-temp"
scratch.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="render-check-", dir=scratch) as tmp:
    base = Path(tmp)
    shutil.copytree(ROOT / "studio", base / "studio", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "web", base / "web")
    (base / "deploy").mkdir()
    shutil.copyfile(ROOT / "deploy" / "render_start.py", base / "deploy" / "render_start.py")
    # The desktop .env, real user data and platform tokens are never copied.
    clean_env = {k:v for k,v in os.environ.items() if not k.startswith(("PEAKCUT_", "GOOGLE_")) and k != "DATABASE_URL"}
    clean_env.update(RENDER_EXTERNAL_URL="https://test-only.onrender.com", PORT="10000",
                     PEAKCUT_DATA=str(base / "persisted"), PEAKCUT_FETCH_MODEL="0",
                     PEAKCUT_UPDATE_CHECK="0", PEAKCUT_SMTP_HOST="", PYTHONUTF8="1")
    code = '''
import os
from deploy.render_start import prepare
prepare(os.environ)
from studio import config, db, server
from fastapi.testclient import TestClient
db.init()
assert config.PUBLIC_URL == "https://test-only.onrender.com"
assert config.PORT == 10000 and config.HOST == "0.0.0.0"
assert config.HTTPS and config.ACCOUNTS
client = TestClient(server.app, base_url=config.PUBLIC_URL)
assert client.get("/healthz").json() == {"ok":True}
assert client.get("/api/status").status_code == 401
assert client.get("/app", follow_redirects=False).status_code == 303
r = client.post("/api/auth/signup", json={"email":"render-test@example.com","password":"only-in-this-test-291827","name":"Render test"}, headers={"Origin":config.PUBLIC_URL})
assert r.status_code == 200, r.text
assert "Secure" in r.headers["set-cookie"]
assert client.get("/api/status").status_code == 200
print("PASS generated HTTPS URL, Render port, health check, sign-in gate and secure session cookie")
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=base, env=clean_env, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    print(result.stdout.strip(), flush=True)
    code = '''
import os
from deploy.render_start import prepare
prepare(os.environ)
from studio import db, auth
db.init()
user=auth.login("render-test@example.com","only-in-this-test-291827")
assert user.email == "render-test@example.com" and not user.is_admin
print("PASS a fresh app process can use the persisted account database")
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=base, env=clean_env, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    print(result.stdout.strip(), flush=True)
print("Render deployment checks passed; no local user data or external services used.")

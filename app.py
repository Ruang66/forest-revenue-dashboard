"""FE Revenue Dashboard — FastAPI backend.

Serves the dashboard with a login gate (session cookie + sign-out) and a JSON API
that persists the full dashboard state to Postgres.
"""
import os
import secrets

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from starlette.middleware.sessions import SessionMiddleware

import db

# ── Config ───────────────────────────────────────────────
APP_USERNAME = os.environ.get("FE_USERNAME", "Forest")
APP_PASSWORD = os.environ.get("FE_PASSWORD", "F@rest1!136")
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(32))
INDEX_PATH = os.path.join(os.path.dirname(__file__), "index.html")
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.svg")

app = FastAPI(title="FE Revenue Dashboard")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=60 * 60 * 24 * 30)


@app.on_event("startup")
def _startup():
    # Never let a DB hiccup crash the app (it would fail Railway's healthcheck).
    # The table is also ensured lazily on first write.
    try:
        db.init_db()
        print("[startup] DB initialised", flush=True)
    except Exception as e:
        print(f"[startup] DB init deferred: {e}", flush=True)


def _is_authed(request: Request) -> bool:
    return request.session.get("user") == APP_USERNAME


LOGIN_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forest Energy — Sign In</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
         background:#0d2830; display:flex; min-height:100vh; align-items:center; justify-content:center; }}
  .card {{ background:#114d5d; padding:40px 36px; border-radius:14px; width:340px;
          box-shadow:0 20px 50px rgba(0,0,0,.45); }}
  .logo {{ display:flex; justify-content:center; margin-bottom:14px; }}
  .logo img {{ height:96px; }}
  .tagline {{ text-align:center; color:#8ca6ae; font-size:12px; letter-spacing:.5px;
             text-transform:uppercase; margin-bottom:22px; }}
  label {{ display:block; font-size:13px; color:#cdd9dc; margin:14px 0 6px; }}
  input {{ width:100%; padding:11px 12px; border:1px solid #46717e; border-radius:8px;
          font-size:14px; background:#fff; color:#0d2830; }}
  input:focus {{ outline:none; border-color:#26f0a3; }}
  button {{ width:100%; margin-top:22px; padding:12px; background:#26f0a3; color:#0d2830; border:none;
           border-radius:8px; font-size:15px; font-weight:700; cursor:pointer; }}
  button:hover {{ background:#5ff3bd; }}
  .err {{ color:#e05c5c; font-size:13px; margin-top:14px; text-align:center; {err_display} }}
</style></head>
<body>
  <form class="card" method="post" action="/login">
    <div class="logo"><img src="/logo.svg" alt="Forest Energy"></div>
    <div class="tagline">Revenue Dashboard</div>
    <label>Username</label>
    <input name="username" autocomplete="username" autofocus required>
    <label>Password</label>
    <input name="password" type="password" autocomplete="current-password" required>
    <button type="submit">Sign In</button>
    <div class="err">Incorrect username or password</div>
  </form>
</body></html>"""


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if _is_authed(request):
        return RedirectResponse("/", status_code=302)
    return HTMLResponse(LOGIN_PAGE.format(err_display="display:none;"))


@app.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    ok_user = secrets.compare_digest(username, APP_USERNAME)
    ok_pass = secrets.compare_digest(password, APP_PASSWORD)
    if ok_user and ok_pass:
        request.session["user"] = APP_USERNAME
        return RedirectResponse("/", status_code=302)
    return HTMLResponse(LOGIN_PAGE.format(err_display=""), status_code=401)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if not _is_authed(request):
        return RedirectResponse("/login", status_code=302)
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/api/data")
def get_data(request: Request):
    if not _is_authed(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return JSONResponse(db.get_state())


@app.post("/api/data")
async def post_data(request: Request):
    if not _is_authed(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")
    db.save_state(payload)
    return {"ok": True}


@app.get("/logo.svg")
def logo():
    return FileResponse(LOGO_PATH, media_type="image/svg+xml")


@app.get("/health")
def health():
    return {"status": "ok"}

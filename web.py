"""
FastAPI web app for user registration, preferences, and instant search.
Digest sending is handled by GitHub Actions — this app only serves the UI.
"""
import os
import json
import traceback
from datetime import datetime

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import bcrypt

from db import (
    init_db, get_conn, _q, get_user, get_sent,
    get_all_internships_df,
)
from matcher import search, location_match
from scrapers import run_all_scrapers
from db import save_internships
from emailer import (
    run_digest_for,
    make_unsubscribe_token,
    read_unsubscribe_token,
)


# ---------- Config ----------
SECRET_KEY = os.environ["SECRET_KEY"]
signer = URLSafeTimedSerializer(SECRET_KEY, salt="session")


# ---------- Auth helpers ----------
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8")[:72], h.encode("utf-8"))
    except Exception:
        return False


def make_session(email: str) -> str:
    return signer.dumps({"email": email})


def read_session(token, max_age=60 * 60 * 24 * 30):
    try:
        return signer.loads(token, max_age=max_age)["email"]
    except (BadSignature, SignatureExpired):
        return None


# ---------- User CRUD ----------
def create_user(email: str, pw: str) -> bool:
    con = get_conn()
    try:
        cur = con.cursor()
        cur.execute(_q("""INSERT INTO users (email, password_hash, created_at)
                          VALUES (?,?,?)"""),
                    (email.lower(), hash_pw(pw), datetime.utcnow().isoformat()))
        con.commit()
        return True
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return False
        print("=== create_user error ===")
        traceback.print_exc()
        return False


def update_prefs(email, keywords, locations, remote_only, subscribed=None):
    remote_tokens = {"remote", "anywhere", "worldwide", "global"}
    locs_in = [l.strip().lower() for l in (locations or []) if l and l.strip()]
    if any(t in remote_tokens for t in locs_in):
        remote_only = True
        locs_in = [l for l in locs_in if l not in remote_tokens]

    con = get_conn()
    cur = con.cursor()
    if subscribed is None:
        cur.execute(_q("""UPDATE users SET keywords=?, locations=?, remote_only=?
                          WHERE email=?"""),
                    (json.dumps(keywords), json.dumps(locs_in),
                     int(remote_only), email.lower()))
    else:
        cur.execute(_q("""UPDATE users SET keywords=?, locations=?, remote_only=?,
                          subscribed=? WHERE email=?"""),
                    (json.dumps(keywords), json.dumps(locs_in),
                     int(remote_only), int(subscribed), email.lower()))
    con.commit()


# ---------- FastAPI ----------
app = FastAPI(title="Internship Aggregator")


BASE_CSS = """
<style>
 body{font-family:system-ui,Arial;max-width:900px;margin:24px auto;padding:0 16px;color:#222}
 h1,h2{color:#0b6}
 input,select,textarea{padding:8px;margin:4px 0;width:100%;box-sizing:border-box;
   border:1px solid #ccc;border-radius:6px}
 button{padding:10px 16px;border:0;border-radius:6px;background:#0b6;color:#fff;
   cursor:pointer;margin-right:8px}
 button.alt{background:#333}
 .card{border:1px solid #eee;border-radius:8px;padding:14px;margin:10px 0}
 .muted{color:#666;font-size:13px}
 .row{display:flex;gap:8px;flex-wrap:wrap}
 .row>*{flex:1}
 .tag{display:inline-block;background:#eef;color:#225;border-radius:10px;
   padding:2px 8px;margin:2px;font-size:12px}
 nav a{margin-right:12px;color:#0b6;text-decoration:none}
 pre{background:#f6f6f6;padding:10px;border-radius:6px;overflow:auto;font-size:12px}
 .ok{color:#0b6} .warn{color:#b60}
</style>
"""


def layout(title, body, user_email=None):
    nav = (f"<nav><a href='/dashboard'>Dashboard</a>"
           f"<a href='/search'>Search</a>"
           f"<a href='/logout'>Logout</a></nav><hr>") if user_email else \
          ("<nav><a href='/login'>Login</a>"
           "<a href='/register'>Register</a></nav><hr>")
    return f"""<!doctype html><html><head><meta charset="utf-8">
    <title>{title}</title>{BASE_CSS}</head><body>{nav}{body}</body></html>"""


def current_user(request: Request):
    tok = request.cookies.get("session")
    if not tok:
        return None
    email = read_session(tok)
    return get_user(email) if email else None


def _error_page(title, e):
    tb = traceback.format_exc()
    return HTMLResponse(layout(title, f"""
      <h2>⚠ {type(e).__name__}</h2><p>{e}</p><pre>{tb}</pre>
      <p><a href="/">← home</a></p>"""), status_code=500)


@app.on_event("startup")
def _startup():
    init_db()
    print("[web] DB initialized")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    u = current_user(request)
    if u:
        return RedirectResponse("/dashboard", 302)
    return HTMLResponse(layout("Home", """
        <h1>Internship Aggregator</h1>
        <p>Scrapes 9 sources, matches to your keywords, delivers by email.</p>
        <p><a href="/register"><button>Create account</button></a>
           <a href="/login"><button class="alt">Login</button></a></p>
    """))


@app.get("/register", response_class=HTMLResponse)
def register_form():
    return HTMLResponse(layout("Register", """
      <h2>Create account</h2>
      <form method="post" action="/register">
        <input name="email" type="email" placeholder="you@example.com" required>
        <input name="password" type="password" placeholder="Password (min 6)"
               required minlength="6">
        <button type="submit">Register</button>
      </form>"""))


@app.post("/register")
def register(email: str = Form(...), password: str = Form(...)):
    try:
        if not create_user(email, password):
            return HTMLResponse(layout("Register",
                "<p>Email already registered. <a href='/login'>Login?</a></p>"),
                status_code=400)
        resp = RedirectResponse("/dashboard", 302)
        resp.set_cookie("session", make_session(email.lower()),
                        httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
        return resp
    except Exception as e:
        print("=== /register error ===")
        traceback.print_exc()
        return _error_page("Register error", e)


@app.get("/login", response_class=HTMLResponse)
def login_form():
    return HTMLResponse(layout("Login", """
      <h2>Login</h2>
      <form method="post" action="/login">
        <input name="email" type="email" required placeholder="you@example.com">
        <input name="password" type="password" required placeholder="Password">
        <button type="submit">Login</button>
      </form>"""))


@app.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    try:
        u = get_user(email)
        if not u or not verify_pw(password, u["password_hash"]):
            return HTMLResponse(layout("Login",
                "<p>Invalid credentials.</p>"), status_code=401)
        resp = RedirectResponse("/dashboard", 302)
        resp.set_cookie("session", make_session(u["email"]),
                        httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
        return resp
    except Exception as e:
        print("=== /login error ===")
        traceback.print_exc()
        return _error_page("Login error", e)


@app.get("/logout")
def logout():
    resp = RedirectResponse("/", 302)
    resp.delete_cookie("session")
    return resp


@app.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: str = ""):
    email = read_unsubscribe_token(token) if token else None
    if not email:
        return HTMLResponse(layout("Unsubscribe",
            "<h2>Invalid or expired link</h2>"), status_code=400)
    u = get_user(email)
    if u:
        update_prefs(email, u["keywords"], u["locations"],
                     u["remote_only"], subscribed=False)
    return HTMLResponse(layout("Unsubscribe", f"""
      <h2>You're unsubscribed</h2>
      <p><b>{email}</b> will no longer receive emails.</p>
      <p><a href="/">← home</a></p>"""))


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, msg: str = ""):
    try:
        u = current_user(request)
        if not u:
            return RedirectResponse("/login", 302)
        kw = ", ".join(u["keywords"])
        loc = ", ".join(u["locations"])
        status = ('<span class="ok"><b>subscribed</b></span>'
                  if u["subscribed"] else '<span class="warn">not subscribed</span>')
        body = f"""
          <h1>Dashboard</h1>
          {f'<p class="ok">{msg}</p>' if msg else ''}
          <form method="post" action="/dashboard">
            <label>Keywords (comma separated)</label>
            <input name="keywords" value="{kw}" placeholder="machine learning, python">
            <label>Locations (comma separated, leave empty for anywhere)</label>
            <input name="locations" value="{loc}" placeholder="berlin, london">
            <p class="muted">Don't type <i>remote</i> here — use the checkbox below.</p>
            <label><input type="checkbox" name="remote_only" value="1"
              {'checked' if u['remote_only'] else ''}> Remote only</label>
            <div class="row">
              <button type="submit" name="action" value="save" class="alt">Save preferences</button>
              <button type="submit" name="action" value="subscribe">Subscribe to emails</button>
              <button type="submit" name="action" value="unsubscribe" class="alt">Unsubscribe</button>
            </div>
          </form>
          <p class="muted">Status: {status}</p>
          <p class="muted">Digests are sent by a scheduled job every 6 hours. New matches arrive automatically.</p>
          <p><a href="/search">→ Try instant Search</a></p>
        """
        return HTMLResponse(layout("Dashboard", body, u["email"]))
    except Exception as e:
        print("=== /dashboard error ===")
        traceback.print_exc()
        return _error_page("Dashboard error", e)


@app.post("/dashboard")
def update_dashboard(request: Request,
                     keywords: str = Form(""),
                     locations: str = Form(""),
                     remote_only: str = Form(None),
                     action: str = Form("save")):
    try:
        u = current_user(request)
        if not u:
            return RedirectResponse("/login", 302)
        kws = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        locs = [l.strip().lower() for l in locations.split(",") if l.strip()]
        ro = bool(remote_only)
        subscribed = u["subscribed"]
        if action == "subscribe":
            subscribed = True
        if action == "unsubscribe":
            subscribed = False
        update_prefs(u["email"], kws, locs, ro, subscribed=subscribed)
        msg = {"subscribe": "Subscribed! You'll receive digests.",
               "unsubscribe": "Unsubscribed.",
               "save": "Preferences saved."}[action]
        return RedirectResponse(f"/dashboard?msg={msg}", 302)
    except Exception as e:
        print("=== /dashboard POST error ===")
        traceback.print_exc()
        return _error_page("Save error", e)


@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request, tf: str = "week"):
    u = current_user(request)
    if not u:
        return RedirectResponse("/login", 302)
    pre_kw = ", ".join(u["keywords"])
    pre_loc = ", ".join(u["locations"])
    hint = "" if pre_kw else ('<p class="warn">⚠ No keywords saved yet. '
                              'Type some below or save them on the Dashboard.</p>')
    body = f"""
      <h1>Instant Search</h1>
      {hint}
      <form method="post" action="/search">
        <label>Keywords (comma separated, required)</label>
        <input name="keywords" value="{pre_kw}" required
               placeholder="python, machine learning, data science">
        <label>Locations (optional, leave empty for anywhere)</label>
        <input name="locations" value="{pre_loc}" placeholder="berlin, london">
        <label><input type="checkbox" name="remote_only" value="1"
          {'checked' if u['remote_only'] else ''}> Remote only</label>
        <label>Time filter</label>
        <select name="tf">
          <option value="24h"  {'selected' if tf=='24h' else ''}>Last 24 hours</option>
          <option value="week" {'selected' if tf=='week' else ''}>Last week</option>
          <option value="month"{'selected' if tf=='month' else ''}>Last month</option>
          <option value="all"  {'selected' if tf=='all' else ''}>All time</option>
        </select>
        <button type="submit">Search</button>
      </form>
      <p class="muted">Tip: broaden keywords or pick <b>All time</b> if you get 0 results.</p>
    """
    return HTMLResponse(layout("Search", body, u["email"]))


@app.post("/search", response_class=HTMLResponse)
def search_run(request: Request,
               keywords: str = Form(""),
               locations: str = Form(""),
               remote_only: str = Form(None),
               tf: str = Form("week")):
    try:
        u = current_user(request)
        if not u:
            return RedirectResponse("/login", 302)
        kws = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        raw_locs = [l.strip().lower() for l in locations.split(",") if l.strip()]
        ro = bool(remote_only)
        # Normalize locations (promote 'remote' to remote_only)
        remote_tokens = {"remote", "anywhere", "worldwide", "global"}
        if any(t in remote_tokens for t in raw_locs):
            ro = True
            raw_locs = [l for l in raw_locs if l not in remote_tokens]
        locs = raw_locs

        total_in_db = len(get_all_internships_df())

        if not kws:
            return HTMLResponse(layout("Results", f"""
              <h1>0 results</h1>
              <p class="warn">⚠ No keywords provided. Please enter at least one.</p>
              <p class="muted">DB currently holds {total_in_db} internships.</p>
              <p><a href="/search">← back</a></p>""", u["email"]))

        rows = search(kws, locs, ro, time_filter=tf, min_score=0.08)

        cards = ""
        for _, r in rows.head(50).iterrows():
            tags = "".join(f"<span class='tag'>{t}</span>"
                           for t in (json.loads(r['tags']) if r['tags'] else [])[:6])
            cards += f"""
            <div class="card">
              <h3 style="margin:0 0 6px 0">{r['title']}</h3>
              <div class="muted"><b>{r['company'] or '—'}</b> ·
                 {r['location'] or '—'} · <i>{r['source']}</i> ·
                 score {r['score']:.2f}</div>
              <p style="font-size:13px">{(r['description'] or '')[:220]}…</p>
              <a href="{r['url']}" target="_blank">View & apply →</a>
              <div>{tags}</div>
            </div>"""

        body = f"""
          <h1>Results ({len(rows)})</h1>
          <p class="muted">filter: <b>{tf}</b> · keywords: {', '.join(kws) or '—'}
             · DB total: {total_in_db}</p>
          <p><a href="/search">← new search</a></p>
          {cards or '<p>No matches. Try broader keywords or All time.</p>'}
        """
        return HTMLResponse(layout("Results", body, u["email"]))
    except Exception as e:
        print("=== /search error ===")
        traceback.print_exc()
        return _error_page("Search error", e)


@app.get("/healthz")
def healthz():
    return {"ok": True, "ts": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

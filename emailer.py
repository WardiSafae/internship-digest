"""
Email digest renderer + sender.
Uses SMTP (works with Brevo, Gmail, Mailgun, etc.).
Signs unsubscribe tokens with SECRET_KEY.
"""
import os
import smtplib
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from db import get_user, get_sent, mark_sent

SECRET_KEY = os.environ["SECRET_KEY"]
_unsub_signer = URLSafeTimedSerializer(SECRET_KEY, salt="unsubscribe")


def make_unsubscribe_token(email):
    return _unsub_signer.dumps({"email": email})


def read_unsubscribe_token(token, max_age=60 * 60 * 24 * 365):
    try:
        return _unsub_signer.loads(token, max_age=max_age)["email"]
    except (BadSignature, SignatureExpired):
        return None


def _dry_run():
    return os.environ.get("DRY_RUN", "1") == "1"


def _normalize_locations(locations, remote_only):
    locs = [l.strip().lower() for l in (locations or []) if l and l.strip()]
    remote_tokens = {"remote", "anywhere", "worldwide", "global"}
    if any(t in remote_tokens for t in locs):
        remote_only = True
        locs = [l for l in locs if l not in remote_tokens]
    return locs, bool(remote_only)


def _base_url():
    return os.environ.get("APP_BASE_URL", "").rstrip("/")


def render_digest(user, rows):
    items = ""
    for _, r in rows.iterrows():
        items += f"""
        <div style="border:1px solid #eee;border-radius:8px;padding:14px;margin:10px 0">
          <h3 style="margin:0 0 6px 0">{r['title']}</h3>
          <div style="color:#555;font-size:13px">
            <b>{r['company'] or '—'}</b> · {r['location'] or '—'} ·
            <i>{r['source']}</i> · match {r.get('score', 0):.2f}
          </div>
          <p style="font-size:13px;color:#333">{(r['description'] or '')[:220]}…</p>
          <a href="{r['url']}" style="color:#0b6">View & apply →</a>
        </div>"""

    unsub = make_unsubscribe_token(user["email"])
    base = _base_url()
    unsub_line = (f'<a href="{base}/unsubscribe?token={unsub}">Unsubscribe</a>'
                  if base else
                  f'Reply STOP to unsubscribe')

    return f"""<html><body style="font-family:Arial,sans-serif;max-width:640px;margin:auto">
      <h2>🎯 {len(rows)} new internship matches</h2>
      <p>Keywords: <i>{', '.join(user['keywords'])}</i></p>
      {items}
      <p style="color:#999;font-size:11px">{unsub_line}</p>
    </body></html>"""


def send_email(to, subject, html):
    if _dry_run():
        print(f"[DRY] → {to}: {subject}")
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = os.environ["FROM_ADDR"]
    msg["To"] = to
    msg["List-Unsubscribe"] = f"<mailto:{os.environ['FROM_ADDR']}?subject=unsubscribe>"
    msg["Precedence"] = "bulk"
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(os.environ["SMTP_HOST"],
                          int(os.environ["SMTP_PORT"]), timeout=20) as s:
            s.starttls()
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
            s.sendmail(os.environ["FROM_ADDR"], [to], msg.as_string())
        return True
    except Exception as e:
        print("smtp fail:", e)
        traceback.print_exc()
        return False


def run_digest_for(email, top_n=10, time_filter="all"):
    """Send digest for one user. Returns a status dict."""
    # Import here to avoid circular imports when matcher imports db
    from matcher import search

    u = get_user(email)
    if not u:
        return {"status": "no_user", "sent": 0}
    if not u["subscribed"]:
        return {"status": "not_subscribed", "sent": 0}
    if not u["keywords"]:
        return {"status": "no_keywords", "sent": 0}

    locs, ro = _normalize_locations(u["locations"], u["remote_only"])
    sent_ids = get_sent(email)

    hits = search(u["keywords"], locs, ro,
                  time_filter=time_filter, min_score=u["min_score"])
    raw = len(hits)
    hits = hits[~hits["id"].isin(sent_ids)].head(top_n)

    print(f"[digest] {email}: raw={raw} already_sent={len(sent_ids)} "
          f"new={len(hits)} kw={u['keywords']} locs={locs} ro={ro}")

    if hits.empty:
        return {"status": "no_new", "raw": raw,
                "already_sent": len(sent_ids), "sent": 0}

    ok = send_email(u["email"],
                    f"🎯 {len(hits)} internship matches — {datetime.utcnow():%Y-%m-%d}",
                    render_digest(u, hits))

    if ok and not _dry_run():
        mark_sent(email, hits["id"].tolist())

    return {"status": "sent" if ok else "send_failed",
            "raw": raw, "sent": len(hits) if ok else 0}
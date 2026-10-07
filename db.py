"""
Database layer for the internship digest.
Reads DATABASE_URL from environment. Uses Postgres.
"""
import os
import json
import threading
from datetime import datetime

import psycopg2

_DB_LOCK = threading.RLock()
_DB_CONN = None

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")


def _q(sql: str) -> str:
    """Convert ? placeholders to %s (Postgres format)."""
    return sql.replace("?", "%s")


def get_conn():
    """Return a live DB connection. Auto-reconnects if the previous one died."""
    global _DB_CONN
    if _DB_CONN is not None:
        # Health check: cheap query to confirm the connection is alive
        try:
            cur = _DB_CONN.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            return _DB_CONN
        except Exception:
            # Connection died (Neon suspension, network blip, etc.)
            try:
                _DB_CONN.close()
            except Exception:
                pass
            _DB_CONN = None

    # Fresh connection
    _DB_CONN = psycopg2.connect(DATABASE_URL)
    return _DB_CONN

def init_db():
    con = get_conn()
    with _DB_LOCK:
        cur = con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS internships (
            id TEXT PRIMARY KEY,
            title TEXT, company TEXT, location TEXT,
            description TEXT, url TEXT, source TEXT, tags TEXT,
            posted_at TEXT, remote INTEGER, scraped_at TEXT
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT,
            keywords TEXT DEFAULT '[]',
            locations TEXT DEFAULT '[]',
            remote_only INTEGER DEFAULT 1,
            min_score REAL DEFAULT 0.12,
            subscribed INTEGER DEFAULT 0,
            created_at TEXT
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS sent (
            email TEXT, internship_id TEXT, sent_at TEXT,
            PRIMARY KEY (email, internship_id)
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scraped ON internships(scraped_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_posted  ON internships(posted_at)")
        con.commit()
    return con


# ---------- Internships ----------

def save_internships(items) -> int:
    con = get_conn()
    n = 0
    with _DB_LOCK:
        cur = con.cursor()
        for it in items:
            cur.execute(_q("SELECT 1 FROM internships WHERE id=?"), (it.id,))
            if cur.fetchone():
                continue
            cur.execute(_q("""INSERT INTO internships
                (id, title, company, location, description, url, source, tags,
                 posted_at, remote, scraped_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)"""),
                (it.id, it.title, it.company, it.location, it.description,
                 it.url, it.source, json.dumps(it.tags), it.posted_at,
                 int(it.remote), datetime.utcnow().isoformat()))
            n += 1
        con.commit()
    return n


def get_all_internships_df():
    import pandas as pd
    con = get_conn()
    with _DB_LOCK:
        cur = con.cursor()
        cur.execute("SELECT * FROM internships")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


# ---------- Users ----------

def get_user(email: str):
    con = get_conn()
    with _DB_LOCK:
        cur = con.cursor()
        cur.execute(_q("SELECT * FROM users WHERE email=?"), (email.lower(),))
        row = cur.fetchone()
    if not row:
        return None
    cols = ["email", "password_hash", "keywords", "locations",
            "remote_only", "min_score", "subscribed", "created_at"]
    u = dict(zip(cols, row))
    u["keywords"] = json.loads(u["keywords"] or "[]")
    u["locations"] = json.loads(u["locations"] or "[]")
    u["remote_only"] = bool(u["remote_only"])
    return u


def get_subscribed_users():
    con = get_conn()
    with _DB_LOCK:
        cur = con.cursor()
        cur.execute("SELECT email FROM users WHERE subscribed=1")
        return [r[0] for r in cur.fetchall()]


# ---------- Sent tracking ----------

def get_sent(email: str):
    con = get_conn()
    with _DB_LOCK:
        cur = con.cursor()
        cur.execute(_q("SELECT internship_id FROM sent WHERE email=?"), (email,))
        return {r[0] for r in cur.fetchall()}


def mark_sent(email: str, ids):
    con = get_conn()
    with _DB_LOCK:
        cur = con.cursor()
        for i in ids:
            cur.execute(_q("""INSERT INTO sent (email, internship_id, sent_at)
                              VALUES (?,?,?)
                              ON CONFLICT (email, internship_id) DO NOTHING"""),
                        (email, i, datetime.utcnow().isoformat()))
        con.commit()

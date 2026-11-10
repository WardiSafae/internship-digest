"""Needs a throw-away PostgreSQL database:

    TEST_DATABASE_URL=postgresql://user:pass@localhost/test pytest tests/test_postgres_pipeline.py
"""
import os

import pytest

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


def test_insert_is_idempotent_and_reports_new_vs_known(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", URL)
    for mod in ("db",):           # db.py reads DATABASE_URL at import time
        import sys
        sys.modules.pop(mod, None)
    import db
    db.init_db()
    cur = db.get_conn().cursor()
    cur.execute("DELETE FROM internships WHERE source='pytest'")
    row = dict(id="a" * 32, title="T", company="C", location="L", description="D",
               url="https://u", source="pytest", tags=["x"], posted_at="", remote=True)
    assert db.insert_internship(cur, row, "2026-01-01T00:00:00") is True
    assert db.insert_internship(cur, row, "2026-01-01T00:00:00") is False   # same id -> ignored
    db.get_conn().commit()
    cur.execute("SELECT count(*), bool_or(remote = 1) FROM internships WHERE source='pytest'")
    assert cur.fetchone() == (1, True)
    cur.execute("DELETE FROM internships WHERE source='pytest'")
    db.get_conn().commit()

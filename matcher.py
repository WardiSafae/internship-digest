"""
Search/matcher over internships. Includes the fixed location filter:
  - word-boundary aware (won't match 'us' inside 'Australia')
  - falls back to the description when the location field is empty
  - case-insensitive
"""
import re
import pandas as pd
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from db import get_all_internships_df


def _age_cutoff(time_filter: str):
    now = datetime.utcnow()
    return {
        "24h":   now - timedelta(hours=24),
        "week":  now - timedelta(days=7),
        "month": now - timedelta(days=30),
        "all":   None,
    }.get(time_filter, None)


def _row_age(r):
    for col in ("posted_at", "scraped_at"):
        v = r.get(col)
        if not v:
            continue
        try:
            return datetime.fromisoformat(str(v).replace("Z", "")[:19])
        except Exception:
            try:
                from email.utils import parsedate_to_datetime
                return parsedate_to_datetime(str(v)).replace(tzinfo=None)
            except Exception:
                continue
    return datetime.utcnow()


# ---------- the fixed location matcher ----------

def location_match(location_text, wanted_locations):
    """
    True if location_text mentions any of wanted_locations.
    Word-boundary aware for short tokens.
    """
    if not wanted_locations:
        return True
    if not location_text:
        return False
    t = str(location_text).lower()
    for loc in wanted_locations:
        loc = loc.strip().lower()
        if not loc:
            continue
        if re.search(rf"\b{re.escape(loc)}\b", t):
            return True
        if len(loc) >= 4 and loc in t:
            return True
    return False


def _row_matches_locations(r, locations):
    """Match against location field first, then description."""
    if location_match(r.get("location", ""), locations):
        return True
    if location_match(r.get("description", ""), locations):
        return True
    return False


# ---------- search ----------

def search(keywords, locations, remote_only, time_filter="week", min_score=0.10):
    df = get_all_internships_df()
    if df.empty:
        return df

    cutoff = _age_cutoff(time_filter)
    if cutoff is not None:
        df["_age"] = df.apply(_row_age, axis=1)
        df = df[df["_age"] >= cutoff]

    if remote_only:
        df = df[df["remote"] == 1]

    if locations and not df.empty:
        mask = df.apply(lambda r: _row_matches_locations(r, locations), axis=1)
        df = df[mask]

    if df.empty or not keywords:
        return df.iloc[0:0]

    kws = " ".join(keywords)
    corpus = (df["title"].fillna("") + " " +
              df["description"].fillna("") + " " +
              df["tags"].fillna("") + " " +
              df["location"].fillna("")).tolist()

    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=20000)
    try:
        M = vec.fit_transform([kws] + corpus)
    except ValueError:
        return df.iloc[0:0]
    base_scores = cosine_similarity(M[0:1], M[1:]).flatten()

    # Title boost
    try:
        tv = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        TM = tv.fit_transform([kws] + df["title"].fillna("").tolist())
        title_scores = cosine_similarity(TM[0:1], TM[1:]).flatten()
    except ValueError:
        title_scores = base_scores * 0.0

    final = 0.7 * base_scores + 0.3 * title_scores
    df = df.assign(score=final)
    return (df[df["score"] >= min_score]
              .sort_values("score", ascending=False)
              .reset_index(drop=True))
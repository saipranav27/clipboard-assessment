"""SQLite state: proposals, decisions, runs.

Re-run safety: every proposal gets a fingerprint from (kind, subject, the exact target
values it would write). A fingerprint that was ever approved/rejected/applied is never
proposed again. If the website or CRM later changes so the *target* differs, that is a
new fingerprint and a new proposal, which is the behaviour we want.
Pending proposals that a later run no longer generates are marked 'stale'.
"""
import hashlib
import json
import sqlite3
import datetime as dt

from . import config

DECIDED = ("approved", "rejected", "applied", "failed")

SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
  fingerprint TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  subject TEXT NOT NULL,
  account_id TEXT,
  site_slug TEXT,
  title TEXT,
  confidence TEXT,
  evidence TEXT,
  ops TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  first_run TEXT,
  last_seen_run TEXT,
  created_at TEXT,
  decided_at TEXT,
  reviewer_comment TEXT,
  result TEXT,
  error TEXT
);
CREATE INDEX IF NOT EXISTS ix_prop_status ON proposals(status);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  started_at TEXT, finished_at TEXT,
  stats TEXT, report TEXT
);
"""


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def connect(path=None):
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, isolation_level=None, timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _strip_volatile(obj):
    """Notes carry today's date; drop them from the fingerprint so dates don't create new items."""
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items()
                if k not in ("append_note", "guard_no_match") and k not in config.FIELD_ALIASES["note"]}
    if isinstance(obj, list):
        return [_strip_volatile(x) for x in obj]
    return obj


def fingerprint(p):
    basis = {"kind": p["kind"], "subject": p["subject"], "ops": _strip_volatile(p["ops"])}
    return hashlib.sha1(json.dumps(basis, sort_keys=True, default=str).encode()).hexdigest()[:16]


def upsert_proposals(con, run_id, proposals):
    stats = {"new": 0, "still_pending": 0, "skipped_already_decided": 0, "stale": 0}
    seen = set()
    for p in proposals:
        fp = fingerprint(p)
        seen.add(fp)
        row = con.execute("SELECT status FROM proposals WHERE fingerprint=?", (fp,)).fetchone()
        if row is None:
            con.execute(
                "INSERT INTO proposals (fingerprint, kind, subject, account_id, site_slug, title, confidence,"
                " evidence, ops, status, first_run, last_seen_run, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (fp, p["kind"], p["subject"], p.get("account_id"), p.get("site_slug"), p["title"],
                 p.get("confidence"), json.dumps(p["evidence"], default=str), json.dumps(p["ops"], default=str),
                 "pending", run_id, run_id, now()))
            stats["new"] += 1
        elif row["status"] in DECIDED:
            stats["skipped_already_decided"] += 1
        else:  # pending or stale -> refresh evidence, keep it pending
            con.execute("UPDATE proposals SET status='pending', last_seen_run=?, evidence=?, title=? WHERE fingerprint=?",
                        (run_id, json.dumps(p["evidence"], default=str), p["title"], fp))
            stats["still_pending"] += 1
    for row in con.execute("SELECT fingerprint FROM proposals WHERE status='pending'").fetchall():
        if row["fingerprint"] not in seen:
            con.execute("UPDATE proposals SET status='stale' WHERE fingerprint=?", (row["fingerprint"],))
            stats["stale"] += 1
    return stats


def record_run(con, run_id, started, stats, report):
    con.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?)",
                (run_id, started, now(), json.dumps(stats), json.dumps(report, default=str)))


def latest_run(con):
    return con.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()


def get(con, fp):
    return con.execute("SELECT * FROM proposals WHERE fingerprint=?", (fp,)).fetchone()


def list_by_status(con, statuses):
    q = ",".join("?" * len(statuses))
    order = ("CASE kind WHEN 'DUPLICATE_PARENT' THEN 0 WHEN 'CHOW' THEN 1 WHEN 'LINK_CHOW' THEN 2 "
             "WHEN 'REPARENT' THEN 3 WHEN 'DUPLICATE' THEN 4 WHEN 'UPDATE_FIELDS' THEN 5 "
             "WHEN 'CREATE' THEN 6 ELSE 7 END, title")
    return con.execute(f"SELECT * FROM proposals WHERE status IN ({q}) ORDER BY {order}", statuses).fetchall()


def set_status(con, fp, status, **extra):
    cols = ", ".join(f"{k}=?" for k in extra)
    con.execute(f"UPDATE proposals SET status=?, decided_at=?{', ' + cols if cols else ''} WHERE fingerprint=?",
                (status, now(), *extra.values(), fp))


def claim(con, fp):
    """Atomically move pending -> approved. Returns False if someone already decided it."""
    cur = con.execute("UPDATE proposals SET status='approved', decided_at=? WHERE fingerprint=? AND status='pending'",
                      (now(), fp))
    return cur.rowcount == 1

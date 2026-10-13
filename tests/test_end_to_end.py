"""End-to-end test against the local fake site + CRM (no network).

Routes `requests` through Flask's test client so the real Scraper/CRM classes are exercised.
Run:  python -m pytest -q
"""
import json
import os
import sys
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from fake_server import make_app  # noqa: E402

BASE = "http://fake.test"


class FlaskSession(requests.Session):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def request(self, method, url, params=None, json=None, timeout=None, **kw):
        path = url.replace(BASE, "") or "/"
        r = self.client.open(path, method=method, query_string=params, json=json, headers=dict(self.headers))
        resp = requests.Response()
        resp.status_code, resp._content, resp.url = r.status_code, r.data, url
        resp.headers.update(dict(r.headers))
        return resp

    def get(self, url, **kw):
        return self.request("GET", url, **kw)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("BH_TOKEN", "test")
    from bh import config
    monkeypatch.setattr(config, "TOKEN", "test")
    monkeypatch.setattr(config, "BASE_URL", BASE)
    monkeypatch.setattr(config, "API_BASE", BASE + "/api/v1")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "state.db")
    monkeypatch.setattr(config, "SNAPSHOT_DIR", tmp_path / "snaps")
    app = make_app()
    client = app.test_client()
    from bh import scraper, crm
    monkeypatch.setattr(scraper.requests, "Session", lambda: FlaskSession(client))
    monkeypatch.setattr(crm.requests, "Session", lambda: FlaskSession(client))
    return app


def acct(app, aid):
    return next(a for a in app.config["STATE"]["accounts"] if a["account_id"] == aid)


def test_full_flow(env):
    import run_pipeline
    from bh import store
    from bh.apply import apply_proposal
    from bh.crm import CRM

    assert run_pipeline.main([]) == 0
    con = store.connect()
    pend = {(r["kind"], r["account_id"] or r["site_slug"]): r for r in store.list_by_status(con, ["pending"])}
    kinds = sorted(pend)
    print(json.dumps(kinds, indent=1))

    expect = {
        ("DUPLICATE_PARENT", "A101"), ("CHOW", "A003"), ("REPARENT", "A004"), ("REPARENT", "A005"),
        ("DUPLICATE", "A007"), ("REPARENT", "A008"), ("UPDATE_FIELDS", "A009"), ("UPDATE_FIELDS", "A002"),
        ("LINK_CHOW", "A014"), ("UPDATE_FIELDS", "A016"), ("ORPHAN", "A017"), ("CHOW", "A018"),
        ("REPARENT", "A019"), ("CREATE", "bellhaven-meadows-of-findlay"),
    }
    assert expect <= set(kinds), expect - set(kinds)
    # Must NOT propose anything for the clean account, the finished CHOW pair, the unrelated Toledo,
    # or the correctly-separate Carlisle / New Carlisle accounts.
    touched = {k[1] for k in kinds}
    for clean in ("A001", "A010", "A011", "A012", "A013", "A020", "A006"):
        assert not any(k[1] == clean and k[0] not in ("UPDATE_FIELDS",) for k in kinds), clean
    assert ("UPDATE_FIELDS", "A001") not in pend
    assert ("UPDATE_FIELDS", "A013") not in pend

    crm = CRM()
    crm.detect_fields(crm.list_accounts())
    # Reject one, approve the rest.
    rej = pend[("ORPHAN", "A017")]["fingerprint"]
    con.execute("UPDATE proposals SET status='rejected' WHERE fingerprint=?", (rej,))
    for k, r in pend.items():
        if r["fingerprint"] != rej:
            ok, info = apply_proposal(con, crm, r["fingerprint"])
            assert ok, (k, info)

    a003 = acct(env, "A003")
    assert a003["parent_id"] == "A200" and a003["chow_current_account"]           # old preserved, linked
    new = acct(env, a003["chow_current_account"])
    assert new["parent_id"] == "A100" and new["name"] == "Bellhaven Terrace of Akron"
    assert acct(env, "A004")["parent_id"] == "A100"                               # rev but no AR
    assert acct(env, "A005")["parent_id"] == "A100"                               # AR but no rev
    assert acct(env, "A008")["parent_id"] == "A100"                               # dup-parent fix
    assert acct(env, "A007")["duplicate_of_account"] == "A006" and acct(env, "A007")["status"] == "Inactive"
    assert acct(env, "A014")["chow_current_account"] == "A015" and acct(env, "A014")["parent_id"] == "A200"
    assert acct(env, "A002")["name"] == "Bellhaven of Wooster" and "formerly" in acct(env, "A002")["note"]
    assert acct(env, "A009")["billing_zip"] == "43615"
    assert acct(env, "A016")["status"] == "Active"
    assert acct(env, "A017")["status"] == "Active"                                # rejected -> untouched
    assert acct(env, "A101")["duplicate_of_account"] == "A100"
    findlay = [a for a in env.config["STATE"]["accounts"] if a["name"] == "Bellhaven Meadows of Findlay"]
    assert len(findlay) == 1 and findlay[0]["parent_id"] == "A100"
    bh = "Bellhaven Senior Living (Parent Account)"
    assert acct(env, "A004")["parent_name"] == bh and new["parent_name"] == bh and findlay[0]["parent_name"] == bh
    assert findlay[0]["care_type"] == "Assisted Living"           # CRM vocabulary, single value
    assert new["care_type"] == "Assisted Living"
    assert acct(env, "A003")["parent_name"] == "Harborview Care Group (Parent Account)"  # old CHOW record untouched

    # Re-run: nothing already decided comes back, and nothing new appears.
    n_before = len(env.config["STATE"]["accounts"])
    assert run_pipeline.main([]) == 0
    again = store.list_by_status(con, ["pending"])
    assert again == [] or all(r["kind"] not in ("CHOW", "CREATE") for r in again), [dict(r)["title"] for r in again]
    assert not again, [r["title"] for r in again]
    assert len(env.config["STATE"]["accounts"]) == n_before


def test_double_approve_is_safe(env):
    import run_pipeline
    from bh import store
    from bh.apply import apply_proposal
    from bh.crm import CRM
    run_pipeline.main([])
    con = store.connect()
    crm = CRM(); crm.detect_fields(crm.list_accounts())
    fp = next(r["fingerprint"] for r in store.list_by_status(con, ["pending"]) if r["kind"] == "CREATE")
    assert apply_proposal(con, crm, fp)[0]
    assert apply_proposal(con, crm, fp)[0] is False
    assert sum(a["name"] == "Bellhaven Meadows of Findlay" for a in env.config["STATE"]["accounts"]) == 1


def test_stale_guard(env):
    import run_pipeline
    from bh import store
    from bh.apply import apply_proposal
    from bh.crm import CRM
    run_pipeline.main([])
    con = store.connect()
    crm = CRM(); crm.detect_fields(crm.list_accounts())
    r = next(r for r in store.list_by_status(con, ["pending"]) if r["kind"] == "REPARENT" and r["account_id"] == "A004")
    acct(env, "A004")["parent_id"] = "A400"  # someone changed it meanwhile
    ok, msg = apply_proposal(con, crm, r["fingerprint"])
    assert not ok and "changed since" in msg
    assert acct(env, "A004")["parent_id"] == "A400"

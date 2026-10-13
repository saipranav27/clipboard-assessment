#!/usr/bin/env python3
"""Review app. Every CRM write happens here, and only after a reviewer approves.

  BH_TOKEN=... python app.py      ->  http://127.0.0.1:5050
"""
import json

from flask import Flask, redirect, render_template_string, request, url_for, flash

from bh import config, store
from bh.apply import apply_proposal, retry
from bh.crm import CRM

app = Flask(__name__)
app.secret_key = "local-review-app"
_crm = None


def crm():
    global _crm
    if _crm is None:
        _crm = CRM()
        _crm.detect_fields(_crm.list_accounts())
    return _crm


TABS = {"pending": ["pending"], "applied": ["applied"], "rejected": ["rejected"],
        "failed": ["failed", "stale", "approved"]}
KIND_LABEL = {
    "CHOW": "Change of ownership", "LINK_CHOW": "Link CHOW pair", "REPARENT": "Re-parent",
    "DUPLICATE": "Duplicate", "DUPLICATE_PARENT": "Duplicate parent", "UPDATE_FIELDS": "Field fix",
    "CREATE": "New location", "ORPHAN": "Not on website",
}
SHOW_FIELDS = ["name", "street", "city", "state", "zip", "phone", "care_offerings", "parent_name", "parent_id",
               "status", "lifetime_revenue", "outstanding_ar", "duplicate_of_account", "chow_current_account", "note"]

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Bellhaven Sync Review</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6a65;--line:#e4e2dc;--accent:#2f5d50;
--ok:#2e7d4f;--bad:#b3412f;--warn:#a46a00;--chip:#eeece6}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 -apple-system,Segoe UI,Inter,sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--ink);color:#fff;padding:14px 24px;display:flex;gap:24px;align-items:center;flex-wrap:wrap}
header h1{font-size:16px;margin:0;font-weight:600;letter-spacing:.2px}header .meta{color:#bbb;font-size:12px}
header form{margin-left:auto}
nav{display:flex;gap:4px;padding:12px 24px 0;flex-wrap:wrap}nav a{padding:8px 14px;border-radius:8px 8px 0 0;color:var(--mute);text-decoration:none;font-weight:500}
nav a.on{background:var(--card);color:var(--ink);border:1px solid var(--line);border-bottom:none}
main{background:var(--card);margin:0 24px 40px;border:1px solid var(--line);border-radius:0 10px 10px 10px;padding:20px}
.flash{padding:10px 14px;border-radius:8px;margin-bottom:12px;background:#e7f2ea;border:1px solid #bfdcc8}
.flash.err{background:#fbecea;border-color:#efc4bd}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}.filters a{padding:4px 10px;border-radius:99px;background:var(--chip);color:var(--ink);text-decoration:none;font-size:12px}
.filters a.on{background:var(--accent);color:#fff}
.card{border:1px solid var(--line);border-radius:10px;margin-bottom:14px;overflow:hidden}
.card .top{display:flex;gap:10px;align-items:center;padding:12px 14px;background:#fbfaf8;border-bottom:1px solid var(--line);flex-wrap:wrap}
.kind{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;padding:3px 8px;border-radius:6px;background:var(--chip)}
.k-CHOW,.k-LINK_CHOW{background:#f3e3c3}.k-REPARENT{background:#dbe7f5}.k-DUPLICATE,.k-DUPLICATE_PARENT{background:#eadcf1}
.k-UPDATE_FIELDS{background:#e0efe5}.k-CREATE{background:#d9efed}.k-ORPHAN{background:#f6dcd6}
.conf{font-size:11px;color:var(--mute)}.conf.high{color:var(--ok)}.conf.low{color:var(--bad)}
.title{font-weight:600;flex:1;min-width:240px}
.body{padding:12px 14px;display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:18px}
@media (max-width:900px){.body{grid-template-columns:1fr}}
table{border-collapse:collapse;width:100%;font-size:12.5px}th,td{text-align:left;padding:4px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mute);font-weight:500;width:130px}td.diff{background:#fff6dd}
h4{margin:4px 0 6px;font-size:12px;color:var(--mute);text-transform:uppercase;letter-spacing:.4px}
ul.sig{margin:0;padding-left:18px}ul.sig li{margin:2px 0}
details summary{cursor:pointer;color:var(--mute);font-size:12px;margin-top:8px}pre{background:#f4f3ef;padding:8px;border-radius:6px;font-size:11px;overflow:auto;max-height:240px}
.actions{display:flex;gap:8px;align-items:center;padding:10px 14px;border-top:1px solid var(--line);background:#fbfaf8;flex-wrap:wrap}
.actions input[type=text]{flex:1;min-width:200px;padding:7px 9px;border:1px solid var(--line);border-radius:6px}
button{border:0;border-radius:6px;padding:8px 14px;font-weight:600;cursor:pointer}
.approve{background:var(--ok);color:#fff}.reject{background:#fff;color:var(--bad);border:1px solid var(--bad)}.ghost{background:#3a3a37;color:#fff}
a.crm{font-size:12px;color:var(--accent)}.err{color:var(--bad);font-size:12px}
.bulk{display:flex;gap:10px;align-items:center;margin-bottom:14px;padding:10px;background:#f4f3ef;border-radius:8px;font-size:13px}
.empty{color:var(--mute);padding:30px;text-align:center}
</style></head><body>
<header><h1>Bellhaven → CRM sync review</h1>
<span class="meta">{% if run %}Last run {{run['started_at']}} · {{run_stats}}{% else %}No runs yet{% endif %}</span>
<span class="meta">Parent: {{parent}}</span>
<form method="post" action="{{url_for('run_now')}}"><button class="ghost">Run pipeline now</button></form></header>
<nav>{% for t,n in counts %}<a class="{{'on' if t==tab}}" href="{{url_for('index',tab=t)}}">{{t|capitalize}} ({{n}})</a>{% endfor %}
<a class="{{'on' if tab=='matches'}}" href="{{url_for('index',tab='matches')}}">Confirmed matches</a></nav>
<main>
{% with msgs = get_flashed_messages(with_categories=true) %}{% for c,m in msgs %}<div class="flash {{c}}">{{m}}</div>{% endfor %}{% endwith %}
{% if tab=='matches' %}
  <table><tr><th>Website location</th><th>CRM account</th><th>Confidence</th><th>Signals</th></tr>
  {% for m in matches %}<tr><td><b>{{m.site.name}}</b><br>{{m.site.street}}, {{m.site.city}} {{m.site.state}} {{m.site.zip}}</td>
  <td><a class="crm" target="_blank" href="{{crm_url(m.account_id)}}">{{m.account_name}} ({{m.account_id}})</a>{% if m.duplicates %}<br><span class="err">+ duplicates: {{m.duplicates|join(', ')}}</span>{% endif %}</td>
  <td class="conf {{m.confidence}}">{{m.confidence}} · {{m.score}}</td><td>{{m.signals|join('; ')}}</td></tr>{% endfor %}</table>
{% else %}
<div class="filters"><a class="{{'on' if not kind}}" href="{{url_for('index',tab=tab)}}">All</a>
{% for k,n in kinds %}<a class="{{'on' if k==kind}}" href="{{url_for('index',tab=tab,kind=k)}}">{{label[k]}} ({{n}})</a>{% endfor %}</div>
{% if tab=='pending' and rows %}<form method="post" action="{{url_for('bulk')}}" id="bulk" class="bulk">
<span>Selected: <b id="nsel">0</b></span><button class="approve" name="action" value="approve">Approve selected</button>
<button class="reject" name="action" value="reject">Reject selected</button><label><input type="checkbox" onclick="document.querySelectorAll('.sel').forEach(c=>{c.checked=this.checked});cnt()"> select all shown</label></form>{% endif %}
{% for r in rows %}{% set ev = r.ev %}
<div class="card"><div class="top">
{% if tab=='pending' %}<input type="checkbox" class="sel" form="bulk" name="fp" value="{{r.fingerprint}}" onchange="cnt()">{% endif %}
<span class="kind k-{{r.kind}}">{{label[r.kind]}}</span><span class="title">{{r.title}}</span>
<span class="conf {{r.confidence}}">{{r.confidence}} confidence</span>
{% if r.account_id %}<a class="crm" target="_blank" href="{{crm_url(r.account_id)}}">open {{r.account_id}} in CRM ↗</a>{% endif %}</div>
<div class="body"><div>
{% if ev.diff %}<h4>Proposed field changes</h4><table><tr><th>Field</th><th>CRM now</th><th>Website</th></tr>
{% for d in ev.diff %}<tr><td>{{d.field}}</td><td>{{d.crm}}</td><td class="diff">{{d.website}}</td></tr>{% endfor %}</table>{% endif %}
<h4 style="margin-top:10px">Side by side</h4><table><tr><th></th><th>Website</th><th>CRM{% if ev.crm %} ({{ev.crm.id}}){% endif %}</th>{% if ev.target %}<th>Target / survivor ({{ev.target.id}})</th>{% endif %}</tr>
{% for f in fields %}{% set s = (ev.site or {}).get(f) %}{% set c = (ev.crm or {}).get(f) %}{% set t = (ev.target or {}).get(f) %}
{% if s or c or t %}<tr><th>{{f}}</th><td>{{s|fmt}}</td><td>{{c|fmt}}</td>{% if ev.target %}<td>{{t|fmt}}</td>{% endif %}</tr>{% endif %}{% endfor %}
{% if ev.site and ev.site.url %}<tr><th>source</th><td colspan="3"><a class="crm" target="_blank" href="{{ev.site.url}}">{{ev.site.url}}</a></td></tr>{% endif %}</table>
</div><div><h4>Evidence & reasoning</h4><ul class="sig">{% for s in ev.signals %}<li>{{s}}</li>{% endfor %}</ul>
<details><summary>API operations that will run on approval</summary><pre>{{r.ops_pretty}}</pre></details>
{% if r.result %}<details open><summary>Result</summary><pre>{{r.result_pretty}}</pre></details>{% endif %}
{% if r.error %}<p class="err">Error: {{r.error}}</p>{% endif %}
{% if r.reviewer_comment %}<p><i>Reviewer: {{r.reviewer_comment}}</i></p>{% endif %}
{% if r.decided_at %}<p class="conf">Decided {{r.decided_at}}</p>{% endif %}</div></div>
{% if r.status=='pending' %}<form class="actions" method="post" action="{{url_for('decide',fp=r.fingerprint)}}">
<input type="text" name="comment" placeholder="Optional comment (saved with the decision)">
<button class="approve" name="action" value="approve">Approve & write to CRM</button><button class="reject" name="action" value="reject">Reject</button></form>
{% elif r.status=='failed' %}<form class="actions" method="post" action="{{url_for('retry_one',fp=r.fingerprint)}}"><button class="ghost">Return to queue</button></form>{% endif %}
</div>{% else %}<div class="empty">Nothing here.</div>{% endfor %}
{% endif %}</main>
<script>function cnt(){document.getElementById('nsel')&&(document.getElementById('nsel').textContent=document.querySelectorAll('.sel:checked').length)}</script>
</body></html>"""


@app.template_filter("fmt")
def fmt(v):
    if v is None or v == "":
        return ""
    if isinstance(v, list):
        return ", ".join(map(str, v))
    return v


@app.context_processor
def helpers():
    return {"crm_url": lambda aid: config.CRM_BROWSER_ACCOUNT_URL.format(id=aid), "label": KIND_LABEL,
            "fields": SHOW_FIELDS}


def _row(r):
    d = dict(r)
    d["ev"] = json.loads(r["evidence"] or "{}")
    d["ops_pretty"] = json.dumps(json.loads(r["ops"] or "[]"), indent=2)
    d["result_pretty"] = json.dumps(json.loads(r["result"]), indent=2) if r["result"] else ""
    return d


@app.get("/")
def index():
    con = store.connect()
    tab = request.args.get("tab", "pending")
    kind = request.args.get("kind")
    run = store.latest_run(con)
    report = json.loads(run["report"]) if run else {}
    counts = [(t, len(store.list_by_status(con, s))) for t, s in TABS.items()]
    rows, kinds = [], []
    if tab in TABS:
        all_rows = store.list_by_status(con, TABS[tab])
        kc = {}
        for r in all_rows:
            kc[r["kind"]] = kc.get(r["kind"], 0) + 1
        kinds = sorted(kc.items(), key=lambda kv: list(KIND_LABEL).index(kv[0]))
        rows = [_row(r) for r in all_rows if not kind or r["kind"] == kind]
    parent = report.get("bellhaven_parent") or {}
    return render_template_string(
        PAGE, tab=tab, kind=kind, rows=rows, kinds=kinds, counts=counts, run=run,
        run_stats=" · ".join(f"{v} {k.replace('_', ' ')}" for k, v in json.loads(run["stats"]).items()) if run else "",
        matches=report.get("matches", []),
        parent=f"{parent.get('name')} ({parent.get('id')})" if parent else "?")


@app.post("/decide/<fp>")
def decide(fp):
    con = store.connect()
    comment = request.form.get("comment", "")
    if request.form["action"] == "reject":
        con.execute("UPDATE proposals SET status='rejected', decided_at=?, reviewer_comment=? "
                    "WHERE fingerprint=? AND status='pending'", (store.now(), comment, fp))
        flash("Rejected. It will not be proposed again.")
    else:
        con.execute("UPDATE proposals SET reviewer_comment=? WHERE fingerprint=?", (comment, fp))
        ok, info = apply_proposal(con, crm(), fp)
        flash(f"Applied to CRM {info if info else ''}" if ok else f"Not applied: {info}", "" if ok else "err")
    return redirect(request.referrer or url_for("index"))


@app.post("/bulk")
def bulk():
    con = store.connect()
    fps = request.form.getlist("fp")
    ok_n, errs = 0, []
    for fp in fps:
        if request.form["action"] == "reject":
            con.execute("UPDATE proposals SET status='rejected', decided_at=? WHERE fingerprint=? AND status='pending'",
                        (store.now(), fp))
            ok_n += 1
        else:
            ok, info = apply_proposal(con, crm(), fp)
            ok_n += ok
            if not ok:
                errs.append(info)
    flash(f"{request.form['action'].capitalize()}d {ok_n} of {len(fps)}." + (f" Errors: {errs[:3]}" if errs else ""),
          "err" if errs else "")
    return redirect(request.referrer or url_for("index"))


@app.post("/retry/<fp>")
def retry_one(fp):
    retry(store.connect(), fp)
    return redirect(url_for("index", tab="pending"))


@app.post("/run")
def run_now():
    import run_pipeline
    global _crm
    _crm = None  # refresh field map / accounts next time
    code = run_pipeline.main([])
    flash("Pipeline run finished." if code == 0 else "Pipeline run aborted; see terminal.", "" if code == 0 else "err")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(__import__("os").environ.get("PORT", 5050)), debug=False)

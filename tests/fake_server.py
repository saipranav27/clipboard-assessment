"""Local stand-in for the website + CRM API, seeded with the edge cases the pipeline must handle."""
import copy
import itertools

from flask import Flask, jsonify, request, abort

SITE = [  # (slug, name, street, city, state, zip, care, on_directory)
    ("bellhaven-of-maplewood", "Bellhaven of Maplewood", "100 Maple Ave", "Maplewood", "OH", "45340", ["Assisted Living"], True),
    ("bellhaven-of-wooster", "Bellhaven of Wooster", "200 Beall Ave", "Wooster", "OH", "44691", ["Short-Term Rehabilitation & Nursing"], True),
    ("bellhaven-terrace-of-akron", "Bellhaven Terrace of Akron", "300 Market St", "Akron", "OH", "44303", ["Assisted Living"], True),
    ("bellhaven-of-saline", "Bellhaven of Saline", "400 Michigan Ave", "Saline", "MI", "48176", ["Short-Term Rehabilitation & Nursing"], True),
    ("bellhaven-of-goshen", "Bellhaven of Goshen", "500 Lincoln Ave", "Goshen", "IN", "46526", ["Assisted Living"], True),
    ("bellhaven-of-meadville", "Bellhaven of Meadville", "600 Park Ave", "Meadville", "PA", "16335", ["Short-Term Rehabilitation & Nursing"], True),
    ("bellhaven-of-defiance", "Bellhaven of Defiance", "700 Clinton St", "Defiance", "OH", "43512", ["Short-Term Rehabilitation & Nursing"], True),
    ("bellhaven-woods-of-toledo", "Bellhaven Woods of Toledo", "800 Woodland Dr", "Toledo", "OH", "43615", ["Memory Support"], True),
    ("bellhaven-of-marion", "Bellhaven of Marion", "900 Delaware Ave", "Marion", "OH", "43302", ["Short-Term Rehabilitation & Nursing"], True),
    ("bellhaven-of-new-carlisle", "Bellhaven of New Carlisle", "1000 Main St", "New Carlisle", "OH", "45344", ["Short-Term Rehabilitation & Nursing"], True),
    ("bellhaven-of-carlisle", "Bellhaven of Carlisle", "1100 Main St", "Carlisle", "PA", "17013", ["Short-Term Rehabilitation & Nursing"], True),
    ("bellhaven-of-kettering", "Bellhaven of Kettering", "1200 Far Hills Ave", "Kettering", "OH", "45429", ["Short-Term Rehabilitation & Nursing"], True),
    ("bellhaven-of-tiffin", "Bellhaven of Tiffin", "1300 Washington St", "Tiffin", "OH", "44883", ["Short-Term Rehabilitation & Nursing"], True),
    ("bellhaven-shores-of-erie", "Bellhaven Shores of Erie", "1400 Peninsula Dr", "Erie", "PA", "16505", ["Assisted Living", "Memory Support"], True),
    ("amberly-manor", "Amberly Manor", "4390 Darrow Rd", "Hudson", "OH", "44236", ["Assisted Living"], True),
    ("bellhaven-meadows-of-findlay", "Bellhaven Meadows of Findlay", "1800 N Blanchard St", "Findlay", "OH", "45840", ["Assisted Living", "Memory Support"], False),
]


def seed():
    A = []
    def acct(id, name, street="", city="", state="", zip="", parent=None, status="Active", rev=0, ar=0, dup=None, chow=None, phone="(555) 000-1111", care="Skilled Nursing"):
        A.append({"account_id": id, "name": name, "parent_id": parent or "", "parent_name": "",
                  "billing_street": street, "billing_city": city, "billing_state": state, "billing_zip": zip,
                  "care_type": care, "phone": phone, "status": status, "note": "", "lifetime_revenue": rev,
                  "outstanding_ar": ar, "duplicate_of_account": dup or "", "chow_current_account": chow or "",
                  "created_by_candidate": False})
    acct("A100", "Bellhaven Senior Living (Parent Account)", "400 Bellhaven Way", "Columbus", "OH", "43215")
    acct("A101", "Bellhaven Senior Living, LLC", "", "Columbus", "OH")
    acct("A200", "Harborview Care Group (Parent Account)", "1 Harbor Rd", "Cleveland", "OH")
    acct("A300", "Cedar Trail Health (Parent Account)", "9 Cedar Trl", "Dayton", "OH")
    acct("A400", "Summit Health Partners (Parent Account)", "5 Summit Way", "Pittsburgh", "PA")
    acct("A001", "Bellhaven of Maplewood", "100 Maple Avenue", "Maplewood", "OH", "45340", "A100", care="Assisted Living")  # clean
    acct("A002", "Bellhaven Rehab of Wooster", "200 Beall Ave", "Wooster", "OH", "44691", "A100")  # outdated name
    acct("A003", "Harborview Terrace of Akron", "300 Market Street", "Akron", "OH", "44303", "A200", rev=52000, ar=1250)  # CHOW
    acct("A004", "Harborview of Saline", "400 Michigan Ave", "Saline", "MI", "48176", "A200", rev=30000, ar=0)  # reparent
    acct("A005", "Cedar Trail of Goshen", "500 Lincoln Ave", "Goshen", "IN", "46526", "A300", rev=0, ar=800)  # reparent
    acct("A006", "Bellhaven of Meadville", "600 Park Ave", "Meadville", "PA", "16335", "A100", rev=9000, ar=0)
    acct("A007", "Bellhaven Meadville", "600 Park Avenue", "Meadville", "PA", "16336", "A100", status="Needs Review")  # dup
    acct("A008", "Bellhaven of Defiance", "700 Clinton St", "Defiance", "OH", "43512", "A101", rev=100, ar=50)  # dup parent
    acct("A009", "Bellhaven Woods of Toledo", "800 Woodland Dr", "Toledo", "OH", "43651", "A100")  # zip typo
    acct("A010", "Harborview of Marion", "900 Delaware Ave", "Marion", "OH", "43302", "A200", rev=40000, ar=900, chow="A011")
    acct("A011", "Bellhaven of Marion", "900 Delaware Ave", "Marion", "OH", "43302", "A100")  # CHOW already done
    acct("A012", "Bellhaven of New Carlisle", "1000 Main St", "New Carlisle", "OH", "45344", "A100")
    acct("A013", "Bellhaven of Carlisle", "1100 Main St", "Carlisle", "PA", "17013", "A100")
    acct("A014", "Harborview of Kettering", "1200 Far Hills Ave", "Kettering", "OH", "45429", "A200", rev=70000, ar=3000)
    acct("A015", "Bellhaven of Kettering", "1200 Far Hills Avenue", "Kettering", "OH", "45429", "A100")  # CHOW pair, link missing
    acct("A016", "Bellhaven of Tiffin", "1300 Washington St", "Tiffin", "OH", "44883", "A100", status="Inactive")
    acct("A017", "Bellhaven of Sandusky", "1500 Cleveland Rd", "Sandusky", "OH", "44870", "A100", rev=500, ar=0)  # orphan
    acct("A018", "Amberly Manor", "4390 Darrow Road", "Hudson", "OH", "44236", "A300", rev=1000, ar=100)  # CHOW
    acct("A019", "Erie Shores Senior Care", "1400 Peninsula Drive", "Erie", "PA", "16505", "A400", rev=0, ar=0)  # reparent
    acct("A020", "Bellhaven of Toledo", "55 Other St", "Toledo", "OH", "43604", "A400")  # unrelated similar name
    names = {a["account_id"]: a["name"] for a in A}
    for a in A:
        a["parent_name"] = names.get(a["parent_id"], "") if a["parent_id"] else ""
    return A


def make_app():
    app = Flask(__name__)
    state = {"accounts": seed()}
    ids = itertools.count(500)
    app.config["STATE"] = state

    def page(body):
        return f"<html><body><header><nav><a href='/'>Home</a><a href='/communities'>Our Communities</a></nav></header><main>{body}</main><footer>Corporate Office: 400 Bellhaven Way</footer></body></html>"

    @app.get("/")
    def home():
        return page("<h1>Bellhaven</h1><p>New: <a href='/communities/bellhaven-meadows-of-findlay'>Findlay</a></p>")

    @app.get("/about")
    def about():
        return page("<h1>About</h1>")

    @app.get("/communities")
    def directory():
        listed = [s for s in SITE if s[7]]
        p = int(request.args.get("page", 1))
        per = 6
        pages = (len(listed) + per - 1) // per
        p = min(p, pages)  # clamp like many sites do
        items = "".join(f"<div class='card'><a href='/communities/{s[0]}'>{s[1]}</a><span>{s[3]}, {s[4]}</span></div>"
                        for s in listed[(p - 1) * per:p * per])
        nxt = f"<a href='/communities?page={p+1}'>Next →</a>" if p < pages else ""
        return page(f"<h1>Our Communities</h1>{items}{nxt}")

    @app.get("/communities/<slug>")
    def detail(slug):
        s = next((x for x in SITE if x[0] == slug), None)
        if not s:
            abort(404)
        care = "".join(f"<span class='badge'>{c}</span>" for c in s[6])
        return page(f"<h1>{s[1]}</h1><div><h3>Address</h3><p>{s[2]}<br>{s[3]}, {s[4]} {s[5]}</p></div>"
                    f"<div><h3>Phone</h3><p>(555) 010-{len(s[1]):04d}</p></div>"
                    f"<div><h3>Care Offerings</h3><div>{care}</div></div><div><h3>Administrator</h3><p>Pat Doe</p></div>")

    def auth():
        if not request.headers.get("Authorization", "").startswith("Bearer "):
            abort(401)

    @app.get("/api/v1/accounts")
    def list_accounts():
        auth()
        rows = state["accounts"]
        for f, col in (("city", "billing_city"), ("state", "billing_state"), ("zip", "billing_zip"), ("parent_id", "parent_id")):
            if request.args.get(f):
                rows = [a for a in rows if str(a.get(col) or "").lower() == request.args[f].lower()]
        if request.args.get("q"):
            rows = [a for a in rows if request.args["q"].lower() in a["name"].lower()]
        page_, size = int(request.args.get("page", 1)), min(int(request.args.get("page_size", 50)), 50)  # server caps at 50
        return jsonify({"items": copy.deepcopy(rows[(page_ - 1) * size:page_ * size]), "total": len(rows),
                        "page": page_, "page_size": size})

    @app.get("/api/v1/accounts/<aid>")
    def get_account(aid):
        auth()
        a = next((a for a in state["accounts"] if a["account_id"] == aid), None)
        return (jsonify(a), 200) if a else (jsonify({"detail": "not found"}), 404)

    @app.patch("/api/v1/accounts/<aid>")
    def patch_account(aid):
        auth()
        a = next((a for a in state["accounts"] if a["account_id"] == aid), None)
        if not a:
            return jsonify({"detail": "not found"}), 404
        body = request.get_json()
        if "status" in body and body["status"] not in ("Active", "Inactive", "Needs Review"):
            return jsonify({"detail": "bad status"}), 422
        a.update(body)
        return jsonify(a)

    @app.post("/api/v1/accounts")
    def create_account():
        auth()
        body = request.get_json()
        a = {"account_id": f"A{next(ids)}", "lifetime_revenue": 0, "outstanding_ar": 0, "duplicate_of_account": "",
             "chow_current_account": "", "parent_name": "", "created_by_candidate": True, **body}
        state["accounts"].append(a)
        return jsonify(a), 201

    return app


if __name__ == "__main__":
    make_app().run(port=5999)

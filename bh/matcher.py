"""Match website locations to CRM accounts and turn the differences into proposals.

A proposal is a reviewable unit: a title, evidence (website vs CRM values, match signals,
reasoning) and a list of API operations that run only after a human approves it.

Operation shapes (executed by apply.py):
  {"op": "create", "ref": "new", "data": {...}}
  {"op": "patch", "id": "<account id or $new>", "data": {...},
   "expect": {...}, "append_note": "text"}
"""
import datetime as dt
from collections import defaultdict

from . import config
from .crm import fget
from .normalize import (name_similarity, street_similarity, norm_city, norm_state, zip5,
                        phone10, norm_name, name_key, norm_street, is_po_box, to_number, care_set, care_canon, clean)

TODAY = dt.date.today().isoformat()


class Ctx:
    """Account lookups with field mapping applied."""

    def __init__(self, accounts, fields):
        self.accounts = accounts
        self.fields = fields
        self.by_id = {str(self.v(a, "id")): a for a in accounts}
        self.children = defaultdict(list)
        for a in accounts:
            p = self.v(a, "parent_id")
            if p:
                self.children[str(p)].append(a)

    def v(self, a, logical):
        return fget(a, logical, self.fields)

    def id(self, a):
        return str(self.v(a, "id"))

    def key(self, logical):
        return self.fields.get(logical) or config.FIELD_ALIASES[logical][0]

    def billing(self, a):
        return to_number(self.v(a, "lifetime_revenue")), to_number(self.v(a, "outstanding_ar"))

    def sop_locked(self, a):
        rev, ar = self.billing(a)
        return rev > 0 and ar > 0

    def summary(self, a):
        if a is None:
            return None
        out = {k: self.v(a, k) for k in config.FIELD_ALIASES}
        p = out.get("parent_id")
        out["parent_name"] = self.v(self.by_id[str(p)], "name") if p and str(p) in self.by_id else None
        return out

    def resolve(self, a, depth=0):
        """Follow chow_current_account / duplicate_of_account links to the live record."""
        if depth > 5:
            return a
        for link in ("chow_current_account", "duplicate_of_account"):
            t = self.v(a, link)
            if t and str(t) in self.by_id and str(t) != self.id(a):
                return self.resolve(self.by_id[str(t)], depth + 1)
        return a


# ---------------------------------------------------------------------------
# Parent detection
# ---------------------------------------------------------------------------
def find_operator_parents(ctx, override_id=None):
    """Return (canonical_parent, [duplicate parent records]) for Bellhaven."""
    def is_parentish(a):
        n = norm_name(ctx.v(a, "name"))
        if config.OPERATOR_KEYWORD not in n:
            return False
        if ctx.children.get(ctx.id(a)):
            return True
        return "senior living" in n or any(w in n for w in ("corporate", "holdings", "group", "management"))

    cands = [a for a in ctx.accounts if is_parentish(a) and not ctx.v(a, "parent_id")]
    if override_id:
        canon = ctx.by_id[str(override_id)]
    else:
        if not cands:
            raise RuntimeError("Could not find the Bellhaven parent account; set BH_PARENT_ID.")

        def rank(a):
            return (
                norm_street(ctx.v(a, "street")) == norm_street(config.CORPORATE_STREET),
                ctx.v(a, "status") == config.STATUS_ACTIVE,
                len(ctx.children.get(ctx.id(a), [])),
                name_similarity(ctx.v(a, "name"), config.OPERATOR_NAME),
                -_id_order(ctx.id(a)),
            )
        canon = max(cands, key=rank)
    dups = [a for a in cands if a is not canon
            and name_similarity(ctx.v(a, "name"), ctx.v(canon, "name")) >= 0.8
            and not ctx.v(a, "duplicate_of_account")]
    return canon, dups


def _id_order(s):
    digits = "".join(ch for ch in str(s) if ch.isdigit())
    return int(digits) if digits else 0


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score_pair(loc, a, ctx):
    sig, score = [], 0.0
    st_sim = street_similarity(loc["street"], ctx.v(a, "street"))
    z_eq = bool(zip5(loc["zip"])) and zip5(loc["zip"]) == zip5(ctx.v(a, "zip"))
    c_eq = bool(loc["city"]) and norm_city(loc["city"]) == norm_city(ctx.v(a, "city"))
    s_a, s_l = norm_state(ctx.v(a, "state")), norm_state(loc["state"])
    s_eq = bool(s_l) and s_l == s_a
    p_eq = bool(phone10(loc["phone"])) and phone10(loc["phone"]) == phone10(ctx.v(a, "phone"))
    n_sim = name_similarity(loc["name"], ctx.v(a, "name"))

    if st_sim is not None:
        if st_sim >= 0.999:
            score += 50; sig.append("street address identical (normalized)")
        elif st_sim >= 0.85:
            score += 40; sig.append(f"street address near-identical ({st_sim:.2f})")
    if z_eq:
        score += 15; sig.append("ZIP matches")
    if c_eq:
        score += 10; sig.append("city matches")
    if s_eq:
        score += 5
    if p_eq:
        score += 15; sig.append("phone matches")
    score += 30 * n_sim
    sig.append(f"name similarity {n_sim:.2f}")

    street_hit = st_sim is not None and st_sim >= 0.85
    street_conflict = st_sim is not None and st_sim < 0.6
    if s_l and s_a and not s_eq and not (street_hit and z_eq):
        return 0, sig + ["state differs"], False
    ok = (
        (street_hit and (z_eq or c_eq))
        or (p_eq and (z_eq or c_eq) and not street_conflict)
        or (n_sim >= 0.85 and c_eq and (s_eq or not s_a) and not street_conflict)
    )
    if street_conflict and ok is False and n_sim >= 0.85 and c_eq:
        sig.append("same name+city but different street address: treated as different facility")
    return round(score, 1), sig, ok


def confidence(score, signals):
    strong = any(s.startswith("street address identical") for s in signals) and "ZIP matches" in signals
    if strong and score >= 85:
        return "high"
    name_sim = next((float(s.split()[-1]) for s in signals if s.startswith("name similarity")), 0.0)
    if name_sim >= 0.95 and "ZIP matches" in signals and "city matches" in signals:
        return "high"  # e.g. CRM holds a PO Box, so there is no street signal
    return "medium" if score >= 70 else "low"


# ---------------------------------------------------------------------------
# Proposal builders
# ---------------------------------------------------------------------------
def _site_view(loc):
    return {k: loc.get(k) for k in ("name", "street", "city", "state", "zip", "phone",
                                     "care_offerings", "url", "discovered_via", "formerly_known_as")}


def _new_account_data(loc, ctx, parent_id, note):
    data = {
        ctx.key("name"): loc["name"], ctx.key("street"): loc["street"], ctx.key("city"): loc["city"],
        ctx.key("state"): loc["state"], ctx.key("zip"): loc["zip"], ctx.key("parent_id"): parent_id,
        ctx.key("status"): config.STATUS_ACTIVE, ctx.key("note"): note,
    }
    if loc.get("phone"):
        data[ctx.key("phone")] = loc["phone"]
    if ctx.fields.get("care") and loc.get("care_offerings"):
        data[ctx.fields["care"]] = _care_value(loc, ctx)
    return data


def _care_vocab(ctx):
    """canonical -> the spelling the CRM actually uses (most common)."""
    from collections import Counter
    seen = Counter(str(ctx.v(a, "care")) for a in ctx.accounts if ctx.v(a, "care"))
    vocab = {}
    for val, _ in seen.most_common():
        for part in val.split(","):
            vocab.setdefault(care_canon(part), part.strip())
    return vocab


def _care_value(loc, ctx):
    """CRM care_type is a single string. Write the website's offerings in CRM vocabulary,
    comma-joined only if the CRM already uses comma-joined values."""
    vocab = _care_vocab(ctx)
    vals = [vocab.get(care_canon(c), c) for c in loc["care_offerings"]]
    multi = any("," in str(ctx.v(a, "care") or "") for a in ctx.accounts)
    sample = next((ctx.v(a, "care") for a in ctx.accounts if ctx.v(a, "care")), None)
    if isinstance(sample, list):
        return vals
    return ", ".join(vals) if multi else vals[0]


def build_proposals(locations, accounts, fields, parent_override=None, scrape_errors=()):
    ctx = Ctx(accounts, fields)
    canon, dup_parents = find_operator_parents(ctx, parent_override)
    bh_id = ctx.id(canon)
    bh_family = {bh_id} | {ctx.id(p) for p in dup_parents}
    parent_ids = set(ctx.children)
    proposals, matches, report = [], [], {"bellhaven_parent": ctx.summary(canon),
                                          "duplicate_parents": [ctx.summary(p) for p in dup_parents],
                                          "scrape_errors": list(scrape_errors)}

    # Duplicate copies of the Bellhaven parent record itself
    for p in dup_parents:
        proposals.append({
            "kind": "DUPLICATE_PARENT", "subject": f"acct:{ctx.id(p)}", "account_id": ctx.id(p),
            "title": f"Mark '{ctx.v(p, 'name')}' as duplicate of parent '{ctx.v(canon, 'name')}'",
            "confidence": "high",
            "evidence": {"crm": ctx.summary(p), "target": ctx.summary(canon), "signals": [
                f"Both are top-level Bellhaven parent records (name similarity "
                f"{name_similarity(ctx.v(p, 'name'), ctx.v(canon, 'name')):.2f})",
                f"Canonical parent has {len(ctx.children.get(bh_id, []))} children; this copy has "
                f"{len(ctx.children.get(ctx.id(p), []))}",
            ]},
            "ops": [{"op": "patch", "id": ctx.id(p),
                     "data": {ctx.key("duplicate_of_account"): bh_id, ctx.key("status"): config.STATUS_INACTIVE},
                     "append_note": f"{config.NOTE_TAG} {TODAY}: duplicate of parent account {bh_id}."}],
        })

    # ---- candidate generation -------------------------------------------------
    eligible = [a for a in accounts if ctx.id(a) not in bh_family and ctx.id(a) not in parent_ids]
    pair_best = {}  # (loc_idx, live_acct_id) -> (score, signals, via)
    for i, loc in enumerate(locations):
        for a in eligible:
            s, sig, ok = score_pair(loc, a, ctx)
            if not ok:
                continue
            live = ctx.resolve(a)
            via = None if live is a else ctx.id(a)
            if live is not a and (ctx.id(live) in bh_family or ctx.id(live) in parent_ids):
                continue
            k = (i, ctx.id(live))
            if k not in pair_best or s > pair_best[k][0]:
                sig2 = sig + ([f"matched via historical account {via} (linked to current record)"] if via else [])
                pair_best[k] = (s, sig2, via)

    # Each live account belongs to the single location it scores best against.
    best_loc_for_acct = {}
    for (i, aid), (s, _, _) in pair_best.items():
        if aid not in best_loc_for_acct or s > best_loc_for_acct[aid][1]:
            best_loc_for_acct[aid] = (i, s)
    cands_by_loc = defaultdict(list)
    for (i, aid), val in pair_best.items():
        if best_loc_for_acct[aid][0] == i:
            cands_by_loc[i].append((aid, *val))

    assigned = set()
    for i, loc in enumerate(locations):
        cands = sorted(cands_by_loc.get(i, []), key=lambda c: -c[1])
        site = _site_view(loc)
        if not cands:
            proposals.append(_create_proposal(loc, ctx, bh_id, eligible))
            continue
        accts = [ctx.by_id[c[0]] for c in cands]
        meta = {c[0]: c for c in cands}
        survivor = max(accts, key=lambda a: (
            ctx.v(a, "parent_id") is not None and str(ctx.v(a, "parent_id")) == bh_id,
            ctx.v(a, "status") == config.STATUS_ACTIVE,
            sum(ctx.billing(a)) > 0,
            meta[ctx.id(a)][1],
            sum(1 for k in ("street", "zip", "phone", "city") if ctx.v(a, k)),
            -_id_order(ctx.id(a)),
        ))
        sid = ctx.id(survivor)
        assigned.update(c[0] for c in cands)
        s_score, s_sig, _ = meta[sid][1:]
        matches.append({"site": site, "account_id": sid, "account_name": ctx.v(survivor, "name"),
                        "score": s_score, "confidence": confidence(s_score, s_sig), "signals": s_sig,
                        "duplicates": [c[0] for c in cands if c[0] != sid]})

        for a in accts:
            if a is survivor:
                continue
            proposals.append(_loser_proposal(a, survivor, loc, ctx, bh_family, meta[ctx.id(a)]))
        proposals.extend(_survivor_proposals(survivor, loc, ctx, bh_id, bh_family, meta[sid]))

    # ---- accounts under Bellhaven that the website no longer lists -------------
    for a in eligible:
        aid = ctx.id(a)
        if aid in assigned or str(ctx.v(a, "parent_id") or "") not in bh_family:
            continue
        if ctx.v(a, "duplicate_of_account") or ctx.v(a, "chow_current_account"):
            continue
        if ctx.v(a, "status") == config.STATUS_INACTIVE:
            continue
        if ctx.v(a, "status") == config.STATUS_REVIEW and config.NOTE_TAG in str(ctx.v(a, "note") or ""):
            continue
        nearest = max(locations, key=lambda l: name_similarity(l["name"], ctx.v(a, "name")), default=None)
        near_txt = (f"Closest website name: '{nearest['name']}' ({nearest['city']}, {nearest['state']}), "
                    f"similarity {name_similarity(nearest['name'], ctx.v(a, 'name')):.2f}, "
                    f"but address/city do not line up") if nearest else "No website locations"
        rev, ar = ctx.billing(a)
        proposals.append({
            "kind": "ORPHAN", "subject": f"acct:{aid}", "account_id": aid,
            "title": f"'{ctx.v(a, 'name')}' is under Bellhaven but not on the website: flag for review",
            "confidence": "medium",
            "evidence": {"crm": ctx.summary(a), "signals": [
                f"Parent is Bellhaven ({ctx.v(a, 'parent_id')}) but no website location matches by "
                f"address, phone, or name+city", near_txt,
                f"Billing: lifetime revenue {rev:,.2f}, outstanding AR {ar:,.2f}",
                "Parent left unchanged: the new owner is unknown, and closing vs. divesting needs a human call",
            ]},
            "ops": [{"op": "patch", "id": aid, "data": {ctx.key("status"): config.STATUS_REVIEW},
                     "expect": {ctx.key("parent_id"): ctx.v(a, "parent_id")},
                     "append_note": f"{config.NOTE_TAG} {TODAY}: no longer listed on {config.OPERATOR_NAME} "
                                    f"website ({config.BASE_URL}/communities). Possibly sold or closed; "
                                    f"verify current owner before re-parenting."}],
        })

    report["matches"] = matches
    report["counts"] = {"locations": len(locations), "accounts": len(accounts), "matched": len(matches)}
    return proposals, report


def _create_proposal(loc, ctx, bh_id, eligible):
    near = sorted(((name_similarity(loc["name"], ctx.v(a, "name")), a) for a in eligible
                   if norm_state(ctx.v(a, "state")) in ("", norm_state(loc["state"]))),
                  key=lambda t: -t[0])[:3]
    near_txt = [f"Nearest CRM name: '{ctx.v(a, 'name')}' ({ctx.v(a, 'city')}, {ctx.v(a, 'state')}; "
                f"{ctx.v(a, 'street') or 'no street'}), similarity {s:.2f}" for s, a in near if s >= 0.5]
    note = f"{config.NOTE_TAG} {TODAY}: created from {loc['url']}"
    return {
        "kind": "CREATE", "subject": f"site:{loc['slug']}", "site_slug": loc["slug"],
        "title": f"New location '{loc['name']}' ({loc['city']}, {loc['state']}): create under Bellhaven",
        "confidence": "high" if not near_txt else "medium",
        "evidence": {"site": _site_view(loc), "signals": [
            "No CRM account matches by street+ZIP/city, phone, or name+city",
            *(near_txt or ["No similarly named accounts in the same state"]),
            f"Found via: {', '.join(loc.get('discovered_via', []))}",
        ]},
        "ops": [{"op": "create", "ref": "new", "data": _new_account_data(loc, ctx, bh_id, note),
                 "guard_no_match": {"street": loc["street"], "zip": loc["zip"]}}],
    }


def _loser_proposal(a, survivor, loc, ctx, bh_family, meta):
    aid, sid = ctx.id(a), ctx.id(survivor)
    rev, ar = ctx.billing(a)
    old_parent = str(ctx.v(a, "parent_id") or "")
    base_ev = {"site": _site_view(loc), "crm": ctx.summary(a), "target": ctx.summary(survivor),
               "signals": list(meta[2]) + [f"match score {meta[1]}"]}
    if ctx.sop_locked(a) and old_parent not in bh_family:
        # Old-owner record with open billing + a record already exists for the facility
        # under the new owner: this is a change-of-ownership pair, not a duplicate.
        base_ev["signals"] += [
            f"This record sits under the previous owner ({ctx.summary(a)['parent_name'] or old_parent}) with "
            f"lifetime revenue {rev:,.2f} and outstanding AR {ar:,.2f}",
            f"CHOW SOP: keep it untouched and point chow_current_account at the current record {sid}",
        ]
        return {"kind": "LINK_CHOW", "subject": f"acct:{aid}", "account_id": aid,
                "title": f"Link old-owner record '{ctx.v(a, 'name')}' to current record via CHOW",
                "confidence": "high", "evidence": base_ev,
                "ops": [{"op": "patch", "id": aid, "data": {ctx.key("chow_current_account"): sid}}]}
    if rev > 0 or ar > 0:
        base_ev["signals"].append(f"Note: losing copy has billing history (revenue {rev:,.2f}, AR {ar:,.2f}); "
                                  f"duplicate_of keeps it traceable to {sid}")
    base_ev["signals"].append(f"Survivor {sid} chosen because: " + _survivor_reason(survivor, a, ctx, bh_family))
    return {"kind": "DUPLICATE", "subject": f"acct:{aid}", "account_id": aid,
            "title": f"Duplicate: '{ctx.v(a, 'name')}' ({aid}) → keep '{ctx.v(survivor, 'name')}' ({sid})",
            "confidence": confidence(meta[1], meta[2]), "evidence": base_ev,
            "ops": [{"op": "patch", "id": aid,
                     "data": {ctx.key("duplicate_of_account"): sid, ctx.key("status"): config.STATUS_INACTIVE},
                     "append_note": f"{config.NOTE_TAG} {TODAY}: duplicate of {sid} "
                                    f"(same facility: {loc['name']}, {loc['street']}, {loc['city']})."}]}


def _survivor_reason(s, loser, ctx, bh_family):
    """Explain, honestly, which ranking rule actually separated survivor from loser."""
    def under_bh(x):
        return str(ctx.v(x, "parent_id") or "") in bh_family
    if under_bh(s) and not under_bh(loser):
        return "it is already under Bellhaven"
    if ctx.v(s, "status") == config.STATUS_ACTIVE and ctx.v(loser, "status") != config.STATUS_ACTIVE:
        return "it is Active and this copy is not"
    if sum(ctx.billing(s)) > 0 and sum(ctx.billing(loser)) == 0:
        return "it carries the billing history"
    tie = "both are under Bellhaven" if under_bh(s) else "neither is under Bellhaven"
    tail = "" if under_bh(s) else " (its own proposals re-parent and rename it)"
    return (f"{tie} with the same status and billing, so the record with the closer "
            f"name/address match to the website was kept{tail}")


def _survivor_proposals(a, loc, ctx, bh_id, bh_family, meta):
    out, aid = [], ctx.id(a)
    score, signals, via = meta[1], meta[2], meta[3]
    conf = confidence(score, signals)
    cur_parent = str(ctx.v(a, "parent_id") or "")
    rev, ar = ctx.billing(a)
    ev_base = {"site": _site_view(loc), "crm": ctx.summary(a), "signals": list(signals) + [f"match score {score}"]}

    if cur_parent != bh_id:
        from_dup_parent = cur_parent in bh_family
        parent_name = ctx.summary(a)["parent_name"] or ("(none)" if not cur_parent else cur_parent)
        sop_text = f"Billing check: lifetime revenue {rev:,.2f}, outstanding AR {ar:,.2f}"
        if ctx.sop_locked(a) and (not from_dup_parent or config.SOP_APPLIES_TO_DUPLICATE_PARENT):
            note = (f"{config.NOTE_TAG} {TODAY}: created by change of ownership from account {aid} "
                    f"(previous parent: {parent_name}). Source: {loc['url']}")
            out.append({
                "kind": "CHOW", "subject": f"acct:{aid}", "account_id": aid, "site_slug": loc["slug"],
                "title": f"Change of ownership: '{loc['name']}' {parent_name} → Bellhaven (new account; old one preserved)",
                "confidence": conf,
                "evidence": {**ev_base, "signals": ev_base["signals"] + [
                    f"Website lists this facility as a Bellhaven community; CRM parent is {parent_name}",
                    sop_text, "Revenue > 0 AND AR > 0 → SOP: leave old account exactly as is, create a new "
                              "account under Bellhaven, set chow_current_account on the old account"]},
                "ops": [
                    {"op": "create", "ref": "new", "data": _new_account_data(loc, ctx, bh_id, note),
                     "guard_no_match": {"street": loc["street"], "zip": loc["zip"], "parent_id": bh_id}},
                    {"op": "patch", "id": aid, "data": {ctx.key("chow_current_account"): "$new"},
                     "expect": {ctx.key("parent_id"): ctx.v(a, "parent_id")}},
                ],
            })
            return out  # old account must stay exactly as is: no field fixes
        why = ("parent is a duplicate copy of the Bellhaven parent record (same owner), so this is a "
               "data fix, not a change of ownership" if from_dup_parent else
               ("no revenue history" if rev <= 0 else "no outstanding AR") + " → SOP allows re-parenting directly")
        out.append({
            "kind": "REPARENT", "subject": f"acct:{aid}", "account_id": aid,
            "title": f"Re-parent '{ctx.v(a, 'name')}': {parent_name} → {ctx.v(ctx.by_id[bh_id], 'name')}",
            "confidence": conf,
            "evidence": {**ev_base, "signals": ev_base["signals"] + [
                f"Website lists this facility as a Bellhaven community; CRM parent is {parent_name}",
                sop_text, why]},
            "ops": [{"op": "patch", "id": aid, "data": {ctx.key("parent_id"): bh_id},
                     "expect": {ctx.key("parent_id"): ctx.v(a, "parent_id")},
                     "append_note": f"{config.NOTE_TAG} {TODAY}: re-parented from {parent_name} to Bellhaven "
                                    f"per website listing ({why})."}],
        })

    # Field-level fixes on the surviving account
    changes, diff = {}, []

    def setf(logical, new, old, label=None):
        changes[ctx.key(logical)] = new
        diff.append({"field": label or logical, "crm": old, "website": new})

    if name_key(ctx.v(a, "name")) != name_key(loc["name"]):
        setf("name", loc["name"], ctx.v(a, "name"))
    if loc["street"] and (is_po_box(ctx.v(a, "street")) or norm_street(ctx.v(a, "street")) != norm_street(loc["street"])):
        setf("street", loc["street"], ctx.v(a, "street"))
    if loc["city"] and norm_city(ctx.v(a, "city")) != norm_city(loc["city"]):
        setf("city", loc["city"], ctx.v(a, "city"))
    if loc["state"] and norm_state(ctx.v(a, "state")) != norm_state(loc["state"]):
        setf("state", loc["state"], ctx.v(a, "state"))
    if loc["zip"] and zip5(ctx.v(a, "zip")) != zip5(loc["zip"]):
        setf("zip", loc["zip"], ctx.v(a, "zip"))
    if loc.get("phone") and not phone10(ctx.v(a, "phone")):
        setf("phone", loc["phone"], ctx.v(a, "phone"))
    if ctx.fields.get("care") and loc.get("care_offerings"):
        cur = ctx.v(a, "care")
        # Single-valued CRM field: only flag when it is empty or shares nothing with the website.
        if not care_set(cur) or not (care_set(cur) & care_set(loc["care_offerings"])):
            setf("care", _care_value(loc, ctx), cur, "care type")
    if ctx.v(a, "status") != config.STATUS_ACTIVE:
        setf("status", config.STATUS_ACTIVE, ctx.v(a, "status"))
    if changes:
        renamed = any(d["field"] == "name" for d in diff)
        note = (f"{config.NOTE_TAG} {TODAY}: updated from website {loc['url']}"
                + (f"; formerly '{ctx.v(a, 'name')}'" if renamed else "") + ".")
        out.append({
            "kind": "UPDATE_FIELDS", "subject": f"acct:{aid}", "account_id": aid,
            "title": f"Update '{ctx.v(a, 'name')}': " + ", ".join(d["field"] for d in diff),
            "confidence": conf,
            "evidence": {**ev_base, "diff": diff},
            "ops": [{"op": "patch", "id": aid, "data": changes, "append_note": note}],
        })
    return out

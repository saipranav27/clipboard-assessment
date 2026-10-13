"""Execute an approved proposal's operations against the CRM.

Safety checks before writing:
  * `expect`  - re-reads the account and refuses if the CRM changed since the proposal was made
  * `guard_no_match` - refuses a create if an account already exists at that street+ZIP
                       (protects against double-creates)
Notes are appended to the existing note, never overwritten.
"""
import json

from . import config, store
from .normalize import norm_street, zip5
from .crm import fget


class StaleProposal(Exception):
    pass


def _resolve(value, refs):
    if isinstance(value, str) and value.startswith("$"):
        return refs[value[1:]]
    return value


def execute(crm, ops, accounts_cache=None):
    refs, log = {}, []
    note_key = crm.key("note")
    id_key = crm.key("id")
    for op in ops:
        if op["op"] == "create":
            guard = op.get("guard_no_match")
            if guard:
                accts = crm.list_accounts(zip=guard["zip"]) if guard.get("zip") else crm.list_accounts()
                for a in accts:
                    same_addr = (norm_street(fget(a, "street", crm.fields)) == norm_street(guard["street"])
                                 and zip5(fget(a, "zip", crm.fields)) == zip5(guard["zip"]))
                    same_parent = ("parent_id" not in guard or
                                   str(fget(a, "parent_id", crm.fields)) == str(guard["parent_id"]))
                    if same_addr and same_parent and not fget(a, "duplicate_of_account", crm.fields):
                        raise StaleProposal(f"An account already exists at this address ({a.get(id_key)}); "
                                            f"re-run the pipeline instead of creating a second one.")
            created = crm.create_account(op["data"])
            new_id = created.get(id_key) or created.get("id")
            if not new_id:
                raise RuntimeError(f"Create returned no id: {json.dumps(created)[:300]}")
            refs[op["ref"]] = new_id
            log.append({"op": "create", "id": new_id, "data": op["data"]})
        elif op["op"] == "patch":
            aid = _resolve(op["id"], refs)
            current = crm.get_account(aid)
            for k, v in (op.get("expect") or {}).items():
                if str(current.get(k) or "") != str(v or ""):
                    raise StaleProposal(f"Account {aid} changed since this was proposed: {k} is now "
                                        f"{current.get(k)!r}, expected {v!r}. Re-run the pipeline.")
            data = {k: _resolve(v, refs) for k, v in op["data"].items()}
            if op.get("append_note"):
                existing = (current.get(note_key) or "").rstrip()
                data[note_key] = (existing + "\n" if existing else "") + op["append_note"]
            crm.update_account(aid, data)
            log.append({"op": "patch", "id": aid, "data": data})
    return refs, log


def apply_proposal(con, crm, fp):
    if not store.claim(con, fp):
        row = store.get(con, fp)
        return False, f"Already {row['status'] if row else 'missing'}"
    row = store.get(con, fp)
    try:
        refs, log = execute(crm, json.loads(row["ops"]))
    except Exception as e:  # noqa: BLE001 - surface any failure to the reviewer
        store.set_status(con, fp, "failed", error=str(e))
        return False, str(e)
    store.set_status(con, fp, "applied", result=json.dumps({"refs": refs, "log": log}, default=str))
    return True, refs


def retry(con, fp):
    """Put a failed proposal back in the queue (e.g. after a transient API error)."""
    con.execute("UPDATE proposals SET status='pending', error=NULL WHERE fingerprint=? AND status='failed'", (fp,))

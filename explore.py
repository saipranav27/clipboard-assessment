#!/usr/bin/env python3
"""Read-only look at the CRM: field names, statuses, parents, and Bellhaven-related accounts.
Run this first; paste the output if the field map needs adjusting."""
import json
from collections import Counter

from bh.crm import CRM, fget

crm = CRM()
accts = crm.list_accounts()
fields = crm.detect_fields(accts)
print(f"{len(accts)} accounts")
print("keys on first account:", sorted(accts[0].keys()))
print("sample account:", json.dumps(accts[0], indent=2, default=str))
print("field map:", fields)
print("care_type values:", Counter(str(fget(a, "care", fields)) for a in accts))
print("statuses:", Counter(str(fget(a, "status", fields)) for a in accts))

by_id = {str(fget(a, "id", fields)): a for a in accts}
kids = Counter(str(fget(a, "parent_id", fields)) for a in accts if fget(a, "parent_id", fields))
print("\nParents (by child count):")
for pid, n in kids.most_common():
    p = by_id.get(pid)
    print(f"  {pid:>10}  {n:>3} children  {fget(p, 'name', fields) if p else '(parent id not found!)'}")

print("\nAccounts mentioning bellhaven / harborview / cedar trail, or under those parents:")
interesting = {pid for pid, a in by_id.items()
               if any(w in str(fget(a, "name", fields)).lower() for w in ("bellhaven", "harborview", "cedar trail"))}
for a in sorted(accts, key=lambda a: str(fget(a, "name", fields))):
    aid = str(fget(a, "id", fields))
    if aid in interesting or str(fget(a, "parent_id", fields)) in interesting:
        print(f"  {aid:>8} | {fget(a,'name',fields)!s:45.45} | {fget(a,'street',fields)!s:25.25} | "
              f"{fget(a,'city',fields)}, {fget(a,'state',fields)} {fget(a,'zip',fields)} | parent={fget(a,'parent_id',fields)} | "
              f"{fget(a,'status',fields)} | rev={fget(a,'lifetime_revenue',fields)} ar={fget(a,'outstanding_ar',fields)} | "
              f"dup={fget(a,'duplicate_of_account',fields)} chow={fget(a,'chow_current_account',fields)}")

from pathlib import Path
out = Path("data") / "crm_dump.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(accts, indent=1, default=str))
print(f"\nFull dump of {len(accts)} accounts written to {out} (attach it in chat for review)")
